"""
APScheduler-based task scheduler for the Tourism Agent pipeline.
Runs the full pipeline 3 × / day and handles analytics, cleanup, etc.
"""

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from utils.logger import logger
from config import SCHEDULE


class AgentScheduler:
    """Wraps APScheduler with convenience helpers for the pipeline."""

    def __init__(self) -> None:
        self.tz = ZoneInfo(SCHEDULE["timezone"])
        self.scheduler = AsyncIOScheduler(timezone=self.tz)
        self._jobs: dict[str, object] = {}

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background scheduler (non-blocking)."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")

    def shutdown(self) -> None:
        """Gracefully stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")

    # ── Registration helpers ───────────────────────────────────────────────────

    def schedule_pipeline(self, pipeline_fn: callable) -> None:
        """
        Register the full pipeline to run at each time in config SCHEDULE.

        Args:
            pipeline_fn: Async callable that runs the full pipeline.
        """
        for time_str in SCHEDULE["post_times"]:
            hour, minute = map(int, time_str.split(":"))
            job_id = f"pipeline_{time_str}"
            self.scheduler.add_job(
                pipeline_fn,
                CronTrigger(hour=hour, minute=minute, timezone=self.tz),
                id=job_id,
                replace_existing=True,
                misfire_grace_time=300,  # 5 min grace
            )
            logger.info(f"Pipeline scheduled at {time_str} ({SCHEDULE['timezone']})")

    def schedule_trend_discovery(self, trend_fn: callable) -> None:
        """Run trend discovery every morning at 07:00."""
        self.scheduler.add_job(
            trend_fn,
            CronTrigger(hour=7, minute=0, timezone=self.tz),
            id="trend_discovery",
            replace_existing=True,
        )
        logger.info("Trend discovery scheduled at 07:00 daily")

    def schedule_analytics(self, analytics_fn: callable, post_ids: dict) -> None:
        """Check analytics 24 hours after publishing."""
        run_at = datetime.now(tz=self.tz) + timedelta(hours=24)
        job_id = f"analytics_{run_at.strftime('%Y%m%d_%H%M%S')}"
        self.scheduler.add_job(
            analytics_fn,
            DateTrigger(run_date=run_at, timezone=self.tz),
            id=job_id,
            args=[post_ids],
        )
        logger.info(f"Analytics check scheduled for {run_at.strftime('%Y-%m-%d %H:%M')}")

    def schedule_cleanup(self, cleanup_fn: callable) -> None:
        """Run temp-file cleanup every Sunday at 03:00."""
        self.scheduler.add_job(
            cleanup_fn,
            CronTrigger(day_of_week="sun", hour=3, minute=0, timezone=self.tz),
            id="weekly_cleanup",
            replace_existing=True,
        )
        logger.info("Weekly cleanup scheduled for Sunday 03:00")

    def schedule_task(
        self,
        fn: callable,
        run_after_hours: float = 0,
        args: list | None = None,
        kwargs: dict | None = None,
    ) -> str:
        """
        Schedule a one-off task to run after a delay.

        Args:
            fn:               Async or sync callable.
            run_after_hours:  Hours from now.
            args:             Positional arguments for *fn*.
            kwargs:           Keyword arguments for *fn*.

        Returns:
            APScheduler job ID.
        """
        run_at = datetime.now(tz=self.tz) + timedelta(hours=run_after_hours)
        job_id = f"task_{fn.__name__}_{run_at.strftime('%Y%m%d_%H%M%S')}"
        self.scheduler.add_job(
            fn,
            DateTrigger(run_date=run_at, timezone=self.tz),
            id=job_id,
            args=args or [],
            kwargs=kwargs or {},
        )
        logger.info(f"Task '{fn.__name__}' scheduled for {run_at.strftime('%H:%M')} (+{run_after_hours}h)")
        return job_id

    def list_jobs(self) -> list[dict]:
        """Return summary of all scheduled jobs."""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "next_run": str(job.next_run_time),
                "func": job.func.__name__ if hasattr(job.func, "__name__") else str(job.func),
            })
        return jobs
