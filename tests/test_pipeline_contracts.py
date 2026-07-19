from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest.mock import patch

from echo_app.repository import EchoRepository
from echo_app.config import AppSettings
from echo_app.schemas import (
    BENCHMARK_ARTIFACT_VERSION,
    AsrSegment,
    AsrWord,
    PipelineManifest,
    PipelineWarning,
    StageTiming,
)
from echo_app.transcription import LocalTranscriptionProvider, WordToken


class PipelineContractTests(unittest.TestCase):
    def test_manifest_v1_round_trips_with_asr_structure_and_warning(self) -> None:
        manifest = PipelineManifest(
            backend="faster-whisper",
            model="large-v3-turbo",
            effective_settings={"alignment_enabled": False, "vad": {"threshold": 0.2}},
            device="cuda",
            compute_type="float16",
            library_versions={"faster-whisper": "1.2.1"},
            stage_timings={"asr": StageTiming(seconds=12.5, cold_start=True)},
            warnings=[PipelineWarning(code="alignment_disabled", message="Alignment wyłączony.")],
            word_counts={"before_alignment": 12, "after_alignment": 12},
            audio_duration_seconds=30.0,
            realtime_factor=0.42,
        )
        segment = AsrSegment(
            start=0.0,
            end=1.2,
            text="Cześć, świecie!",
            words=[AsrWord(text="Cześć", start=0.0, end=0.4)],
        )

        restored = PipelineManifest.model_validate_json(manifest.model_dump_json())

        self.assertEqual(restored.artifact_version, BENCHMARK_ARTIFACT_VERSION)
        self.assertEqual(restored.stage_timings["asr"].seconds, 12.5)
        self.assertFalse(restored.effective_settings["alignment_enabled"])
        self.assertEqual(segment.words[0].text, "Cześć")

    def test_rejects_unknown_artifact_version(self) -> None:
        with self.assertRaises(ValueError):
            PipelineManifest.model_validate(
                {
                    "artifact_version": "benchmark-artifact/v2",
                    "backend": "mock",
                    "model": "mock",
                    "device": "cpu",
                    "compute_type": "int8",
                }
            )

    def test_manifest_has_timing_and_never_serializes_hf_token(self) -> None:
        settings = AppSettings(huggingface_token="hf_private_secret")
        provider = LocalTranscriptionProvider(settings)
        with (
            patch.object(provider, "_collect_hardware", return_value={"gpu": "RTX test", "peak_vram_mb": 123}),
            patch.object(provider, "_read_app_commit", return_value="abc123"),
        ):
            manifest = provider._build_manifest(
                audio_duration=2.0,
                timings={"total": StageTiming(seconds=1.0)},
                warnings=[PipelineWarning(code="fallback", message="test")],
                words=[WordToken(start=0, end=1, text="test")],
            )

        self.assertEqual(manifest.realtime_factor, 0.5)
        self.assertEqual(manifest.word_counts, {"asr": 1, "aligned": 1})
        self.assertEqual(manifest.hardware["gpu"], "RTX test")
        self.assertEqual(manifest.library_versions["echo_commit"], "abc123")
        self.assertNotIn("hf_private_secret", manifest.model_dump_json())

    def test_legacy_minimal_result_json_still_exposes_segments(self) -> None:
        payload = {
            "id": "job-1",
            "recording_id": "recording-1",
            "provider": "local",
            "status": "completed",
            "progress_percent": 100,
            "progress_stage": "completed",
            "progress_message": "ok",
            "created_at": "2026-07-18T00:00:00+00:00",
            "updated_at": "2026-07-18T00:00:00+00:00",
            "error": None,
            "transcript_text": "Cześć świecie",
            "result_json": json.dumps(
                {
                    "segments": [
                        {"speaker": "Speaker 1", "start": 0, "end": 1, "text": "Cześć świecie"}
                    ]
                }
            ),
        }

        job = EchoRepository(Path("unused-test.db"))._job_payload_to_dict(payload)

        self.assertEqual(job["segments"][0]["text"], "Cześć świecie")
        self.assertIsNone(job.get("manifest"))


if __name__ == "__main__":
    unittest.main()
