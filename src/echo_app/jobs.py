from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from .repository import EchoRepository
from .transcription import TranscriptionProgress, TranscriptionProvider

LOGGER = logging.getLogger("echo.jobs")


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
    def __init__(
        self,
        repository: EchoRepository,
        provider: TranscriptionProvider,
        *,
        job_timeout_seconds: float = 6 * 60 * 60,
    ) -> None:
        self.repository = repository
        self.provider = provider
        self.job_timeout_seconds = max(0.1, float(job_timeout_seconds))
        self._worker_task: asyncio.Task | None = None
        self._wake_event = asyncio.Event()
        self._current_job: tuple[str, str] | None = None

    def has_active_tasks(self) -> bool:
        return self._current_job is not None or self.repository.has_active_jobs()

    async def submit(self, recording_id: str) -> dict:
        job = self.repository.create_or_get_active_job(recording_id, self.provider.name)
        self.start()
        self._wake_event.set()
        return job

    def start(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        if self._worker_task is None:
            return
        self._worker_task.cancel()
        try:
            await self._worker_task
        except asyncio.CancelledError:
            pass
        self._worker_task = None

    async def _worker_loop(self) -> None:
        while True:
            job = self.repository.claim_next_queued_job()
            if job is None:
                self._wake_event.clear()
                await self._wake_event.wait()
                continue
            self._current_job = (job["id"], job["recording_id"])
            try:
                await self._run_job(job["id"], job["recording_id"])
            except asyncio.CancelledError:
                self.repository.update_job_status(
                    job["id"], "interrupted", "Job przerwany podczas zatrzymania serwera.",
                    progress_stage="interrupted", progress_message="Job przerwany podczas zatrzymania serwera.",
                )
                raise
            finally:
                self._current_job = None

    async def _run_job(self, job_id: str, recording_id: str) -> None:
        self.repository.set_recording_status(recording_id, "processing")
        progress = JobProgressReporter(self.repository, job_id)
        progress.report("starting", 1, "Uruchamianie joba.", force=True)
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
            result = await asyncio.wait_for(
                self.provider.transcribe(Path(recording["stored_path"]), progress=progress),
                timeout=self.job_timeout_seconds,
            )
            progress.report("finalizing", 99, "Zapisywanie wyniku joba.", force=True)
            self.repository.complete_job(
                job_id,
                transcript_text=result.text,
                segments=[segment.model_dump() for segment in result.segments],
                manifest=result.manifest.model_dump() if result.manifest else None,
                warnings=[warning.model_dump() for warning in (result.manifest.warnings if result.manifest else [])],
            )
        except TimeoutError:
            message = f"Job przekroczył limit czasu {self.job_timeout_seconds:.0f} s."
            LOGGER.error("Job %s timed out", job_id)
            self.repository.update_job_status(
                job_id, "failed", message, progress_percent=progress.last_percent,
                progress_stage="timeout", progress_message=message,
            )
        except Exception as exc:
            LOGGER.exception("Job %s failed during transcription", job_id)
            message = "Transkrypcja nie powiodła się. Sprawdź logi serwera."
            self.repository.update_job_status(
                job_id,
                "failed",
                message,
                progress_percent=progress.last_percent,
                progress_stage="failed",
                progress_message=message,
            )
        finally:
            self.repository.set_recording_status(recording_id, "ready")
