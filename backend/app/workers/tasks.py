import asyncio
from app.workers.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.entities import Case, Notification
from app.services.media.url_analyzer import verify_url_live_status
from datetime import datetime, timezone
import uuid

def _task_decorator(fn):
    return celery_app.task(name="truthshield.verify_case_urls")(fn) if celery_app is not None else fn


@_task_decorator
def verify_case_urls_task(case_id: str, user_id: str) -> dict:
    """Background task to recheck case URLs and notify if verified removed."""
    db = SessionLocal()
    try:
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case or not case.urls:
            return {"case_id": case_id, "checked": 0}

        async def _check_all():
            results = []
            for url in case.urls:
                try:
                    results.append(await verify_url_live_status(url))
                except Exception as exc:
                    results.append({"url": url, "confirmed_removed": False, "detail": str(exc)})
            return results

        checks = asyncio.run(_check_all())
        all_removed = len(checks) > 0 and all(c.get("confirmed_removed") for c in checks)

        if all_removed and case.status != "confirmed_removed":
            case.status = "confirmed_removed"
            case.updated_at = datetime.now(timezone.utc)
            notif = Notification(
                id=str(uuid.uuid4()),
                user_id=user_id,
                title=f"Removal Verified: {case.case_number}",
                message="All target URLs for this case returned HTTP 404/410 or unavailable notices.",
                notification_type="removal_update",
                case_id=case.id,
            )
            db.add(notif)
            db.commit()

        return {"case_id": case_id, "checked": len(checks), "all_removed": all_removed}
    finally:
        db.close()
