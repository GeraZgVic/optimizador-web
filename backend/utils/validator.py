"""
utils/validator.py — Validación profunda de imágenes.
Va más allá de la extensión: verifica que el archivo sea una imagen real
y que sus dimensiones sean procesables por Real-ESRGAN.
"""

import io
import logging
from pathlib import Path

from PIL import Image

from backend.config import MAX_INPUT_PIXELS

logger = logging.getLogger(__name__)


def validate_image_content(file_bytes: bytes) -> tuple[bool, str, dict]:
    """
    Abre la imagen con Pillow para verificar que no está corrupta
    y que sus dimensiones son razonables.

    Retorna:
        (valid: bool, error_msg: str, info: dict)
        info contiene: width, height, mode, format
    """
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.verify()  # detecta archivos corruptos sin decodificar completamente
    except Exception as e:
        logger.warning(f"Imagen inválida o corrupta: {e}")
        return False, "El archivo no es una imagen válida o está corrupto.", {}

    # Reabrimos porque .verify() consume el stream
    img  = Image.open(io.BytesIO(file_bytes))
    w, h = img.size
    info = {"width": w, "height": h, "mode": img.mode, "format": img.format}

    # Verificamos que no sea demasiado pequeña para que tenga sentido procesarla
    if w < 8 or h < 8:
        return False, f"La imagen es demasiado pequeña ({w}x{h} px). Mínimo 8x8.", info

    # Verificamos que no sea tan grande que el procesamiento falle por memoria
    total_pixels = w * h
    if total_pixels > MAX_INPUT_PIXELS:
        max_approx = int(MAX_INPUT_PIXELS ** 0.5)
        return (
            False,
            f"La imagen es demasiado grande ({w}x{h} = {total_pixels:,} px). "
            f"Máximo ~{max_approx}x{max_approx} px.",
            info,
        )

    return True, "", info


def get_image_info(image_path: Path) -> dict:
    """
    Lee metadatos básicos de una imagen ya guardada en disco.
    Útil para incluir en la respuesta al usuario.
    """
    try:
        img  = Image.open(image_path)
        w, h = img.size
        size_kb = image_path.stat().st_size / 1024
        return {
            "width":   w,
            "height":  h,
            "mode":    img.mode,
            "format":  img.format,
            "size_kb": round(size_kb, 1),
        }
    except Exception as e:
        logger.error(f"No se pudo leer info de {image_path}: {e}")
        return {}
