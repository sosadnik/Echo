from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from echo_app.config import AppSettings


class AppSettingsDefaultsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(
            os.environ,
            {
                "XDG_DATA_HOME": self.temp_dir.name,
            },
            clear=False,
        )
        self.env_patch.start()
        for key in (
            "ECHO_WHISPER_MODEL",
            "ECHO_WHISPER_DEVICE",
            "ECHO_WHISPER_COMPUTE_TYPE",
            "ECHO_ALIGNMENT_ENABLED",
            "ECHO_ASR_FILTER_PRESET",
            "ECHO_DIARIZATION_FILTER_PRESET",
            "ECHO_PREPARE_FILTER_PRESET",
        ):
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        self.env_patch.stop()
        self.temp_dir.cleanup()

    def test_default_whisper_model_is_large_v3_turbo(self) -> None:
        settings = AppSettings()
        self.assertEqual(settings.whisper_model, "large-v3-turbo")

    def test_default_compute_type_is_float16_on_cuda(self) -> None:
        with patch.dict(os.environ, {"ECHO_WHISPER_DEVICE": "cuda"}, clear=False):
            settings = AppSettings()
        self.assertEqual(settings.whisper_device, "cuda")
        self.assertEqual(settings.whisper_compute_type, "auto")
        self.assertEqual(settings.effective_whisper_compute_type, "float16")

    def test_default_compute_type_is_int8_on_cpu(self) -> None:
        with patch.dict(os.environ, {"ECHO_WHISPER_DEVICE": "cpu"}, clear=False):
            settings = AppSettings()
        self.assertEqual(settings.whisper_device, "cpu")
        self.assertEqual(settings.whisper_compute_type, "auto")
        self.assertEqual(settings.effective_whisper_compute_type, "int8")

    def test_auto_compute_type_recalculates_when_device_changes(self) -> None:
        settings = AppSettings()

        settings.apply_runtime_overrides({"whisper_device": "cuda:0"})
        self.assertEqual(settings.whisper_compute_type, "auto")
        self.assertEqual(settings.effective_whisper_compute_type, "float16")

        settings.apply_runtime_overrides({"whisper_device": "cpu"})
        self.assertEqual(settings.effective_whisper_compute_type, "int8")

    def test_model_alias_is_canonical_and_unknown_model_is_preserved(self) -> None:
        settings = AppSettings(whisper_model="turbo")
        self.assertEqual(settings.whisper_model, "large-v3-turbo")

        settings.apply_runtime_overrides({"whisper_model": "custom/model-v1"})
        self.assertEqual(settings.whisper_model, "custom/model-v1")

    def test_runtime_overrides_persist_new_pipeline_settings(self) -> None:
        settings = AppSettings()
        settings.apply_runtime_overrides(
            {
                "alignment_enabled": False,
                "asr_filter_preset": "light",
                "diarization_filter_preset": "none",
                "whisper_compute_type": "auto",
            }
        )
        settings.save_runtime_overrides()

        restored = AppSettings()
        restored.load_runtime_overrides()

        self.assertFalse(restored.alignment_enabled)
        self.assertEqual(restored.asr_filter_preset, "light")
        self.assertEqual(restored.diarization_filter_preset, "none")


if __name__ == "__main__":
    unittest.main()
