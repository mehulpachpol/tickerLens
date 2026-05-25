from __future__ import annotations

import argparse
import logging
import sys
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from tickerlens_api.db.session import SessionLocal
from tickerlens_api.ingestion.runner import run_nse_sync
from tickerlens_api.ingestion.universe_service import seed_nifty50
from tickerlens_api.settings import settings


IST = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger("tickerlens.ingestion.scheduler")


def daily_job() -> None:
    if not settings.ingestion_enabled:
        logger.info("Ingestion disabled (TICKERLENS_INGESTION_ENABLED=false); skipping.")
        return

    db = SessionLocal()
    try:
        # Bootstrap default universe (idempotent).
        if settings.ingestion_universe_id.upper() == "NIFTY_50":
            seed_nifty50(db)

        result = run_nse_sync(
            db,
            universe_id=settings.ingestion_universe_id,
            lookback_days=settings.ingestion_lookback_days,
            limit_per_ticker=settings.ingestion_limit_per_ticker,
        )
        discovery_ok = sum(1 for r in result["discovery"] if r.get("status") == "succeeded")
        ingest_ok = sum(1 for r in result["ingest"] if r.get("status") == "succeeded")
        logger.info("Daily job finished. discovery_ok=%s ingest_ok=%s", discovery_ok, ingest_ok)
    except Exception:
        logger.exception("Daily job failed")
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TickerLens daily NSE ingestion scheduler")
    parser.add_argument("--run-once", action="store_true", help="Run the daily job once and exit.")
    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

    if args.run_once:
        daily_job()
        return 0

    if not settings.ingestion_scheduler_enabled:
        logger.info(
            "Scheduler disabled (TICKERLENS_INGESTION_SCHEDULER_ENABLED=false); exiting."
        )
        return 0

    scheduler = BlockingScheduler(timezone=IST)
    trigger = CronTrigger(
        hour=int(settings.ingestion_cron_hour_ist),
        minute=int(settings.ingestion_cron_minute_ist),
        timezone=IST,
    )
    scheduler.add_job(
        daily_job,
        trigger=trigger,
        id="tickerlens_nse_daily",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60 * 60,
    )

    logger.info(
        "Scheduler started (IST). Next run according to cron hour=%s minute=%s.",
        settings.ingestion_cron_hour_ist,
        settings.ingestion_cron_minute_ist,
    )
    scheduler.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

