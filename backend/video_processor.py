"""
backend/video_processor.py — Pipeline de video con FFmpeg.

Responsable de:
1. Validar videos (extensión, tamaño, duración, resolución)
2. Extraer frames con FFmpeg
3. Procesar cada frame con Real-ESRGAN (+ GFPGAN opcional)
4. Reensamblar el video final preservando el audio original
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

from backend.config import (
    FFMPEG_BIN,
    FFPROBE_BIN,
    MAX_VIDEO_DURATION_SEC,
    MAX_VIDEO_RESOLUTION,
    MAX_VIDEO_SIZE_MB,
    MODELS,
    OUTPUT_DIR,
    VIDEO_FPS_OUTPUT,
)
from backend.processor import enhance_image

logger = logging.getLogger(__name__)

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}


def run_subprocess(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )


def probe_video(video_path: Path) -> dict:
    command = [
        FFPROBE_BIN,
        "-v", "error",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        str(video_path),
    ]
    result = run_subprocess(command)
    data = json.loads(result.stdout)
    video_stream = next(
        (stream for stream in data.get("streams", []) if stream.get("codec_type") == "video"),
        None,
    )
    if not video_stream:
        raise ValueError("No se encontró un stream de video válido.")

    duration = float(data.get("format", {}).get("duration") or video_stream.get("duration") or 0)
    width = int(video_stream.get("width") or 0)
    height = int(video_stream.get("height") or 0)
    fps_raw = video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate") or "0/1"
    fps_num, fps_den = fps_raw.split("/")
    fps = round(float(fps_num) / float(fps_den), 3) if float(fps_den) else 0

    return {
        "duration_sec": duration,
        "width": width,
        "height": height,
        "fps": fps,
        "has_audio": any(stream.get("codec_type") == "audio" for stream in data.get("streams", [])),
    }


def validate_video_upload(filename: str, file_size_bytes: int, info: dict) -> tuple[bool, str]:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_VIDEO_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_VIDEO_EXTENSIONS))
        return False, f"Formato de video no permitido. Usa: {allowed}"

    max_size_bytes = MAX_VIDEO_SIZE_MB * 1024 * 1024
    if file_size_bytes > max_size_bytes:
        return False, f"El video supera el límite de {MAX_VIDEO_SIZE_MB} MB"

    if info["duration_sec"] > MAX_VIDEO_DURATION_SEC:
        return False, f"El video supera el límite de {MAX_VIDEO_DURATION_SEC} segundos"

    if max(info["width"], info["height"]) > MAX_VIDEO_RESOLUTION:
        return False, f"La resolución máxima permitida es {MAX_VIDEO_RESOLUTION}px en el lado mayor"

    return True, ""


def extract_frames(video_path: Path, frames_dir: Path) -> None:
    frames_dir.mkdir(parents=True, exist_ok=True)
    command = [
        FFMPEG_BIN,
        "-y",
        "-i", str(video_path),
        "-vsync", "0",
        str(frames_dir / "frame_%06d.png"),
    ]
    run_subprocess(command)


def reassemble_video(
    enhanced_frames_dir: Path,
    source_video_path: Path,
    output_path: Path,
    fps: float,
) -> None:
    output_fps = VIDEO_FPS_OUTPUT or fps or 30
    command = [
        FFMPEG_BIN,
        "-y",
        "-framerate", str(output_fps),
        "-i", str(enhanced_frames_dir / "frame_%06d.png"),
        "-i", str(source_video_path),
        "-map", "0:v:0",
        "-map", "1:a:0?",
        "-c:v", "libx264",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(output_path),
    ]
    run_subprocess(command)


def process_video_pipeline(
    task,
    task_id: str,
    input_video_path: Path,
    task_dir: Path,
    model_key: str,
    face_enhance: bool,
    gfpgan_weight: float = 0.5,
) -> dict:
    if model_key not in MODELS:
        raise ValueError(f"Modelo inválido para video: {model_key}")

    frames_dir = task_dir / "frames"
    enhanced_frames_dir = task_dir / "enhanced_frames"
    enhanced_frames_dir.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{task_id}_enhanced.mp4"

    try:
        task.update_state(state="PROGRESS", meta={
            "stage": "extracting",
            "current_frame": 0,
            "total_frames": 0,
            "progress_percent": 0,
            "message": "Extrayendo frames con FFmpeg...",
        })
        info = probe_video(input_video_path)
        extract_frames(input_video_path, frames_dir)

        frame_paths = sorted(frames_dir.glob("frame_*.png"))
        total_frames = len(frame_paths)
        if not total_frames:
            raise RuntimeError("FFmpeg no extrajo frames del video.")

        for idx, frame_path in enumerate(frame_paths, start=1):
            enhanced_frame_path = enhanced_frames_dir / frame_path.name
            try:
                enhance_image(
                    frame_path,
                    enhanced_frame_path,
                    model_key=model_key,
                    face_enhance=face_enhance,
                    gfpgan_weight=gfpgan_weight,
                )
            except Exception as e:
                logger.warning(f"Frame {frame_path.name} falló y se conservará el original: {e}")
                shutil.copy2(frame_path, enhanced_frame_path)

            progress = round((idx / total_frames) * 100, 1)
            task.update_state(state="PROGRESS", meta={
                "stage": "processing",
                "current_frame": idx,
                "total_frames": total_frames,
                "progress_percent": progress,
                "message": f"Frame {idx} / {total_frames} — {progress}%",
            })

        task.update_state(state="PROGRESS", meta={
            "stage": "assembling",
            "current_frame": total_frames,
            "total_frames": total_frames,
            "progress_percent": 99,
            "message": "Reensamblando video final con FFmpeg...",
        })

        reassemble_video(enhanced_frames_dir, input_video_path, output_path, info["fps"])

        return {
            "task_id": task_id,
            "state": "done",
            "output_file": output_path.name,
            "download_url": f"/download-video/{task_id}",
            "total_frames": total_frames,
            "face_enhance": face_enhance,
            "gfpgan_weight": gfpgan_weight,
        }
    finally:
        shutil.rmtree(task_dir, ignore_errors=True)
