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

### 🔲 Módulo 5 — Procesamiento asíncrono (Celery + Redis)
**Prioridad:** Media — necesario para múltiples usuarios simultáneos

Descripción:
- Reemplaza el procesamiento síncrono por una cola de tareas
- El endpoint `/enhance` retorna un `task_id` inmediatamente
- El frontend hace polling a `GET /status/{task_id}` cada 2 segundos
- Workers Celery procesan las imágenes en background
- Redis como broker de mensajes

Cambios estimados:
- `backend/tasks.py` — nuevo archivo con las Celery tasks
- `backend/main.py` — endpoints `/status/{task_id}` y ajuste de `/enhance`
- `frontend/app.js` — lógica de polling
- `requirements.txt` — agregar `celery`, `redis`
- Requiere Redis corriendo localmente

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

### 🔲 Módulo 8 — Upscaling de video
**Prioridad:** Alta — siguiente módulo a implementar
**Prerrequisitos:** Redis + FFmpeg instalados en el sistema

#### Contexto y decisión de arquitectura
El procesamiento síncrono del Módulo 1 NO es viable para video. Un video de
30 segundos a 30fps = 900 frames × ~0.4s = ~6 minutos de procesamiento.
FastAPI/HTTP no puede mantener una petición abierta ese tiempo.
Por eso este módulo introduce Celery + Redis obligatoriamente.

#### Pipeline completo
```
video.mp4 (upload)
  → FFmpeg extrae frames → /tmp/video_{id}/frames/frame_0001.png ...
  → Celery worker procesa cada frame con Real-ESRGAN (+ GFPGAN opcional)
  → FFmpeg reensambla frames → /tmp/outputs/video_{id}_enhanced.mp4
  → Usuario descarga el video final
```

#### Stack nuevo requerido
- **Redis** — broker de mensajes para Celery
  - Windows: https://github.com/microsoftarchive/redis/releases
  - Ejecutar: redis-server.exe
  - Verificar: redis-cli ping → debe responder PONG
- **FFmpeg** — extracción y reensamblado de frames
  - Windows: https://ffmpeg.org/download.html → agregar al PATH
  - Verificar: ffmpeg -version
- **Celery** — worker de tareas asíncronas
  - pip install celery redis

#### Archivos a crear / modificar
```
backend/
  tasks.py             ← NUEVO — Celery app + task process_video()
  video_processor.py   ← NUEVO — lógica FFmpeg + loop de frames
  main.py              ← MODIFICAR — nuevos endpoints de video
  config.py            ← MODIFICAR — parámetros de video y Celery
frontend/
  index.html           ← MODIFICAR — sección nueva para video
  style.css            ← MODIFICAR — estilos del panel de video
  app.js               ← MODIFICAR — upload video + polling de progreso
requirements.txt       ← MODIFICAR — agregar celery, redis
```

#### Endpoints nuevos
- POST /enhance-video   → recibe video, encola tarea, retorna task_id inmediatamente
- GET  /status/{task_id} → estado: pending/processing/done/error + frame N/total
- GET  /download-video/{task_id} → descarga el video procesado

#### UI — panel de video
- Sección separada del panel de imágenes (no mezclar flujos)
- Drop zone para .mp4, .avi, .mov, .mkv
- Selector de escala (×2 o ×4) y toggle "Restaurar caras"
- Límite recomendado: 720p máximo, <2 minutos (ajustable en config.py)
- Barra de progreso real: "Frame 342 / 900 — 38%"
- Polling cada 3 segundos a /status/{task_id}
- Advertencia visible: "El procesamiento puede tardar varios minutos"

#### Tiempos estimados (RTX 4070 Ti SUPER)
- 10s a 30fps  →  300 frames  →  ~2-3 min
- 30s a 30fps  →  900 frames  →  ~6-8 min
- 1min a 30fps → 1800 frames  →  ~12-15 min
- Con GFPGAN activo: ×3-4x más lento

#### Parámetros a agregar en config.py
```python
MAX_VIDEO_SIZE_MB      = 500
MAX_VIDEO_DURATION_SEC = 120
MAX_VIDEO_RESOLUTION   = 1280
VIDEO_FPS_OUTPUT       = None   # None = mismo fps que el original
CELERY_BROKER_URL      = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND  = "redis://localhost:6379/0"
```

#### Notas críticas para Celery en Windows
- El worker se lanza con: celery -A backend.tasks worker --pool=solo -l info
- --pool=solo es OBLIGATORIO en Windows (los otros pools no funcionan)
- Celery y FastAPI deben correr en terminales SEPARADAS
- FFmpeg debe preservar el audio original en el reensamblado
- Codec de salida: libx264 con crf=18 (alta calidad, tamaño razonable)
- Si un frame falla: loggearlo y continuar, no abortar todo el video
- Los frames temporales se guardan en /tmp/video_{task_id}/frames/ y se limpian al terminar