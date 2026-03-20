"""
config.py — Configuración centralizada del proyecto.
Todos los parámetros ajustables están aquí. No hardcodees valores en otros archivos.
"""

import os
import shutil
from pathlib import Path

# ── Rutas base ────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent.parent
UPLOAD_DIR  = BASE_DIR / "tmp" / "uploads"
OUTPUT_DIR  = BASE_DIR / "tmp" / "outputs"
MODELS_DIR  = BASE_DIR / "backend" / "models"
VIDEO_TMP_DIR = BASE_DIR / "tmp" / "videos"

# Crea los directorios si no existen
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_TMP_DIR.mkdir(parents=True, exist_ok=True)

# ── Validación de imágenes ────────────────────────────────────────────────────
ALLOWED_EXTENSIONS  = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE_MB    = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Resolución máxima de entrada (píxeles totales).
# Real-ESRGAN x4 convierte una imagen 2160x3840 → 8640x15360.
# Este valor permite imágenes grandes, pero conviene usar tiles pequeños.
MAX_INPUT_PIXELS = 9_000_000  # ~3000x3000 px equivalentes

# ── Parámetros del modelo ─────────────────────────────────────────────────────
# Modelos disponibles. Puedes agregar más aquí en el futuro.
MODELS = {
    "general_x4": {
        "name":        "RealESRGAN_x4plus",
        "scale":       4,
        "description": "Fotos y uso general — escalado x4",
    },
    "general_x2": {
        "name":        "RealESRGAN_x4plus",   # mismo modelo, se reescala a x2 en post
        "scale":       2,
        "description": "Fotos y uso general — escalado x2",
    },
    "anime_x4": {
        "name":        "RealESRGAN_x4plus_anime_6B",
        "scale":       4,
        "description": "Ilustraciones y anime — escalado x4",
    },
}
DEFAULT_MODEL = "general_x4"

# tile_size: cuántos píxeles procesa Real-ESRGAN a la vez.
# Valores más altos = más rápido pero más RAM/VRAM.
# 128 reduce el consumo de memoria y es más seguro para imágenes grandes.
# Puedes subirlo si priorizas velocidad y tu VRAM lo soporta.
TILE_SIZE    = 128
TILE_PADDING = 10   # solapamiento entre tiles para evitar artefactos en los bordes

# ── API ───────────────────────────────────────────────────────────────────────
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", 8000))
API_RELOAD = os.getenv("API_RELOAD", "false").lower() == "true"

# ── Limpieza de archivos temporales ──────────────────────────────────────────
# Archivos más antiguos que este valor (en horas) serán eliminados
CLEANUP_MAX_AGE_HOURS = 2


def _find_binary(binary_name: str) -> str:
    candidates = [
        shutil.which(binary_name),
        str(Path(os.getenv("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / f"{binary_name}.exe"),
        str(Path("C:/Program Files/Redis") / f"{binary_name}.exe"),
        str(
            Path(os.getenv("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
            / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
            / "ffmpeg-8.1-full_build" / "bin" / f"{binary_name}.exe"
        ),
    ]

    winget_packages = Path(os.getenv("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if winget_packages.exists():
        if binary_name in {"ffmpeg", "ffprobe"}:
            candidates.extend(
                str(path)
                for path in winget_packages.glob(f"Gyan.FFmpeg*/**/{binary_name}.exe")
            )

    for candidate in candidates:
        if not candidate:
            continue
        try:
            if Path(candidate).exists():
                return candidate
        except OSError:
            continue

    return binary_name


# ── Video / Celery ───────────────────────────────────────────────────────────
MAX_VIDEO_SIZE_MB      = 500
MAX_VIDEO_DURATION_SEC = 120
MAX_VIDEO_RESOLUTION   = 1280
VIDEO_FPS_OUTPUT       = None   # None = mismo fps que el original
CELERY_BROKER_URL      = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND  = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
FFMPEG_BIN             = os.getenv("FFMPEG_BIN", _find_binary("ffmpeg"))
FFPROBE_BIN            = os.getenv("FFPROBE_BIN", _find_binary("ffprobe"))

if FFMPEG_BIN == "ffmpeg" and FFPROBE_BIN != "ffprobe":
    FFMPEG_BIN = str(Path(FFPROBE_BIN).with_name("ffmpeg.exe"))
