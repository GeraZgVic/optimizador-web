"""
utils/file_handler.py — Manejo de archivos temporales.
Responsable de guardar uploads, construir rutas de salida y limpiar archivos viejos.
"""

import time
import uuid
import logging
from pathlib import Path

from backend.config import (
    UPLOAD_DIR,
    OUTPUT_DIR,
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
    CLEANUP_MAX_AGE_HOURS,
)

logger = logging.getLogger(__name__)


def generate_unique_filename(original_filename: str) -> str:
    """
    Genera un nombre único usando UUID para evitar colisiones entre usuarios.
    Ejemplo: 'foto.jpg' → 'a3f2c1d8-4b5e-...jpg'
    """
    suffix = Path(original_filename).suffix.lower()
    return f"{uuid.uuid4()}{suffix}"


def save_upload(file_bytes: bytes, original_filename: str) -> Path:
    """
    Guarda los bytes de la imagen subida en UPLOAD_DIR.
    Retorna la ruta completa del archivo guardado.
    """
    unique_name = generate_unique_filename(original_filename)
    dest_path   = UPLOAD_DIR / unique_name

    dest_path.write_bytes(file_bytes)
    logger.info(f"Upload guardado: {dest_path}")
    return dest_path


def get_output_path(input_path: Path) -> Path:
    """
    Construye la ruta de salida para la imagen procesada.
    Usa el mismo UUID del input para poder relacionarlos fácilmente.
    Siempre guarda como PNG para preservar calidad máxima.
    """
    stem = input_path.stem   # UUID sin extensión
    return OUTPUT_DIR / f"{stem}_enhanced.png"


def validate_file(filename: str, file_bytes: bytes) -> tuple[bool, str]:
    """
    Valida que el archivo sea una imagen permitida y no exceda el tamaño máximo.
    Retorna (True, '') si es válido, o (False, 'mensaje de error') si no.
    """
    suffix = Path(filename).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(ALLOWED_EXTENSIONS)
        return False, f"Formato no permitido. Usa: {allowed}"

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        max_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
        return False, f"El archivo supera el límite de {max_mb:.0f} MB"

    return True, ""


def cleanup_old_files() -> dict:
    """
    Elimina archivos temporales más antiguos que CLEANUP_MAX_AGE_HOURS.
    Llama esta función periódicamente (por ejemplo, en cada petición o con un scheduler).
    Retorna un dict con cuántos archivos se eliminaron.
    """
    max_age_seconds = CLEANUP_MAX_AGE_HOURS * 3600
    now             = time.time()
    deleted         = {"uploads": 0, "outputs": 0}

    for directory, key in [(UPLOAD_DIR, "uploads"), (OUTPUT_DIR, "outputs")]:
        for file_path in directory.iterdir():
            if not file_path.is_file():
                continue
            age = now - file_path.stat().st_mtime
            if age > max_age_seconds:
                file_path.unlink()
                deleted[key] += 1
                logger.info(f"Archivo eliminado (>2h): {file_path.name}")

    if any(deleted.values()):
        logger.info(f"Limpieza completada: {deleted}")

    return deleted
