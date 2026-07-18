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
            filter_preset="full",
        )

        self.assertIn("-af", command)
        filter_index = command.index("-af") + 1
        self.assertEqual(command[filter_index], self.provider.PREPARE_AUDIO_FILTER)
        self.assertEqual(
            command[-7:],
            ["-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "/tmp/output.wav"],
        )
        self.assertEqual(command[-1], "/tmp/output.wav")

    def test_build_prepare_audio_command_light_preset_uses_short_filter_chain(self) -> None:
        command = self.provider._build_prepare_audio_command(
            "/usr/bin/ffmpeg",
            Path("/tmp/input.wav"),
            Path("/tmp/output.wav"),
            filter_preset="light",
        )

        self.assertIn("-af", command)
        filter_index = command.index("-af") + 1
        self.assertEqual(command[filter_index], "highpass=f=90,lowpass=f=7600")
        self.assertEqual(command[filter_index], self.provider.PREPARE_AUDIO_FILTER_LIGHT)

    def test_build_prepare_audio_command_can_disable_filters(self) -> None:
        command = self.provider._build_prepare_audio_command(
            "/usr/bin/ffmpeg",
            Path("/tmp/input.wav"),
            Path("/tmp/output.wav"),
            filter_preset="none",
        )

        self.assertNotIn("-af", command)
        self.assertEqual(command[-1], "/tmp/output.wav")

    def test_build_prepare_audio_command_unknown_preset_falls_back_to_full(self) -> None:
        command = self.provider._build_prepare_audio_command(
            "/usr/bin/ffmpeg",
            Path("/tmp/input.wav"),
            Path("/tmp/output.wav"),
            filter_preset="bogus",
        )

        self.assertIn("-af", command)
        filter_index = command.index("-af") + 1
        self.assertEqual(command[filter_index], self.provider.PREPARE_AUDIO_FILTER)

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

    def test_prepare_audio_source_uses_none_preset_without_af_flag(self) -> None:
        self.settings.prepare_filter_preset = "none"
        commands: list[list[str]] = []

        def fake_run(command: list[str], check: bool, capture_output: bool, text: bool):
            del check, capture_output, text
            commands.append(command)
            Path(command[-1]).write_bytes(b"RIFF")
            return subprocess.CompletedProcess(command, 0)

        with (
            patch("echo_app.transcription.shutil.which", return_value="/usr/bin/ffmpeg"),
            patch("echo_app.transcription.subprocess.run", side_effect=fake_run),
        ):
            with self.provider._prepare_audio_source(Path("/tmp/input.wav")) as audio_path:
                self.assertTrue(audio_path.exists())

        self.assertEqual(len(commands), 1)
        self.assertNotIn("-af", commands[0])

    def test_prepare_audio_source_uses_light_preset_filter_chain(self) -> None:
        self.settings.prepare_filter_preset = "light"
        commands: list[list[str]] = []

        def fake_run(command: list[str], check: bool, capture_output: bool, text: bool):
            del check, capture_output, text
            commands.append(command)
            Path(command[-1]).write_bytes(b"RIFF")
            return subprocess.CompletedProcess(command, 0)

        with (
            patch("echo_app.transcription.shutil.which", return_value="/usr/bin/ffmpeg"),
            patch("echo_app.transcription.subprocess.run", side_effect=fake_run),
        ):
            with self.provider._prepare_audio_source(Path("/tmp/input.wav")) as audio_path:
                self.assertTrue(audio_path.exists())

        self.assertEqual(len(commands), 1)
        self.assertIn("-af", commands[0])
        filter_index = commands[0].index("-af") + 1
        self.assertEqual(commands[0][filter_index], self.provider.PREPARE_AUDIO_FILTER_LIGHT)


class PrepareFilterPresetSettingsTests(unittest.TestCase):
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

    def tearDown(self) -> None:
        self.env_patch.stop()
        self.temp_dir.cleanup()

    def test_default_prepare_filter_preset_is_full(self) -> None:
        settings = AppSettings()
        self.assertEqual(settings.prepare_filter_preset, "full")

    def test_prepare_filter_preset_reads_env_variable(self) -> None:
        with patch.dict(os.environ, {"ECHO_PREPARE_FILTER_PRESET": "light"}, clear=False):
            settings = AppSettings()
        self.assertEqual(settings.prepare_filter_preset, "light")

    def test_prepare_filter_preset_normalizes_case(self) -> None:
        with patch.dict(os.environ, {"ECHO_PREPARE_FILTER_PRESET": "NONE"}, clear=False):
            settings = AppSettings()
        self.assertEqual(settings.prepare_filter_preset, "none")

    def test_prepare_filter_preset_falls_back_to_full_for_invalid_value(self) -> None:
        with patch.dict(os.environ, {"ECHO_PREPARE_FILTER_PRESET": "bogus"}, clear=False):
            settings = AppSettings()
        self.assertEqual(settings.prepare_filter_preset, "full")

    def test_prepare_filter_preset_falls_back_to_full_when_set_invalid_directly(self) -> None:
        settings = AppSettings()
        settings.prepare_filter_preset = "invalid"
        settings._normalize_runtime_settings()
        self.assertEqual(settings.prepare_filter_preset, "full")


class BuildTranscribeKwargsTests(unittest.TestCase):
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

    def tearDown(self) -> None:
        self.env_patch.stop()
        self.temp_dir.cleanup()

    def test_build_transcribe_kwargs_uses_safe_defaults(self) -> None:
        settings = AppSettings()
        provider = LocalTranscriptionProvider(settings)

        kwargs = provider._build_transcribe_kwargs()

        self.assertEqual(kwargs["beam_size"], 5)
        self.assertIs(kwargs["vad_filter"], True)
        self.assertIs(kwargs["word_timestamps"], True)
        self.assertIs(kwargs["condition_on_previous_text"], False)
        self.assertEqual(kwargs["language"], "pl")

    def test_build_transcribe_kwargs_uses_permissive_vad_threshold(self) -> None:
        # Domyslny prog VAD faster-whisper (0.5) lezy na granicy decyzyjnej dla cichej,
        # mamrotanej mowy z dyktafonu -> niedeterminizm kerneli CUDA (float16 i float32)
        # losowo przechyla decyzje "mowa"/"cisza" miedzy identycznymi przebiegami (patrz
        # docs/03_reports z 2026-07-18: 3x ten sam plik i ustawienia -> 2-23 segmentow).
        # Nizszy prog przesuwa decyzje z granicy: eliminuje niedeterminizm i wykrywa
        # realna mowe, ktora domyslny prog gubil.
        settings = AppSettings()
        provider = LocalTranscriptionProvider(settings)

        kwargs = provider._build_transcribe_kwargs()

        self.assertIn("vad_parameters", kwargs)
        vad_parameters = kwargs["vad_parameters"]
        self.assertEqual(vad_parameters["threshold"], 0.2)
        self.assertEqual(vad_parameters["min_silence_duration_ms"], 1000)
        self.assertEqual(vad_parameters["speech_pad_ms"], 600)

    def test_build_transcribe_kwargs_omits_language_when_no_hint(self) -> None:
        settings = AppSettings()
        settings.language_hint = None
        provider = LocalTranscriptionProvider(settings)

        kwargs = provider._build_transcribe_kwargs()

        self.assertNotIn("language", kwargs)


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
