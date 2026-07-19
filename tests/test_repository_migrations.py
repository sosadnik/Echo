from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from echo_app.repository import EchoRepository


class RepositoryMigrationTests(unittest.TestCase):
    def test_fresh_database_has_provenance_warning_and_recovery_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "echo.db"
            repository = EchoRepository(database_path)

            repository.initialize()
            repository.initialize()

            with sqlite3.connect(database_path) as connection:
                columns = {row[1] for row in connection.execute("pragma table_info(jobs)")}

        self.assertTrue(
            {
                "progress_percent",
                "progress_stage",
                "progress_message",
                "manifest_json",
                "warnings_json",
                "interrupted_at",
            }.issubset(columns)
        )

    def test_old_schema_migrates_without_losing_transcript_or_segments(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "echo.db"
            with sqlite3.connect(database_path) as connection:
                connection.executescript(
                    """
                    create table recordings (
                        id text primary key,
                        original_name text not null,
                        stored_path text not null,
                        status text not null,
                        created_at text not null
                    );
                    create table jobs (
                        id text primary key,
                        recording_id text not null,
                        provider text not null,
                        status text not null,
                        created_at text not null,
                        updated_at text not null,
                        error text,
                        transcript_text text,
                        result_json text
                    );
                    """
                )
                connection.execute(
                    "insert into recordings values (?, ?, ?, ?, ?)",
                    ("recording-1", "sample.wav", "/tmp/sample.wav", "ready", "2026-07-18T00:00:00+00:00"),
                )
                connection.execute(
                    "insert into jobs values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        "job-1",
                        "recording-1",
                        "local",
                        "completed",
                        "2026-07-18T00:00:00+00:00",
                        "2026-07-18T00:01:00+00:00",
                        None,
                        "Cześć świecie",
                        json.dumps(
                            {
                                "segments": [
                                    {
                                        "speaker": "Speaker 1",
                                        "start": 0,
                                        "end": 1,
                                        "text": "Cześć świecie",
                                    }
                                ]
                            }
                        ),
                    ),
                )

            repository = EchoRepository(database_path)
            repository.initialize()
            job = repository.get_job("job-1")

        self.assertIsNotNone(job)
        assert job is not None
        self.assertEqual(job["transcript_text"], "Cześć świecie")
        self.assertEqual(job["segments"][0]["text"], "Cześć świecie")
        self.assertIsNone(job["manifest"])
        self.assertEqual(job["warnings"], [])
        self.assertEqual(job["progress_percent"], 100)

    def test_initialize_interrupts_orphaned_running_job_and_restores_recording(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = EchoRepository(Path(temp_dir) / "echo.db")
            repository.initialize()
            recording = repository.create_recording("sample.wav", Path("/tmp/sample.wav"))
            job = repository.create_job(recording["id"], "mock")
            repository.update_job_status(job["id"], "running")
            repository.set_recording_status(recording["id"], "processing")

            repository.initialize()
            recovered = repository.get_job(job["id"])
            restored_recording = repository.get_recording(recording["id"])

        assert recovered is not None
        assert restored_recording is not None
        self.assertEqual(recovered["status"], "interrupted")
        self.assertEqual(recovered["progress_stage"], "interrupted")
        self.assertEqual(restored_recording["status"], "ready")

    def test_active_job_is_deduplicated_and_queued_jobs_are_claimed_fifo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = EchoRepository(Path(temp_dir) / "echo.db")
            repository.initialize()
            first_recording = repository.create_recording("first.wav", Path("/tmp/first.wav"))
            second_recording = repository.create_recording("second.wav", Path("/tmp/second.wav"))
            first = repository.create_or_get_active_job(first_recording["id"], "mock")
            duplicate = repository.create_or_get_active_job(first_recording["id"], "mock")
            second = repository.create_or_get_active_job(second_recording["id"], "mock")

            claimed_first = repository.claim_next_queued_job()
            claimed_second = repository.claim_next_queued_job()

        self.assertEqual(first["id"], duplicate["id"])
        assert claimed_first is not None
        assert claimed_second is not None
        self.assertEqual(claimed_first["id"], first["id"])
        self.assertEqual(claimed_second["id"], second["id"])

    def test_completed_job_persists_manifest_and_sanitized_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = EchoRepository(Path(temp_dir) / "echo.db")
            repository.initialize()
            recording = repository.create_recording("sample.wav", Path("/tmp/sample.wav"))
            job = repository.create_job(recording["id"], "local")
            repository.complete_job(
                job["id"],
                "tekst",
                [],
                manifest={"artifact_version": "benchmark-artifact/v1", "backend": "local"},
                warnings=[{"code": "degraded", "message": "bez tokenu"}],
            )
            stored = repository.get_job(job["id"])

        assert stored is not None
        self.assertEqual(stored["manifest"]["backend"], "local")
        self.assertEqual(stored["warnings"][0]["code"], "degraded")


if __name__ == "__main__":
    unittest.main()
