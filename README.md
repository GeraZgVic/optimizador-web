# Real-ESRGAN Web — Image Enhancer

Aplicación web para mejorar la calidad de imágenes usando **Real-ESRGAN**.  
Backend en FastAPI + procesamiento con PyTorch. Frontend en HTML/CSS/JS vanilla.

---

## Requisitos del sistema

- Python 3.10 o superior
- pip
- ~1GB de espacio en disco (para los pesos del modelo)
- GPU NVIDIA con CUDA (opcional pero muy recomendado)

---

## Instalación paso a paso

### 1. Clonar / descargar el proyecto

```bash
# Si usas git:
git clone <url-del-repo>
cd realesrgan-web

# O simplemente coloca la carpeta donde quieras y entra a ella.
```

### 2. Crear entorno virtual

```bash
python -m venv venv

# Activar:
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate
```

### 3. Instalar PyTorch

**Este es el paso más importante.** La versión exacta depende de si tienes GPU.

**Con GPU NVIDIA (CUDA 11.8):**
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

**Con GPU NVIDIA (CUDA 12.1):**
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

**Solo CPU (sin GPU):**
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

> Si no sabes qué versión de CUDA tienes, corre: `nvidia-smi`
> El número en la esquina superior derecha es tu versión de CUDA.

### 4. Instalar el resto de dependencias

```bash
pip install -r requirements.txt
```

### 5. Verificar la instalación

```bash
python -c "import torch; print('CUDA:', torch.cuda.is_available(), '| GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"
```

---

## Correr la aplicación

Desde la raíz del proyecto:

```bash
python -m backend.main

.\venv\Scripts\python.exe -m backend.main
```

Abre el navegador en: **http://localhost:8000**

La primera vez que uses un modelo, se descargará automáticamente (~65-130 MB).
Después queda guardado en `backend/models/` y no se vuelve a descargar.

---

## Uso

1. Abre http://localhost:8000
2. Selecciona el modelo que quieras usar:
   - **Fotos x4** — para fotos reales, mejora detalles y nitidez (↑4x resolución)
   - **Fotos x2** — mismo modelo, resultado ↑2x
   - **Anime x4** — optimizado para ilustraciones y anime
3. Arrastra tu imagen o haz clic en el área de subida
4. Haz clic en **Mejorar imagen**
5. Espera el procesamiento (varía según tu hardware)
6. Descarga el resultado como PNG

---

## Límites de la versión actual

| Parámetro | Valor |
|---|---|
| Formatos aceptados | JPG, PNG, WEBP |
| Tamaño máximo | 10 MB |
| Resolución máxima de entrada | ~1225 × 1225 px |
| Archivos temporales | Se borran automáticamente después de 2 horas |

---

## Ajustar parámetros

Todos los parámetros configurables están en `backend/config.py`:

```python
TILE_SIZE          = 256    # Sube a 512 si tienes GPU con 8GB+ VRAM (más rápido)
MAX_FILE_SIZE_MB   = 10     # Límite de tamaño de archivo
MAX_INPUT_PIXELS   = 1_500_000  # Límite de resolución de entrada
CLEANUP_MAX_AGE_HOURS = 2   # Cuánto tiempo se conservan los archivos temporales
```

---

## Estructura del proyecto

```
realesrgan-web/
├── backend/
│   ├── __init__.py
│   ├── main.py          ← FastAPI: endpoints y servidor
│   ├── processor.py     ← Real-ESRGAN: lógica de inferencia
│   ├── config.py        ← todos los parámetros configurables
│   ├── models/          ← pesos .pth descargados automáticamente
│   └── utils/
│       ├── file_handler.py   ← guardar/limpiar archivos
│       └── validator.py      ← validar imágenes
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── tmp/
│   ├── uploads/         ← imágenes subidas (temporales)
│   └── outputs/         ← imágenes procesadas (temporales)
├── requirements.txt
└── README.md
```

---

## API REST

La documentación interactiva está en: **http://localhost:8000/docs**

| Endpoint | Método | Descripción |
|---|---|---|
| `/` | GET | Frontend |
| `/enhance` | POST | Procesar imagen |
| `/download/{filename}` | GET | Descargar resultado |
| `/models` | GET | Listar modelos disponibles |
| `/health` | GET | Estado del servidor y GPU |

---

## Próximos pasos (mejoras sugeridas)

- [X] Agregar slider de comparación antes/después
- [X] Soporte para restauración de caras (GFPGAN)
- [ ] Procesamiento asíncrono con Celery para múltiples usuarios
- [ ] Docker Compose para despliegue en servidor
- [ ] Rate limiting por IP
- [ ] Historial de imágenes procesadas