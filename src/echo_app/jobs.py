from __future__ import annotations

import asyncio
import time
from pathlib import Path

from .repository import EchoRepository
from .transcription import TranscriptionProgress, TranscriptionProvider


class JobProgressReporter:
    def __init__(self, repository: EchoRepository, job_id: str) -> None:
        self.repository = repository
        self.job_id = job_id
        self.last_percent = 0
        self.last_stage: str | None = None
        self.last_message: str | None = None
        self._last_persisted_percent = -1
        self._last_persisted_at = 0.0

    def __call__(self, progress: TranscriptionProgress) -> None:
        self.report(progress.stage, progress.percent, progress.message)

    def report(self, stage: str, percent: int, message: str, *, force: bool = False) -> None:
        previous_stage = self.last_stage
        previous_message = self.last_message
        normalized_percent = max(self.last_percent, max(0, min(100, int(percent))))
        normalized_message = message.strip() or None

        self.last_percent = normalized_percent
        self.last_stage = stage
        self.last_message = normalized_message

        now = time.monotonic()
        should_persist = force
        should_persist = should_persist or stage != previous_stage
        should_persist = should_persist or normalized_message != previous_message
        should_persist = should_persist or normalized_percent in {0, 100}
        should_persist = should_persist or normalized_percent - self._last_persisted_percent >= 1
        should_persist = should_persist or now - self._last_persisted_at >= 0.75
        if not should_persist:
            return

        self.repository.update_job_progress(
            self.job_id,
            normalized_percent,
            progress_stage=stage,
            progress_message=normalized_message,
        )
        self._last_persisted_percent = normalized_percent
        self._last_persisted_at = now


class JobRunner:
    def __init__(self, repository: EchoRepository, provider: TranscriptionProvider) -> None:
        self.repository = repository
        self.provider = provider
        self._tasks: dict[str, asyncio.Task] = {}

    def has_active_tasks(self) -> bool:
        return any(not task.done() for task in self._tasks.values())

    async def submit(self, recording_id: str) -> dict:
        job = self.repository.create_job(recording_id, self.provider.name)
        task = asyncio.create_task(self._run_job(job["id"], recording_id))
        task.add_done_callback(lambda _: self._tasks.pop(job["id"], None))
        self._tasks[job["id"]] = task
        return job

    async def _run_job(self, job_id: str, recording_id: str) -> None:
        self.repository.set_recording_status(recording_id, "processing")
        progress = JobProgressReporter(self.repository, job_id)
        progress.report("starting", 1, "Uruchamianie joba.", force=True)
        self.repository.update_job_status(
            job_id,
            "running",
            progress_percent=progress.last_percent,
            progress_stage=progress.last_stage,
            progress_message=progress.last_message,
        )
        recording = self.repository.get_recording(recording_id)

        if not recording:
            self.repository.update_job_status(
                job_id,
                "failed",
                "Nie znaleziono nagrania.",
                progress_percent=progress.last_percent,
                progress_stage="failed",
                progress_message="Nie znaleziono nagrania.",
            )
            self.repository.set_recording_status(recording_id, "ready")
            return

        try:
            result = await self.provider.transcribe(Path(recording["stored_path"]), progress=progress)
            progress.report("finalizing", 99, "Zapisywanie wyniku joba.", force=True)
            self.repository.complete_job(
                job_id,
                transcript_text=result.text,
                segments=[segment.model_dump() for segment in result.segments],
            )
        except Exception as exc:
            self.repository.update_job_status(
                job_id,
                "failed",
                str(exc),
                progress_percent=progress.last_percent,
                progress_stage="failed",
                progress_message=str(exc),
            )
        finally:
            self.repository.set_recording_status(recording_id, "ready")
