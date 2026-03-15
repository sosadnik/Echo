from __future__ import annotations

import asyncio
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import wave

from echo_app.app import create_app


class RecordingAudioEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(
            os.environ,
            {
                "ECHO_TRANSCRIPTION_PROVIDER": "mock",
                "XDG_DATA_HOME": self.temp_dir.name,
            },
            clear=False,
        )
        self.env_patch.start()
        self.app = create_app()

    def tearDown(self) -> None:
        self.env_patch.stop()
        self.temp_dir.cleanup()

    def _get_endpoint(self, path: str):
        for route in self.app.routes:
            if getattr(route, "path", "") == path:
                return route.endpoint
        raise AssertionError(f"Endpoint not found: {path}")

    def _write_wav(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(b"\x00\x00" * 160)

    def test_media_endpoint_serves_wav_inline(self) -> None:
        stored_path = self.app.state.settings.recordings_dir / "imported.wav"
        self._write_wav(stored_path)
        recording = self.app.state.repository.create_recording(
            original_name="spotkanie.wav",
            stored_path=stored_path,
        )

        response = asyncio.run(self._get_endpoint("/api/recordings/{recording_id}/media")(recording["id"]))

        self.assertEqual(response.headers["content-type"], "audio/wav")
        self.assertIn("inline;", response.headers["content-disposition"])
        self.assertIn('filename="spotkanie.wav"', response.headers["content-disposition"])

    def test_media_endpoint_uses_original_extension_for_audio_type(self) -> None:
        stored_path = self.app.state.settings.recordings_dir / "imported.bin"
        stored_path.parent.mkdir(parents=True, exist_ok=True)
        stored_path.write_bytes(b"not-a-real-m4a")
        recording = self.app.state.repository.create_recording(
            original_name="dyktafon.m4a",
            stored_path=stored_path,
        )

        response = asyncio.run(self._get_endpoint("/api/recordings/{recording_id}/media")(recording["id"]))

        self.assertEqual(response.headers["content-type"], "audio/mp4")

    def test_playback_endpoint_generates_pcm_wav_for_wav_input(self) -> None:
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path is None:
            self.skipTest("ffmpeg is required for playback conversion test")

        source_pcm_path = self.app.state.settings.recordings_dir / "source_pcm.wav"
        stored_path = self.app.state.settings.recordings_dir / "compressed.wav"
        self._write_wav(source_pcm_path)
        subprocess.run(
            [
                ffmpeg_path,
                "-v",
                "error",
                "-y",
                "-i",
                str(source_pcm_path),
                "-c:a",
                "adpcm_ima_wav",
                str(stored_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        recording = self.app.state.repository.create_recording(
            original_name="dyktafon.wav",
            stored_path=stored_path,
        )

        response = asyncio.run(self._get_endpoint("/api/recordings/{recording_id}/playback")(recording["id"]))

        playback_path = self.app.state.settings.playback_dir / f"{recording['id']}.wav"
        self.assertEqual(Path(response.path), playback_path)
        self.assertNotEqual(Path(response.path), stored_path)
        self.assertEqual(response.headers["content-type"], "audio/wav")
        with wave.open(str(playback_path), "rb") as wav_file:
            self.assertEqual(wav_file.getcomptype(), "NONE")
            self.assertEqual(wav_file.getframerate(), 16000)
            self.assertEqual(wav_file.getnchannels(), 1)

    def test_playback_endpoint_uses_original_file_for_mp3_input(self) -> None:
        stored_path = self.app.state.settings.recordings_dir / "voice.mp3"
        stored_path.parent.mkdir(parents=True, exist_ok=True)
        stored_path.write_bytes(b"fake-mp3")
        recording = self.app.state.repository.create_recording(
            original_name="voice.mp3",
            stored_path=stored_path,
        )

        response = asyncio.run(self._get_endpoint("/api/recordings/{recording_id}/playback")(recording["id"]))

        self.assertEqual(Path(response.path), stored_path)
        self.assertEqual(response.headers["content-type"], "audio/mpeg")


if __name__ == "__main__":
    unittest.main()
