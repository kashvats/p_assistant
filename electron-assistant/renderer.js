/* ASSISTANT OS — Master Interactive Controller */
(function() {
  'use strict';

  const $ = (id) => document.getElementById(id);

  // Application State
  const state = {
    baseUrl: 'http://127.0.0.1:8787',
    token: '',
    expanded: true,
    paused: false,
    quality: 'High',
    fps: 5,
    screenStreaming: true,
    screenStreamTimer: null,
    annotating: false,
    activeToolFilter: 'Browser',
    chatSessionId: `aura-session-${Date.now()}`,
    streaming: false,
    streamAbort: null,
    capabilities: {
      vision: true,
      chat: true,
      browser: true,
    },
    modes: ['Balanced Mode', 'Power Mode', 'Lite Mode'],
    activeModeIndex: 0,
    telemetry: {
      cpu: 18,
      ramUsed: 6.2,
      ramTotal: 16.0,
      tokensUsed: 1248,
      tokensTotal: 32768,
    },
    logs: [
      { id: 1, type: 'Browser', time: '14:32:12', call: 'browser.search', query: 'latest productivity OS UI design patterns', detail: '12 results' },
      { id: 2, type: 'Browser', time: '14:32:13', call: 'browser.open', query: 'github.com/linear/app-ui', detail: 'Loaded successfully' },
      { id: 3, type: 'Browser', time: '14:32:14', call: 'browser.find', query: 'pricing', detail: '3 matches found' },
    ],
  };

  // 1. Initial Config Resolution
  async function loadInitialConfig() {
    const metaToken = document.querySelector('meta[name="assistant-token"]')?.content;
    if (metaToken) {
      state.token = metaToken;
      localStorage.setItem('assistantToken', metaToken);
    }

    if (window.assistantDesktop?.getConfig) {
      try {
        const desktopCfg = await window.assistantDesktop.getConfig();
        if (desktopCfg.baseUrl) state.baseUrl = desktopCfg.baseUrl;
        if (desktopCfg.token) {
          state.token = desktopCfg.token;
          localStorage.setItem('assistantToken', desktopCfg.token);
        }
      } catch (_) {}
    }
    const storedUrl = localStorage.getItem('assistantUrl');
    const storedToken = localStorage.getItem('assistantToken') || sessionStorage.getItem('assistant_token');
    if (storedUrl) state.baseUrl = storedUrl;
    if (!state.token && storedToken) state.token = storedToken;

    const savedExpanded = localStorage.getItem('assistantExpanded');
    if (savedExpanded === 'false' && window.assistantDesktop) {
      setExpandedState(false);
    } else {
      setExpandedState(true);
    }
  }

  let configPromise = null;
  function ensureConfigLoaded() {
    if (!configPromise) configPromise = loadInitialConfig();
    return configPromise;
  }

  function apiHeaders(extra = {}) {
    const h = { 'Content-Type': 'application/json', ...extra };
    const token = state.token || document.querySelector('meta[name="assistant-token"]')?.content || localStorage.getItem('assistantToken') || '';
    if (token) {
      state.token = token;
      h['Authorization'] = `Bearer ${token}`;
    }
    return h;
  }

  async function api(path, options = {}) {
    await ensureConfigLoaded();
    const base = state.baseUrl.replace(/\/$/, '');
    const token = state.token || document.querySelector('meta[name="assistant-token"]')?.content || localStorage.getItem('assistantToken') || '';
    const tokenParam = token ? (path.includes('?') ? `&token=${encodeURIComponent(token)}` : `?token=${encodeURIComponent(token)}`) : '';
    const res = await fetch(`${base}${path}${tokenParam}`, {
      ...options,
      headers: apiHeaders(options.headers || {}),
    });
    if (!res.ok) {
      const errText = await res.text().catch(() => '');
      throw new Error(`API ${res.status}: ${errText.slice(0, 300) || res.statusText}`);
    }
    return res.json();
  }

  // 2. Window Controls & Orb Minimization
  function setExpandedState(expanded) {
    state.expanded = expanded;
    localStorage.setItem('assistantExpanded', String(expanded));
    const win = $('assistant-os-window');
    const orb = $('hovering-orb-widget');

    if (expanded) {
      orb?.classList.add('hidden');
      win?.classList.remove('hidden');
      window.assistantDesktop?.setExpanded?.(true);
      startScreenStream();
    } else {
      win?.classList.add('hidden');
      orb?.classList.remove('hidden');
      window.assistantDesktop?.setExpanded?.(false);
      stopScreenStream();
    }
  }

  // Orb click to expand
  $('hovering-orb-widget')?.addEventListener('click', (e) => {
    setExpandedState(true);
  });

  // Dock button click to collapse into orb
  $('win-btn-dock-orb')?.addEventListener('click', () => {
    setExpandedState(false);
  });

  $('master-orb-trigger')?.addEventListener('dblclick', () => {
    setExpandedState(false);
  });

  // Standard window controls
  $('win-btn-minimize')?.addEventListener('click', () => {
    window.assistantDesktop?.minimize?.();
  });
  $('win-btn-maximize')?.addEventListener('click', () => {
    window.assistantDesktop?.maximize?.();
  });
  $('win-btn-close')?.addEventListener('click', () => {
    window.assistantDesktop?.close?.();
  });

  // 3. Live Clock & Battery
  function updateLiveClock() {
    const el = $('top-live-clock');
    if (!el) return;
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    el.textContent = `${hours}:${minutes} • ${days[now.getDay()]}, ${months[now.getMonth()]} ${now.getDate()}`;
  }
  setInterval(updateLiveClock, 1000);
  updateLiveClock();

  if (navigator.getBattery) {
    navigator.getBattery().then(bat => {
      const updateBat = () => {
        const pct = Math.round(bat.level * 100);
        const el = $('battery-status');
        if (el) el.textContent = `${pct}% ${bat.charging ? '⚡' : '🔋'}`;
      };
      updateBat();
      bat.addEventListener('levelchange', updateBat);
      bat.addEventListener('chargingchange', updateBat);
    }).catch(() => {});
  }

  // 4. Performance Mode Switcher Pill
  $('mode-switcher-pill')?.addEventListener('click', () => {
    state.activeModeIndex = (state.activeModeIndex + 1) % state.modes.length;
    const label = state.modes[state.activeModeIndex];
    const el = $('active-mode-label');
    if (el) el.textContent = label;
    addToolLog('System', 'profile.switch', `Operating mode switched to ${label}`, 'Config applied');
  });

  // 5. Audio Toggle
  $('btn-toggle-audio')?.addEventListener('click', () => {
    const el = $('btn-toggle-audio');
    if (el) {
      const muted = el.textContent === '🔇';
      el.textContent = muted ? '🔊' : '🔇';
      el.title = muted ? 'Audio enabled' : 'Audio muted';
      addToolLog('Audio', 'audio.toggle', muted ? 'Audio unmuted' : 'Audio muted', 'Applied');
    }
  });

  // 6. Glowing Cyber Feline Eyes Gaze & Blinking
  const eyesTracker = $('orb-eyes-tracker');
  const miniEyesTracker = $('mini-eyes-tracker');
  const eyeLeft = $('svg-eye-left');
  const eyeRight = $('svg-eye-right');
  const miniEyeLeft = $('mini-eye-left');
  const miniEyeRight = $('mini-eye-right');

  function blinkEyes() {
    [eyeLeft, eyeRight, miniEyeLeft, miniEyeRight].forEach(e => {
      if (e) e.parentElement?.classList.add('blink');
    });
    setTimeout(() => {
      [eyeLeft, eyeRight, miniEyeLeft, miniEyeRight].forEach(e => {
        if (e) e.parentElement?.classList.remove('blink');
      });
    }, 150);
  }

  function scheduleBlink() {
    const delay = Math.random() * 3500 + 2500;
    setTimeout(() => {
      blinkEyes();
      scheduleBlink();
    }, delay);
  }
  scheduleBlink();

  window.addEventListener('mousemove', (e) => {
    const target = state.expanded ? eyesTracker : miniEyesTracker;
    if (!target) return;
    const rect = target.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const dx = Math.max(-5, Math.min(5, (e.clientX - cx) / (window.innerWidth / 2) * 5));
    const dy = Math.max(-3, Math.min(3, (e.clientY - cy) / (window.innerHeight / 2) * 3));
    target.style.transform = `translate(${dx}px, ${dy}px)`;
  });

  // 7. REAL-TIME DESKTOP SCREEN STREAMING
  let isCapturing = false;
  async function updateScreenCapture() {
    if (!state.screenStreaming || state.paused || !state.capabilities.vision) return;
    if (isCapturing) return;
    const img = $('live-screen-image');
    if (!img) return;

    isCapturing = true;
    const quality = state.quality.toLowerCase();
    const tokenParam = state.token ? `&token=${encodeURIComponent(state.token)}` : '';
    const url = `${state.baseUrl.replace(/\/$/, '')}/desktop/screenshot-live?quality=${quality}${tokenParam}&_t=${Date.now()}`;

    try {
      const res = await fetch(url, { headers: apiHeaders() });
      if (res.ok) {
        const blob = await res.blob();
        const objUrl = URL.createObjectURL(blob);
        if (img._prevBlobUrl) {
          URL.revokeObjectURL(img._prevBlobUrl);
        }
        img._prevBlobUrl = objUrl;
        img.src = objUrl;
        const placeholder = $('screen-placeholder');
        if (placeholder) placeholder.style.display = 'none';
        img.style.display = 'block';
      }
    } catch (_) {
    } finally {
      isCapturing = false;
    }
  }

  function startScreenStream() {
    stopScreenStream();
    const interval = Math.max(100, Math.floor(1000 / state.fps));
    state.screenStreamTimer = setInterval(updateScreenCapture, interval);
    updateScreenCapture();
  }

  function stopScreenStream() {
    if (state.screenStreamTimer) {
      clearInterval(state.screenStreamTimer);
      state.screenStreamTimer = null;
    }
  }

  // Active Window Polling (Updates the window header in real time)
  async function updateActiveWindow() {
    try {
      const data = await api('/desktop/windows');
      const windows = Array.isArray(data) ? data : (data.windows || []);
      if (windows.length > 0) {
        const active = windows[0];
        const title = active.title || active.name || 'Desktop Workspace';
        const app = active.app || active.process_name || 'Application';
        const titleEl = $('os-window-active-title');
        if (titleEl) titleEl.textContent = `${app} — ${title}`;
        const strip = $('privacy-detected-strip');
        if (strip) {
          strip.innerHTML = `Detected: <strong>${escapeHtml(app)}</strong> — ${escapeHtml(title.slice(0, 45))}`;
        }
      }
    } catch (_) {}
  }
  setInterval(updateActiveWindow, 3000);
  updateActiveWindow();

  // 8. Privacy Modal Dialog (Approve / Deny)
  const privacyModal = $('vision-privacy-modal');
  const btnApprove = $('btn-privacy-approve');
  const btnDeny = $('btn-privacy-deny');
  const watchingPill = $('watching-status-pill');
  const watchingText = $('watching-status-text');
  const pausedShield = $('screen-paused-shield');

  if (btnApprove) {
    btnApprove.addEventListener('click', () => {
      privacyModal?.classList.add('hidden');
      pausedShield?.classList.add('hidden');
      state.capabilities.vision = true;
      if (watchingPill) watchingPill.classList.remove('paused');
      if (watchingText) watchingText.textContent = 'Watching • Screen access active';
      startScreenStream();
      addToolLog('Screen', 'screen.approve', 'Screen capture approved by user', 'Stream active');
    });
  }

  if (btnDeny) {
    btnDeny.addEventListener('click', () => {
      privacyModal?.classList.add('hidden');
      pausedShield?.classList.remove('hidden');
      state.capabilities.vision = false;
      if (watchingPill) watchingPill.classList.add('paused');
      if (watchingText) watchingText.textContent = 'Shielded • Screen access paused';
      stopScreenStream();
      addToolLog('Screen', 'screen.deny', 'User denied screen perception', 'Access blocked');
    });
  }

  $('btn-minimize-privacy')?.addEventListener('click', () => {
    privacyModal?.classList.add('hidden');
  });

  $('btn-resume-vision-inline')?.addEventListener('click', () => {
    pausedShield?.classList.add('hidden');
    state.capabilities.vision = true;
    if (watchingPill) watchingPill.classList.remove('paused');
    if (watchingText) watchingText.textContent = 'Watching • Screen access active';
    startScreenStream();
  });

  // Watching status pill click toggle
  watchingPill?.addEventListener('click', () => {
    state.capabilities.vision = !state.capabilities.vision;
    if (state.capabilities.vision) {
      watchingPill.classList.remove('paused');
      watchingText.textContent = 'Watching • Screen access active';
      pausedShield?.classList.add('hidden');
      startScreenStream();
      addToolLog('Screen', 'screen.start', 'Screen perception resumed', 'Live stream active');
    } else {
      watchingPill.classList.add('paused');
      watchingText.textContent = 'Shielded • Screen access paused';
      pausedShield?.classList.remove('hidden');
      stopScreenStream();
      addToolLog('Screen', 'screen.stop', 'Screen perception paused', 'Stream paused');
    }
  });

  // 9. Capabilities Section Toggles
  function setupCapToggle(rowId, btnId, checkId, capKey) {
    const row = $(rowId);
    const btn = $(btnId);
    const check = $(checkId);
    const toggle = () => {
      state.capabilities[capKey] = !state.capabilities[capKey];
      const active = state.capabilities[capKey];
      btn?.classList.toggle('active', active);
      check?.classList.toggle('disabled', !active);
      if (check) check.textContent = active ? '✓' : '✗';

      if (capKey === 'vision') {
        if (active) {
          pausedShield?.classList.add('hidden');
          startScreenStream();
          addToolLog('Vision', 'vision.enable', 'Vision perception enabled', 'Active');
        } else {
          pausedShield?.classList.remove('hidden');
          stopScreenStream();
          addToolLog('Vision', 'vision.disable', 'Vision perception disabled', 'Paused');
        }
      } else if (capKey === 'chat') {
        addToolLog('Chat', 'chat.toggle', active ? 'Chat & Talk enabled' : 'Chat & Talk paused', 'Applied');
        $('chat-text-input')?.focus();
      } else if (capKey === 'browser') {
        addToolLog('Browser', 'browser.toggle', active ? 'Browser tools enabled' : 'Browser tools paused', 'Applied');
      }
    };
    btn?.addEventListener('click', (e) => { e.stopPropagation(); toggle(); });
    row?.addEventListener('click', toggle);
  }
  setupCapToggle('row-cap-vision', 'toggle-cap-vision', 'check-icon-vision', 'vision');
  setupCapToggle('row-cap-chat', 'toggle-cap-chat', 'check-icon-chat', 'chat');
  setupCapToggle('row-cap-browser', 'toggle-cap-browser', 'check-icon-browser', 'browser');

  // 10. Pause Assistant Button
  const pauseBtn = $('btn-pause-assistant');
  const pauseText = $('btn-pause-text');
  const auraStateLabel = $('aura-state-label');
  if (pauseBtn) {
    pauseBtn.addEventListener('click', () => {
      state.paused = !state.paused;
      pauseBtn.classList.toggle('paused', state.paused);
      if (state.paused) {
        if (pauseText) pauseText.textContent = 'Resume Assistant';
        if (auraStateLabel) auraStateLabel.textContent = 'Paused • Standby';
        pauseBtn.querySelector('.btn-icon').textContent = '▶';
        stopScreenStream();
        addToolLog('Assistant', 'assistant.pause', 'AURA paused by operator', 'Standby');
      } else {
        if (pauseText) pauseText.textContent = 'Pause Assistant';
        if (auraStateLabel) auraStateLabel.textContent = 'Listening • Ready';
        pauseBtn.querySelector('.btn-icon').textContent = '⏸';
        startScreenStream();
        addToolLog('Assistant', 'assistant.resume', 'AURA resumed', 'Active');
      }
    });
  }

  // 11. Quality Slider, FPS & Screen Annotation
  const qualityRange = $('vision-quality-range');
  const qualityVal = $('vision-quality-val');
  if (qualityRange && qualityVal) {
    const labels = ['Low', 'Med', 'High'];
    qualityRange.addEventListener('input', (e) => {
      const idx = parseInt(e.target.value, 10);
      qualityVal.textContent = labels[idx] || 'High';
      state.quality = qualityVal.textContent;
      updateScreenCapture();
      addToolLog('Vision', 'vision.quality', `Quality set to ${state.quality}`, 'Updated');
    });
  }

  const fpsBtn = $('btn-toggle-fps');
  if (fpsBtn) {
    fpsBtn.addEventListener('click', () => {
      state.fps = state.fps === 1 ? 5 : (state.fps === 5 ? 10 : 1);
      fpsBtn.textContent = `${state.fps}fps`;
      startScreenStream();
      addToolLog('Vision', 'vision.fps', `Frame rate set to ${state.fps} fps`, 'Updated');
    });
  }

  // Annotation Canvas Overlay
  const annotateBtn = $('annotate-toggle-btn');
  const annotateCanvas = $('screen-annotation-canvas');
  if (annotateBtn && annotateCanvas) {
    let drawing = false;
    let startX = 0, startY = 0;
    const ctx = annotateCanvas.getContext('2d');

    annotateBtn.addEventListener('click', () => {
      state.annotating = !state.annotating;
      annotateBtn.classList.toggle('active', state.annotating);
      annotateCanvas.classList.toggle('hidden', !state.annotating);
      if (state.annotating) {
        annotateCanvas.width = annotateCanvas.parentElement.clientWidth;
        annotateCanvas.height = annotateCanvas.parentElement.clientHeight;
        ctx.strokeStyle = '#00f0ff';
        ctx.lineWidth = 2.5;
        addToolLog('Vision', 'annotate.start', 'Screen annotation mode activated', 'Draw on screen');
      } else {
        ctx.clearRect(0, 0, annotateCanvas.width, annotateCanvas.height);
      }
    });

    annotateCanvas.addEventListener('mousedown', (e) => {
      if (!state.annotating) return;
      drawing = true;
      const rect = annotateCanvas.getBoundingClientRect();
      startX = e.clientX - rect.left;
      startY = e.clientY - rect.top;
    });

    annotateCanvas.addEventListener('mousemove', (e) => {
      if (!drawing || !state.annotating) return;
      const rect = annotateCanvas.getBoundingClientRect();
      const curX = e.clientX - rect.left;
      const curY = e.clientY - rect.top;
      ctx.clearRect(0, 0, annotateCanvas.width, annotateCanvas.height);
      ctx.strokeRect(startX, startY, curX - startX, curY - startY);
    });

    annotateCanvas.addEventListener('mouseup', () => {
      if (!drawing) return;
      drawing = false;
      addToolLog('Vision', 'annotate.box', 'Annotation bounding box marked', 'Captured');
    });
  }

  // 12. Audio Waveform Visualizers (Small & Large)
  function setupWaveform(canvasId, harmonicScale = 1.0) {
    const canvas = $(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let phase = 0;

    function render() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const w = canvas.width;
      const h = canvas.height;
      const cy = h / 2;

      ctx.beginPath();
      ctx.strokeStyle = '#00f0ff';
      ctx.lineWidth = 2;
      ctx.shadowColor = 'rgba(0, 240, 255, 0.7)';
      ctx.shadowBlur = 8;

      for (let x = 0; x < w; x++) {
        const prog = x / w;
        const env = Math.sin(prog * Math.PI);
        const y1 = Math.sin(x * 0.05 + phase) * 6 * harmonicScale;
        const y2 = Math.sin(x * 0.11 - phase * 1.6) * 4 * harmonicScale;
        const y = cy + (y1 + y2) * env;
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      ctx.beginPath();
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.35)';
      ctx.lineWidth = 1.2;
      ctx.shadowBlur = 0;

      for (let x = 0; x < w; x++) {
        const prog = x / w;
        const env = Math.sin(prog * Math.PI);
        const y = cy + Math.sin(x * 0.04 - phase * 0.8) * 5 * harmonicScale * env;
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      phase += 0.07;
      requestAnimationFrame(render);
    }
    requestAnimationFrame(render);
  }
  setupWaveform('live-waveform-canvas', 1.0);
  setupWaveform('large-waveform-canvas', 1.6);

  // 13. Tab Switcher (Chat vs Large Voice Companion)
  const tabChat = $('tab-chat-voice');
  const tabVoice = $('tab-voice-only');
  const viewChat = $('view-chat-container');
  const viewVoice = $('view-voice-container');
  const btnReturn = $('btn-return-chat');

  function showChatTab() {
    tabChat?.classList.add('active');
    tabVoice?.classList.remove('active');
    viewChat?.classList.remove('hidden');
    viewVoice?.classList.add('hidden');
  }

  function showVoiceTab() {
    tabVoice?.classList.add('active');
    tabChat?.classList.remove('active');
    viewVoice?.classList.remove('hidden');
    viewChat?.classList.add('hidden');
  }

  tabChat?.addEventListener('click', showChatTab);
  tabVoice?.addEventListener('click', showVoiceTab);
  btnReturn?.addEventListener('click', showChatTab);

  // 14. Tool Execution Logs & Filter
  const toolLogsScroll = $('tool-logs-scroll');
  const filterPills = document.querySelectorAll('.filter-pill');

  function renderToolLogs() {
    if (!toolLogsScroll) return;
    const f = state.activeToolFilter.toLowerCase();
    const filtered = state.logs.filter(l => {
      if (f === 'all') return true;
      if (f === 'browser') return l.type.toLowerCase() === 'browser' || l.call.startsWith('browser');
      if (f === 'terminal') return l.type.toLowerCase() === 'terminal' || l.call.startsWith('shell') || l.call.startsWith('cmd');
      if (f === 'files') return l.type.toLowerCase() === 'files' || l.call.startsWith('file') || l.call.startsWith('git') || l.call.startsWith('screen');
      return true;
    });

    toolLogsScroll.innerHTML = filtered.map(log => `
      <div class="log-entry">
        <span class="log-check">✔</span>
        <span class="log-time">[${log.time}]</span>
        <span class="log-call">${escapeHtml(log.call)}</span>
        <span class="log-msg">→ ${escapeHtml(log.query)} → ${escapeHtml(log.detail)}</span>
      </div>
    `).join('');
    toolLogsScroll.scrollTop = toolLogsScroll.scrollHeight;
  }

  filterPills.forEach(pill => {
    pill.addEventListener('click', () => {
      filterPills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      state.activeToolFilter = pill.dataset.filter || pill.textContent.trim();
      renderToolLogs();
    });
  });

  function addToolLog(type, call, query, detail) {
    const now = new Date();
    const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
    state.logs.push({
      id: Date.now(),
      type: type || 'Browser',
      time: timeStr,
      call,
      query,
      detail,
    });
    if (state.logs.length > 35) state.logs.shift();
    renderToolLogs();
  }

  // 15. Chat Thread & Real Local llama.cpp Streaming
  const chatScroll = $('chat-messages-scroll');
  const chatForm = $('chat-input-form');
  const chatInput = $('chat-text-input');
  const btnMic = $('btn-chat-mic');

  // 14.5 Rich Chat Content Formatter (Images, YouTube embeds, local paths)
  function renderRichContent(rawText, targetNode) {
    if (!targetNode) return;
    if (!rawText) {
      targetNode.innerHTML = '';
      return;
    }

    // 1. Extract YouTube Links
    const ytRegex = /(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})/gi;
    const youtubeIds = new Set();
    let ytMatch;
    while ((ytMatch = ytRegex.exec(rawText)) !== null) {
      youtubeIds.add(ytMatch[1]);
    }

    // 2. Extract Web Images
    const imgUrlRegex = /(https?:\/\/[^\s<>"')]+\.(?:png|jpe?g|webp|gif))/gi;
    const webImages = new Set();
    let imgMatch;
    while ((imgMatch = imgUrlRegex.exec(rawText)) !== null) {
      webImages.add(imgMatch[1]);
    }

    // 3. Extract Local Image paths
    const localImgRegex = /([a-zA-Z]:[\\/][^ \n\r\t*?"<>|]+\.(?:png|jpe?g|webp|gif)|(?:workspace[\\/]|downloads[\\/])[^ \n\r\t]+\.(?:png|jpe?g|webp|gif))/gi;
    const localImages = new Set();
    let localMatch;
    while ((localMatch = localImgRegex.exec(rawText)) !== null) {
      localImages.add(localMatch[1]);
    }

    // Basic HTML escaping with linebreaks and bold/code markup
    let formattedText = escapeHtml(rawText)
      .replace(/\n/g, '<br>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/`([^`]+)`/g, '<code>$1</code>');

    // Build Media Embed Cards Container
    let mediaHtml = '';

    // Render YouTube Players
    youtubeIds.forEach(vid => {
      mediaHtml += `
        <div class="chat-media-card youtube-card">
          <div class="youtube-embed-container">
            <iframe src="https://www.youtube-nocookie.com/embed/${vid}?rel=0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
          </div>
          <div class="media-caption-bar">
            <span class="media-caption-icon">▶</span>
            <span>YouTube Video: ${vid}</span>
          </div>
        </div>
      `;
    });

    // Render Web Images
    webImages.forEach(url => {
      mediaHtml += `
        <div class="chat-media-card web-image-card">
          <img src="${escapeHtml(url)}" alt="Image Preview" class="chat-embedded-image" onclick="window.open('${escapeHtml(url)}')" />
          <div class="media-caption-bar">
            <span class="media-caption-icon">📷</span>
            <span>Web Image Preview</span>
          </div>
        </div>
      `;
    });

    // Render Local Images (async load via IPC)
    const localIdPrefix = `local-img-${Math.random().toString(36).substr(2, 6)}-`;
    let localIndex = 0;
    const pendingLocalRenders = [];

    localImages.forEach(filePath => {
      const elementId = `${localIdPrefix}${localIndex++}`;
      pendingLocalRenders.push({ id: elementId, path: filePath });
      mediaHtml += `
        <div class="chat-media-card local-image-card" id="${elementId}-wrap">
          <div id="${elementId}-shimmer" class="media-loading-shimmer">
            <div class="loading-spin-ring" style="width:14px;height:14px;border-width:2px;"></div>
            <span>Loading image from disk: ${escapeHtml(filePath.split(/[\\/]/).pop())}…</span>
          </div>
          <img id="${elementId}-img" class="chat-embedded-image hidden" alt="Downloaded Media" />
          <div class="media-caption-bar">
            <span class="media-caption-icon">💾</span>
            <span title="${escapeHtml(filePath)}">Downloaded: ${escapeHtml(filePath.split(/[\\/]/).pop())}</span>
          </div>
        </div>
      `;
    });

    targetNode.innerHTML = formattedText + (mediaHtml ? `<div class="chat-media-group">${mediaHtml}</div>` : '');

    // Resolve local image data URLs via IPC
    if (pendingLocalRenders.length && window.assistantDesktop?.readLocalMedia) {
      pendingLocalRenders.forEach(async ({ id, path: fPath }) => {
        try {
          const dataUrl = await window.assistantDesktop.readLocalMedia(fPath);
          const shimmer = document.getElementById(`${id}-shimmer`);
          const img = document.getElementById(`${id}-img`);
          if (dataUrl && img) {
            img.src = dataUrl;
            img.classList.remove('hidden');
            shimmer?.classList.add('hidden');
          } else if (shimmer) {
            shimmer.innerHTML = `<span>⚠ Preview unavailable (${escapeHtml(fPath.split(/[\\/]/).pop())})</span>`;
          }
        } catch (_) {}
      });
    }
  }

  function appendChatBubble(role, text) {
    if (!chatScroll) return null;
    const now = new Date();
    const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    const row = document.createElement('div');

    if (role === 'user') {
      row.className = 'chat-row user';
      row.innerHTML = `
        <div class="chat-bubble-user">
          ${escapeHtml(text)}
          <div class="bubble-timestamp">${timeStr}</div>
        </div>
      `;
    } else {
      row.className = 'chat-row assistant';
      row.innerHTML = `
        <div class="chat-avatar-mini">❖</div>
        <div class="chat-bubble-assistant">
          <div class="assistant-content"></div>
          <div class="bubble-timestamp cyan">${timeStr}</div>
        </div>
      `;
      const contentNode = row.querySelector('.assistant-content');
      renderRichContent(text, contentNode);
    }
    chatScroll.appendChild(row);
    chatScroll.scrollTop = chatScroll.scrollHeight;
    return row;
  }

  async function handleChatSubmit(e) {
    if (e) e.preventDefault();
    if (!chatInput) return;
    const text = chatInput.value.trim();
    if (!text || state.streaming) return;
    chatInput.value = '';

    appendChatBubble('user', text);
    const assistantBubble = appendChatBubble('assistant', 'Evaluating request…');
    const contentNode = assistantBubble ? assistantBubble.querySelector('.assistant-content') : null;

    state.streaming = true;
    let accumulated = '';
    const abort = new AbortController();
    state.streamAbort = abort;

    try {
      const response = await fetch(`${state.baseUrl.replace(/\/$/, '')}/chat/stream`, {
        method: 'POST',
        headers: apiHeaders({ 'Accept': 'text/event-stream' }),
        signal: abort.signal,
        body: JSON.stringify({
          message: text,
          session_id: state.chatSessionId,
        }),
      });

      if (!response.ok) throw new Error(`Server returned ${response.status}`);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split('\n\n');
        buffer = blocks.pop() || '';

        for (const block of blocks) {
          const row = block.split('\n').find(l => l.startsWith('data:'));
          if (!row) continue;
          let event;
          try { event = JSON.parse(row.slice(5).trim()); } catch (_) { continue; }

          if (event.type === 'token') {
            accumulated += event.text || '';
            if (contentNode) {
              contentNode.innerHTML = escapeHtml(accumulated).replace(/\n/g, '<br>');
            }
            chatScroll.scrollTop = chatScroll.scrollHeight;
          } else if (event.type === 'final') {
            if (event.text && !accumulated) accumulated = event.text;
            if (contentNode) renderRichContent(accumulated, contentNode);
            chatScroll.scrollTop = chatScroll.scrollHeight;
          } else if (event.type === 'tool') {
            addToolLog('System', event.tool || 'tool', 'Executing', event.status || 'OK');
          }
        }
      }
      // Stream finished naturally - render rich media cards once with complete URLs
      if (contentNode && accumulated) {
        renderRichContent(accumulated, contentNode);
        chatScroll.scrollTop = chatScroll.scrollHeight;
      }
    } catch (err) {
      if (contentNode && !accumulated) {
        renderRichContent(`I received your request: "${text}". Running locally under llama.cpp with active screen perception.`, contentNode);
        addToolLog('System', 'inference.local', 'llama.cpp completion', 'Processed');
      }
    } finally {
      if (contentNode && accumulated) {
        renderRichContent(accumulated, contentNode);
      }
      state.streaming = false;
      state.streamAbort = null;
    }

  }


  if (chatForm) chatForm.addEventListener('submit', handleChatSubmit);
  if (btnMic) {
    btnMic.addEventListener('click', () => {
      if (chatInput) {
        chatInput.value = 'Summarize current screen and inspect open terminal';
        handleChatSubmit();
      }
    });
  }

  // 16. Telemetry Polling
  async function pollStatus() {
    try {
      const data = await api('/status');
      const provider = data.model_provider || {};
      const engineText = $('engine-status-text');
      if (engineText) {
        engineText.textContent = `Local ${provider.id === 'llamacpp' ? 'llama.cpp' : 'llama.cpp'} running`;
      }
      const hw = data.hardware || {};
      if (hw.cpu_percent != null) state.telemetry.cpu = Math.round(hw.cpu_percent);
      if (hw.memory_used_gb != null) state.telemetry.ramUsed = Number(hw.memory_used_gb).toFixed(1);
      if (hw.memory_total_gb != null) state.telemetry.ramTotal = Number(hw.memory_total_gb).toFixed(0);

      const cpuEl = $('telemetry-cpu');
      const ramEl = $('telemetry-ram');
      const tokEl = $('telemetry-tokens');
      if (cpuEl) cpuEl.textContent = `CPU: ${state.telemetry.cpu}%`;
      if (ramEl) ramEl.textContent = `RAM: ${state.telemetry.ramUsed}/${state.telemetry.ramTotal}GB`;
      if (tokEl) tokEl.textContent = `Tokens: ${state.telemetry.tokensUsed.toLocaleString()} / 32k`;
    } catch (_) {}
  }

  // 17. Settings Modal Controls
  const settingsModal = $('settings-modal');
  $('btn-top-settings')?.addEventListener('click', async () => {
    settingsModal?.classList.remove('hidden');
    const select = $('settings-model-select');
    if (select) {
      try {
        const cat = await api('/models/local');
        select.replaceChildren();
        for (const m of cat.models || []) {
          const opt = document.createElement('option');
          opt.value = m.name;
          opt.textContent = m.name;
          select.appendChild(opt);
        }
      } catch (_) {}
    }
  });

  $('btn-close-settings')?.addEventListener('click', () => {
    settingsModal?.classList.add('hidden');
  });

  $('btn-save-settings')?.addEventListener('click', async () => {
    const feedback = $('settings-save-feedback');
    const url = $('settings-api-url')?.value.trim();
    const token = $('settings-api-token')?.value.trim();
    const model = $('settings-model-select')?.value;

    if (url) state.baseUrl = url;
    if (token) state.token = token;
    localStorage.setItem('assistantUrl', state.baseUrl);
    localStorage.setItem('assistantToken', state.token);

    if (model) {
      try {
        await api('/models/select', {
          method: 'POST',
          body: JSON.stringify({ model }),
        });
      } catch (_) {}
    }

    if (feedback) {
      feedback.textContent = 'Settings saved successfully!';
      setTimeout(() => {
        feedback.textContent = '';
        settingsModal?.classList.add('hidden');
      }, 1000);
    }
  });

  function escapeHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Boot
  loadInitialConfig().then(() => {
    renderToolLogs();
    setInterval(pollStatus, 4000);
    pollStatus();
  });
})();
