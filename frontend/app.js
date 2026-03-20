/**
 * app.js — Lógica del frontend.
 *
 * Responsabilidades:
 *  1. Cargar modelos disponibles desde la API y renderizar el selector
 *  2. Consultar el estado del device (GPU/CPU) para mostrarlo en el header
 *  3. Manejo del drag-and-drop y selección de archivo
 *  4. Enviar la imagen al endpoint /enhance
 *  5. Mostrar progreso, resultado y estadísticas
 *  6. Manejar errores con mensajes claros al usuario
 */

const API = '';   // Vacío = mismo origen. Cambia a 'http://localhost:8000' si corres frontend por separado.

// ── Referencias al DOM ────────────────────────────────────────────────────────
const dropzone       = document.getElementById('dropzone');
const fileInput      = document.getElementById('file-input');
const dropzoneMeta   = document.getElementById('dropzone-meta');
const previewWrap    = document.getElementById('preview-wrap');
const previewImg     = document.getElementById('preview-img');
const btnClear       = document.getElementById('btn-clear');
const btnEnhance     = document.getElementById('btn-enhance');
const btnLabel       = document.getElementById('btn-label');
const modelGrid      = document.getElementById('model-grid');
const deviceBadge    = document.getElementById('device-badge');
const faceEnhanceToggle = document.getElementById('face-enhance-toggle');
const gfpganIntensity = document.getElementById('gfpgan-intensity');
const gfpganWeightInput = document.getElementById('gfpgan-weight');
const gfpganWeightValue = document.getElementById('gfpgan-weight-value');
const videoDropzone  = document.getElementById('video-dropzone');
const videoInput     = document.getElementById('video-input');
const videoDropzoneMeta = document.getElementById('video-dropzone-meta');
const videoScaleSelect = document.getElementById('video-scale');
const videoFaceEnhanceToggle = document.getElementById('video-face-enhance-toggle');
const videoGfpganIntensity = document.getElementById('video-gfpgan-intensity');
const videoGfpganWeightInput = document.getElementById('video-gfpgan-weight');
const videoGfpganWeightValue = document.getElementById('video-gfpgan-weight-value');
const btnEnhanceVideo = document.getElementById('btn-enhance-video');
const btnVideoLabel = document.getElementById('btn-video-label');

const resultEmpty    = document.getElementById('result-empty');
const resultProgress = document.getElementById('result-progress');
const resultDone     = document.getElementById('result-done');
const resultError    = document.getElementById('result-error');
const progressLabel  = document.getElementById('progress-label');
const resultStats    = document.getElementById('result-stats');
const btnDownload    = document.getElementById('btn-download');
const resultErrorMsg = document.getElementById('result-error-msg');
const btnRetry       = document.getElementById('btn-retry');
const videoStatusEmpty = document.getElementById('video-status-empty');
const videoStatusProgress = document.getElementById('video-status-progress');
const videoStatusDone = document.getElementById('video-status-done');
const videoStatusError = document.getElementById('video-status-error');
const videoProgressTitle = document.getElementById('video-progress-title');
const videoProgressPercent = document.getElementById('video-progress-percent');
const videoProgressFill = document.getElementById('video-progress-fill');
const videoProgressCopy = document.getElementById('video-progress-copy');
const videoDoneCopy = document.getElementById('video-done-copy');
const btnDownloadVideo = document.getElementById('btn-download-video');
const videoErrorMsg = document.getElementById('video-error-msg');

// ── Estado de la app ──────────────────────────────────────────────────────────
let selectedFile  = null;
let selectedModel = null;   // se setea cuando cargan los modelos
let isProcessing  = false;
let faceEnhanceEnabled = false;
let gfpganWeight = 0.5;
let compareValue  = 50;
let compareDragActive = false;
let selectedVideoFile = null;
let isVideoProcessing = false;
let videoPollingTimer = null;
let videoGfpganWeight = 0.5;

function getCompareElements() {
  return {
    viewer: document.getElementById('compare-viewer'),
    overlay: document.getElementById('compare-overlay'),
    divider: document.getElementById('compare-divider'),
    range: document.getElementById('compare-range'),
    originalImg: document.getElementById('compare-original-img'),
    enhancedImg: document.getElementById('compare-enhanced-img'),
  };
}

// ── 1. Inicialización ─────────────────────────────────────────────────────────

async function init() {
  await Promise.all([loadModels(), loadDeviceInfo()]);
}

async function loadModels() {
  try {
    const res    = await fetch(`${API}/models`);
    const models = await res.json();

    modelGrid.innerHTML = '';

    Object.entries(models).forEach(([key, model], i) => {
      const card = document.createElement('div');
      card.className   = 'model-card' + (i === 0 ? ' active' : '');
      card.dataset.key = key;
      card.innerHTML   = `
        <div class="model-card-dot"></div>
        <div class="model-card-info">
          <div class="model-card-name">${model.description.split('—')[0].trim()}</div>
          <div class="model-card-desc">${model.description.split('—')[1]?.trim() ?? ''}</div>
        </div>
        <div class="model-card-scale">×${model.scale}</div>
      `;
      card.addEventListener('click', () => selectModel(key));
      modelGrid.appendChild(card);

      if (i === 0) selectedModel = key;
    });
  } catch (e) {
    modelGrid.innerHTML = '<div style="color:var(--text-3);font-size:.8rem">No se pudo conectar con la API</div>';
  }
}

async function loadDeviceInfo() {
  try {
    const res  = await fetch(`${API}/health`);
    const data = await res.json();

    if (data.cuda && data.gpu) {
      deviceBadge.textContent = `GPU — ${data.gpu}`;
      deviceBadge.classList.add('gpu');
    } else {
      deviceBadge.textContent = 'CPU — sin GPU detectada';
      deviceBadge.classList.add('cpu');
    }
  } catch {
    deviceBadge.textContent = 'API no disponible';
  }
}

// ── 2. Selección de modelo ────────────────────────────────────────────────────

function selectModel(key) {
  selectedModel = key;
  document.querySelectorAll('.model-card').forEach(card => {
    card.classList.toggle('active', card.dataset.key === key);
  });
}

// ── 3. Drag & Drop + selección de archivo ────────────────────────────────────

dropzone.addEventListener('click', () => fileInput.click());

dropzone.addEventListener('dragover', e => {
  e.preventDefault();
  dropzone.classList.add('drag-over');
});

dropzone.addEventListener('dragleave', () => {
  dropzone.classList.remove('drag-over');
});

dropzone.addEventListener('drop', e => {
  e.preventDefault();
  dropzone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) setFile(file);
});

fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) setFile(fileInput.files[0]);
});

function setFile(file) {
  // Validación básica en el cliente (el server también valida)
  const allowed = ['image/jpeg', 'image/png', 'image/webp'];
  if (!allowed.includes(file.type)) {
    showDropzoneError('Formato no permitido. Usa JPG, PNG o WEBP.');
    return;
  }

  const maxMB = 10;
  if (file.size > maxMB * 1024 * 1024) {
    showDropzoneError(`El archivo supera los ${maxMB} MB.`);
    return;
  }

  selectedFile = file;

  // Mostrar preview
  const reader = new FileReader();
  reader.onload = e => {
    previewImg.src = e.target.result;
    previewWrap.style.display = 'block';
    dropzone.style.display    = 'none';
  };
  reader.readAsDataURL(file);

  // Actualizar metadatos en el dropzone
  const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
  dropzoneMeta.textContent = `${file.name} — ${sizeMB} MB`;

  btnEnhance.disabled = false;
  showResultState('empty');
}

function showDropzoneError(msg) {
  dropzoneMeta.style.color = 'var(--danger)';
  dropzoneMeta.textContent = msg;
  setTimeout(() => {
    dropzoneMeta.style.color = '';
    dropzoneMeta.textContent = '';
  }, 3000);
}

btnClear.addEventListener('click', clearFile);
btnRetry.addEventListener('click', clearFile);

function clearFile() {
  selectedFile        = null;
  fileInput.value     = '';
  previewWrap.style.display = 'none';
  dropzone.style.display    = '';
  previewImg.src            = '';
  dropzoneMeta.textContent  = '';
  btnEnhance.disabled       = true;
  showResultState('empty');
}

faceEnhanceToggle.addEventListener('change', event => {
  faceEnhanceEnabled = event.target.checked;
  gfpganIntensity.style.display = faceEnhanceEnabled ? '' : 'none';
});

gfpganWeightInput.addEventListener('input', event => {
  gfpganWeight = Number(event.target.value);
  gfpganWeightValue.textContent = gfpganWeight.toFixed(1);
});

videoFaceEnhanceToggle.addEventListener('change', event => {
  videoGfpganIntensity.style.display = event.target.checked ? '' : 'none';
});

videoGfpganWeightInput.addEventListener('input', event => {
  videoGfpganWeight = Number(event.target.value);
  videoGfpganWeightValue.textContent = videoGfpganWeight.toFixed(1);
});

function showVideoState(state, options = {}) {
  videoStatusEmpty.style.display = state === 'empty' ? '' : 'none';
  videoStatusProgress.style.display = state === 'progress' ? '' : 'none';
  videoStatusDone.style.display = state === 'done' ? '' : 'none';
  videoStatusError.style.display = state === 'error' ? '' : 'none';

  if (state === 'progress') {
    videoProgressTitle.textContent = options.title || 'Procesando video…';
    videoProgressPercent.textContent = `${options.percent ?? 0}%`;
    videoProgressFill.style.width = `${options.percent ?? 0}%`;
    videoProgressCopy.textContent = options.copy || 'Esperando respuesta del worker…';
  }

  if (state === 'done') {
    videoDoneCopy.textContent = options.copy || 'El video mejorado está disponible para descarga.';
  }

  if (state === 'error') {
    videoErrorMsg.textContent = options.copy || 'No se pudo procesar el video.';
  }
}

function clearVideoPolling() {
  if (!videoPollingTimer) return;
  clearInterval(videoPollingTimer);
  videoPollingTimer = null;
}

function setVideoFile(file) {
  const allowed = ['video/mp4', 'video/x-msvideo', 'video/quicktime', 'video/x-matroska'];
  const allowedByExt = /\.(mp4|avi|mov|mkv)$/i.test(file.name);
  if (!(allowed.includes(file.type) || allowedByExt)) {
    videoDropzoneMeta.style.color = 'var(--danger)';
    videoDropzoneMeta.textContent = 'Formato no permitido. Usa MP4, AVI, MOV o MKV.';
    return;
  }

  selectedVideoFile = file;
  const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
  videoDropzoneMeta.style.color = '';
  videoDropzoneMeta.textContent = `${file.name} — ${sizeMB} MB`;
  btnEnhanceVideo.disabled = false;
  showVideoState('empty');
}

videoDropzone.addEventListener('click', () => videoInput.click());
videoDropzone.addEventListener('dragover', event => {
  event.preventDefault();
  videoDropzone.classList.add('drag-over');
});
videoDropzone.addEventListener('dragleave', () => {
  videoDropzone.classList.remove('drag-over');
});
videoDropzone.addEventListener('drop', event => {
  event.preventDefault();
  videoDropzone.classList.remove('drag-over');
  const file = event.dataTransfer.files[0];
  if (file) setVideoFile(file);
});
videoInput.addEventListener('change', () => {
  if (videoInput.files[0]) setVideoFile(videoInput.files[0]);
});

btnEnhanceVideo.addEventListener('click', async () => {
  if (!selectedVideoFile || isVideoProcessing) return;
  await processVideo();
});

async function processVideo() {
  isVideoProcessing = true;
  btnEnhanceVideo.disabled = true;
  btnEnhanceVideo.classList.add('loading');
  btnVideoLabel.textContent = 'Encolando video…';

  const formData = new FormData();
  formData.append('file', selectedVideoFile);
  formData.append('scale', videoScaleSelect.value);
  formData.append('face_enhance', videoFaceEnhanceToggle.checked ? 'true' : 'false');
  formData.append('gfpgan_weight', videoGfpganWeight.toFixed(1));

  try {
    const res = await fetch(`${API}/enhance-video`, {
      method: 'POST',
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || `Error ${res.status}`);
    }

    showVideoState('progress', {
      title: 'Video en cola',
      percent: 0,
      copy: 'La tarea fue enviada al worker. Iniciando seguimiento…',
    });
    startVideoPolling(data.task_id);
  } catch (error) {
    showVideoState('error', { copy: error.message });
    isVideoProcessing = false;
    btnEnhanceVideo.disabled = false;
    btnEnhanceVideo.classList.remove('loading');
    btnVideoLabel.textContent = 'Mejorar video';
  }
}

function startVideoPolling(taskId) {
  clearVideoPolling();
  const poll = async () => {
    try {
      const res = await fetch(`${API}/status/${taskId}`);
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `Error ${res.status}`);
      }

      if (data.state === 'pending') {
        showVideoState('progress', {
          title: 'Video en cola',
          percent: 0,
          copy: 'Esperando a que el worker tome la tarea…',
        });
        return;
      }

      if (data.state === 'processing') {
        showVideoState('progress', {
          title: 'Procesando video',
          percent: Math.round(data.progress_percent || 0),
          copy: data.message || `Frame ${data.current_frame} / ${data.total_frames}`,
        });
        return;
      }

      if (data.state === 'done') {
        clearVideoPolling();
        isVideoProcessing = false;
        btnEnhanceVideo.disabled = false;
        btnEnhanceVideo.classList.remove('loading');
        btnVideoLabel.textContent = 'Mejorar video';
        btnDownloadVideo.href = `${API}${data.download_url}`;
        btnDownloadVideo.download = data.output_file || 'video_enhanced.mp4';
        showVideoState('done', {
          copy: `Video completado. Frames procesados: ${data.total_frames || 0}.`,
        });
        return;
      }

      if (data.state === 'error') {
        throw new Error(data.message || 'Error desconocido al procesar el video.');
      }
    } catch (error) {
      clearVideoPolling();
      isVideoProcessing = false;
      btnEnhanceVideo.disabled = false;
      btnEnhanceVideo.classList.remove('loading');
      btnVideoLabel.textContent = 'Mejorar video';
      showVideoState('error', { copy: error.message });
    }
  };

  poll();
  videoPollingTimer = setInterval(poll, 3000);
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function updateCompareUI(value) {
  const { overlay, divider, range } = getCompareElements();
  if (!overlay || !divider || !range) return;

  compareValue = clamp(Number(value) || 0, 0, 100);
  overlay.style.clipPath = `inset(0 ${100 - compareValue}% 0 0)`;
  divider.style.left = `${compareValue}%`;
  range.value = compareValue;
}

function updateCompareFromClientX(clientX) {
  const { viewer } = getCompareElements();
  if (!viewer) return;

  const rect = viewer.getBoundingClientRect();
  if (!rect.width) return;
  const percent = ((clientX - rect.left) / rect.width) * 100;
  updateCompareUI(percent);
}

function onComparePointerMove(event) {
  if (!compareDragActive) return;
  updateCompareFromClientX(event.clientX);
}

function onCompareTouchMove(event) {
  if (!compareDragActive || !event.touches.length) return;
  event.preventDefault();
  updateCompareFromClientX(event.touches[0].clientX);
}

function stopCompareDrag() {
  compareDragActive = false;
  window.removeEventListener('mousemove', onComparePointerMove);
  window.removeEventListener('mouseup', stopCompareDrag);
  window.removeEventListener('touchmove', onCompareTouchMove);
  window.removeEventListener('touchend', stopCompareDrag);
}

function startCompareDrag(clientX) {
  compareDragActive = true;
  updateCompareFromClientX(clientX);
  window.addEventListener('mousemove', onComparePointerMove);
  window.addEventListener('mouseup', stopCompareDrag);
  window.addEventListener('touchmove', onCompareTouchMove, { passive: false });
  window.addEventListener('touchend', stopCompareDrag);
}

function initCompareSlider() {
  const { viewer, range } = getCompareElements();
  if (!viewer || !range) return;

  viewer.addEventListener('mousedown', event => {
    event.preventDefault();
    startCompareDrag(event.clientX);
  });

  viewer.addEventListener('touchstart', event => {
    if (!event.touches.length) return;
    startCompareDrag(event.touches[0].clientX);
  }, { passive: true });

  range.addEventListener('input', event => {
    updateCompareUI(event.target.value);
  });

  updateCompareUI(compareValue);
}

// ── 4. Enviar imagen a la API ─────────────────────────────────────────────────

btnEnhance.addEventListener('click', async () => {
  if (!selectedFile || isProcessing) return;
  await processImage();
});

async function processImage() {
  isProcessing = true;
  btnEnhance.disabled = true;
  btnEnhance.classList.add('loading');
  btnLabel.textContent = 'Procesando…';

  showResultState('progress');
  animateProgressLabel();

  const formData = new FormData();
  formData.append('file',      selectedFile);
  formData.append('model_key', selectedModel);
  formData.append('face_enhance', faceEnhanceEnabled ? 'true' : 'false');
  formData.append('gfpgan_weight', gfpganWeight.toFixed(1));

  try {
    const res = await fetch(`${API}/enhance`, {
      method: 'POST',
      body:   formData,
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || `Error ${res.status}`);
    }

    showResult(data);

  } catch (e) {
    showResultState('error', e.message);
  } finally {
    isProcessing            = false;
    btnEnhance.disabled     = false;
    btnEnhance.classList.remove('loading');
    btnLabel.textContent    = 'Mejorar imagen';
  }
}

// ── 5. Mostrar resultado ──────────────────────────────────────────────────────

function showResult(data) {
  const { input_info, processing, download_url } = data;
  const { viewer, originalImg, enhancedImg } = getCompareElements();

  if (!viewer || !originalImg || !enhancedImg) {
    throw new Error('El comparador no está disponible en la interfaz. Recarga la página.');
  }

  const originalUrl = URL.createObjectURL(selectedFile);
  const enhancedUrl = `${API}${download_url}?t=${Date.now()}`;

  originalImg.src = originalUrl;
  enhancedImg.src = enhancedUrl;
  originalImg.onload = () => URL.revokeObjectURL(originalUrl);
  enhancedImg.onload = () => {
    const w = enhancedImg.naturalWidth;
    const h = enhancedImg.naturalHeight;
    if (w && h) {
      viewer.style.aspectRatio = `${w} / ${h}`;
    }
  };
  compareValue = 50;
  updateCompareUI(compareValue);

  btnDownload.href     = `${API}${download_url}`;
  btnDownload.download = `enhanced_${selectedFile.name.replace(/\.[^.]+$/, '')}.png`;

  // Stats
  const durationStr = processing.duration_sec >= 60
    ? `${(processing.duration_sec / 60).toFixed(1)} min`
    : `${processing.duration_sec}s`;

  resultStats.innerHTML = `
    <div class="stat-item">
      <div class="stat-label">Original</div>
      <div class="stat-value">${input_info.width} × ${input_info.height}</div>
    </div>
    <div class="stat-item">
      <div class="stat-label">Mejorada</div>
      <div class="stat-value accent">${processing.output_size.width} × ${processing.output_size.height}</div>
    </div>
    <div class="stat-item">
      <div class="stat-label">Tiempo</div>
      <div class="stat-value">${durationStr}</div>
    </div>
    <div class="stat-item">
      <div class="stat-label">Procesado en</div>
      <div class="stat-value">${processing.device.toUpperCase()}</div>
    </div>
    ${processing.face_enhanced ? `
      <div class="stat-item">
        <div class="stat-label">Caras</div>
        <div class="stat-value accent">Restauradas</div>
      </div>
    ` : ''}
  `;

  showResultState('done');
}

// ── 6. Gestión de estados del panel resultado ─────────────────────────────────

function showResultState(state, errorMsg = '') {
  resultEmpty.style.display    = state === 'empty'    ? '' : 'none';
  resultProgress.style.display = state === 'progress' ? '' : 'none';
  resultDone.style.display     = state === 'done'     ? '' : 'none';
  resultError.style.display    = state === 'error'    ? '' : 'none';

  if (state === 'error') {
    resultErrorMsg.textContent = errorMsg || 'Error desconocido. Revisa la consola del servidor.';
  }
}

// Animación de mensajes de progreso mientras espera
function animateProgressLabel() {
  const messages = [
    'Cargando modelo Real-ESRGAN…',
    'Aplicando super-resolución…',
    'Procesando tiles de la imagen…',
    'Reconstruyendo detalles…',
    'Casi listo…',
  ];
  let i = 0;
  const interval = setInterval(() => {
    if (resultProgress.style.display === 'none') {
      clearInterval(interval);
      return;
    }
    i = (i + 1) % messages.length;
    progressLabel.textContent = messages[i];
  }, 4000);
}

// ── Arranque ──────────────────────────────────────────────────────────────────
initCompareSlider();
init();
