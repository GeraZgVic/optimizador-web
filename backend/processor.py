"""
backend/processor.py — Núcleo de procesamiento con Real-ESRGAN.

Este módulo es el corazón del sistema. Se encarga de:
1. Descargar el modelo si no existe localmente
2. Cargar Real-ESRGAN con el modelo correcto
3. Ejecutar la inferencia (CPU o GPU automáticamente)
4. Guardar el resultado

Usamos la librería `realesrgan` del repositorio oficial de xinntao.
"""

import logging
import sys
import urllib.request
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image

# Compatibilidad para BasicSR con versiones recientes de torchvision.
# BasicSR importa `torchvision.transforms.functional_tensor`, pero en
# torchvision nuevo ese módulo pasó a `_functional_tensor`.
try:
    import torchvision.transforms._functional_tensor as _tv_functional_tensor

    sys.modules.setdefault(
        "torchvision.transforms.functional_tensor",
        _tv_functional_tensor,
    )
except Exception:
    pass

from basicsr.archs.rrdbnet_arch import RRDBNet
from realesrgan import RealESRGANer

from backend.config import MODELS_DIR, TILE_SIZE, TILE_PADDING, MODELS

logger = logging.getLogger(__name__)
UPSAMPLER_CACHE: dict[tuple[str, str], RealESRGANer] = {}
FACE_RESTORER_CACHE: dict[str, object] = {}


# ── Descarga automática de pesos ──────────────────────────────────────────────

MODEL_URLS = {
    "RealESRGAN_x4plus": (
        "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/"
        "RealESRGAN_x4plus.pth"
    ),
    "RealESRGAN_x4plus_anime_6B": (
        "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/"
        "RealESRGAN_x4plus_anime_6B.pth"
    ),
    "GFPGANv1.4": (
        "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.4/"
        "GFPGANv1.4.pth"
    ),
}


def _get_model_path(model_name: str) -> Path:
    """
    Retorna la ruta local del modelo. Si no existe, lo descarga desde GitHub.
    Los pesos se guardan en backend/models/ y no se vuelven a descargar.
    """
    model_path = MODELS_DIR / f"{model_name}.pth"

    if model_path.exists():
        logger.info(f"Modelo encontrado en caché: {model_path}")
        return model_path

    url = MODEL_URLS.get(model_name)
    if not url:
        raise ValueError(f"Modelo desconocido: {model_name}. Opciones: {list(MODEL_URLS)}")

    logger.info(f"Descargando modelo '{model_name}' desde GitHub...")
    logger.info(f"URL: {url}")
    logger.info("Esto solo ocurre la primera vez (~65MB). Ten paciencia...")

    urllib.request.urlretrieve(url, model_path)
    logger.info(f"Modelo guardado en: {model_path}")
    return model_path


# ── Arquitectura del modelo ───────────────────────────────────────────────────

def _build_network(model_name: str) -> RRDBNet:
    """
    Construye la red neuronal con los parámetros correctos según el modelo.
    RealESRGAN_x4plus usa 23 bloques RRDB (versión completa).
    RealESRGAN_x4plus_anime_6B usa solo 6 bloques (más ligero, optimizado para anime).
    """
    if model_name == "RealESRGAN_x4plus_anime_6B":
        return RRDBNet(
            num_in_ch=3, num_out_ch=3,
            num_feat=64, num_block=6, num_grow_ch=32,
            scale=4,
        )
    else:  # RealESRGAN_x4plus (modelo por defecto)
        return RRDBNet(
            num_in_ch=3, num_out_ch=3,
            num_feat=64, num_block=23, num_grow_ch=32,
            scale=4,
        )


def _get_upsampler(model_name: str, device: torch.device) -> RealESRGANer:
    cache_key = (model_name, device.type)
    cached = UPSAMPLER_CACHE.get(cache_key)
    if cached is not None:
        return cached

    model_path = _get_model_path(model_name)
    network = _build_network(model_name)
    upsampler = RealESRGANer(
        scale=4,
        model_path=str(model_path),
        model=network,
        tile=TILE_SIZE,
        tile_pad=TILE_PADDING,
        pre_pad=0,
        half=(device.type == "cuda"),
        device=device,
    )
    UPSAMPLER_CACHE[cache_key] = upsampler
    return upsampler


def enhance_faces(output_path: Path, weight: float = 0.5) -> bool:
    """
    Restaura caras sobre la imagen ya mejorada por Real-ESRGAN.
    Si algo falla o no hay caras detectables, no interrumpe el flujo.
    """
    try:
        from gfpgan import GFPGANer

        logger.info("GFPGAN ejecutándose...")
        cache_key = "gfpgan_v14"
        face_restorer = FACE_RESTORER_CACHE.get(cache_key)
        if face_restorer is None:
            model_path = _get_model_path("GFPGANv1.4")
            face_restorer = GFPGANer(
                model_path=str(model_path),
                upscale=1,
                arch="clean",
                channel_multiplier=2,
                bg_upsampler=None,
            )
            FACE_RESTORER_CACHE[cache_key] = face_restorer

        image_bgr = cv2.imread(str(output_path), cv2.IMREAD_COLOR)
        if image_bgr is None:
            logger.warning("GFPGAN no pudo leer la imagen procesada.")
            return False

        _, restored_faces, restored_img = face_restorer.enhance(
            image_bgr,
            has_aligned=False,
            only_center_face=False,
            paste_back=True,
            weight=weight,
        )

        face_count = len(restored_faces) if restored_faces else 0
        logger.info(f"Caras detectadas: {face_count}")

        if not restored_faces or restored_img is None:
            logger.info("GFPGAN no detectó caras. Se conserva el resultado original.")
            return False

        cv2.imwrite(str(output_path), restored_img)
        logger.info(f"GFPGAN restauró {len(restored_faces)} cara(s).")
        return True
    except Exception as e:
        logger.warning(f"GFPGAN falló; se conserva Real-ESRGAN sin cambios: {e}")
        return False


# ── Función principal de procesamiento ───────────────────────────────────────

def enhance_image(
    input_path: Path,
    output_path: Path,
    model_key: str = "general_x4",
    face_enhance: bool = False,
    gfpgan_weight: float = 0.5,
) -> dict:
    """
    Procesa una imagen con Real-ESRGAN y la guarda en output_path.

    Args:
        input_path: ruta de la imagen original
        output_path: ruta donde se guardará el resultado
        model_key: clave del modelo en config.MODELS (ej: 'general_x4')

    Returns:
        dict con metadatos del procesamiento (tiempos, tamaños, device usado)

    Raises:
        FileNotFoundError: si input_path no existe
        RuntimeError: si el procesamiento falla
    """
    import time

    if not input_path.exists():
        raise FileNotFoundError(f"Imagen de entrada no encontrada: {input_path}")

    model_config = MODELS.get(model_key)
    if not model_config:
        raise ValueError(f"model_key inválido: {model_key}. Opciones: {list(MODELS)}")

    model_name   = model_config["name"]
    output_scale = model_config["scale"]   # puede ser 2 o 4

    # ── Detectar device ──────────────────────────────────────────────────────
    if torch.cuda.is_available():
        device = torch.device("cuda")
        gpu_name = torch.cuda.get_device_name(0)
        logger.info(f"GPU detectada: {gpu_name}")
    else:
        device = torch.device("cpu")
        logger.info("GPU no disponible. Usando CPU (puede tardar 30-60s).")

    # ── Cargar modelo ────────────────────────────────────────────────────────
    t_start     = time.time()
    upsampler = _get_upsampler(model_name, device)

    t_loaded = time.time()
    logger.info(f"Modelo cargado en {t_loaded - t_start:.2f}s")

    # ── Leer imagen de entrada ────────────────────────────────────────────────
    img_pil = Image.open(input_path).convert("RGB")
    img_np  = np.array(img_pil)   # shape: (H, W, 3), dtype uint8
    w_in, h_in = img_pil.size

    logger.info(f"Procesando imagen {w_in}x{h_in} con modelo '{model_name}'...")

    # ── Inferencia ────────────────────────────────────────────────────────────
    try:
        # enhance() retorna (output_array BGR, None)
        # Real-ESRGAN trabaja internamente en BGR (herencia de OpenCV)
        output_bgr, _ = upsampler.enhance(img_np[:, :, ::-1], outscale=output_scale)
    except RuntimeError as e:
        # Error común: CUDA out of memory. Reintentamos en CPU con tile más pequeño.
        if "out of memory" in str(e).lower():
            logger.warning("VRAM insuficiente. Reintentando en CPU con tiles pequeños...")
            torch.cuda.empty_cache()
            model_path = _get_model_path(model_name)
            upsampler_cpu = RealESRGANer(
                scale=4,
                model_path=str(model_path),
                model=_build_network(model_name),
                tile=128,      # tile más pequeño para CPU con poca RAM
                tile_pad=TILE_PADDING,
                pre_pad=0,
                half=False,
                device=torch.device("cpu"),
            )
            output_bgr, _ = upsampler_cpu.enhance(img_np[:, :, ::-1], outscale=output_scale)
        else:
            raise RuntimeError(f"Error en la inferencia de Real-ESRGAN: {e}") from e

    # Convertir BGR → RGB para guardar con Pillow
    output_rgb = output_bgr[:, :, ::-1]
    output_pil = Image.fromarray(output_rgb)

    # ── Guardar resultado ─────────────────────────────────────────────────────
    output_pil.save(str(output_path), format="PNG", optimize=False)

    face_enhanced = False
    if face_enhance:
        logger.info("GFPGAN activado. Intentando restauración facial...")
        face_enhanced = enhance_faces(output_path, weight=gfpgan_weight)

    t_end = time.time()

    w_out, h_out = output_pil.size
    duration     = round(t_end - t_loaded, 2)
    size_out_kb  = round(output_path.stat().st_size / 1024, 1)

    logger.info(
        f"Procesamiento completado en {duration}s. "
        f"Resultado: {w_out}x{h_out} px ({size_out_kb} KB)"
    )

    return {
        "device":         device.type,
        "model":          model_name,
        "scale":          output_scale,
        "input_size":     {"width": w_in,  "height": h_in},
        "output_size":    {"width": w_out, "height": h_out},
        "duration_sec":   duration,
        "output_size_kb": size_out_kb,
        "face_enhanced":  face_enhanced,
    }
