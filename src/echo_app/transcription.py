from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Callable, Iterator, Protocol
import wave

from .config import AppSettings
from .schemas import TranscriptResult, TranscriptSegment


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
    WHISPER_END = 74
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

    async def transcribe(self, recording_path: Path, progress: ProgressCallback | None = None) -> TranscriptResult:
        return await asyncio.to_thread(self._transcribe_sync, recording_path, progress)

    def _transcribe_sync(
        self,
        recording_path: Path,
        progress: ProgressCallback | None = None,
    ) -> TranscriptResult:
        emit_progress(progress, "prepare", self.PREPARE_START, "Przygotowanie audio do transkrypcji.")
        with self._prepare_audio_source(recording_path, progress) as audio_path:
            audio_duration = self._read_wav_duration(audio_path)
            emit_progress(progress, "whisper", self.WHISPER_START, "Whisper: start transkrypcji i timestampów.")
            words, transcript_text = self._run_whisper(
                audio_path,
                recording_path.name,
                audio_duration,
                progress,
            )
            emit_progress(progress, "diarization", self.DIARIZATION_START, "Diarizacja: start analizy speakerów.")
            speaker_turns = self._run_diarization(audio_path, recording_path.name, progress)
        emit_progress(progress, "merge", self.MERGE_START, "Scalanie segmentów i przygotowanie wyniku.")
        segments = self._merge_words_into_segments(words, speaker_turns)

        if not segments and transcript_text:
            segments = [
                TranscriptSegment(
                    speaker="Speaker 1",
                    start=0.0,
                    end=max((word.end for word in words), default=0.0),
                    text=transcript_text,
                )
            ]

        emit_progress(progress, "merge", self.MERGE_END, "Finalizacja wyniku transkrypcji.")
        return TranscriptResult(provider=self.name, text=transcript_text, segments=segments)

    @contextmanager
    def _prepare_audio_source(
        self,
        recording_path: Path,
        progress: ProgressCallback | None = None,
    ) -> Iterator[Path]:
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path is None:
            raise TranscriptionError(
                "Brak `ffmpeg` w systemie. Jest wymagany do przygotowania pliku audio przed transkrypcja."
            )

        with tempfile.TemporaryDirectory(prefix="echo-audio-") as temp_dir:
            normalized_path = Path(temp_dir) / f"{recording_path.stem}.wav"
            try:
                self._run_prepare_command(
                    self._build_prepare_audio_command(
                        ffmpeg_path,
                        recording_path,
                        normalized_path,
                        use_filters=True,
                    )
                )
            except subprocess.CalledProcessError as exc:
                details = (exc.stderr or exc.stdout or "").strip()
                if self._should_retry_prepare_without_filters(details):
                    try:
                        self._run_prepare_command(
                            self._build_prepare_audio_command(
                                ffmpeg_path,
                                recording_path,
                                normalized_path,
                                use_filters=False,
                            )
                        )
                    except subprocess.CalledProcessError as fallback_exc:
                        fallback_details = (fallback_exc.stderr or fallback_exc.stdout or "").strip()
                        suffix = f" {fallback_details}" if fallback_details else ""
                        raise TranscriptionError(
                            f"Nie udalo sie przygotowac pliku audio `{recording_path.name}` przy pomocy ffmpeg.{suffix}"
                        ) from fallback_exc
                else:
                    suffix = f" {details}" if details else ""
                    raise TranscriptionError(
                        f"Nie udalo sie przygotowac pliku audio `{recording_path.name}` przy pomocy ffmpeg.{suffix}"
                    ) from exc

            if not normalized_path.exists():
                raise TranscriptionError(
                    f"Nie udalo sie przygotowac pliku audio `{recording_path.name}`: brak pliku wyjsciowego."
                )

            emit_progress(progress, "prepare", self.PREPARE_END, "Audio przygotowane. Start modelu Whisper.")
            yield normalized_path

    def _build_prepare_audio_command(
        self,
        ffmpeg_path: str,
        recording_path: Path,
        normalized_path: Path,
        *,
        use_filters: bool,
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
        if use_filters:
            command.extend(["-af", self.PREPARE_AUDIO_FILTER])
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

    def _run_prepare_command(self, command: list[str]) -> None:
        subprocess.run(command, check=True, capture_output=True, text=True)

    def _should_retry_prepare_without_filters(self, details: str) -> bool:
        normalized = str(details or "").strip()
        return any(marker in normalized for marker in self.PREPARE_FILTER_ERROR_MARKERS)

    def _run_whisper(
        self,
        audio_path: Path,
        source_name: str,
        audio_duration: float,
        progress: ProgressCallback | None = None,
    ) -> tuple[list[WordToken], str]:
        whisper_model = self._load_whisper_model()

        transcribe_kwargs = {
            "beam_size": 5,
            "vad_filter": false,
            "word_timestamps": True,
        }
        if self.settings.language_hint:
            transcribe_kwargs["language"] = self.settings.language_hint

        try:
            segments_iter, _ = whisper_model.transcribe(str(audio_path), **transcribe_kwargs)
        except Exception as exc:
            raise TranscriptionError(f"Whisper failed for `{source_name}`: {exc}") from exc

        words: list[WordToken] = []
        transcript_parts: list[str] = []
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
            if segment_words:
                for word in segment_words:
                    text = (getattr(word, "word", "") or "").strip()
                    start = getattr(word, "start", None)
                    end = getattr(word, "end", None)
                    if not text or start is None or end is None or is_punctuation_only(text):
                        continue
                    words.append(WordToken(start=float(start), end=float(end), text=text))
                continue

            if segment_text and not is_punctuation_only(segment_text):
                words.append(
                    WordToken(
                        start=float(getattr(segment, "start", 0.0) or 0.0),
                        end=float(getattr(segment, "end", 0.0) or 0.0),
                        text=segment_text,
                    )
                )

        transcript_text = " ".join(part for part in transcript_parts if part).strip()
        emit_progress(progress, "whisper", self.WHISPER_END, "Whisper: transkrypcja zakończona.")
        return words, transcript_text

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
                compute_type=self.settings.whisper_compute_type,
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
        turn_index = 0

        for word in words:
            raw_speaker, turn_index = self._pick_speaker_for_word(word, speaker_turns, turn_index)
            display_speaker = speaker_labels.setdefault(
                raw_speaker,
                f"Speaker {len(speaker_labels) + 1}",
            )

            if merged_segments and merged_segments[-1].speaker == display_speaker and word.start - merged_segments[-1].end <= 1.2:
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
        turn_index: int,
    ) -> tuple[str, int]:
        if not speaker_turns:
            return "SPEAKER_00", turn_index

        midpoint = (word.start + word.end) / 2
        last_index = len(speaker_turns) - 1

        while turn_index < last_index and midpoint > speaker_turns[turn_index].end:
            turn_index += 1

        current_turn = speaker_turns[turn_index]
        if current_turn.start <= midpoint <= current_turn.end:
            return current_turn.speaker, turn_index

        if turn_index > 0:
            previous_turn = speaker_turns[turn_index - 1]
            distance_to_previous = abs(midpoint - previous_turn.end)
            distance_to_current = abs(current_turn.start - midpoint)
            if distance_to_previous <= distance_to_current:
                return previous_turn.speaker, turn_index

        return current_turn.speaker, turn_index

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
