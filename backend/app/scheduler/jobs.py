"""Scheduled job entrypoints for land monitoring and AI analysis automation."""

import logging
from datetime import datetime, timedelta, timezone

from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


def run_land_monitoring_cycle() -> None:
    """
    Run the full land monitoring cycle: fetch satellite data, compute indices,
    create climate/soil/crop records. After completion, auto-trigger AI analysis
    for any land whose data was just refreshed.
    """
    db = SessionLocal()
    try:
        from app.pipeline import land_monitoring_pipeline
        completed_land_ids = land_monitoring_pipeline.run_monitoring_cycle(db)
        
        # Auto-run AI analysis for every land that just got fresh data
        if completed_land_ids:
            logger.info(
                "Monitoring cycle complete. Auto-triggering AI for %d land(s): %s",
                len(completed_land_ids), completed_land_ids
            )
            _run_ai_for_lands(db, completed_land_ids)
        
    except Exception:
        logger.exception("Scheduled land monitoring cycle failed")
        db.rollback()
    finally:
        db.close()


def run_ai_analysis_cycle() -> None:
    """
    Periodic AI analysis job: finds all lands with stale insights (older than
    AI_INSIGHT_STALE_HOURS) or no insights at all, and runs fresh AI analysis.
    
    This ensures every land gets AI coverage even if the monitoring cycle
    did not flag it as freshly updated.
    """
    from app.core.config import settings
    
    db = SessionLocal()
    try:
        from app.models.land import Land
        from app.models.land_ai_insight import LandAiInsight
        
        stale_cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.AI_INSIGHT_STALE_HOURS)
        
        # Find all active lands
        all_lands = db.query(Land).filter(
            Land.status.in_(["ready", "active"])
        ).all()
        
        stale_land_ids = []
        for land in all_lands:
            # Check for any recent insight
            last_insight = (
                db.query(LandAiInsight)
                .filter(LandAiInsight.land_id == land.land_id)
                .order_by(LandAiInsight.created_at.desc())
                .first()
            )
            if not last_insight or last_insight.created_at.replace(tzinfo=timezone.utc) < stale_cutoff:
                stale_land_ids.append(land.land_id)
        
        if stale_land_ids:
            logger.info(
                "AI stale check: %d land(s) need fresh insights: %s",
                len(stale_land_ids), stale_land_ids
            )
            _run_ai_for_lands(db, stale_land_ids)
        else:
            logger.info("AI stale check: all lands have recent insights. Nothing to do.")
        
    except Exception:
        logger.exception("AI analysis cycle failed")
        db.rollback()
    finally:
        db.close()


def _run_ai_for_lands(db, land_ids: list) -> None:
    """Helper: run AI analysis for a list of land_ids and emit LandAlert notifications."""
    from app.ai.land_analyst import run_ai_land_analysis
    from app.models.land import Land
    from app.models.land_alert import LandAlert
    
    for land_id in land_ids:
        try:
            land = db.query(Land).filter(Land.land_id == land_id).first()
            if not land:
                continue
            
            insights = run_ai_land_analysis(land_id=land_id, db=db, user_id=land.user_id)
            
            if insights:
                # Create a low-severity notification so the bell lights up
                alert = LandAlert(
                    land_id=land_id,
                    user_id=land.user_id,
                    alert_type="ai_analysis_complete",
                    severity="low",
                    message=f"Scheduled AI analysis complete for '{land.name}': {len(insights)} insights generated.",
                    payload={"insight_count": len(insights), "public_id": land.public_id},
                    is_read=False,
                )
                db.add(alert)
                db.commit()
                logger.info("AI analysis complete for land_id=%s (%s insights)", land_id, len(insights))
            else:
                logger.warning("AI analysis produced no insights for land_id=%s (quota or empty context)", land_id)
        except Exception:
            logger.exception("AI analysis failed for land_id=%s — skipping", land_id)
            db.rollback()
