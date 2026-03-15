from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import logging
import mimetypes
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from .config import AppSettings
from .jobs import JobRunner
from .repository import EchoRepository
from .schemas import JobOut, RecordingOut, RecordingRenameIn, SettingsOut, SettingsUpdateIn, TranscriptTxtExportIn
from .transcription import build_provider


def _resolve_static_dir() -> Path:
    if getattr(sys, "frozen", False):
        bundled_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "echo_app" / "static"
        if bundled_dir.exists():
            return bundled_dir
    return Path(__file__).resolve().parent / "static"


STATIC_DIR = _resolve_static_dir()
LOGGER = logging.getLogger("echo.app")
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
AUDIO_MEDIA_TYPES = {
    ".aac": "audio/aac",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".mp4": "audio/mp4",
    ".oga": "audio/ogg",
    ".ogg": "audio/ogg",
    ".opus": "audio/ogg",
    ".wav": "audio/wav",
    ".wave": "audio/wav",
    ".webm": "audio/webm",
}
DIRECT_PLAYBACK_EXTENSIONS = {
    ".aac",
    ".m4a",
    ".mp3",
    ".mp4",
}


class PlaybackPreparationError(RuntimeError):
    pass


def _store_upload(upload: UploadFile, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as output_file:
        shutil.copyfileobj(upload.file, output_file, length=1024 * 1024)


def _delete_stored_file(path: Path) -> bool:
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        LOGGER.exception("Could not delete file %s", path)
        return False


def _delete_playback_file(playback_dir: Path, recording_id: str) -> bool:
    return _delete_stored_file(playback_dir / f"{recording_id}.wav")


def _build_stored_path(recordings_dir: Path, original_name: str) -> Path:
    suffix = Path(original_name).suffix or ".bin"
    stored_name = f"{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex}{suffix}"
    return recordings_dir / stored_name


def _normalize_recording_name(value: str | None, *, fallback: str | None = None) -> str:
    normalized = Path(str(value or "")).name.strip()
    if normalized:
        return normalized

    fallback_name = Path(str(fallback or "")).name.strip()
    if fallback_name:
        return fallback_name

    raise ValueError("Nazwa nagrania nie może być pusta.")


def _guess_recording_media_type(original_name: str, stored_path: Path) -> str:
    for candidate in (original_name, stored_path.name):
        suffix = Path(candidate).suffix.lower()
        if suffix in AUDIO_MEDIA_TYPES:
            return AUDIO_MEDIA_TYPES[suffix]

    for candidate in (original_name, stored_path.name):
        media_type, _ = mimetypes.guess_type(candidate)
        if media_type == "audio/x-wav":
            return "audio/wav"
        if media_type:
            return media_type

    return "application/octet-stream"


def _build_playback_path(playback_dir: Path, recording_id: str) -> Path:
    return playback_dir / f"{recording_id}.wav"


def _build_playback_filename(original_name: str) -> str:
    base_name = Path(original_name).stem.strip() or "recording"
    safe_name = SAFE_FILENAME_RE.sub("_", base_name).strip("._") or "recording"
    return f"{safe_name}.wav"


def _should_use_generated_playback(original_name: str, stored_path: Path) -> bool:
    suffix = Path(original_name).suffix.lower()
    if not suffix:
        suffix = stored_path.suffix.lower()
    return suffix not in DIRECT_PLAYBACK_EXTENSIONS


def _prepare_playback_file(source_path: Path, destination_path: Path) -> Path:
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        raise PlaybackPreparationError(
            "Brak `ffmpeg` w systemie. Jest wymagany do przygotowania wersji audio do odtwarzacza."
        )

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination_path.with_name(f"{destination_path.stem}_{uuid4().hex}.tmp.wav")
    command = [
        ffmpeg_path,
        "-v",
        "error",
        "-y",
        "-i",
        str(source_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(temp_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        if not temp_path.exists():
            raise PlaybackPreparationError("ffmpeg nie utworzył pliku wyjściowego.")
        temp_path.replace(destination_path)
        return destination_path
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        suffix = f" {details}" if details else ""
        raise PlaybackPreparationError(
            f"Nie udało się przygotować wersji odtwarzacza dla `{source_path.name}`.{suffix}"
        ) from exc
    except OSError as exc:
        raise PlaybackPreparationError(
            f"Nie udało się zapisać pliku odtwarzacza dla `{source_path.name}`: {exc}"
        ) from exc
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                LOGGER.warning("Could not remove temporary playback file %s", temp_path)


def _resolve_playback_source(
    *,
    recording_id: str,
    original_name: str,
    stored_path: Path,
    playback_dir: Path,
) -> tuple[Path, str, str]:
    if not _should_use_generated_playback(original_name, stored_path):
        return stored_path, _guess_recording_media_type(original_name, stored_path), original_name

    playback_path = _build_playback_path(playback_dir, recording_id)
    stored_mtime = stored_path.stat().st_mtime_ns
    playback_is_fresh = playback_path.exists() and playback_path.stat().st_mtime_ns >= stored_mtime
    if not playback_is_fresh:
        playback_path = _prepare_playback_file(stored_path, playback_path)

    return playback_path, "audio/wav", _build_playback_filename(original_name)


def _format_timecode(value: float) -> str:
    seconds = max(0.0, float(value or 0.0))
    whole_seconds = int(seconds)
    hours = whole_seconds // 3600
    minutes = (whole_seconds % 3600) // 60
    secs = whole_seconds % 60
    tenths = int(((seconds - whole_seconds) * 10) + 1e-6)

    hour_prefix = f"{hours}:" if hours else ""
    minute_part = f"{minutes:02d}"
    second_part = f"{secs:02d}"
    fraction = f".{tenths}" if tenths > 0 else ""
    return f"{hour_prefix}{minute_part}:{second_part}{fraction}"


def _build_export_text(segments: list[dict], speaker_names: dict[str, str]) -> str:
    entries: list[str] = []

    for segment in segments:
        raw_speaker = str(segment.get("speaker") or "Speaker")
        display_speaker = speaker_names.get(raw_speaker, raw_speaker).strip() or raw_speaker
        start = _format_timecode(segment.get("start", 0.0))
        end = _format_timecode(segment.get("end", 0.0))
        text = str(segment.get("text") or "").strip()
        entries.append(f"[{start} - {end}] {display_speaker}\n{text}")

    return "\n\n".join(entries).strip() + "\n"


def _build_export_filename(original_name: str) -> str:
    base_name = Path(original_name).stem.strip() or "transcript"
    safe_name = SAFE_FILENAME_RE.sub("_", base_name).strip("._") or "transcript"
    return f"{safe_name}_diarized.txt"


def create_app() -> FastAPI:
    settings = AppSettings()
    settings.load_runtime_overrides()
    settings.prepare()

    repository = EchoRepository(settings.database_path)
    repository.initialize()

    provider = build_provider(settings)
    job_runner = JobRunner(repository, provider)

    app = FastAPI(title=settings.app_name)
    app.state.settings = settings
    app.state.repository = repository
    app.state.provider = provider
    app.state.job_runner = job_runner

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    def current_settings() -> AppSettings:
        return app.state.settings

    def current_repository() -> EchoRepository:
        return app.state.repository

    def current_provider():
        return app.state.provider

    def current_job_runner() -> JobRunner:
        return app.state.job_runner

    def serialize_settings(active_settings: AppSettings | None = None) -> SettingsOut:
        value = active_settings or current_settings()
        return SettingsOut(
            app_name=value.app_name,
            app_version=value.app_version,
            host=value.host,
            port=value.port,
            data_root=str(value.data_root),
            recordings_dir=str(value.recordings_dir),
            exports_dir=str(value.exports_dir),
            models_dir=str(value.models_dir),
            transcription_provider=value.transcription_provider,
            whisper_model=value.whisper_model,
            whisper_device=value.whisper_device,
            whisper_compute_type=value.whisper_compute_type,
            diarization_model=value.diarization_model,
            diarization_device=value.diarization_device,
            language_hint=value.language_hint,
            min_speakers=value.min_speakers,
            max_speakers=value.max_speakers,
            huggingface_token_configured=bool(value.huggingface_token),
        )

    def has_active_jobs() -> bool:
        return current_job_runner().has_active_tasks()

    def apply_settings_update(payload: SettingsUpdateIn) -> AppSettings:
        next_settings = replace(current_settings())
        next_settings.apply_runtime_overrides(payload.model_dump(exclude_none=True, exclude_unset=True))

        if (
            next_settings.min_speakers is not None
            and next_settings.max_speakers is not None
            and next_settings.min_speakers > next_settings.max_speakers
        ):
            raise HTTPException(status_code=422, detail="Minimalna liczba mówców nie może być większa od maksymalnej.")

        next_settings.prepare()
        next_settings.save_runtime_overrides()

        app.state.settings = next_settings
        app.state.provider = build_provider(next_settings)
        app.state.job_runner = JobRunner(current_repository(), app.state.provider)
        return next_settings

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        index_path = STATIC_DIR / "index.html"
        html = index_path.read_text(encoding="utf-8")
        css_version = str(int((STATIC_DIR / "app.css").stat().st_mtime))
        js_version = str(int((STATIC_DIR / "app.js").stat().st_mtime))
        html = html.replace("/static/app.css", f"/static/app.css?v={css_version}")
        html = html.replace("/static/app.js", f"/static/app.js?v={js_version}")
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    @app.get("/api/health")
    async def health() -> dict:
        active_settings = current_settings()
        active_provider = current_provider()
        return {
            "status": "ok",
            "provider": active_provider.name,
            "data_root": str(active_settings.data_root),
            "time": datetime.now(UTC).isoformat(),
        }

    @app.get("/api/settings", response_model=SettingsOut)
    async def get_settings() -> SettingsOut:
        return serialize_settings()

    @app.put("/api/settings", response_model=SettingsOut)
    async def update_settings(payload: SettingsUpdateIn) -> SettingsOut:
        if has_active_jobs():
            raise HTTPException(
                status_code=409,
                detail="Nie mozna zmienic konfiguracji podczas przetwarzania joba.",
            )

        updated = apply_settings_update(payload)
        LOGGER.info(
            "Updated runtime settings: whisper=%s/%s/%s diarization=%s/%s",
            updated.whisper_model,
            updated.whisper_device,
            updated.whisper_compute_type,
            updated.diarization_model,
            updated.diarization_device,
        )
        return serialize_settings(updated)

    @app.get("/api/recordings", response_model=list[RecordingOut])
    async def list_recordings() -> list[RecordingOut]:
        return [RecordingOut.model_validate(item) for item in current_repository().list_recordings()]

    @app.post("/api/recordings/clear")
    async def clear_recordings() -> dict:
        recordings = current_repository().list_recordings()
        if any(recording["status"] == "processing" for recording in recordings):
            raise HTTPException(status_code=409, detail="Nie mozna czyscic plikow podczas przetwarzania.")

        deleted = current_repository().clear_recordings()
        files_deleted = 0
        for recording in deleted["recordings"]:
            if _delete_stored_file(Path(recording["stored_path"])):
                files_deleted += 1
            _delete_playback_file(current_settings().playback_dir, recording["id"])

        LOGGER.info(
            "Cleared recordings: %s recordings, %s jobs, %s files",
            deleted["recordings_deleted"],
            deleted["jobs_deleted"],
            files_deleted,
        )
        return {
            "recordings_deleted": deleted["recordings_deleted"],
            "jobs_deleted": deleted["jobs_deleted"],
            "files_deleted": files_deleted,
        }

    @app.post("/api/recordings/import", response_model=RecordingOut)
    async def import_recording(file: UploadFile = File(...)) -> RecordingOut:
        try:
            original_name = _normalize_recording_name(file.filename, fallback="recording.bin")
        except ValueError as exc:
            await file.close()
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        stored_path = _build_stored_path(current_settings().recordings_dir, original_name)
        LOGGER.info("Importing recording `%s` -> %s", original_name, stored_path)

        try:
            await run_in_threadpool(_store_upload, file, stored_path)
        except Exception as exc:
            LOGGER.exception("Recording import failed for `%s`", original_name)
            if stored_path.exists():
                try:
                    os.remove(stored_path)
                except OSError:
                    pass
            raise HTTPException(status_code=500, detail=f"Recording import failed: {exc}") from exc
        finally:
            await file.close()

        recording = current_repository().create_recording(original_name=original_name, stored_path=stored_path)
        LOGGER.info("Recording imported `%s` as %s", original_name, recording["id"])
        return RecordingOut.model_validate(recording)

    @app.post("/api/recordings/import/raw", response_model=RecordingOut)
    async def import_recording_raw(
        request: Request,
        filename: str = Query(..., min_length=1),
    ) -> RecordingOut:
        try:
            original_name = _normalize_recording_name(filename, fallback="recording.bin")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        stored_path = _build_stored_path(current_settings().recordings_dir, original_name)
        LOGGER.info("Importing raw recording `%s` -> %s", original_name, stored_path)

        try:
            with stored_path.open("wb") as output_file:
                async for chunk in request.stream():
                    if not chunk:
                        continue
                    output_file.write(chunk)
        except Exception as exc:
            LOGGER.exception("Raw recording import failed for `%s`", original_name)
            if stored_path.exists():
                try:
                    os.remove(stored_path)
                except OSError:
                    pass
            raise HTTPException(status_code=500, detail=f"Recording import failed: {exc}") from exc

        recording = current_repository().create_recording(original_name=original_name, stored_path=stored_path)
        LOGGER.info("Raw recording imported `%s` as %s", original_name, recording["id"])
        return RecordingOut.model_validate(recording)

    @app.patch("/api/recordings/{recording_id}", response_model=RecordingOut)
    async def rename_recording(recording_id: str, payload: RecordingRenameIn) -> RecordingOut:
        recording = current_repository().get_recording(recording_id)
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found.")

        try:
            original_name = _normalize_recording_name(payload.original_name)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        updated = current_repository().rename_recording(recording_id, original_name)
        if not updated:
            raise HTTPException(status_code=404, detail="Recording not found.")

        LOGGER.info("Renamed recording `%s` -> `%s`", recording["original_name"], original_name)
        return RecordingOut.model_validate(updated)

    @app.delete("/api/recordings/{recording_id}")
    async def delete_recording(recording_id: str) -> dict:
        recording = current_repository().get_recording(recording_id)
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found.")
        if recording["status"] == "processing":
            raise HTTPException(status_code=409, detail="Nie mozna usunac pliku podczas przetwarzania.")

        deleted = current_repository().delete_recording(recording_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Recording not found.")

        file_deleted = _delete_stored_file(Path(deleted["stored_path"]))
        _delete_playback_file(current_settings().playback_dir, deleted["id"])
        LOGGER.info(
            "Deleted recording `%s` with %s jobs, file_deleted=%s",
            deleted["original_name"],
            deleted["jobs_deleted"],
            file_deleted,
        )
        return {
            "recording_id": deleted["id"],
            "original_name": deleted["original_name"],
            "jobs_deleted": deleted["jobs_deleted"],
            "file_deleted": file_deleted,
        }

    @app.get("/api/recordings/{recording_id}/media")
    async def get_recording_media(recording_id: str) -> FileResponse:
        recording = current_repository().get_recording(recording_id)
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found.")

        stored_path = Path(recording["stored_path"])
        if not stored_path.exists() or not stored_path.is_file():
            raise HTTPException(status_code=404, detail="Recording file not found.")

        return FileResponse(
            stored_path,
            filename=recording["original_name"],
            media_type=_guess_recording_media_type(recording["original_name"], stored_path),
            content_disposition_type="inline",
        )

    @app.get("/api/recordings/{recording_id}/playback")
    async def get_recording_playback(recording_id: str) -> FileResponse:
        recording = current_repository().get_recording(recording_id)
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found.")

        stored_path = Path(recording["stored_path"])
        if not stored_path.exists() or not stored_path.is_file():
            raise HTTPException(status_code=404, detail="Recording file not found.")

        try:
            playback_path, media_type, filename = _resolve_playback_source(
                recording_id=recording["id"],
                original_name=recording["original_name"],
                stored_path=stored_path,
                playback_dir=current_settings().playback_dir,
            )
        except PlaybackPreparationError as exc:
            LOGGER.warning("Playback preparation failed for `%s`: %s", recording["original_name"], exc)
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        return FileResponse(
            playback_path,
            filename=filename,
            media_type=media_type,
            content_disposition_type="inline",
        )

    @app.get("/api/jobs", response_model=list[JobOut])
    async def list_jobs() -> list[JobOut]:
        return [JobOut.model_validate(item) for item in current_repository().list_jobs()]

    @app.post("/api/jobs/{job_id}/export/txt")
    async def export_job_txt(job_id: str, payload: TranscriptTxtExportIn) -> Response:
        job = current_repository().get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found.")

        if job["status"] != "completed":
            raise HTTPException(status_code=409, detail="Mozna eksportowac tylko zakonczony job.")

        if not job["segments"]:
            raise HTTPException(status_code=409, detail="Ten job nie zawiera segmentow diarizacji do eksportu.")

        recording = current_repository().get_recording(job["recording_id"])
        export_text = _build_export_text(
            job["segments"],
            {
                str(key): str(value).strip()
                for key, value in payload.speaker_names.items()
                if str(key).strip() and str(value).strip()
            },
        )
        filename = _build_export_filename(recording["original_name"] if recording else f"job_{job_id}")
        return Response(
            content=export_text,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.post("/api/jobs/transcribe/{recording_id}", response_model=JobOut, status_code=202)
    async def transcribe_recording(recording_id: str) -> JobOut:
        recording = current_repository().get_recording(recording_id)
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found.")

        job = await current_job_runner().submit(recording_id)
        return JobOut.model_validate(job)

    return app
