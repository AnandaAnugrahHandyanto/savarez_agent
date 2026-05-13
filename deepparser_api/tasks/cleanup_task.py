from __future__ import annotations

import asyncio
import logging

from .. import db

logger = logging.getLogger(__name__)

_COMPLETED_STATUSES = ("READY", "PARSE_FAILED", "TIMEOUT")


async def cleanup_expired_jobs() -> None:
    """Delete expired jobs.

    Completed jobs (READY / PARSE_FAILED / TIMEOUT): delete when completed_at > 24h ago.
    Orphaned in-flight jobs (QUEUED / PARSING with no completion): delete when
    created_at > 48h ago — gives long-running parses and queue backlogs a wide window
    before assuming the task is orphaned from a prior server restart.
    """
    async with db.connect() as conn:
        # Completed jobs: expire based on when they finished.
        cursor = await conn.execute(
            """
            DELETE FROM parse_jobs
            WHERE status IN ({}) AND completed_at < datetime('now', '-24 hours')
            """.format(",".join("?" * len(_COMPLETED_STATUSES))),
            _COMPLETED_STATUSES,
        )
        deleted_completed = cursor.rowcount

        # Orphaned in-flight jobs: must be very old (48h) to avoid racing active tasks.
        cursor = await conn.execute(
            """
            DELETE FROM parse_jobs
            WHERE status IN ('QUEUED', 'PARSING') AND created_at < datetime('now', '-48 hours')
            """,
        )
        deleted_orphaned = cursor.rowcount

        await conn.commit()

    deleted = deleted_completed + deleted_orphaned
    if deleted:
        logger.info(
            "cleanup deleted %d expired jobs (%d completed, %d orphaned)",
            deleted, deleted_completed, deleted_orphaned,
        )


async def run_cleanup_loop() -> None:
    """Run cleanup every hour forever. Survives individual DB errors."""
    while True:
        await asyncio.sleep(3600)
        try:
            await cleanup_expired_jobs()
        except Exception:
            logger.exception("cleanup loop error (non-fatal)")
