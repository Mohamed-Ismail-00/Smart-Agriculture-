"""
Blocking APScheduler loop for the `agri_scheduler` Docker service.

Two scheduled jobs:
1. land_monitoring   — runs every LAND_MONITOR_INTERVAL_MINUTES (default: 1440 = 24h)
   Fetches satellite data, computes indices, then auto-triggers AI analysis.

2. ai_analysis_cycle — runs every AI_AUTO_ANALYZE_HOURS (default: 6h)
   Proactively refreshes AI insights for any land whose insights are stale (>AI_INSIGHT_STALE_HOURS).

Configure intervals with environment variables in .env.backend.
"""

from __future__ import annotations

import logging
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler

from app.core.config import settings
from app.scheduler import jobs

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger(__name__)


def main() -> None:
    scheduler = BlockingScheduler()

    # Job 1: Full land monitoring cycle (satellite + AI auto-trigger)
    scheduler.add_job(
        jobs.run_land_monitoring_cycle,
        "interval",
        minutes=max(1, settings.LAND_MONITOR_INTERVAL_MINUTES),
        id="land_monitoring",
        replace_existing=True,
    )

    # Job 2: Proactive AI stale insight refresh
    scheduler.add_job(
        jobs.run_ai_analysis_cycle,
        "interval",
        hours=max(1, settings.AI_AUTO_ANALYZE_HOURS),
        id="ai_analysis_cycle",
        replace_existing=True,
    )

    def shutdown(signum: int, frame: object | None) -> None:
        if scheduler.running:
            scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info(
        "Scheduler started: land_monitoring every %s min(s), AI analysis cycle every %s hour(s)",
        settings.LAND_MONITOR_INTERVAL_MINUTES,
        settings.AI_AUTO_ANALYZE_HOURS,
    )
    scheduler.start()


if __name__ == "__main__":
    main()
