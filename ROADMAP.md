# ROADMAP.md — Real-ESRGAN Web

Hoja de ruta del proyecto. Registra módulos completados, pendientes y decisiones de arquitectura tomadas en el camino.

---

## Módulos completados

### ✅ Módulo 1 — MVP base
**Stack:** FastAPI + Real-ESRGAN (PyTorch) + HTML/CSS/JS vanilla. Sin Docker, sin Celery.

Incluye:
- Endpoint `POST /enhance` — recibe imagen, procesa, retorna metadatos
- Endpoint `GET /download/{filename}` — descarga resultado
- Endpoint `GET /models` — lista modelos disponibles
- Endpoint `GET /health` — estado del servidor y GPU
- Detección automática GPU/CPU con fallback
- Descarga automática de pesos `.pth` (primera vez)
- Tile-based inference (funciona con poca VRAM/RAM)
- Validación de archivos (extensión, tamaño, contenido real)
- Limpieza automática de archivos temporales (+2h)
- Frontend: drop zone, preview, selector de modelo, stats, descarga

Modelos disponibles:
- `general_x4` — RealESRGAN_x4plus, fotos y uso general ×4
- `general_x2` — RealESRGAN_x4plus, fotos y uso general ×2
- `anime_x4`   — RealESRGAN_x4plus_anime_6B, ilustraciones ×4

---

### ✅ Módulo 2 — Slider de comparación antes/después
**Técnica:** `clip-path: inset()` sobre la imagen mejorada. Sin librerías externas.

Incluye:
- Imagen original y mejorada superpuestas en el mismo contenedor
- Divisor arrastrable con mouse y touch (mobile)
- Input range sincronizado con el arrastre
- `aspect-ratio` dinámico calculado desde JS según dimensiones reales de la imagen
- Etiquetas ORIGINAL / MEJORADA sobre cada lado
- `object-fit: contain` + `max-height: 70vh` para imágenes de cualquier proporción
- Cero cambios al backend

---

### ✅ Módulo 3 — Restauración de caras con GFPGAN
**Flujo:** Real-ESRGAN primero → GFPGAN encima (opcional).

Incluye:
- Toggle "Restaurar caras" en el panel izquierdo (OFF por defecto)
- Descripción: "GFPGAN — recomendado para fotos de personas"
- Descarga lazy del modelo GFPGANv1.4 (~81MB) solo si el usuario activa el toggle
- `upscale=1` — GFPGAN solo restaura, no escala (Real-ESRGAN ya escaló)
- Si no detecta caras: continúa sin error, devuelve resultado de Real-ESRGAN
- Si GFPGAN falla: degradación silenciosa, nunca rompe la petición
- Stat card extra "CARAS — Restauradas" cuando GFPGAN actúa
- Parámetro `face_enhance` enviado en FormData desde el frontend

Tiempos observados (RTX 4070 Ti SUPER):
- Solo Real-ESRGAN: ~0.4s
- Real-ESRGAN + GFPGAN (primera vez, con descarga): ~54s
- Real-ESRGAN + GFPGAN (modelos en caché): ~2-4s estimado

---

### ✅ Módulo 8 — Upscaling de video
**Prioridad:** Alta
**Arquitectura:** Celery + Redis + FFmpeg

#### Pipeline implementado
```
video.mp4 (upload)
  → FFmpeg extrae frames → /tmp/videos/{task_id}/frames/frame_000001.png ...
  → Celery worker procesa cada frame con Real-ESRGAN (+ GFPGAN opcional)
  → FFmpeg reensambla frames y preserva el audio original
  → /tmp/outputs/{task_id}_enhanced.mp4
  → Usuario descarga el video final
```

Incluye:
- Endpoint `POST /enhance-video` para encolar videos
- Endpoint `GET /status/{task_id}` para polling de progreso
- Endpoint `GET /download-video/{task_id}` para descargar el resultado
- `backend/tasks.py` con Celery app + task `process_video`
- `backend/video_processor.py` con validación, FFprobe, FFmpeg y loop de frames
- Panel de video separado en el frontend
- Drop zone para `.mp4`, `.avi`, `.mov`, `.mkv`
- Selector de escala `×2` / `×4`
- Toggle `Restaurar caras` también para video
- Barra de progreso con `frame actual / total`
- Polling cada 3 segundos
- Limpieza de temporales al finalizar
- Si un frame falla: se loggea y se conserva el frame original

Prerrequisitos ya integrados:
- Redis instalado y validado con `redis-cli ping`
- FFmpeg y FFprobe instalados y detectados desde config
- Worker de Windows usando `--pool=solo`

Comandos de arranque:

```powershell
.\venv\Scripts\python.exe -m backend.main
.\venv\Scripts\celery.exe -A backend.tasks worker --pool=solo -l info
```

Limitaciones actuales:
- El flujo fue implementado, pero todavía conviene validar con videos reales de distintos codecs
- El polling es básico; aún no hay cancelación de tareas
- El resultado de video se genera en `.mp4` con `libx264` + audio AAC

---

## Módulos pendientes

### 🔲 Módulo 4 — Procesamiento por lote
**Prioridad:** Alta

Descripción:
- Subir múltiples imágenes a la vez
- Cola visual con estado individual por imagen (esperando / procesando / completada / error)
- Barra de progreso global (ej: 3/7)
- Descarga individual disponible en cuanto cada imagen termina
- Botón "Descargar todo" genera un ZIP en el frontend con JSZip (sin tocar el backend)
- Las imágenes se procesan en secuencia, no en paralelo (evita competencia por VRAM)

Cambios estimados:
- `frontend/index.html` — drop zone multi-archivo + lista de cola
- `frontend/style.css` — estilos de la lista y estados
- `frontend/app.js` — lógica de cola secuencial + generación de ZIP
- `backend/` — sin cambios (el endpoint `/enhance` ya soporta una imagen a la vez)

Dependencia nueva: `JSZip` (CDN, solo frontend)

---

### 🔲 Módulo 5 — Procesamiento asíncrono para imágenes
**Prioridad:** Media

Descripción:
- Reemplaza también el procesamiento síncrono de imágenes por una cola de tareas
- El endpoint `/enhance` retorna un `task_id` inmediatamente
- El frontend hace polling a `GET /status/{task_id}` cada 2 segundos
- Workers Celery procesan las imágenes en background
- Redis ya está integrado por el Módulo 8

Cambios estimados:
- `backend/tasks.py` — agregar task específica para imágenes
- `backend/main.py` — endpoints `/status/{task_id}` y ajuste de `/enhance`
- `frontend/app.js` — lógica de polling
- Reutiliza la infraestructura ya montada

---

### 🔲 Módulo 6 — Docker Compose
**Prioridad:** Baja — para despliegue en servidor o compartir la herramienta

Descripción:
- `Dockerfile` para la app FastAPI
- `docker-compose.yml` con servicios: app + redis (si ya está el Módulo 5)
- Variables de entorno en `.env`
- Volumen persistente para `backend/models/` (no re-descargar pesos en cada deploy)
- Instrucciones de despliegue en VPS (Hetzner / DigitalOcean)

---

### 🔲 Módulo 7 — Mejoras futuras (sin fecha)

- [ ] Slider de intensidad GFPGAN (parámetro `weight` 0.0–1.0 expuesto en UI)
- [ ] Rate limiting por IP con `slowapi`
- [ ] Historial de imágenes procesadas (SQLite)
- [ ] Soporte para más modelos (ESRGAN-anime-video, SwinIR)
- [ ] Comparador con zoom (ver detalle de píxeles)
- [ ] Exportar en formatos adicionales (JPEG con calidad configurable, WEBP)

---

## Decisiones de arquitectura

| Decisión | Elegido | Alternativa descartada | Razón |
|---|---|---|---|
| Backend | FastAPI | Flask | Async nativo, validación con Pydantic, docs automáticas |
| Cola de tareas | Síncrono (por ahora) | Celery desde el inicio | YAGNI — para uso personal no hace falta |
| Frontend | JS vanilla | React | Sin build step, menos dependencias |
| Almacenamiento | Disco local `/tmp` | S3 / MinIO | Suficiente para uso local/personal |
| Inferencia | Tile-based (256px) | Full image | Funciona con cualquier VRAM |
| ZIP frontend | JSZip (CDN) | ZIP en backend | No carga el servidor, más simple |

---

## Entorno de desarrollo actual

- GPU: NVIDIA GeForce RTX 4070 Ti SUPER
- OS: Windows
- Python: venv local
- Sin Docker
- Servidor: `python -m backend.main` (uvicorn con reload)

---

