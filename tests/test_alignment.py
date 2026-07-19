from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from echo_app.alignment import ForcedAligner
from echo_app.config import AppSettings
from echo_app.transcription import LocalTranscriptionProvider, WordToken


class ForcedAlignerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.words = [
            WordToken(start=0.0, end=0.4, text="Cześć"),
            WordToken(start=0.5, end=1.0, text="świecie"),
        ]

    def test_align_returns_original_words_when_empty(self) -> None:
        aligner = ForcedAligner()
        result = aligner.align([], Path("/tmp/input.wav"), "nagranie.wav")
        self.assertEqual(result, [])

    def test_align_happy_path_uses_whisperx_output(self) -> None:
        aligner = ForcedAligner(device="cpu", language="pl")
        aligned = [
            WordToken(start=0.02, end=0.38, text="Cześć"),
            WordToken(start=0.48, end=0.97, text="świecie"),
        ]

        with patch.object(aligner, "_align_with_whisperx", return_value=aligned) as mocked:
            result = aligner.align(self.words, Path("/tmp/input.wav"), "nagranie.wav")

        mocked.assert_called_once()
        self.assertEqual(result, aligned)

    def test_align_falls_back_to_raw_words_on_exception(self) -> None:
        aligner = ForcedAligner()

        with patch.object(aligner, "_align_with_whisperx", side_effect=RuntimeError("boom")):
            result = aligner.align(self.words, Path("/tmp/input.wav"), "nagranie.wav")

        self.assertEqual(result, self.words)

    def test_align_falls_back_when_whisperx_dependency_missing(self) -> None:
        aligner = ForcedAligner()

        with patch.object(
            aligner,
            "_align_with_whisperx",
            side_effect=ImportError("No module named 'whisperx'"),
        ):
            result = aligner.align(self.words, Path("/tmp/input.wav"), "nagranie.wav")

        self.assertEqual(result, self.words)

    def test_align_with_whisperx_uses_cached_model(self) -> None:
        aligner = ForcedAligner(device="cpu", language="pl")

        fake_whisperx = unittest.mock.Mock()
        fake_whisperx.load_align_model.return_value = ("model", "metadata")
        fake_whisperx.load_audio.return_value = "audio-array"
        fake_whisperx.align.return_value = {
            "segments": [
                {
                    "words": [
                        {"word": "Cześć", "start": 0.02, "end": 0.38},
                        {"word": "świecie", "start": 0.48, "end": 0.97},
                    ]
                }
            ]
        }

        with patch.dict("sys.modules", {"whisperx": fake_whisperx}):
            result = aligner._align_with_whisperx(self.words, Path("/tmp/input.wav"))
            aligner._align_with_whisperx(self.words, Path("/tmp/input.wav"))

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].text, "Cześć")
        self.assertAlmostEqual(result[0].start, 0.02)
        fake_whisperx.load_align_model.assert_called_once()

    def test_align_with_whisperx_raises_when_result_empty(self) -> None:
        aligner = ForcedAligner()

        fake_whisperx = unittest.mock.Mock()
        fake_whisperx.load_align_model.return_value = ("model", "metadata")
        fake_whisperx.load_audio.return_value = "audio-array"
        fake_whisperx.align.return_value = {"segments": []}

        with patch.dict("sys.modules", {"whisperx": fake_whisperx}):
            with self.assertRaises(Exception):
                aligner._align_with_whisperx(self.words, Path("/tmp/input.wav"))

    def test_align_processes_long_input_in_chunks_and_preserves_missing_words(self) -> None:
        words = [WordToken(start=float(index), end=float(index + 1), text=f"w{index}") for index in range(5)]
        aligner = ForcedAligner(max_words_per_chunk=2)

        with patch.object(
            aligner,
            "_align_with_whisperx",
            side_effect=[
                [WordToken(start=0.1, end=0.9, text="w0")],
                RuntimeError("chunk failure"),
                [WordToken(start=4.1, end=4.9, text="w4")],
            ],
        ) as mocked:
            result = aligner.align(words, Path("/tmp/input.wav"), "long.wav")

        self.assertEqual([word.text for word in result], [word.text for word in words])
        self.assertAlmostEqual(result[0].start, 0.1)
        self.assertTrue(result[0].aligned)
        self.assertEqual(result[1].start, 1.0)
        self.assertTrue(result[1].aligned)
        self.assertEqual(result[2].start, 2.0)
        self.assertTrue(result[2].aligned)
        self.assertEqual(mocked.call_count, 3)


class LocalTranscriptionProviderAlignmentIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(
            os.environ,
            {"XDG_DATA_HOME": self.temp_dir.name},
            clear=False,
        )
        self.env_patch.start()
        self.settings = AppSettings()
        self.provider = LocalTranscriptionProvider(self.settings)
        self.raw_words = [
            WordToken(start=0.0, end=0.5, text="Cześć"),
            WordToken(start=0.6, end=1.1, text="świecie"),
        ]

    def tearDown(self) -> None:
        self.env_patch.stop()
        self.temp_dir.cleanup()

    def test_run_alignment_uses_corrected_timestamps_from_aligner(self) -> None:
        corrected_words = [
            WordToken(start=0.02, end=0.48, text="Cześć"),
            WordToken(start=0.55, end=1.05, text="świecie"),
        ]
        fake_aligner = unittest.mock.Mock()
        fake_aligner.align.return_value = corrected_words

        with patch.object(self.provider, "_load_aligner", return_value=fake_aligner):
            result = self.provider._run_alignment(
                self.raw_words,
                Path("/tmp/input.wav"),
                "nagranie.wav",
            )

        self.assertEqual(result, corrected_words)
        fake_aligner.align.assert_called_once_with(
            self.raw_words, Path("/tmp/input.wav"), "nagranie.wav"
        )

    def test_run_alignment_exception_does_not_interrupt_transcription(self) -> None:
        fake_aligner = unittest.mock.Mock()
        fake_aligner.align.side_effect = RuntimeError("aligner exploded")

        with patch.object(self.provider, "_load_aligner", return_value=fake_aligner):
            with self.assertRaises(RuntimeError):
                self.provider._run_alignment(
                    self.raw_words,
                    Path("/tmp/input.wav"),
                    "nagranie.wav",
                )

    def test_run_alignment_missing_dependency_falls_back_to_raw_words(self) -> None:
        real_aligner = ForcedAligner(device="cpu", language="pl")

        with patch.object(
            real_aligner,
            "_align_with_whisperx",
            side_effect=ImportError("No module named 'whisperx'"),
        ):
            with patch.object(self.provider, "_load_aligner", return_value=real_aligner):
                result = self.provider._run_alignment(
                    self.raw_words,
                    Path("/tmp/input.wav"),
                    "nagranie.wav",
                )

        self.assertEqual(result, self.raw_words)

    def test_run_alignment_returns_raw_words_when_setting_is_disabled(self) -> None:
        self.settings.alignment_enabled = False
        fake_aligner = unittest.mock.Mock()

        with patch.object(self.provider, "_load_aligner", return_value=fake_aligner):
            result = self.provider._run_alignment(
                self.raw_words,
                Path("/tmp/input.wav"),
                "nagranie.wav",
            )

        self.assertEqual(result, self.raw_words)
        fake_aligner.align.assert_not_called()


if __name__ == "__main__":
    unittest.main()
