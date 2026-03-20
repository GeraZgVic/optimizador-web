"""
backend/main.py — Aplicación FastAPI. Punto de entrada del servidor.

Endpoints:
  POST /enhance          — recibe imagen, la procesa, retorna metadatos + task_id
  GET  /download/{name}  — descarga la imagen procesada
  GET  /models           — lista los modelos disponibles
  GET  /health           — healthcheck (útil para monitoreo)
"""

import logging
import sys
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from celery.result import AsyncResult

from backend.config import MODELS, DEFAULT_MODEL, OUTPUT_DIR, BASE_DIR, VIDEO_TMP_DIR
from backend.processor import enhance_image
from backend.tasks import celery_app, process_video
from backend.utils.file_handler import (
    save_upload,
    get_output_path,
    validate_file,
    cleanup_old_files,
)
from backend.utils.validator import validate_image_content, get_image_info
from backend.video_processor import probe_video, validate_video_upload

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Real-ESRGAN Image Enhancer",
    description="API para mejorar la calidad de imágenes usando Real-ESRGAN.",
    version="1.0.0",
)

# CORS: permite que el frontend (en otro puerto durante desarrollo) haga requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # En producción, reemplaza * por tu dominio
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sirve el frontend estático desde /  (index.html, style.css, app.js)
FRONTEND_DIR = BASE_DIR / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    """Verifica que el servidor esté corriendo. Útil para CI/CD o monitoreo."""
    import torch
    return {
        "status":      "ok",
        "cuda":        torch.cuda.is_available(),
        "gpu":         torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }


@app.get("/models")
def list_models():
    """Retorna los modelos disponibles para mostrar en el selector del frontend."""
    return {
        key: {
            "key":         key,
            "description": val["description"],
            "scale":       val["scale"],
        }
        for key, val in MODELS.items()
    }


def _map_video_scale_to_model(scale: int) -> str:
    if scale == 2:
        return "general_x2"
    if scale == 4:
        return "general_x4"
    raise ValueError("La escala de video debe ser 2 o 4")


@app.post("/enhance")
async def enhance(
    file:         UploadFile = File(...),
    model_key:    str        = Form(DEFAULT_MODEL),
    face_enhance: bool       = Form(False),
):
    """
    Endpoint principal. Recibe una imagen, la mejora con Real-ESRGAN y
    retorna metadatos del resultado junto con el nombre del archivo de salida.

    El frontend usa ese nombre para hacer GET /download/{filename}.
    """
    # ── 1. Leer bytes del upload ──────────────────────────────────────────────
    file_bytes = await file.read()
    logger.info(f"face_enhance recibido: {str(face_enhance).lower()}")

    # ── 2. Validar extensión y tamaño ─────────────────────────────────────────
    ok, err = validate_file(file.filename, file_bytes)
    if not ok:
        raise HTTPException(status_code=400, detail=err)

    # ── 3. Validar que sea una imagen real y no esté corrupta ─────────────────
    ok, err, img_info = validate_image_content(file_bytes)
    if not ok:
        raise HTTPException(status_code=400, detail=err)

    # ── 4. Validar model_key ──────────────────────────────────────────────────
    if model_key not in MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Modelo inválido. Opciones: {list(MODELS.keys())}",
        )

    # ── 5. Guardar imagen en disco ────────────────────────────────────────────
    input_path  = save_upload(file_bytes, file.filename)
    output_path = get_output_path(input_path)

    logger.info(
        f"Nueva petición — archivo: {file.filename} "
        f"({img_info['width']}x{img_info['height']}), modelo: {model_key}, "
        f"restaurar_caras: {face_enhance}"
    )

    # ── 6. Procesar con Real-ESRGAN ───────────────────────────────────────────
    try:
        result = enhance_image(
            input_path,
            output_path,
            model_key=model_key,
            face_enhance=face_enhance,
        )
    except Exception as e:
        logger.error(f"Error en el procesamiento: {e}", exc_info=True)
        # Limpiamos el archivo de entrada si falló
        if input_path.exists():
            input_path.unlink()
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar la imagen: {str(e)}",
        )

    # ── 7. Limpiar archivos viejos (housekeeping pasivo) ─────────────────────
    cleanup_old_files()

    # ── 8. Responder al frontend ──────────────────────────────────────────────
    return JSONResponse({
        "success":       True,
        "output_file":   output_path.name,      # el frontend usará este nombre
        "input_info":    img_info,
        "processing":    result,
        "download_url":  f"/download/{output_path.name}",
    })


@app.post("/enhance-video")
async def enhance_video(
    file: UploadFile = File(...),
    scale: int = Form(4),
    face_enhance: bool = Form(False),
):
    file_bytes = await file.read()
    task_id = str(uuid.uuid4())
    task_dir = VIDEO_TMP_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    try:
        model_key = _map_video_scale_to_model(scale)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    input_video_path = task_dir / f"input{Path(file.filename or 'video.mp4').suffix.lower() or '.mp4'}"
    input_video_path.write_bytes(file_bytes)

    try:
        video_info = probe_video(input_video_path)
        ok, err = validate_video_upload(file.filename or input_video_path.name, len(file_bytes), video_info)
        if not ok:
            raise HTTPException(status_code=400, detail=err)

        logger.info(
            f"Nueva petición de video — archivo: {file.filename}, "
            f"escala: x{scale}, restaurar_caras: {face_enhance}"
        )

        process_video.apply_async(
            args=[task_id, str(input_video_path), str(task_dir), model_key, face_enhance],
            task_id=task_id,
        )

        return JSONResponse({
            "success": True,
            "task_id": task_id,
            "video_info": video_info,
            "status_url": f"/status/{task_id}",
            "download_url": f"/download-video/{task_id}",
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error preparando video: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"No se pudo preparar el video: {e}") from e


@app.get("/status/{task_id}")
def get_status(task_id: str):
    result = AsyncResult(task_id, app=celery_app)

    if result.state == "PENDING":
        return {"task_id": task_id, "state": "pending"}

    if result.state in {"STARTED", "PROGRESS"}:
        meta = result.info or {}
        return {
            "task_id": task_id,
            "state": "processing",
            "stage": meta.get("stage"),
            "current_frame": meta.get("current_frame", 0),
            "total_frames": meta.get("total_frames", 0),
            "progress_percent": meta.get("progress_percent", 0),
            "message": meta.get("message", "Procesando video..."),
        }

    if result.state == "SUCCESS":
        payload = result.result or {}
        return {
            "task_id": task_id,
            "state": "done",
            "download_url": payload.get("download_url", f"/download-video/{task_id}"),
            "output_file": payload.get("output_file"),
            "total_frames": payload.get("total_frames", 0),
        }

    if result.state == "FAILURE":
        return {
            "task_id": task_id,
            "state": "error",
            "message": str(result.result),
        }

    return {"task_id": task_id, "state": result.state.lower()}


@app.get("/download-video/{task_id}")
def download_video(task_id: str):
    result = AsyncResult(task_id, app=celery_app)
    if result.state != "SUCCESS":
        raise HTTPException(status_code=404, detail="El video aún no está listo para descargar.")

    payload = result.result or {}
    output_file = payload.get("output_file")
    if not output_file:
        raise HTTPException(status_code=404, detail="No se encontró el archivo de salida.")

    file_path = OUTPUT_DIR / Path(output_file).name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="El archivo de video no existe o expiró.")

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="video/mp4",
    )


@app.get("/download/{filename}")
def download(filename: str):
    """
    Descarga una imagen procesada por su nombre de archivo.
    Valida que el nombre sea seguro (no permite path traversal como '../etc/passwd').
    """
    # Seguridad: asegurarse de que el nombre no contiene rutas relativas
    safe_name = Path(filename).name
    file_path = OUTPUT_DIR / safe_name

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Archivo no encontrado. Puede haber expirado (>2 horas).",
        )

    return FileResponse(
        path=str(file_path),
        filename=f"enhanced_{safe_name}",
        media_type="image/png",
    )


# ── Sirve el index.html en la raíz ────────────────────────────────────────────
@app.get("/")
def serve_frontend():
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        return JSONResponse({"message": "Frontend no encontrado. Coloca index.html en /frontend/"})
    return FileResponse(str(index_path))


# ── Entry point para desarrollo ───────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    from backend.config import API_HOST, API_PORT, API_RELOAD

    uvicorn.run("backend.main:app", host=API_HOST, port=API_PORT, reload=API_RELOAD)
