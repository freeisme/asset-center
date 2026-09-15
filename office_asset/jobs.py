from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from datetime import datetime

from .sql import SqlGateway


def job_run_key(job_name: str, when: datetime | None = None) -> str:
    instant = when or datetime.now()
    value = f"{job_name}:{instant.strftime('%Y-%m-%d:%H:%M:%S:%f')}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def start_job_execution(db: SqlGateway, job_name: str, run_key: str) -> None:
    db.execute(
        f"""
        INSERT INTO job_execution (job_name, run_key, status)
        VALUES ({db.quote(job_name)}, {db.quote(run_key)}, 'running')
        ON DUPLICATE KEY UPDATE
          status = 'running',
          started_at = CURRENT_TIMESTAMP,
          completed_at = NULL,
          error_message = '';
        """
    )


def finish_job_execution(
    db: SqlGateway,
    job_name: str,
    run_key: str,
    succeeded: bool,
    details: dict | None = None,
    error_message: str = "",
) -> None:
    status = "completed" if succeeded else "failed"
    db.execute(
        f"""
        UPDATE job_execution
        SET status = {db.quote(status)},
            completed_at = CURRENT_TIMESTAMP,
            details = {db.json_value(details or {})},
            error_message = {db.quote(error_message[:1000])}
        WHERE job_name = {db.quote(job_name)}
          AND run_key = {db.quote(run_key)};
        """
    )


def run_periodic_job(
    *,
    poll_seconds: int,
    retry_seconds: int,
    is_due: Callable[[datetime], bool],
    execute: Callable[[datetime], None],
    report_error: Callable[[Exception], None],
) -> None:
    next_retry_at = 0.0
    while True:
        try:
            current_time = datetime.now()
            if is_due(current_time) and time.monotonic() >= next_retry_at:
                try:
                    execute(current_time)
                    next_retry_at = 0.0
                except Exception as exc:
                    next_retry_at = time.monotonic() + retry_seconds
                    report_error(exc)
        except Exception as exc:  # pragma: no cover - background jobs must keep serving
            report_error(exc)
        time.sleep(poll_seconds)
