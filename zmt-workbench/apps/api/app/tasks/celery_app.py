"""Celery 应用定义（S0 建立队列基础设施，S3 承载转写/渲染任务）。"""

from celery import Celery

from app.core.config import settings

celery = Celery(
    "zmt",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.celery_app"],
)

celery.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    timezone="Asia/Shanghai",
    enable_utc=True,
)


@celery.task(name="app.tasks.ping")
def ping() -> str:
    """健康心跳任务，验证 worker 与 broker 连通。"""
    return "pong"
