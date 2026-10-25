"""Celery 应用定义：4 队列拓扑 + 路由 + beat 调度。

队列隔离（TD 6.1）：
- monitor     并发 1   —— 对标账号巡检（拉取作品）
- transcribe  并发 1~2 —— ASR 转写（CPU/GPU 密集）
- analyze     并发 2~4 —— LLM 特征/分镜分析（IO 密集）
- render      并发 1   —— Remotion/FFmpeg 渲染（独占编码资源）
"""

from celery import Celery
from celery.schedules import crontab
from kombu import Queue

from app.core.config import settings

celery = Celery(
    "zmt",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.tasks", "app.tasks.media_cleanup"],
)

celery.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    timezone="Asia/Shanghai",
    enable_utc=True,
    result_expires=60 * 60 * 24,
    task_queues=(
        Queue("monitor", routing_key="monitor"),
        Queue("transcribe", routing_key="transcribe"),
        Queue("analyze", routing_key="analyze"),
        Queue("render", routing_key="render"),
    ),
    task_default_queue="analyze",
    task_routes={
        "app.tasks.monitor": {"queue": "monitor"},
        "app.tasks.transcribe": {"queue": "transcribe"},
        "app.tasks.analyze": {"queue": "analyze"},
        "app.tasks.render": {"queue": "render"},
        "app.tasks.ping": {"queue": "monitor"},
        "app.tasks.cleanup_media": {"queue": "monitor"},
    },
    beat_schedule={
        "monitor-benchmark-every-1h": {
            "task": "app.tasks.monitor",
            "schedule": 60 * 60,
        },
        # 媒体生命周期清理：每天 03:15（低峰期）
        "cleanup-media-daily": {
            "task": "app.tasks.cleanup_media",
            "schedule": crontab(hour=3, minute=15),
        },
    },
)


@celery.task(name="app.tasks.ping")
def ping() -> str:
    """健康心跳任务，验证 worker 与 broker 连通。"""
    return "pong"
