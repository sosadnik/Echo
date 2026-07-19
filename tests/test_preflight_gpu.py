from __future__ import annotations

from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from preflight_gpu import run_preflight  # noqa: E402


class GpuPreflightTests(unittest.TestCase):
    def test_reports_all_checks_without_requiring_gpu_in_unit_test(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch("preflight_gpu.shutil.which", return_value="/usr/bin/ffmpeg"),
            patch("preflight_gpu.shutil.disk_usage", return_value=SimpleNamespace(total=100, used=10, free=90)),
            patch("preflight_gpu._cuda_info", return_value={"available": True, "gpu": "RTX test", "cuda": "12.8"}),
            patch("preflight_gpu._package_versions", return_value={
                "faster-whisper": "1.2.1",
                "pyannote.audio": "4.0.7",
                "whisperx": "3.8.6",
                "torch": "2.8.0+cu128",
                "ctranslate2": "4.8.1",
            }),
        ):
            result = run_preflight(Path(temp_dir), minimum_free_bytes=50)

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["checks"]["cuda"]["ok"])
        self.assertEqual(result["checks"]["models_dir"]["path"], temp_dir)

    def test_fails_when_cuda_or_disk_is_unavailable(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch("preflight_gpu.shutil.which", return_value=None),
            patch("preflight_gpu.shutil.disk_usage", return_value=SimpleNamespace(total=100, used=99, free=1)),
            patch("preflight_gpu._cuda_info", return_value={"available": False}),
            patch("preflight_gpu._package_versions", return_value={}),
        ):
            result = run_preflight(Path(temp_dir), minimum_free_bytes=50)

        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["checks"]["ffmpeg"]["ok"])
        self.assertFalse(result["checks"]["disk"]["ok"])


if __name__ == "__main__":
    unittest.main()
