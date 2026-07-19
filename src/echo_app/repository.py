from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
import threading
from typing import Iterator
from uuid import uuid4


SCHEMA = """
create table if not exists recordings (
    id text primary key,
    original_name text not null,
    stored_path text not null,
    status text not null,
    created_at text not null
);

create table if not exists jobs (
    id text primary key,
    recording_id text not null,
    provider text not null,
    status text not null,
    progress_percent integer not null default 0,
    progress_stage text,
    progress_message text,
    created_at text not null,
    updated_at text not null,
    error text,
    transcript_text text,
    result_json text,
    manifest_json text,
    warnings_json text,
    interrupted_at text,
    foreign key (recording_id) references recordings(id)
);

create index if not exists idx_jobs_recording_created_at
    on jobs(recording_id, created_at desc);
"""


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class EchoRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self._lock = threading.Lock()

    def initialize(self) -> None:
        with self.connection() as connection:
            connection.executescript(SCHEMA)
            self._migrate_jobs_table(connection)
            self._recover_interrupted_jobs(connection)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            connection = sqlite3.connect(self.database_path, check_same_thread=False)
            connection.row_factory = sqlite3.Row
            try:
                yield connection
                connection.commit()
            finally:
                connection.close()

    def list_recordings(self) -> list[dict]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                select id, original_name, stored_path, status, created_at
                from recordings
                order by created_at desc
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_recording(self, recording_id: str) -> dict | None:
        with self.connection() as connection:
            row = connection.execute(
                """
                select id, original_name, stored_path, status, created_at
                from recordings
                where id = ?
                """,
                (recording_id,),
            ).fetchone()
        return dict(row) if row else None

    def create_recording(self, original_name: str, stored_path: Path) -> dict:
        now = utc_now()
        payload = {
            "id": uuid4().hex,
            "original_name": original_name,
            "stored_path": str(stored_path),
            "status": "ready",
            "created_at": now,
        }
        with self.connection() as connection:
            connection.execute(
                """
                insert into recordings (id, original_name, stored_path, status, created_at)
                values (:id, :original_name, :stored_path, :status, :created_at)
                """,
                payload,
            )
        return payload

    def rename_recording(self, recording_id: str, original_name: str) -> dict | None:
        with self.connection() as connection:
            recording_row = connection.execute(
                """
                select id, original_name, stored_path, status, created_at
                from recordings
                where id = ?
                """,
                (recording_id,),
            ).fetchone()
            if not recording_row:
                return None

            connection.execute(
                "update recordings set original_name = ? where id = ?",
                (original_name, recording_id),
            )

        payload = dict(recording_row)
        payload["original_name"] = original_name
        return payload

    def set_recording_status(self, recording_id: str, status: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "update recordings set status = ? where id = ?",
                (status, recording_id),
            )

    def delete_recording(self, recording_id: str) -> dict | None:
        with self.connection() as connection:
            recording_row = connection.execute(
                """
                select id, original_name, stored_path, status, created_at
                from recordings
                where id = ?
                """,
                (recording_id,),
            ).fetchone()
            if not recording_row:
                return None

            jobs_deleted = connection.execute(
                "select count(*) from jobs where recording_id = ?",
                (recording_id,),
            ).fetchone()[0]
            connection.execute("delete from jobs where recording_id = ?", (recording_id,))
            connection.execute("delete from recordings where id = ?", (recording_id,))

        payload = dict(recording_row)
        payload["jobs_deleted"] = int(jobs_deleted)
        return payload

    def clear_recordings(self) -> dict:
        with self.connection() as connection:
            recording_rows = connection.execute(
                """
                select id, original_name, stored_path, status, created_at
                from recordings
                order by created_at desc
                """
            ).fetchall()
            jobs_deleted = connection.execute("select count(*) from jobs").fetchone()[0]
            recordings_deleted = len(recording_rows)
            connection.execute("delete from jobs")
            connection.execute("delete from recordings")

        return {
            "recordings": [dict(row) for row in recording_rows],
            "recordings_deleted": recordings_deleted,
            "jobs_deleted": int(jobs_deleted),
        }

    def list_jobs(self) -> list[dict]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                select id, recording_id, provider, status, progress_percent, progress_stage, progress_message,
                       created_at, updated_at, error,
                       transcript_text, result_json, manifest_json, warnings_json, interrupted_at
                from jobs
                order by created_at desc
                """
            ).fetchall()
        return [self._job_row_to_dict(row) for row in rows]

    def get_job(self, job_id: str) -> dict | None:
        with self.connection() as connection:
            row = connection.execute(
                """
                select id, recording_id, provider, status, progress_percent, progress_stage, progress_message,
                       created_at, updated_at, error,
                       transcript_text, result_json, manifest_json, warnings_json, interrupted_at
                from jobs
                where id = ?
                """,
                (job_id,),
            ).fetchone()
        return self._job_row_to_dict(row) if row else None

    def has_active_jobs(self) -> bool:
        with self.connection() as connection:
            row = connection.execute(
                "select 1 from jobs where status in ('queued', 'running') limit 1"
            ).fetchone()
        return row is not None

    def create_job(self, recording_id: str, provider: str) -> dict:
        now = utc_now()
        payload = {
            "id": uuid4().hex,
            "recording_id": recording_id,
            "provider": provider,
            "status": "queued",
            "progress_percent": 0,
            "progress_stage": "queued",
            "progress_message": "Job czeka w kolejce.",
            "created_at": now,
            "updated_at": now,
            "error": None,
            "transcript_text": None,
            "result_json": None,
            "manifest_json": None,
            "warnings_json": None,
            "interrupted_at": None,
        }
        with self.connection() as connection:
            self._insert_job(connection, payload)
        return self._job_payload_to_dict(payload)

    def create_or_get_active_job(self, recording_id: str, provider: str) -> dict:
        with self.connection() as connection:
            active = connection.execute(
                "select * from jobs where recording_id = ? and status in ('queued', 'running') order by created_at asc limit 1",
                (recording_id,),
            ).fetchone()
            if active:
                return self._job_row_to_dict(active)
            now = utc_now()
            payload = {
                "id": uuid4().hex, "recording_id": recording_id, "provider": provider,
                "status": "queued", "progress_percent": 0, "progress_stage": "queued",
                "progress_message": "Job czeka w kolejce.", "created_at": now, "updated_at": now,
                "error": None, "transcript_text": None, "result_json": None, "manifest_json": None,
                "warnings_json": None, "interrupted_at": None,
            }
            self._insert_job(connection, payload)
        return self._job_payload_to_dict(payload)

    def _insert_job(self, connection: sqlite3.Connection, payload: dict) -> None:
        connection.execute(
            """
            insert into jobs (
                id, recording_id, provider, status, progress_percent, progress_stage, progress_message,
                created_at, updated_at, error, transcript_text, result_json,
                manifest_json, warnings_json, interrupted_at
            ) values (
                :id, :recording_id, :provider, :status, :progress_percent, :progress_stage, :progress_message,
                :created_at, :updated_at, :error, :transcript_text, :result_json,
                :manifest_json, :warnings_json, :interrupted_at
            )
            """, payload
        )

    def claim_next_queued_job(self) -> dict | None:
        with self.connection() as connection:
            row = connection.execute(
                "select id from jobs where status = 'queued' order by created_at asc, id asc limit 1"
            ).fetchone()
            if not row:
                return None
            job_id = str(row["id"])
            connection.execute(
                "update jobs set status = 'running', updated_at = ?, progress_percent = 1, progress_stage = 'starting', progress_message = 'Uruchamianie joba.' where id = ? and status = 'queued'",
                (utc_now(), job_id),
            )
            claimed = connection.execute("select * from jobs where id = ?", (job_id,)).fetchone()
        return self._job_row_to_dict(claimed) if claimed else None

    def update_job_status(
        self,
        job_id: str,
        status: str,
        error: str | None = None,
        *,
        progress_percent: int | None = None,
        progress_stage: str | None = None,
        progress_message: str | None = None,
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                update jobs
                set status = ?,
                    updated_at = ?,
                    error = ?,
                    progress_percent = coalesce(?, progress_percent),
                    progress_stage = coalesce(?, progress_stage),
                    progress_message = coalesce(?, progress_message)
                where id = ?
                """,
                (
                    status,
                    utc_now(),
                    error,
                    self._normalize_progress_percent(progress_percent) if progress_percent is not None else None,
                    progress_stage,
                    progress_message,
                    job_id,
                ),
            )

    def update_job_progress(
        self,
        job_id: str,
        progress_percent: int,
        progress_stage: str | None = None,
        progress_message: str | None = None,
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                update jobs
                set updated_at = ?,
                    progress_percent = ?,
                    progress_stage = coalesce(?, progress_stage),
                    progress_message = coalesce(?, progress_message)
                where id = ?
                """,
                (
                    utc_now(),
                    self._normalize_progress_percent(progress_percent),
                    progress_stage,
                    progress_message,
                    job_id,
                ),
            )

    def complete_job(
        self,
        job_id: str,
        transcript_text: str,
        segments: list[dict],
        *,
        manifest: dict | None = None,
        warnings: list[dict] | None = None,
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                update jobs
                set status = ?,
                    progress_percent = ?,
                    progress_stage = ?,
                    progress_message = ?,
                    updated_at = ?,
                    error = ?,
                    transcript_text = ?,
                    result_json = ?,
                    manifest_json = ?,
                    warnings_json = ?
                where id = ?
                """,
                (
                    "completed",
                    100,
                    "completed",
                    "Transkrypcja zakończona.",
                    utc_now(),
                    None,
                    transcript_text,
                    json.dumps({"segments": segments}),
                    json.dumps(manifest, ensure_ascii=False) if manifest else None,
                    json.dumps(warnings or [], ensure_ascii=False),
                    job_id,
                ),
            )

    def _migrate_jobs_table(self, connection: sqlite3.Connection) -> None:
        existing_columns = {
            str(row["name"])
            for row in connection.execute("pragma table_info(jobs)").fetchall()
        }

        required_columns = {
            "progress_percent": "integer not null default 0",
            "progress_stage": "text",
            "progress_message": "text",
            "manifest_json": "text",
            "warnings_json": "text",
            "interrupted_at": "text",
        }
        for column_name, definition in required_columns.items():
            if column_name not in existing_columns:
                connection.execute(f"alter table jobs add column {column_name} {definition}")

        connection.execute(
            """
            update jobs
            set progress_percent = case
                when status = 'completed' then 100
                when status = 'running' and coalesce(progress_percent, 0) = 0 then 1
                else coalesce(progress_percent, 0)
            end
            """
        )
        connection.execute(
            """
            update jobs
            set progress_stage = coalesce(
                progress_stage,
                case
                    when status = 'completed' then 'completed'
                    when status = 'failed' then 'failed'
                    when status = 'running' then 'running'
                    when status = 'queued' then 'queued'
                    else null
                end
            )
            """
        )
        connection.execute(
            """
            update jobs
            set progress_message = coalesce(
                progress_message,
                case
                    when status = 'completed' then 'Transkrypcja zakończona.'
                    when status = 'failed' then coalesce(error, 'Job zakończył się błędem.')
                    when status = 'running' then 'Job jest w toku.'
                    when status = 'queued' then 'Job czeka w kolejce.'
                    else null
                end
            )
            """
        )

    def _recover_interrupted_jobs(self, connection: sqlite3.Connection) -> None:
        now = utc_now()
        interrupted = connection.execute(
            "select recording_id from jobs where status = 'running'"
        ).fetchall()
        if not interrupted:
            return
        connection.execute(
            "update jobs set status = 'interrupted', updated_at = ?, interrupted_at = ?, error = 'Job przerwany przez restart serwera.', progress_stage = 'interrupted', progress_message = 'Job przerwany przez restart serwera.' where status = 'running'",
            (now, now),
        )
        connection.executemany(
            "update recordings set status = 'ready' where id = ?",
            [(str(row["recording_id"]),) for row in interrupted],
        )

    def _job_row_to_dict(self, row: sqlite3.Row) -> dict:
        payload = dict(row)
        return self._job_payload_to_dict(payload)

    def _job_payload_to_dict(self, payload: dict) -> dict:
        raw_result = payload.pop("result_json", None)
        raw_manifest = payload.pop("manifest_json", None)
        raw_warnings = payload.pop("warnings_json", None)
        segments: list[dict] = []
        if raw_result:
            try:
                parsed = json.loads(raw_result)
                segments = parsed.get("segments", [])
            except json.JSONDecodeError:
                segments = []
        payload["segments"] = segments
        payload["manifest"] = self._parse_json_object(raw_manifest)
        payload["warnings"] = self._parse_json_list(raw_warnings)
        payload["progress_percent"] = self._normalize_progress_percent(payload.get("progress_percent"))
        payload["progress_stage"] = payload.get("progress_stage")
        payload["progress_message"] = payload.get("progress_message")
        return payload

    def _parse_json_object(self, raw_value: object) -> dict | None:
        if not raw_value:
            return None
        try:
            parsed = json.loads(str(raw_value))
        except (TypeError, json.JSONDecodeError):
            return None
        return parsed if isinstance(parsed, dict) else None

    def _parse_json_list(self, raw_value: object) -> list[dict]:
        if not raw_value:
            return []
        try:
            parsed = json.loads(str(raw_value))
        except (TypeError, json.JSONDecodeError):
            return []
        return parsed if isinstance(parsed, list) else []

    def _normalize_progress_percent(self, value: object) -> int:
        try:
            return max(0, min(100, int(value or 0)))
        except (TypeError, ValueError):
            return 0
