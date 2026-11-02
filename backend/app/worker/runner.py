"""Run long jobs (repository analysis) outside the HTTP request.

Jobs run in a small thread pool inside the API process. Their state is stored in the
database, so a restart loses nothing except jobs that were mid-run (those are marked
failed on startup, see services/repositories.mark_interrupted). If load grows, this
can be swapped for a real queue (Redis + a worker process) behind the same `submit`.
"""

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class JobRunner:
    def __init__(self, workers: int):
        self._executor: ThreadPoolExecutor | None = None
        self._workers = workers

    def submit(self, job: Callable[..., None], *args: Any) -> None:
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=self._workers, thread_name_prefix="analysis"
            )
        self._executor.submit(self._run, job, *args)

    @staticmethod
    def _run(job: Callable[..., None], *args: Any) -> None:
        try:
            job(*args)
        except Exception:
            # Jobs record their own failures; this is the last line of defence so a
            # bug can never kill the worker thread silently.
            logger.exception("Background job crashed")

    def shutdown(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None


@lru_cache
def get_job_runner() -> JobRunner:
    """FastAPI dependency. Tests override it with a runner that executes inline."""
    return JobRunner(workers=get_settings().analysis_workers)
