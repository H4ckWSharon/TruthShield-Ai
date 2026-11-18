from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "truthshield_workers",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)

def is_redis_available() -> bool:
    """Quick ping check to see if Redis broker is reachable."""
    try:
        import redis
        client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1.0)
        return bool(client.ping())
    except Exception:
        return False
