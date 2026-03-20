# ROADMAP

## Enfoque del proyecto

Este proyecto esta pensado para uso local y privado.

- No esta orientado a despliegue en servidor publico.
- No esta orientado a multiusuario.
- La prioridad es calidad de procesamiento, control local y flujo comodo para un solo usuario.

Por esa razon, el roadmap se reorganiza alrededor del uso real del sistema y no de una arquitectura de red publica.

---

## Estado actual

### Modulos completados

#### Modulo 1 - MVP base de mejora de imagenes

Implementado.

- Stack: FastAPI + Real-ESRGAN + HTML/CSS/JS vanilla.
- FastAPI funcionando con frontend vanilla.
- Real-ESRGAN integrado para imagenes.
- Endpoints base de salud, modelos, mejora y descarga.
- Validacion de imagenes, archivos temporales y descarga automatica de pesos.

Incluye tambien:

- Deteccion automatica GPU/CPU con fallback.
- Tile-based inference para controlar uso de memoria.
- Modelos base `general_x4`, `general_x2` y `anime_x4`.

#### Modulo 2 - Comparador antes / despues

Implementado.

- Comparador visual con divisor arrastrable.
- Soporte para mouse, touch y slider inferior.
- Etiquetas "ORIGINAL" y "MEJORADA".
- Ajuste dinamico de aspect ratio para mostrar la imagen completa.
- Superposicion original/mejorada sin librerias externas.

#### Modulo 3 - Restauracion facial con GFPGAN

Implementado.

- Toggle de "Restaurar caras" para imagenes.
- GFPGAN como post-procesado opcional despues de Real-ESRGAN.
- Descarga lazy del modelo.
- Degradacion silenciosa si GFPGAN falla o no detecta caras.
- Slider de intensidad GFPGAN (`weight`) para imagenes.

Notas operativas:

- `upscale=1` en GFPGAN, porque el escalado ya lo hace Real-ESRGAN.
- El backend retorna si hubo restauracion facial efectiva.
- Ya existe card visual de "Caras restauradas" en el frontend.

#### Modulo 8 - Mejora de video local con cola asincrona

Implementado.

- Subida y procesamiento de videos MP4.
- Pipeline con FFmpeg + Celery + Redis.
- Endpoints de estado y descarga de video procesado.
- Soporte de GFPGAN en video.
- Slider de intensidad GFPGAN tambien disponible para video.

Pipeline implementado:

`video -> FFmpeg extrae frames -> Celery procesa frame por frame -> FFmpeg reensambla -> descarga final`

Incluye ademas:

- `POST /enhance-video`
- `GET /status/{task_id}`
- `GET /download-video/{task_id}`
- Procesamiento por frames con preservacion de audio
- Worker de Windows con `--pool=solo`
- Limpieza de temporales al terminar
- Si un frame falla, se conserva el frame original

Estado real:

- Redis y FFmpeg ya estan integrados localmente
- La infraestructura asincrona ya existe y funciona
- Todavia conviene seguir validando con videos reales de distintos codecs y duraciones

---

## Proximo foco

### Modulo 9 - Face Swap local con FaceFusion

Prioridad: media-alta. Siguiente objetivo real del proyecto.

Prerrequisitos:

- Modulo 8 completo.
- Redis, Celery y FFmpeg ya disponibles localmente.

Contexto:

FaceFusion es la linea natural siguiente para este proyecto. La idea es tomar la identidad facial de una foto origen y transferirla a cada frame de un video destino, preservando pose, expresion e iluminacion del frame original.

Uso previsto:

- Experimental.
- Educativo.
- Creativo.
- Uso estrictamente local.
- Solo con consentimiento explicito de todas las personas involucradas.

#### Pipeline por frame

Entradas:

- `video_destino.mp4` - video donde se reemplaza el rostro
- `foto_origen.jpg` - cara que se quiere insertar

Por cada frame:

1. Deteccion facial
   - RetinaFace o YOLOFace
   - obtiene coordenadas exactas del rostro
   - extrae landmarks faciales
2. Alineacion
   - recorte y normalizacion de ambas caras a resolucion de trabajo
   - correccion de inclinacion y rotacion
3. Swap
   - InSwapper o SimSwap
   - embedding de identidad desde la foto origen
   - mezcla de identidad origen con pose/expresion del frame destino
4. Mejora opcional
   - GFPGAN o CodeFormer sobre la cara generada
5. Blending
   - mascara suave
   - fusion de la cara generada en el frame original
   - ajuste de color para igualar iluminacion

Salida:

- Frame con rostro reemplazado, listo para reensamblar en video final

#### Modelos involucrados

- RetinaFace - deteccion facial precisa - descarga automatica
- YOLOFace - deteccion facial rapida - descarga automatica
- InSwapper_128 - modelo principal de swap - descarga automatica
- GFPGAN v1.4 - mejora facial - ya integrado en el proyecto
- CodeFormer - alternativa a GFPGAN - descarga automatica
- Face parsing - mascaras de fusion mas precisas - descarga automatica

Primera descarga estimada:

- Aproximadamente 700 MB, solo la primera vez

#### Enfoque tecnico recomendado

Opcion A - FaceFusion como subproceso

- Instalar FaceFusion dentro del proyecto en su propio directorio
- Ejecutarlo desde Python via `subprocess`
- Ventaja: menos conflictos de dependencias
- Ventaja: FaceFusion administra sus propios modelos
- Desventaja: menos control fino del pipeline

Opcion B - Librerias integradas directamente

- Importar `onnxruntime` y componentes del pipeline facial desde Python
- Ventaja: mayor control
- Desventaja: integracion y mantenimiento mas complejos

Recomendacion actual:

- Empezar con Opcion A
- Si mas adelante hace falta control granular, migrar o hibridar con Opcion B

#### Dependencias nuevas previstas

- `onnxruntime-gpu`
- `insightface`

Si se usa FaceFusion como subproceso:

- clonar `facefusion`
- instalar sus dependencias
- ejecutar su instalador local

#### Archivos a crear o modificar

Backend:

- `backend/face_swap_processor.py` - nuevo, logica de face swap
- `backend/tasks.py` - agregar `process_face_swap()`
- `backend/main.py` - agregar endpoint `/face-swap` y descarga
- `backend/config.py` - parametros de face swap

Frontend:

- `frontend/index.html` - tercera seccion o tab "Face Swap"
- `frontend/style.css` - estilos del panel
- `frontend/app.js` - upload dual, polling y estados

#### Endpoints previstos

- `POST /face-swap` - recibe video y foto, encola tarea y retorna `task_id`
- `GET /status/{task_id}` - reutiliza el endpoint de estado existente
- `GET /download-swap/{task_id}` - descarga el video final con swap aplicado

Payload esperado:

- `video`
- `source_face`
- `face_enhancer`
- `enhancer_model`
- `detector`
- `blend_ratio`

#### UI prevista

Seccion nueva en la misma pagina, manteniendo el estilo dark industrial.

Navegacion esperada:

- Imagenes
- Video
- Face Swap

Panel izquierdo:

- Drop zone de video destino
- Drop zone de foto origen
- Preview circular de la foto origen
- Selector de detector
- Slider de `blend_ratio`
- Toggle de mejora facial
- Selector `GFPGAN / CodeFormer` si la mejora esta activa
- Boton "Aplicar Face Swap"
- Advertencia de uso con consentimiento

Panel derecho:

- Estado vacio / procesando / completado / error
- Progreso por frames
- Preview del primer frame procesado cuando este disponible
- Stats: frames, tiempo, detector y enhancer
- Boton de descarga final

#### Parametros previstos en config.py

- `FACESWAP_MAX_VIDEO_SIZE_MB = 500`
- `FACESWAP_MAX_VIDEO_DURATION_SEC = 120`
- `FACESWAP_DEFAULT_DETECTOR = "retinaface"`
- `FACESWAP_DEFAULT_BLEND_RATIO = 1.0`
- `FACESWAP_DEFAULT_ENHANCER = "gfpgan"`
- `FACEFUSION_DIR = BASE_DIR / "facefusion"`

#### Tiempos estimados en hardware local potente

Referencia aproximada para una GPU tipo RTX 4070 Ti SUPER:

- 10 segundos a 30 fps: alrededor de 1 a 2 min sin enhancer, 4 a 6 min con enhancer
- 30 segundos a 30 fps: alrededor de 3 a 6 min sin enhancer, 12 a 18 min con enhancer
- 1 minuto a 30 fps: alrededor de 6 a 12 min sin enhancer, 25 a 35 min con enhancer

#### Consideraciones de calidad

Foto origen ideal:

- Resolucion minima recomendada de 512 x 512
- Iluminacion frontal
- Cara visible completa
- Pocas oclusiones
- Expresion neutra

`blend_ratio`:

- `1.0` = swap completo
- `0.7` a `0.8` = reduce flickering
- `0.5` = mezcla mas suave

Flickering entre frames:

- Causa: cada frame se procesa de manera independiente
- Mitigacion: bajar `blend_ratio`
- Mitigacion: usar CodeFormer cuando convenga
- Mitigacion futura: smoothing temporal con FFmpeg

#### Notas operativas para Windows y Celery

- Reutilizar el worker actual de video
- Mantener `--pool=solo` en Windows
- Guardar temporales por tarea
- Limpiar directorios al finalizar
- Si no se detecta cara en un frame, conservar el frame original

#### Diferencias clave respecto a Modulo 8

- Modulo 8 procesa un video como entrada unica; Modulo 9 usa video + foto origen
- Modulo 8 mejora todo el frame; Modulo 9 actua sobre la region facial
- Modulo 8 usa Real-ESRGAN por frame; Modulo 9 usa swap + blending
- Modulo 8 es mas predecible; Modulo 9 depende mucho de la calidad de la foto origen

---

## Modulos pospuestos

### Modulo 4 - Procesamiento por lote

Pospuesto.

No es prioridad para uso local de un solo usuario. Se puede retomar despues de cerrar el flujo principal de imagen, video y face swap.

Contexto funcional:

- Permitir subir multiples imagenes a la vez.
- Mostrar una cola visual con estado individual por imagen.
- Ofrecer progreso global del lote.
- Permitir descarga individual apenas cada imagen termine.
- Permitir "Descargar todo" sin tocar backend, generando ZIP desde frontend.

Comportamiento esperado:

- Procesamiento secuencial, no paralelo, para evitar competencia por VRAM.
- Estados por item: esperando, procesando, completada, error.
- Resumen global tipo `3 / 7`.

Cambios estimados:

- `frontend/index.html` - drop zone multiarchivo y lista de cola
- `frontend/style.css` - estados visuales del lote
- `frontend/app.js` - cola secuencial y generacion ZIP
- `backend/` - en principio sin cambios, reutilizando `/enhance`

Dependencia prevista:

- `JSZip` en frontend

### Modulo 5 - Procesamiento asincrono para imagenes (Celery + Redis)

Pospuesto.

La infraestructura asincrona ya existe por el trabajo de video, pero el flujo de imagen actual funciona bien en modo directo para uso local.

Contexto funcional:

- Hacer que tambien las imagenes puedan entrar a una cola de tareas.
- Responder con `task_id` inmediato en vez de esperar toda la inferencia en la peticion HTTP.
- Usar polling desde frontend como ya se hace en video.

Comportamiento esperado:

- `POST /enhance` retorna `task_id`
- `GET /status/{task_id}` informa progreso y estado
- Worker Celery procesa la imagen en segundo plano

Cambios estimados:

- `backend/tasks.py` - task especifica para imagenes
- `backend/main.py` - ajuste del endpoint `/enhance`
- `frontend/app.js` - polling y transicion de estados
- `requirements.txt` - ya cubierto hoy por el trabajo previo de video
- Redis reutilizado como broker de mensajes

Nota actual:

- La infraestructura base ya existe gracias al Modulo 8, por eso este modulo ya no es tecnico-dificil, solo no es prioritario hoy

### Modulo 6 - Docker Compose

Pospuesto.

Como el sistema no se desplegara a servidor publico por ahora, Docker deja de ser urgente y pasa a ser una mejora futura opcional.

Contexto funcional:

- Empaquetar app, Redis y dependencias de forma reproducible.
- Facilitar reinstalacion o migracion a otra maquina.
- Mantener volumen persistente para pesos descargados.

Alcance previsto si se retoma:

- `Dockerfile` para FastAPI
- `docker-compose.yml` con app + redis
- variables en `.env`
- volumen persistente para `backend/models/`
- instrucciones de arranque local o VPS

Nota de prioridad:

- Como el uso es local y en una sola maquina, este modulo se mueve al fondo de la cola

### Modulo 7 - Mejoras avanzadas y pulido

Pospuesto parcialmente.

Ya se implemento:

- Slider de intensidad GFPGAN.

Queda pendiente para una fase posterior:

- Rate limiting por IP con `slowapi`
- Historial de imagenes procesadas con SQLite
- Mas modelos ESRGAN.
- Comparador con zoom.
- Exportaciones adicionales.

Contexto general:

- Este modulo agrupa mejoras de experiencia, control y variedad de salida.
- No bloquea el uso real actual del sistema.
- Varias de estas mejoras tienen mas sentido despues de cerrar Modulo 9.

Ideas previstas:

- Historial local con miniaturas, fecha, modelo y tiempo
- Soporte adicional para anime-video, SwinIR u otros modelos
- Comparador con zoom para inspeccion fina de detalles
- Exportacion en JPEG y WEBP con calidad configurable

---

## Decisiones de arquitectura vigentes

- Imagenes: procesamiento directo, simple y rapido para uso local.
- Videos: procesamiento asincrono con Celery + Redis por ser tareas largas.
- Modelos: descarga lazy para mantener el repo limpio.
- Frontend: HTML, CSS y JS vanilla, sin frameworks externos.
- Despliegue esperado: maquina local del usuario.

---

## Entorno actual del proyecto

- Backend: FastAPI
- Frontend: HTML + CSS + JS vanilla
- Upscaling: Real-ESRGAN
- Restauracion facial: GFPGAN
- Video: FFmpeg
- Cola de tareas: Celery + Redis
- Ejecucion objetivo: Windows local con GPU NVIDIA

---

## Resumen de prioridad

1. Modulo 9 - Face Swap local con FaceFusion
2. Ajustes y estabilizacion del flujo local
3. Retomar modulos 4, 5, 6 y 7 solo si hacen falta mas adelante
