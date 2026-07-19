from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Callable, Iterator, Protocol
import wave

from .config import AppSettings
from .schemas import (
    AsrSegment,
    AsrWord,
    PipelineManifest,
    PipelineWarning,
    StageTiming,
    TranscriptResult,
    TranscriptSegment,
)


class TranscriptionError(RuntimeError):
    pass


class TranscriptionProvider(Protocol):
    name: str

    async def transcribe(
        self,
        recording_path: Path,
        progress: "ProgressCallback | None" = None,
    ) -> TranscriptResult:
        ...


@dataclass(slots=True)
class TranscriptionProgress:
    stage: str
    percent: int
    message: str


ProgressCallback = Callable[[TranscriptionProgress], None]


@dataclass(slots=True)
class WordToken:
    start: float
    end: float
    text: str
    aligned: bool = True
    raw_speaker: str | None = None
    speaker_overlap_seconds: float = 0.0


@dataclass(slots=True)
class AsrResult:
    """Wynik ASR, którego tekst i granice segmentów są źródłem prawdy."""

    text: str
    segments: list[AsrSegment]

    @property
    def words(self) -> list[WordToken]:
        return [
            WordToken(
                start=word.start,
                end=word.end,
                text=word.text,
                aligned=word.aligned,
                raw_speaker=word.speaker,
            )
            for segment in self.segments
            for word in segment.words
        ]

    def with_aligned_words(self, words: list[WordToken]) -> "AsrResult":
        """Zachowuje tekst ASR i liczbę słów, aktualizując jedynie metadane słów."""
        iterator = iter(words)
        updated: list[AsrSegment] = []
        for segment in self.segments:
            segment_words: list[AsrWord] = []
            for raw_word in segment.words:
                word = next(iterator, None)
                if word is None:
                    segment_words.append(raw_word)
                    continue
                segment_words.append(
                    AsrWord(
                        text=raw_word.text,
                        start=word.start,
                        end=word.end,
                        aligned=word.aligned,
                        speaker=word.raw_speaker,
                    )
                )
            updated.append(segment.model_copy(update={"words": segment_words}))
        return AsrResult(text=self.text, segments=updated)


@dataclass(frozen=True, slots=True)
class PreparedAudioSources:
    neutral_path: Path
    asr_path: Path
    diarization_path: Path


@dataclass(slots=True)
class SpeakerTurn:
    start: float
    end: float
    speaker: str


def emit_progress(
    callback: ProgressCallback | None,
    stage: str,
    percent: int,
    message: str,
) -> None:
    if callback is None:
        return
    callback(
        TranscriptionProgress(
            stage=stage,
            percent=max(0, min(100, int(round(percent)))),
            message=message.strip(),
        )
    )


def scale_progress(ratio: float, start: int, end: int) -> int:
    clamped = max(0.0, min(1.0, float(ratio)))
    return max(start, min(end, start + int(round((end - start) * clamped))))


def is_punctuation_only(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return False
    return all(not char.isalnum() for char in normalized)


class PipelineProgressHook:
    def __init__(
        self,
        callback: ProgressCallback | None,
        *,
        stage: str,
        start_percent: int,
        end_percent: int,
        prefix: str,
    ) -> None:
        self.callback = callback
        self.stage = stage
        self.start_percent = start_percent
        self.end_percent = end_percent
        self.prefix = prefix

    def __call__(
        self,
        step_name: str,
        step_artifact,
        file=None,
        total: int | None = None,
        completed: int | None = None,
    ) -> None:
        del step_artifact, file

        total_items = max(int(total or 0), 0)
        completed_items = max(int(completed or 0), 0)
        if total_items > 0:
            ratio = completed_items / total_items
        elif completed is not None:
            ratio = 1.0
        else:
            ratio = 0.0

        step_label = self._format_step_name(step_name)
        emit_progress(
            self.callback,
            self.stage,
            scale_progress(ratio, self.start_percent, self.end_percent),
            f"{self.prefix}: {step_label}.",
        )

    def _format_step_name(self, step_name: str) -> str:
        labels = {
            "segmentation": "segmentacja mowy",
            "speaker_counting": "szacowanie liczby speakerów",
            "embeddings": "liczenie embeddingów",
            "clustering": "grupowanie speakerów",
            "reconstruction": "składanie wyniku",
        }
        normalized = str(step_name or "").strip().lower()
        if normalized in labels:
            return labels[normalized]
        return normalized.replace("_", " ") or "przetwarzanie"


class MockTranscriptionProvider:
    name = "mock"

    async def transcribe(self, recording_path: Path, progress: ProgressCallback | None = None) -> TranscriptResult:
        emit_progress(progress, "prepare", 8, "Przygotowanie audio testowego.")
        await asyncio.sleep(0.25)
        emit_progress(progress, "whisper", 34, "Mock Whisper: generowanie transkrypcji.")
        await asyncio.sleep(0.4)
        emit_progress(progress, "diarization", 72, "Mock diarizacja speakerów.")
        await asyncio.sleep(0.35)
        emit_progress(progress, "merge", 94, "Mock scalanie segmentów.")
        await asyncio.sleep(0.2)
        stem = recording_path.stem.replace("_", " ").strip() or "Nagranie"
        segments = [
            TranscriptSegment(
                speaker="Speaker 1",
                start=0.0,
                end=4.1,
                text=f"To jest przykładowy segment dla pliku {stem}.",
            ),
            TranscriptSegment(
                speaker="Speaker 2",
                start=4.1,
                end=8.6,
                text="Ten provider jest tylko szkieletem pod docelową diarizację.",
            ),
        ]
        transcript_text = " ".join(segment.text for segment in segments)
        return TranscriptResult(provider=self.name, text=transcript_text, segments=segments)


class LocalTranscriptionProvider:
    name = "local"
    PREPARE_START = 4
    PREPARE_END = 12
    WHISPER_START = 14
    WHISPER_END = 64
    ALIGNMENT_START = 66
    ALIGNMENT_END = 74
    DIARIZATION_START = 76
    DIARIZATION_END = 96
    MERGE_START = 97
    MERGE_END = 99
    # Recorder captures in this project are quiet, compressed, and noisy enough
    # that Whisper benefits from a conservative speech-focused cleanup pass.
    PREPARE_AUDIO_FILTER = (
        "highpass=f=90,"
        "lowpass=f=7600,"
        "afftdn=nf=-20:tn=1,"
        "speechnorm=e=3.5:r=0.0001:l=1,"
        "alimiter=limit=0.95"
    )
    # "light" preset: keep only the frequency shaping, drop denoise/speechnorm/limiter
    # (candidates that can distort speech on already-compressed dictaphone recordings).
    PREPARE_AUDIO_FILTER_LIGHT = "highpass=f=90,lowpass=f=7600"
    # Quiet/mumbled dictaphone speech sits right at the default VAD threshold (0.5) decision
    # boundary, where non-deterministic CUDA kernel rounding (float16 and float32 alike) can
    # flip "speech"/"silence" between otherwise identical runs (verified 2026-07-18: same file
    # + settings produced 2-23 segments across repeated runs). A lower threshold moves the
    # decision away from that boundary, which both recovers real speech the default threshold
    # dropped and makes detection deterministic run-to-run.
    VAD_PARAMETERS = {
        "threshold": 0.2,
        "min_silence_duration_ms": 1000,
        "speech_pad_ms": 600,
    }
    PREPARE_FILTER_ERROR_MARKERS = (
        "No such filter",
        "Error initializing filter",
        "Failed to configure output pad",
        "Invalid argument",
    )

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self._whisper_model = None
        self._diarization_pipeline = None
        self._aligner = None
        self.vad_parameters = dict(self.VAD_PARAMETERS)

    async def transcribe(self, recording_path: Path, progress: ProgressCallback | None = None) -> TranscriptResult:
        return await asyncio.to_thread(self._transcribe_sync, recording_path, progress)

    def _transcribe_sync(
        self,
        recording_path: Path,
        progress: ProgressCallback | None = None,
    ) -> TranscriptResult:
        timings: dict[str, StageTiming] = {}
        warnings: list[PipelineWarning] = []
        pipeline_started = time.perf_counter()
        emit_progress(progress, "prepare", self.PREPARE_START, "Przygotowanie audio do transkrypcji.")
        prepare_started = time.perf_counter()
        with self._prepare_audio_sources(recording_path, progress) as audio_sources:
            timings["prepare"] = StageTiming(seconds=time.perf_counter() - prepare_started)
            audio_duration = self._read_wav_duration(audio_sources.neutral_path)
            emit_progress(progress, "whisper", self.WHISPER_START, "Whisper: start transkrypcji i timestampów.")
            whisper_cold_start = self._whisper_model is None
            load_started = time.perf_counter()
            self._load_whisper_model()
            timings["whisper_load"] = StageTiming(
                seconds=time.perf_counter() - load_started,
                cold_start=whisper_cold_start,
            )
            asr_started = time.perf_counter()
            asr_result = self._run_whisper(
                audio_sources.asr_path,
                recording_path.name,
                audio_duration,
                progress,
            )
            timings["asr"] = StageTiming(seconds=time.perf_counter() - asr_started)
            words = asr_result.words
            emit_progress(progress, "alignment", self.ALIGNMENT_START, "Alignment: dopasowywanie słów do audio.")
            alignment_started = time.perf_counter()
            words = self._run_alignment(words, audio_sources.neutral_path, recording_path.name, progress)
            timings["alignment"] = StageTiming(seconds=time.perf_counter() - alignment_started)
            warnings.extend(
                PipelineWarning(code="alignment_fallback", stage="alignment", message=message)
                for message in getattr(self._aligner, "warnings", [])
            )
            emit_progress(progress, "diarization", self.DIARIZATION_START, "Diarizacja: start analizy speakerów.")
            diarization_started = time.perf_counter()
            try:
                speaker_turns = self._run_diarization(audio_sources.diarization_path, recording_path.name, progress)
            except TranscriptionError:
                if self.settings.diarization_strict:
                    raise
                speaker_turns = []
                warnings.append(
                    PipelineWarning(
                        code="diarization_degraded",
                        stage="diarization",
                        message="Diarizacja nie powiodła się; zachowano transkrypcję jako jednego speakera.",
                    )
                )
            timings["diarization"] = StageTiming(seconds=time.perf_counter() - diarization_started)
        emit_progress(progress, "merge", self.MERGE_START, "Scalanie segmentów i przygotowanie wyniku.")
        merge_started = time.perf_counter()
        segments = self._merge_words_into_segments(words, speaker_turns)

        asr_result = asr_result.with_aligned_words(words)
        if not segments and asr_result.text:
            segments = [
                TranscriptSegment(
                    speaker="Speaker 1",
                    start=0.0,
                    end=max((word.end for word in words), default=0.0),
                    text=asr_result.text,
                )
            ]

        timings["merge"] = StageTiming(seconds=time.perf_counter() - merge_started)
        timings["total"] = StageTiming(seconds=time.perf_counter() - pipeline_started)
        manifest = self._build_manifest(
            audio_duration=audio_duration,
            timings=timings,
            warnings=warnings,
            words=words,
        )
        emit_progress(progress, "merge", self.MERGE_END, "Finalizacja wyniku transkrypcji.")
        return TranscriptResult(
            provider=self.name,
            text=asr_result.text,
            segments=segments,
            asr_segments=asr_result.segments,
            manifest=manifest,
        )

    def _build_manifest(
        self,
        *,
        audio_duration: float,
        timings: dict[str, StageTiming],
        warnings: list[PipelineWarning],
        words: list[WordToken],
    ) -> PipelineManifest:
        versions: dict[str, str] = {}
        for package in ("faster-whisper", "pyannote.audio", "whisperx"):
            try:
                versions[package] = metadata.version(package)
            except metadata.PackageNotFoundError:
                continue
        commit = self._read_app_commit()
        if commit:
            versions["echo_commit"] = commit
        total_seconds = timings["total"].seconds
        return PipelineManifest(
            backend=self.name,
            model=self.settings.whisper_model,
            effective_settings={
                "alignment_enabled": self.settings.alignment_enabled,
                "asr_filter_preset": self.settings.asr_filter_preset,
                "diarization_filter_preset": self.settings.diarization_filter_preset,
                "vad_parameters": dict(self.vad_parameters),
                "diarization_strict": self.settings.diarization_strict,
                "speaker_overlap_threshold_seconds": self.settings.speaker_overlap_threshold_seconds,
            },
            device=self.settings.whisper_device,
            compute_type=self.settings.effective_whisper_compute_type,
            library_versions=versions,
            stage_timings=timings,
            warnings=warnings,
            word_counts={"asr": len(words), "aligned": sum(word.aligned for word in words)},
            audio_duration_seconds=audio_duration or None,
            realtime_factor=(total_seconds / audio_duration) if audio_duration > 0 else None,
            hardware=self._collect_hardware(),
        )

    def _read_app_commit(self) -> str | None:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short=12", "HEAD"],
                cwd=Path(__file__).resolve().parents[2],
                check=True,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return result.stdout.strip() or None

    def _collect_hardware(self) -> dict[str, str | int | float]:
        hardware: dict[str, str | int | float] = {
            "platform": platform.platform(),
            "processor": platform.processor() or "unknown",
        }
        try:
            import resource

            peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # Linux reports KiB, macOS bytes.
            divisor = 1024 * 1024 if sys.platform == "darwin" else 1024
            hardware["peak_ram_mb"] = round(float(peak_rss) / divisor, 2)
        except (ImportError, OSError, ValueError):
            pass
        try:
            import torch

            hardware["torch_cuda"] = str(torch.version.cuda or "unavailable")
            if torch.cuda.is_available():
                hardware["gpu"] = str(torch.cuda.get_device_name(0))
                hardware["peak_vram_mb"] = round(torch.cuda.max_memory_allocated(0) / (1024 * 1024), 2)
        except (ImportError, RuntimeError):
            pass
        return hardware

    @contextmanager
    def _prepare_audio_source(
        self,
        recording_path: Path,
        progress: ProgressCallback | None = None,
    ) -> Iterator[Path]:
        with self._prepare_audio_sources(recording_path, progress) as sources:
            yield sources.asr_path

    @contextmanager
    def _prepare_audio_sources(
        self,
        recording_path: Path,
        progress: ProgressCallback | None = None,
    ) -> Iterator[PreparedAudioSources]:
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path is None:
            raise TranscriptionError(
                "Brak `ffmpeg` w systemie. Jest wymagany do przygotowania pliku audio przed transkrypcja."
            )

        with tempfile.TemporaryDirectory(prefix="echo-audio-") as temp_dir:
            neutral_path = Path(temp_dir) / "neutral.wav"
            try:
                self._run_prepare_command(
                    self._build_prepare_audio_command(
                        ffmpeg_path,
                        recording_path,
                        neutral_path,
                        filter_preset="none",
                    )
                )
            except subprocess.CalledProcessError as exc:
                details = (exc.stderr or exc.stdout or "").strip()
                suffix = f" {details}" if details else ""
                raise TranscriptionError(
                    f"Nie udalo sie przygotowac pliku audio `{recording_path.name}` przy pomocy ffmpeg.{suffix}"
                ) from exc

            if not neutral_path.exists():
                raise TranscriptionError(
                    f"Nie udalo sie przygotowac pliku audio `{recording_path.name}`: brak pliku wyjsciowego."
                )

            asr_path = self._prepare_audio_variant(
                ffmpeg_path, neutral_path, Path(temp_dir) / "asr.wav", self.settings.asr_filter_preset
            )
            diarization_path = self._prepare_audio_variant(
                ffmpeg_path, neutral_path, Path(temp_dir) / "diarization.wav", self.settings.diarization_filter_preset
            )

            emit_progress(progress, "prepare", self.PREPARE_END, "Audio przygotowane. Start modelu Whisper.")
            yield PreparedAudioSources(neutral_path, asr_path, diarization_path)

    def _prepare_audio_variant(self, ffmpeg_path: str, neutral_path: Path, output_path: Path, preset: str) -> Path:
        if str(preset).strip().lower() == "none":
            return neutral_path
        command = self._build_prepare_audio_command(ffmpeg_path, neutral_path, output_path, filter_preset=preset)
        try:
            self._run_prepare_command(command)
        except subprocess.CalledProcessError as exc:
            details = (exc.stderr or exc.stdout or "").strip()
            if not self._should_retry_prepare_without_filters(details):
                raise TranscriptionError(f"Nie udalo sie przygotowac wariantu audio. {details}") from exc
            return neutral_path
        if not output_path.exists():
            raise TranscriptionError("ffmpeg nie utworzyl wariantu audio.")
        return output_path

    def _build_prepare_audio_command(
        self,
        ffmpeg_path: str,
        recording_path: Path,
        normalized_path: Path,
        *,
        filter_preset: str,
    ) -> list[str]:
        command = [
            ffmpeg_path,
            "-v",
            "error",
            "-y",
            "-i",
            str(recording_path),
            "-vn",
        ]
        audio_filter = self._resolve_prepare_audio_filter(filter_preset)
        if audio_filter:
            command.extend(["-af", audio_filter])
        command.extend(
            [
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(normalized_path),
            ]
        )
        return command

    def _resolve_prepare_audio_filter(self, filter_preset: str) -> str | None:
        normalized = str(filter_preset or "").strip().lower()
        if normalized == "light":
            return self.PREPARE_AUDIO_FILTER_LIGHT
        if normalized == "none":
            return None
        return self.PREPARE_AUDIO_FILTER

    def _run_prepare_command(self, command: list[str]) -> None:
        subprocess.run(command, check=True, capture_output=True, text=True)

    def _should_retry_prepare_without_filters(self, details: str) -> bool:
        normalized = str(details or "").strip()
        return any(marker in normalized for marker in self.PREPARE_FILTER_ERROR_MARKERS)

    def _build_transcribe_kwargs(self) -> dict[str, object]:
        transcribe_kwargs: dict[str, object] = {
            "beam_size": 5,
            "vad_filter": True,
            "vad_parameters": dict(self.vad_parameters),
            "word_timestamps": True,
            "condition_on_previous_text": False,
        }
        if self.settings.language_hint:
            transcribe_kwargs["language"] = self.settings.language_hint
        return transcribe_kwargs

    def _run_whisper(
        self,
        audio_path: Path,
        source_name: str,
        audio_duration: float,
        progress: ProgressCallback | None = None,
    ) -> AsrResult:
        whisper_model = self._load_whisper_model()
        transcribe_kwargs = self._build_transcribe_kwargs()

        try:
            segments_iter, _ = whisper_model.transcribe(str(audio_path), **transcribe_kwargs)
        except Exception as exc:
            raise TranscriptionError(f"Whisper failed for `{source_name}`: {exc}") from exc

        transcript_parts: list[str] = []
        asr_segments: list[AsrSegment] = []
        for segment in segments_iter:
            segment_end = float(getattr(segment, "end", 0.0) or 0.0)
            if audio_duration > 0:
                emit_progress(
                    progress,
                    "whisper",
                    scale_progress(segment_end / audio_duration, self.WHISPER_START, self.WHISPER_END),
                    "Whisper: transkrypcja i timestampy słów.",
                )
            segment_text = (getattr(segment, "text", "") or "").strip()
            if segment_text:
                transcript_parts.append(segment_text)

            segment_words = getattr(segment, "words", None) or []
            parsed_words: list[AsrWord] = []
            if segment_words:
                for word in segment_words:
                    text = (getattr(word, "word", "") or "").strip()
                    start = getattr(word, "start", None)
                    end = getattr(word, "end", None)
                    if not text or start is None or end is None or is_punctuation_only(text):
                        continue
                    parsed_words.append(AsrWord(start=float(start), end=float(end), text=text))

            if not parsed_words and segment_text and not is_punctuation_only(segment_text):
                parsed_words.append(
                    AsrWord(
                        start=float(getattr(segment, "start", 0.0) or 0.0),
                        end=float(getattr(segment, "end", 0.0) or 0.0),
                        text=segment_text,
                    )
                )

            if segment_text or parsed_words:
                asr_segments.append(
                    AsrSegment(
                        start=float(getattr(segment, "start", 0.0) or 0.0),
                        end=segment_end,
                        text=segment_text,
                        words=parsed_words,
                    )
                )

        transcript_text = " ".join(part for part in transcript_parts if part).strip()
        emit_progress(progress, "whisper", self.WHISPER_END, "Whisper: transkrypcja zakończona.")
        return AsrResult(text=transcript_text, segments=asr_segments)

    def _run_alignment(
        self,
        words: list[WordToken],
        audio_path: Path,
        source_name: str,
        progress: ProgressCallback | None = None,
    ) -> list[WordToken]:
        if not self.settings.alignment_enabled:
            emit_progress(progress, "alignment", self.ALIGNMENT_END, "Alignment: wyłączony w ustawieniach.")
            return words
        aligner = self._load_aligner()
        aligned_words = aligner.align(words, audio_path, source_name)
        emit_progress(progress, "alignment", self.ALIGNMENT_END, "Alignment: słowa dopasowane do audio.")
        return aligned_words

    def _load_aligner(self):
        if self._aligner is not None:
            return self._aligner

        from .alignment import ForcedAligner

        self._aligner = ForcedAligner(
            device=self.settings.diarization_device,
            language=self.settings.language_hint,
        )
        return self._aligner

    def _run_diarization(
        self,
        audio_path: Path,
        source_name: str,
        progress: ProgressCallback | None = None,
    ) -> list[SpeakerTurn]:
        pipeline = self._load_diarization_pipeline()

        diarization_kwargs: dict[str, int] = {}
        if self.settings.min_speakers is not None:
            diarization_kwargs["min_speakers"] = self.settings.min_speakers
        if self.settings.max_speakers is not None:
            diarization_kwargs["max_speakers"] = self.settings.max_speakers

        progress_hook = PipelineProgressHook(
            progress,
            stage="diarization",
            start_percent=self.DIARIZATION_START,
            end_percent=self.DIARIZATION_END,
            prefix="Diarizacja",
        )
        try:
            diarization_result = pipeline(str(audio_path), hook=progress_hook, **diarization_kwargs)
        except Exception as exc:
            raise TranscriptionError(f"Diarization failed for `{source_name}`: {exc}") from exc

        annotation = getattr(diarization_result, "exclusive_speaker_diarization", None)
        if annotation is None:
            annotation = getattr(diarization_result, "speaker_diarization", None)
        if annotation is None:
            annotation = diarization_result

        speaker_turns: list[SpeakerTurn] = []
        for turn, _, speaker in annotation.itertracks(yield_label=True):
            speaker_turns.append(
                SpeakerTurn(
                    start=float(turn.start),
                    end=float(turn.end),
                    speaker=str(speaker),
                )
            )

        speaker_turns.sort(key=lambda item: (item.start, item.end))
        emit_progress(progress, "diarization", self.DIARIZATION_END, "Diarizacja: speakerzy gotowi.")
        return speaker_turns

    def _read_wav_duration(self, audio_path: Path) -> float:
        try:
            with wave.open(str(audio_path), "rb") as wav_file:
                frame_rate = wav_file.getframerate() or 0
                if frame_rate <= 0:
                    return 0.0
                return wav_file.getnframes() / frame_rate
        except (wave.Error, OSError):
            return 0.0

    def _load_whisper_model(self):
        if self._whisper_model is not None:
            return self._whisper_model

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise TranscriptionError(
                "Brak zaleznosci lokalnych modeli. Zainstaluj `pip install -e .[local]`."
            ) from exc

        model_ref = self.settings.whisper_model
        try:
            self._whisper_model = WhisperModel(
                model_ref,
                device=self.settings.whisper_device,
                compute_type=self.settings.effective_whisper_compute_type,
                download_root=str(self.settings.whisper_cache_dir),
            )
        except Exception as exc:
            raise TranscriptionError(
                f"Nie udalo sie zaladowac modelu Whisper `{model_ref}`: {exc}"
            ) from exc
        return self._whisper_model

    def _load_diarization_pipeline(self):
        if self._diarization_pipeline is not None:
            return self._diarization_pipeline

        try:
            from pyannote.audio import Pipeline
        except ImportError as exc:
            raise TranscriptionError(
                "Brak pyannote.audio. Zainstaluj `pip install -e .[local]`."
            ) from exc

        model_ref = self.settings.diarization_model
        try:
            if self.settings.huggingface_token:
                pipeline = Pipeline.from_pretrained(model_ref, token=self.settings.huggingface_token)
            else:
                pipeline = Pipeline.from_pretrained(model_ref)
        except Exception as exc:
            hint = ""
            if not Path(model_ref).exists() and not self.settings.huggingface_token:
                hint = " Ustaw `HF_TOKEN` albo wskaz lokalny katalog modelu diarizacji."
            raise TranscriptionError(
                f"Nie udalo sie zaladowac modelu diarizacji `{model_ref}`.{hint}"
            ) from exc

        if self.settings.diarization_device:
            try:
                import torch

                pipeline.to(torch.device(self.settings.diarization_device))
            except ImportError:
                pass
            except Exception as exc:
                raise TranscriptionError(
                    f"Nie udalo sie ustawic urzadzenia diarizacji `{self.settings.diarization_device}`: {exc}"
                ) from exc

        self._diarization_pipeline = pipeline
        return self._diarization_pipeline

    def _merge_words_into_segments(
        self,
        words: list[WordToken],
        speaker_turns: list[SpeakerTurn],
    ) -> list[TranscriptSegment]:
        if not words:
            return []

        speaker_labels: dict[str, str] = {}
        merged_segments: list[TranscriptSegment] = []
        for word in words:
            raw_speaker, overlap = self._pick_speaker_for_word(word, speaker_turns)
            word.raw_speaker = raw_speaker
            word.speaker_overlap_seconds = overlap
            if raw_speaker == "UNKNOWN":
                display_speaker = "UNKNOWN"
            else:
                display_speaker = speaker_labels.setdefault(raw_speaker, f"Speaker {len(speaker_labels) + 1}")

            if (
                merged_segments
                and merged_segments[-1].speaker == display_speaker
                and word.start - merged_segments[-1].end <= self.settings.segment_merge_gap_seconds
            ):
                merged_segments[-1].end = word.end
                merged_segments[-1].text = self._append_text(merged_segments[-1].text, word.text)
                continue

            merged_segments.append(
                TranscriptSegment(
                    speaker=display_speaker,
                    start=word.start,
                    end=word.end,
                    text=word.text,
                )
            )

        return merged_segments

    def _pick_speaker_for_word(
        self,
        word: WordToken,
        speaker_turns: list[SpeakerTurn],
    ) -> tuple[str, float]:
        if not speaker_turns:
            return "SPEAKER_00", 0.0

        winner: SpeakerTurn | None = None
        winner_overlap = 0.0
        for turn in speaker_turns:
            overlap = max(0.0, min(word.end, turn.end) - max(word.start, turn.start))
            if overlap > winner_overlap:
                winner = turn
                winner_overlap = overlap
        if winner is None or winner_overlap < self.settings.speaker_overlap_threshold_seconds:
            return "UNKNOWN", winner_overlap
        return winner.speaker, winner_overlap

    def _append_text(self, current_text: str, token: str) -> str:
        if not current_text:
            return token

        no_space_before = {".", ",", "!", "?", ":", ";", "%", ")", "]", "}"}
        no_space_after = {"(", "[", "{", "/", '"'}
        if token[:1] in no_space_before or current_text[-1:] in no_space_after:
            return f"{current_text}{token}"
        return f"{current_text} {token}"


def build_provider(settings: AppSettings) -> TranscriptionProvider:
    normalized = settings.transcription_provider.strip().lower()
    if normalized == "mock":
        return MockTranscriptionProvider()
    if normalized == "local":
        return LocalTranscriptionProvider(settings)
    return MockTranscriptionProvider()
