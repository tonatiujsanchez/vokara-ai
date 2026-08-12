"""Celery application.

No beat: nothing in 001 is scheduled, and a process without a periodic task is
infrastructure with no consumer (research R-28). Redis is the broker and
nothing else — ADR-008 removed its other two uses.

Minimal on purpose. T082 adds the task modules and the startup reaper; what
lives here is what the `worker` service of the Compose needs in order to start
and wait for work.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("vokara", broker=settings.redis_url)
celery_app.conf.update(
    # A task lost mid-run is re-delivered; taking it is guarded by an UPDATE on
    # the job row, so re-delivery cannot duplicate work (research R-07).
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    timezone="UTC",
    enable_utc=True,
)
