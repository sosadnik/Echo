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
        self.assertEqual(settings.whisper_compute_type, "float16")

    def test_default_compute_type_is_int8_on_cpu(self) -> None:
        with patch.dict(os.environ, {"ECHO_WHISPER_DEVICE": "cpu"}, clear=False):
            settings = AppSettings()
        self.assertEqual(settings.whisper_device, "cpu")
        self.assertEqual(settings.whisper_compute_type, "int8")


if __name__ == "__main__":
    unittest.main()
