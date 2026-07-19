from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile
import unittest

from echo_app.jobs import JobRunner
from echo_app.repository import EchoRepository
from echo_app.schemas import TranscriptResult


class BlockingProvider:
    name = "test"

    def __init__(self) -> None:
        self.started: list[str] = []
        self.release = asyncio.Event()

    async def transcribe(self, recording_path: Path, progress=None) -> TranscriptResult:
        del progress
        self.started.append(recording_path.name)
        await self.release.wait()
        return TranscriptResult(provider=self.name, text=recording_path.stem)


class NeverCompletesProvider:
    name = "test"

    async def transcribe(self, recording_path: Path, progress=None) -> TranscriptResult:
        del recording_path, progress
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


class JobRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_submissions_run_fifo_and_deduplicate_recording(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = EchoRepository(Path(temp_dir) / "echo.db")
            repository.initialize()
            first_recording = repository.create_recording("first.wav", Path("/tmp/first.wav"))
            second_recording = repository.create_recording("second.wav", Path("/tmp/second.wav"))
            provider = BlockingProvider()
            runner = JobRunner(repository, provider)

            first, second, duplicate = await asyncio.gather(
                runner.submit(first_recording["id"]),
                runner.submit(second_recording["id"]),
                runner.submit(first_recording["id"]),
            )
            self.assertEqual(duplicate["id"], first["id"])
            await self._wait_until(lambda: provider.started == ["first.wav"])

            queued = repository.get_job(second["id"])
            assert queued is not None
            self.assertEqual(queued["status"], "queued")
            provider.release.set()
            await self._wait_until(lambda: repository.get_job(first["id"])["status"] == "completed")
            await self._wait_until(lambda: repository.get_job(second["id"])["status"] == "completed")
            self.assertEqual(provider.started, ["first.wav", "second.wav"])
            await runner.stop()

    async def test_timeout_marks_job_failed_and_releases_recording(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = EchoRepository(Path(temp_dir) / "echo.db")
            repository.initialize()
            recording = repository.create_recording("slow.wav", Path("/tmp/slow.wav"))
            runner = JobRunner(repository, NeverCompletesProvider(), job_timeout_seconds=0.01)

            job = await runner.submit(recording["id"])
            await self._wait_until(lambda: repository.get_job(job["id"])["status"] == "failed")

            stored_job = repository.get_job(job["id"])
            restored_recording = repository.get_recording(recording["id"])
            assert stored_job is not None
            assert restored_recording is not None
            self.assertEqual(stored_job["progress_stage"], "timeout")
            self.assertEqual(restored_recording["status"], "ready")
            await runner.stop()

    async def test_stop_interrupts_running_job_and_releases_recording(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = EchoRepository(Path(temp_dir) / "echo.db")
            repository.initialize()
            recording = repository.create_recording("blocked.wav", Path("/tmp/blocked.wav"))
            provider = BlockingProvider()
            runner = JobRunner(repository, provider)

            job = await runner.submit(recording["id"])
            await self._wait_until(lambda: provider.started == ["blocked.wav"])
            await runner.stop()

            stored_job = repository.get_job(job["id"])
            restored_recording = repository.get_recording(recording["id"])
            assert stored_job is not None
            assert restored_recording is not None
            self.assertEqual(stored_job["status"], "interrupted")
            self.assertEqual(restored_recording["status"], "ready")

    async def _wait_until(self, predicate) -> None:
        for _ in range(100):
            if predicate():
                return
            await asyncio.sleep(0.01)
        self.fail("Warunek asynchroniczny nie został spełniony.")


if __name__ == "__main__":
    unittest.main()
