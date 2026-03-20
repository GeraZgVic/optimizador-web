"""
backend/tasks.py — Celery app y tasks asíncronas para video.
"""

from __future__ import annotations

from pathlib import Path

from celery import Celery

from backend.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND
from backend.video_processor import process_video_pipeline

celery_app = Celery(
    "realesrgan_web",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_track_started=True,
    result_extended=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)


@celery_app.task(bind=True, name="backend.tasks.process_video")
def process_video(self, task_id: str, input_video_path: str, task_dir: str, model_key: str, face_enhance: bool):
    return process_video_pipeline(
        self,
        task_id=task_id,
        input_video_path=Path(input_video_path),
        task_dir=Path(task_dir),
        model_key=model_key,
        face_enhance=face_enhance,
    )
