from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


BENCHMARK_ARTIFACT_VERSION = "benchmark-artifact/v1"


class StageTiming(BaseModel):
    """Czas jednego etapu pipeline'u, zapisywany w sekundach monotonicznych."""

    seconds: float = Field(ge=0)
    cold_start: bool = False


class PipelineWarning(BaseModel):
    """Jawna degradacja lub fallback, który może wpłynąć na wynik."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    stage: str | None = None


class AsrWord(BaseModel):
    text: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    speaker: str | None = None
    aligned: bool = True


class AsrSegment(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    text: str
    words: list[AsrWord] = Field(default_factory=list)


class PipelineManifest(BaseModel):
    """Wersjonowany provenance wspólny dla joba i artefaktu benchmarku."""

    artifact_version: Literal["benchmark-artifact/v1"] = BENCHMARK_ARTIFACT_VERSION
    backend: str = Field(min_length=1)
    model: str = Field(min_length=1)
    effective_settings: dict[str, Any] = Field(default_factory=dict)
    device: str = Field(min_length=1)
    compute_type: str = Field(min_length=1)
    library_versions: dict[str, str] = Field(default_factory=dict)
    stage_timings: dict[str, StageTiming] = Field(default_factory=dict)
    warnings: list[PipelineWarning] = Field(default_factory=list)
    word_counts: dict[str, int] = Field(default_factory=dict)
    audio_duration_seconds: float | None = Field(default=None, ge=0)
    realtime_factor: float | None = Field(default=None, ge=0)
    hardware: dict[str, str | int | float] = Field(default_factory=dict)


class TranscriptSegment(BaseModel):
    speaker: str
    start: float
    end: float
    text: str


class TranscriptResult(BaseModel):
    provider: str
    text: str
    segments: list[TranscriptSegment] = Field(default_factory=list)
    asr_segments: list[AsrSegment] = Field(default_factory=list)
    manifest: PipelineManifest | None = None


class RecordingOut(BaseModel):
    id: str
    original_name: str
    stored_path: str
    status: str
    created_at: str


class RecordingRenameIn(BaseModel):
    original_name: str = Field(..., min_length=1, max_length=255)


class JobOut(BaseModel):
    id: str
    recording_id: str
    provider: str
    status: str
    progress_percent: int = 0
    progress_stage: str | None = None
    progress_message: str | None = None
    created_at: str
    updated_at: str
    error: str | None = None
    transcript_text: str | None = None
    segments: list[TranscriptSegment] = Field(default_factory=list)
    manifest: PipelineManifest | None = None
    warnings: list[PipelineWarning] = Field(default_factory=list)


class TranscriptTxtExportIn(BaseModel):
    speaker_names: dict[str, str] = Field(default_factory=dict)


class ClipRangeIn(BaseModel):
    start: float = Field(..., ge=0)
    end: float = Field(..., gt=0)


class RecordingClipPreviewIn(BaseModel):
    ranges: list[ClipRangeIn] = Field(..., min_length=1, max_length=64)
    padding_ms: int = Field(default=180, ge=0, le=1000)


class SettingsOut(BaseModel):
    app_name: str
    app_version: str
    host: str
    port: int
    data_root: str
    recordings_dir: str
    exports_dir: str
    models_dir: str
    transcription_provider: str
    whisper_model: str
    whisper_device: str
    whisper_compute_type: str
    effective_whisper_compute_type: str
    diarization_model: str
    diarization_device: str
    alignment_enabled: bool
    asr_filter_preset: str
    diarization_filter_preset: str
    language_hint: str | None = None
    min_speakers: int | None = None
    max_speakers: int | None = None
    huggingface_token_configured: bool


class SettingsUpdateIn(BaseModel):
    whisper_model: str | None = Field(default=None, min_length=1)
    whisper_device: str | None = Field(default=None, min_length=1)
    whisper_compute_type: str | None = Field(default=None, min_length=1)
    diarization_model: str | None = Field(default=None, min_length=1)
    diarization_device: str | None = Field(default=None, min_length=1)
    alignment_enabled: bool | None = None
    asr_filter_preset: str | None = Field(default=None, min_length=1)
    diarization_filter_preset: str | None = Field(default=None, min_length=1)
