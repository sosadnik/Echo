from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from echo_app.config import AppSettings
from echo_app.transcription import LocalTranscriptionProvider, is_punctuation_only


class PrepareAudioCommandTests(unittest.TestCase):
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
        self.settings = AppSettings()
        self.provider = LocalTranscriptionProvider(self.settings)

    def tearDown(self) -> None:
        self.env_patch.stop()
        self.temp_dir.cleanup()

    def test_build_prepare_audio_command_uses_cleanup_filters(self) -> None:
        command = self.provider._build_prepare_audio_command(
            "/usr/bin/ffmpeg",
            Path("/tmp/input.wav"),
            Path("/tmp/output.wav"),
            use_filters=True,
        )

        self.assertIn("-af", command)
        filter_index = command.index("-af") + 1
        self.assertEqual(command[filter_index], self.provider.PREPARE_AUDIO_FILTER)
        self.assertEqual(
            command[-7:],
            ["-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "/tmp/output.wav"],
        )
        self.assertEqual(command[-1], "/tmp/output.wav")

    def test_build_prepare_audio_command_can_disable_filters(self) -> None:
        command = self.provider._build_prepare_audio_command(
            "/usr/bin/ffmpeg",
            Path("/tmp/input.wav"),
            Path("/tmp/output.wav"),
            use_filters=False,
        )

        self.assertNotIn("-af", command)
        self.assertEqual(command[-1], "/tmp/output.wav")

    def test_prepare_audio_source_falls_back_to_basic_conversion_for_filter_errors(self) -> None:
        commands: list[list[str]] = []

        def fake_run(command: list[str], check: bool, capture_output: bool, text: bool):
            del check, capture_output, text
            commands.append(command)
            if len(commands) == 1:
                raise subprocess.CalledProcessError(
                    1,
                    command,
                    stderr="No such filter: 'speechnorm'",
                )
            Path(command[-1]).write_bytes(b"RIFF")
            return subprocess.CompletedProcess(command, 0)

        with (
            patch("echo_app.transcription.shutil.which", return_value="/usr/bin/ffmpeg"),
            patch("echo_app.transcription.subprocess.run", side_effect=fake_run),
        ):
            with self.provider._prepare_audio_source(Path("/tmp/input.wav")) as audio_path:
                self.assertTrue(audio_path.exists())

        self.assertEqual(len(commands), 2)
        self.assertIn("-af", commands[0])
        self.assertNotIn("-af", commands[1])


class TranscriptParsingHelpersTests(unittest.TestCase):
    def test_is_punctuation_only_detects_placeholder_tokens(self) -> None:
        self.assertTrue(is_punctuation_only("."))
        self.assertTrue(is_punctuation_only("..."))
        self.assertTrue(is_punctuation_only("?!"))
        self.assertFalse(is_punctuation_only("tak"))
        self.assertFalse(is_punctuation_only("3"))
        self.assertFalse(is_punctuation_only("a."))


if __name__ == "__main__":
    unittest.main()
