// ClipPulse AI Frontend Application Logic

document.addEventListener('DOMContentLoaded', () => {
  // Initialize Lucide icons
  if (window.lucide) {
    window.lucide.createIcons();
  }

  // State
  let currentSourceType = 'url'; // 'url' or 'upload'
  let selectedFile = null;
  let activeTaskId = null;
  let pollInterval = null;

  // DOM Elements
  const tabUrl = document.getElementById('tabUrl');
  const tabUpload = document.getElementById('tabUpload');
  const panelUrl = document.getElementById('panelUrl');
  const panelUpload = document.getElementById('panelUpload');
  const youtubeUrlInput = document.getElementById('youtubeUrlInput');
  const pasteUrlBtn = document.getElementById('pasteUrlBtn');
  const dropZone = document.getElementById('dropZone');
  const fileInput = document.getElementById('fileInput');
  const filePrompt = document.getElementById('filePrompt');
  const clipStyleSelect = document.getElementById('clipStyleSelect');
  const durationSelect = document.getElementById('durationSelect');
  const maxClipsSelect = document.getElementById('maxClipsSelect');
  const focusPromptInput = document.getElementById('focusPromptInput');
  const startProcessBtn = document.getElementById('startProcessBtn');

  // Progress Section
  const progressSection = document.getElementById('progressSection');
  const progressBar = document.getElementById('progressBar');
  const progressPercent = document.getElementById('progressPercent');
  const progressMessage = document.getElementById('progressMessage');
  const progressStatusTitle = document.getElementById('progressStatusTitle');
  const errorBanner = document.getElementById('errorBanner');
  const errorMessage = document.getElementById('errorMessage');

  // Results Section
  const resultsSection = document.getElementById('resultsSection');
  const resultTitle = document.getElementById('resultTitle');
  const resultMeta = document.getElementById('resultMeta');
  const resultThumb = document.getElementById('resultThumb');
  const clipsGrid = document.getElementById('clipsGrid');
  const downloadAllBtn = document.getElementById('downloadAllBtn');

  // Modals
  const previewModal = document.getElementById('previewModal');
  const modalTitle = document.getElementById('modalTitle');
  const modalVideo = document.getElementById('modalVideo');
  const modalTimestamp = document.getElementById('modalTimestamp');
  const modalDownloadBtn = document.getElementById('modalDownloadBtn');
  const closeModalBtn = document.getElementById('closeModalBtn');

  const apiKeyBtn = document.getElementById('apiKeyBtn');
  const apiKeyModal = document.getElementById('apiKeyModal');
  const closeKeyModalBtn = document.getElementById('closeKeyModalBtn');
  const modalKeyInput = document.getElementById('modalKeyInput');
  const saveKeyBtn = document.getElementById('saveKeyBtn');
  const apiKeyStatusText = document.getElementById('apiKeyStatusText');

  // Load stored API Key if user configured one locally
  let storedKey = localStorage.getItem('GEMINI_API_KEY') || '';
  if (storedKey) {
    modalKeyInput.value = storedKey;
    apiKeyStatusText.textContent = 'API Key Configured';
  }

  // Check system status
  fetch('/api/system')
    .then(r => r.json())
    .then(data => {
      const pill = document.getElementById('systemStatusPill');
      if (data.ffmpeg) {
        pill.className = "flex items-center space-x-2 text-xs font-medium px-3 py-1.5 rounded-lg bg-emerald-950/60 border border-emerald-800 text-emerald-400";
        pill.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span><span>FFmpeg & Engine Ready</span>`;
      } else {
        pill.className = "flex items-center space-x-2 text-xs font-medium px-3 py-1.5 rounded-lg bg-amber-950/60 border border-amber-800 text-amber-400";
        pill.innerHTML = `<span class="w-2 h-2 rounded-full bg-amber-500"></span><span>FFmpeg Required</span>`;
      }

      if (data.gemini_api_key) {
        apiKeyStatusText.textContent = 'API Key Ready ✓';
      }
    })
    .catch(() => {});

  // Tab switching
  tabUrl.addEventListener('click', () => {
    currentSourceType = 'url';
    tabUrl.className = "tab-btn flex-1 pb-3 text-sm font-semibold flex items-center justify-center space-x-2 border-b-2 border-brand-500 text-brand-500 transition";
    tabUpload.className = "tab-btn flex-1 pb-3 text-sm font-semibold flex items-center justify-center space-x-2 border-b-2 border-transparent text-gray-400 hover:text-gray-200 transition";
    panelUrl.classList.remove('hidden');
    panelUpload.classList.add('hidden');
  });

  tabUpload.addEventListener('click', () => {
    currentSourceType = 'upload';
    tabUpload.className = "tab-btn flex-1 pb-3 text-sm font-semibold flex items-center justify-center space-x-2 border-b-2 border-brand-500 text-brand-500 transition";
    tabUrl.className = "tab-btn flex-1 pb-3 text-sm font-semibold flex items-center justify-center space-x-2 border-b-2 border-transparent text-gray-400 hover:text-gray-200 transition";
    panelUpload.classList.remove('hidden');
    panelUrl.classList.add('hidden');
  });

  // Paste URL
  pasteUrlBtn.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        youtubeUrlInput.value = text;
      }
    } catch (e) {
      youtubeUrlInput.focus();
    }
  });

  // File Drop Zone
  dropZone.addEventListener('click', () => fileInput.click());

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('border-brand-500', 'bg-dark-900');
  });

  dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('border-brand-500', 'bg-dark-900');
  });

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('border-brand-500', 'bg-dark-900');
    if (e.dataTransfer.files.length) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) {
      handleFileSelected(e.target.files[0]);
    }
  });

  function handleFileSelected(file) {
    selectedFile = file;
    const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
    filePrompt.innerHTML = `Selected: <span class="text-white font-semibold">${file.name}</span> (${sizeMb} MB)`;
  }

  // API Key Modal Controls
  apiKeyBtn.addEventListener('click', () => apiKeyModal.classList.remove('hidden'));
  closeKeyModalBtn.addEventListener('click', () => apiKeyModal.classList.add('hidden'));
  saveKeyBtn.addEventListener('click', () => {
    const key = modalKeyInput.value.strip ? modalKeyInput.value.strip() : modalKeyInput.value.trim();
    if (key) {
      localStorage.setItem('GEMINI_API_KEY', key);
      apiKeyStatusText.textContent = 'API Key Configured';
    } else {
      localStorage.removeItem('GEMINI_API_KEY');
      apiKeyStatusText.textContent = 'API Key';
    }
    apiKeyModal.classList.add('hidden');
  });

  // Start Processing
  startProcessBtn.addEventListener('click', async () => {
    const style = clipStyleSelect.value;
    const [minDur, maxDur] = durationSelect.value.split('-').map(Number);
    const maxClips = parseInt(maxClipsSelect.value, 10);
    const focusPrompt = focusPromptInput.value.trim();
    const apiKey = localStorage.getItem('GEMINI_API_KEY') || '';

    // Validate
    if (currentSourceType === 'url') {
      const url = youtubeUrlInput.value.trim();
      if (!url) {
        showError('Please enter a valid YouTube URL.');
        return;
      }
    } else {
      if (!selectedFile) {
        showError('Please select or drop a video file to upload.');
        return;
      }
    }

    hideError();
    resultsSection.classList.add('hidden');
    progressSection.classList.remove('hidden');
    updateProgress(5, "Initializing task...");
    startProcessBtn.disabled = true;
    startProcessBtn.classList.add('opacity-50', 'cursor-not-allowed');

    try {
      let res;
      if (currentSourceType === 'url') {
        res = await fetch('/api/process/url', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            source_type: 'url',
            youtube_url: youtubeUrlInput.value.trim(),
            style,
            min_duration: minDur,
            max_duration: maxDur,
            max_clips: maxClips,
            focus_prompt: focusPrompt,
            api_key: apiKey
          })
        });
      } else {
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('style', style);
        formData.append('min_duration', minDur);
        formData.append('max_duration', maxDur);
        formData.append('max_clips', maxClips);
        if (focusPrompt) formData.append('focus_prompt', focusPrompt);
        if (apiKey) formData.append('api_key', apiKey);

        res = await fetch('/api/process/upload', {
          method: 'POST',
          body: formData
        });
      }

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to start video processing job.');
      }

      activeTaskId = data.task_id;
      startPolling(activeTaskId);

    } catch (err) {
      showError(err.message);
      startProcessBtn.disabled = false;
      startProcessBtn.classList.remove('opacity-50', 'cursor-not-allowed');
      progressSection.classList.add('hidden');
    }
  });

  // Polling Task Status
  function startPolling(taskId) {
    if (pollInterval) clearInterval(pollInterval);

    pollInterval = setInterval(async () => {
      try {
        const res = await fetch(`/api/tasks/${taskId}`);
        if (!res.ok) return;

        const task = await res.json();
        updateProgress(task.progress, task.message);
        highlightSteps(task.status);

        if (task.status === 'completed') {
          clearInterval(pollInterval);
          renderResults(task);
          progressSection.classList.add('hidden');
          startProcessBtn.disabled = false;
          startProcessBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        } else if (task.status === 'failed') {
          clearInterval(pollInterval);
          showError(task.error || 'Video processing failed.');
          progressSection.classList.add('hidden');
          startProcessBtn.disabled = false;
          startProcessBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        }
      } catch (e) {
        console.error('Polling error:', e);
      }
    }, 1500);
  }

  function updateProgress(percent, msg) {
    progressBar.style.width = `${Math.max(5, percent)}%`;
    progressPercent.textContent = `${percent}%`;
    progressMessage.textContent = msg;
  }

  function highlightSteps(status) {
    const s1 = document.getElementById('stepIngest');
    const s2 = document.getElementById('stepAnalyze');
    const s3 = document.getElementById('stepClip');
    const s4 = document.getElementById('stepDone');

    const reset = (el) => el.className = "flex flex-col items-center space-y-1 text-gray-500";
    const active = (el) => el.className = "flex flex-col items-center space-y-1 text-brand-400 font-bold";

    reset(s1); reset(s2); reset(s3); reset(s4);

    if (status === 'queued' || status === 'downloading') {
      active(s1);
    } else if (status === 'analyzing') {
      active(s1); active(s2);
    } else if (status === 'clipping') {
      active(s1); active(s2); active(s3);
    } else if (status === 'completed') {
      active(s1); active(s2); active(s3); active(s4);
    }
  }

  // Render Result Cards
  function renderResults(task) {
    resultTitle.textContent = task.video_title || 'Processed Video';
    const durMins = task.video_duration ? `${Math.floor(task.video_duration / 60)}m ${Math.floor(task.video_duration % 60)}s` : '';
    resultMeta.textContent = `${task.moments.length} Viral Clips Generated • Duration: ${durMins}`;

    if (task.thumbnail_url) {
      resultThumb.src = task.thumbnail_url;
      resultThumb.classList.remove('hidden');
    } else {
      document.getElementById('resultThumbContainer').classList.add('hidden');
    }

    downloadAllBtn.onclick = () => {
      window.location.href = `/api/download-all/${task.task_id}`;
    };

    clipsGrid.innerHTML = '';

    task.moments.forEach((moment, idx) => {
      const card = document.createElement('div');
      card.className = "bg-dark-800 border border-gray-800 rounded-2xl overflow-hidden shadow-xl hover:border-brand-500/50 transition flex flex-col";

      const previewThumb = moment.thumbnail_url || task.thumbnail_url || '';

      card.innerHTML = `
        <div class="relative bg-black group cursor-pointer overflow-hidden" style="min-height: 220px;" onclick="openPreview('${moment.title.replace(/'/g, "\\'")}', '${moment.clip_url}', '${moment.start_formatted} - ${moment.end_formatted}')">
          ${previewThumb ? `<img src="${previewThumb}" class="w-full h-56 object-cover opacity-85 group-hover:scale-105 transition duration-300">` : `<div class="w-full h-56 bg-dark-900 flex items-center justify-center text-gray-600"><i data-lucide="video" class="w-12 h-12"></i></div>`}
          
          <!-- Play Overlay Button -->
          <div class="absolute inset-0 bg-black/40 group-hover:bg-black/20 flex items-center justify-center transition">
            <div class="w-12 h-12 rounded-full bg-brand-600/90 text-white flex items-center justify-center shadow-lg group-hover:scale-110 transition">
              <i data-lucide="play" class="w-6 h-6 fill-current ml-0.5"></i>
            </div>
          </div>

          <!-- Virality Badge -->
          <div class="absolute top-3 right-3 px-2.5 py-1 rounded-full text-xs font-bold bg-dark-900/90 backdrop-blur border border-pink-500/40 text-pink-400 flex items-center space-x-1 shadow-md">
            <span>🔥</span>
            <span>${moment.virality_score}% Virality</span>
          </div>

          <!-- Timestamp Pill -->
          <div class="absolute bottom-3 left-3 px-2 py-0.5 rounded text-xs font-mono font-semibold bg-black/80 backdrop-blur text-gray-200">
            ${moment.start_formatted} - ${moment.end_formatted} (${moment.duration.toFixed(0)}s)
          </div>
        </div>

        <!-- Card Content -->
        <div class="p-5 flex-1 flex flex-col justify-between space-y-4">
          <div class="space-y-2">
            <h3 class="text-sm font-bold text-white line-clamp-2 leading-snug">${moment.title}</h3>
            ${moment.hook ? `
              <div class="p-2.5 rounded-xl bg-brand-950/40 border border-brand-800/40 text-xs text-brand-300">
                <span class="font-bold text-brand-400">🪝 Hook:</span> "${moment.hook}"
              </div>` : ''}
            <p class="text-xs text-gray-400 line-clamp-2">${moment.summary}</p>
          </div>

          <!-- Actions -->
          <div class="space-y-2 pt-2 border-t border-gray-800">
            <div class="flex items-center space-x-2">
              <button onclick="copyCaption('${encodeURIComponent(moment.suggested_caption + '\n\n' + moment.hashtags.join(' '))}', this)" 
                      class="flex-1 py-2 px-3 bg-dark-900 hover:bg-dark-700 border border-gray-700 rounded-xl text-xs font-medium text-gray-300 hover:text-white transition flex items-center justify-center space-x-1.5">
                <i data-lucide="copy" class="w-3.5 h-3.5"></i>
                <span>Copy Caption</span>
              </button>
              <a href="${moment.clip_url}" download class="flex-1 py-2 px-3 bg-brand-600 hover:bg-brand-500 rounded-xl text-xs font-semibold text-white transition flex items-center justify-center space-x-1.5 shadow-md shadow-brand-500/20">
                <i data-lucide="download" class="w-3.5 h-3.5"></i>
                <span>Download</span>
              </a>
            </div>
          </div>
        </div>
      `;

      clipsGrid.appendChild(card);
    });

    if (window.lucide) {
      window.lucide.createIcons();
    }

    resultsSection.classList.remove('hidden');
    resultsSection.scrollIntoView({ behavior: 'smooth' });
  }

  // Preview Modal
  window.openPreview = (title, videoUrl, timestamp) => {
    modalTitle.textContent = title;
    modalVideo.src = videoUrl;
    modalTimestamp.textContent = timestamp;
    modalDownloadBtn.href = videoUrl;
    previewModal.classList.remove('hidden');
    modalVideo.play();
  };

  closeModalBtn.addEventListener('click', () => {
    modalVideo.pause();
    modalVideo.src = '';
    previewModal.classList.add('hidden');
  });

  previewModal.addEventListener('click', (e) => {
    if (e.target === previewModal) {
      modalVideo.pause();
      modalVideo.src = '';
      previewModal.classList.add('hidden');
    }
  });

  // Copy Caption to Clipboard
  window.copyCaption = async (encodedText, btn) => {
    const text = decodeURIComponent(encodedText);
    try {
      await navigator.clipboard.writeText(text);
      const originalHtml = btn.innerHTML;
      btn.innerHTML = `<i data-lucide="check" class="w-3.5 h-3.5 text-emerald-400"></i><span class="text-emerald-400">Copied!</span>`;
      if (window.lucide) window.lucide.createIcons();
      setTimeout(() => {
        btn.innerHTML = originalHtml;
        if (window.lucide) window.lucide.createIcons();
      }, 2000);
    } catch (err) {
      console.error('Clipboard copy failed:', err);
    }
  };

  function showError(msg) {
    errorMessage.textContent = msg;
    errorBanner.classList.remove('hidden');
  }

  function hideError() {
    errorBanner.classList.add('hidden');
  }
});
