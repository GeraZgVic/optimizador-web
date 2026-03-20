# Real-ESRGAN Web — Image & Video Enhancer

Aplicación web para mejorar imágenes y videos con **Real-ESRGAN**, con
restauración facial opcional usando **GFPGAN**.

Stack actual:
- Backend: FastAPI + PyTorch
- Cola asíncrona para video: Celery + Redis
- Frontend: HTML/CSS/JS vanilla
- Video pipeline: FFmpeg

---

## Funcionalidades actuales

### Imágenes
- Upscaling con Real-ESRGAN
- Modelos disponibles:
  - `general_x4`
  - `general_x2`
  - `anime_x4`
- Comparador antes/después con slider
- Restauración facial opcional con GFPGAN
- Detección automática GPU / CPU
- Descarga automática de pesos `.pth`

### Videos
- Subida de `.mp4`, `.avi`, `.mov`, `.mkv`
- Procesamiento asíncrono con Celery
- Extracción y reensamblado de frames con FFmpeg
- Polling de progreso desde el frontend
- Restauración facial opcional frame por frame
- Preservación de audio en el video final

---

## Requisitos del sistema

- Python 3.10 o superior
- pip
- Redis instalado y corriendo
- FFmpeg instalado
- GPU NVIDIA con CUDA opcional, pero muy recomendada

En Windows, este proyecto fue preparado para correr con:
- Redis on Windows
- FFmpeg instalado vía WinGet

---

## Instalación

### 1. Entrar al proyecto

```bash
cd realesrgan-web
```

### 2. Crear entorno virtual

```bash
python -m venv venv
```

Activar:

```bash
# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Instalar PyTorch

Instala primero la variante correcta para tu sistema.

#### GPU NVIDIA con CUDA 12.1

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

#### Solo CPU

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

Verificación:

```bash
python -c "import torch; print('CUDA:', torch.cuda.is_available(), '| GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"
```

### 4. Instalar dependencias del proyecto

```bash
pip install -r requirements.txt
```

---

## Prerrequisitos para video

El módulo de video requiere:

### Redis

Verificar:

```bash
redis-cli ping
```

Debe responder:

```text
PONG
```

### FFmpeg

Verificar:

```bash
ffmpeg -version
ffprobe -version
```

---

## Cómo correr la aplicación

## Opción 1 — Solo imágenes

Si vas a trabajar solo con imágenes:

```powershell
.\venv\Scripts\python.exe -m backend.main
```

Abrir:

```text
http://localhost:8000
```

## Opción 2 — Imágenes + video

Para video necesitas FastAPI y Celery en terminales separadas.

### Terminal 1 — FastAPI

```powershell
.\venv\Scripts\python.exe -m backend.main
```

### Terminal 2 — Celery worker

```powershell
.\venv\Scripts\celery.exe -A backend.tasks worker --pool=solo -l info
```

Importante en Windows:
- `--pool=solo` es obligatorio
- Redis debe estar corriendo antes de iniciar Celery

Luego abre:

```text
http://localhost:8000
```

---

## Uso

## Imágenes

1. Abre `http://localhost:8000`
2. Elige modelo
3. Opcional: activa `Restaurar caras`
4. Sube una imagen
5. Haz clic en `Mejorar imagen`
6. Usa el comparador antes/después
7. Descarga el PNG final

## Videos

1. Sube un video en la sección `video`
2. Elige escala `×2` o `×4`
3. Opcional: activa `Restaurar caras`
4. Haz clic en `Mejorar video`
5. Espera el avance del polling
6. Descarga el `.mp4` final cuando termine

---

## Límites actuales

### Imágenes

| Parámetro | Valor |
|---|---|
| Formatos | JPG, PNG, WEBP |
| Tamaño máximo | 10 MB |
| Resolución máxima | configurable en `backend/config.py` |

### Videos

| Parámetro | Valor |
|---|---|
| Formatos | MP4, AVI, MOV, MKV |
| Tamaño máximo | 500 MB |
| Duración máxima | 120 s |
| Resolución máxima | 1280 px lado mayor |

---

## Configuración importante

Todo está centralizado en [backend/config.py](./backend/config.py).

Parámetros relevantes:

```python
TILE_SIZE = 256
MAX_FILE_SIZE_MB = 10
MAX_INPUT_PIXELS = 2_000_000
CLEANUP_MAX_AGE_HOURS = 2

MAX_VIDEO_SIZE_MB = 500
MAX_VIDEO_DURATION_SEC = 120
MAX_VIDEO_RESOLUTION = 1280
VIDEO_FPS_OUTPUT = None

CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
```

---

## Endpoints disponibles

La documentación interactiva está en:

```text
http://localhost:8000/docs
```

| Endpoint | Método | Descripción |
|---|---|---|
| `/` | GET | Frontend |
| `/health` | GET | Estado del servidor y GPU |
| `/models` | GET | Modelos disponibles |
| `/enhance` | POST | Procesar imagen |
| `/download/{filename}` | GET | Descargar imagen procesada |
| `/enhance-video` | POST | Encolar procesamiento de video |
| `/status/{task_id}` | GET | Estado de tarea de video |
| `/download-video/{task_id}` | GET | Descargar video procesado |

---

## Estructura del proyecto

```text
realesrgan-web/
├── backend/
│   ├── __init__.py
│   ├── config.py
│   ├── main.py
│   ├── processor.py
│   ├── tasks.py
│   ├── video_processor.py
│   ├── models/
│   └── utils/
│       ├── file_handler.py
│       └── validator.py
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── tmp/
│   ├── uploads/
│   ├── outputs/
│   └── videos/
├── requirements.txt
├── ROADMAP.md
└── README.md
```

---

## Notas operativas

- La primera vez que uses Real-ESRGAN o GFPGAN, descargará los pesos automáticamente.
- GFPGAN es opcional y degrada silenciosamente si falla o no detecta caras.
- El procesamiento de video puede tardar varios minutos.
- Si un frame de video falla, el pipeline lo loggea y continúa.
- Los temporales de video se limpian al terminar la tarea.

---

## Estado del proyecto

Módulos implementados:
- Módulo 1 — MVP base
- Módulo 2 — Comparador antes/después
- Módulo 3 — Restauración de caras con GFPGAN
- Módulo 8 — Upscaling de video con Celery + Redis + FFmpeg

Para roadmap detallado:
- [ROADMAP.md](./ROADMAP.md)
