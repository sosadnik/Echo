from __future__ import annotations

from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    speaker: str
    start: float
    end: float
    text: str


class TranscriptResult(BaseModel):
    provider: str
    text: str
    segments: list[TranscriptSegment] = Field(default_factory=list)


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
    diarization_model: str
    diarization_device: str
    language_hint: str | None = None
    min_speakers: int | None = None
    max_speakers: int | None = None
    huggingface_token_configured: bool


class SettingsUpdateIn(BaseModel):
    whisper_model: str | None = Field(default=None, min_length=1)
    whisper_device: str | None = Field(default=None, min_length=1)
    diarization_model: str | None = Field(default=None, min_length=1)
    diarization_device: str | None = Field(default=None, min_length=1)
