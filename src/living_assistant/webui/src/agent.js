/* Floating desktop agent: a round face with eyes that hovers over the desktop.
   Click to talk (live spectrum while listening), drag to move, right-click for options.
   Runs inside the Electron shell (window.agentShell) or any browser tab (degrades gracefully). */

const shell = window.agentShell || null;
const token = document.querySelector('meta[name="assistant-token"]')?.getAttribute('content') || '';
const $ = (id) => document.getElementById(id);
const face = $('agent-face');
const dock = $('agent-dock');
const bubble = $('agent-bubble');
const bubbleText = $('agent-bubble-text');
const bubbleMeta = $('agent-bubble-meta');
const actions = $('agent-bubble-actions');
const canvas = $('agent-spectrum');
const ctx = canvas.getContext('2d');
const pupils = [...document.querySelectorAll('#agent-face .pupil')];

const state = {
  mood: 'idle',
  busy: false,
  listening: false,
  micActive: false,
  bands: new Array(16).fill(0),
  smooth: new Array(16).fill(0),
  hideTimer: null,
  hoverBubble: false,
  speakReplies: readFlag('agent_speak_replies', true),
  approvals: 0,
  online: true,
  controller: null,
};

function readFlag(key, fallback) {
  try { const v = localStorage.getItem(key); return v === null ? fallback : v === '1'; } catch (_) { return fallback; }
}

async function api(path, options = {}) {
  const headers = Object.assign({}, options.headers || {}, token ? {Authorization: `Bearer ${token}`} : {});
  const res = await fetch(path, {...options, headers});
  if (!res.ok) throw new Error((await res.text()).slice(0, 300) || `HTTP ${res.status}`);
  return (res.headers.get('content-type') || '').includes('json') ? res.json() : res.text();
}

// ---- mood & bubble -------------------------------------------------------------

function setMood(mood) {
  state.mood = mood;
  face.className = `agent-face md mood-${mood}`;
}

function refreshIdleMood() {
  if (state.busy) return;
  if (!state.online) setMood('error');
  else if (state.approvals) setMood('alert');
  else setMood('idle');
}

function showBubble(text, meta = '', {autoHideMs = 0} = {}) {
  clearTimeout(state.hideTimer);
  actions.hidden = true;
  bubbleText.textContent = text;
  bubbleMeta.textContent = meta;
  bubble.hidden = !text && !meta;
  bubbleText.scrollTop = bubbleText.scrollHeight;
  if (autoHideMs) scheduleHide(autoHideMs);
}

function scheduleHide(ms) {
  clearTimeout(state.hideTimer);
  state.hideTimer = setTimeout(() => { if (!state.hoverBubble && !state.busy) bubble.hidden = true; }, ms);
}

// ---- eyes follow the cursor anywhere on screen -----------------------------------

function lookAt(screenX, screenY) {
  const r = face.getBoundingClientRect();
  const cx = (window.screenX || 0) + r.left + r.width / 2;
  const cy = (window.screenY || 0) + r.top + r.height / 2;
  const dx = screenX - cx, dy = screenY - cy;
  const dist = Math.hypot(dx, dy) || 1;
  const reach = Math.min(1, dist / 320);
  const tx = (dx / dist) * 38 * reach, ty = (dy / dist) * 30 * reach;
  pupils.forEach((p) => { p.style.transform = `translate(${tx}%, ${ty}%)`; });
}

if (shell && shell.onCursor) shell.onCursor(({x, y}) => { if (state.mood !== 'thinking') lookAt(x, y); });
document.addEventListener('pointermove', (e) => lookAt(e.screenX, e.screenY), {passive: true});

// ---- spectrum ring --------------------------------------------------------------

function drawSpectrum() {
  const w = canvas.width, h = canvas.height, cx = w / 2, cy = h / 2;
  ctx.clearRect(0, 0, w, h);
  const target = state.listening || state.micActive ? state.bands : state.bands.map(() => 0);
  let energy = 0;
  for (let i = 0; i < 16; i += 1) {
    state.smooth[i] += (target[i] - state.smooth[i]) * 0.35;
    energy += state.smooth[i];
  }
  if (energy > 0.05) {
    const inner = 74, maxLen = 64, bars = 48;
    for (let b = 0; b < bars; b += 1) {
      // Mirror the 16 bands around the ring so it reads as a symmetric spectrum.
      const band = Math.floor((b < bars / 2 ? b : bars - 1 - b) / (bars / 2) * 16) % 16;
      const v = state.smooth[band];
      const angle = (b / bars) * Math.PI * 2 - Math.PI / 2;
      const len = 4 + v * maxLen;
      const x1 = cx + Math.cos(angle) * inner, y1 = cy + Math.sin(angle) * inner;
      const x2 = cx + Math.cos(angle) * (inner + len), y2 = cy + Math.sin(angle) * (inner + len);
      ctx.strokeStyle = `hsla(${350 - v * 120}, 90%, ${55 + v * 20}%, ${0.35 + v * 0.65})`;
      ctx.lineWidth = 5;
      ctx.lineCap = 'round';
      ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
    }
  }
  requestAnimationFrame(drawSpectrum);
}
requestAnimationFrame(drawSpectrum);

// The meter is polled all the time so the ring also moves when listening was started
// elsewhere (hands-free mode, the dashboard mic): fast while recording, slow otherwise.
async function meterLoop() {
  while (true) {
    let active = false;
    try {
      const m = await api('/voice/meter');
      active = !!m.active;
      state.bands = active && Array.isArray(m.bands) && m.bands.length ? m.bands : new Array(16).fill(0);
      if (active !== state.micActive) {
        state.micActive = active;
        if (!state.busy) { if (active) setMood('listening'); else refreshIdleMood(); }
      }
      if (active && (state.listening || !state.busy)) {
        const label = {calibrating: 'Listening… (calibrating mic)', waiting: 'Listening… speak now', speech: 'Hearing you…'}[m.phase] || 'Listening…';
        if (state.listening) bubbleMeta.textContent = label;
        else showBubble('', label);
      } else if (!active && !state.busy && bubble.hidden === false && !bubbleText.textContent && /^Listening|^Hearing/.test(bubbleMeta.textContent)) {
        bubble.hidden = true;
      }
    } catch (_) {
      state.bands = new Array(16).fill(0);
    }
    await new Promise((r) => setTimeout(r, active || state.listening ? 70 : 500));
  }
}
meterLoop();

// ---- talk: listen -> transcript -> streamed answer -> optional speech -------------

async function talk() {
  if (state.busy) { if (state.controller) state.controller.abort(); return; }
  state.busy = true;
  state.listening = true;
  setMood('listening');
  showBubble('', 'Listening… speak now');
  let transcript = '';
  try {
    const res = await api('/voice/transcribe', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({max_seconds: 15})});
    state.listening = false;
    if (res.approval_required && res.approval_id) {
      // Microphone use needs the user's consent for each listen; ask right here.
      state.busy = false;
      askMicApproval(res.approval_id);
      return;
    }
    if (!res.ok) throw new Error(res.error || res.message || 'I did not catch that.');
    transcript = res.transcript;
  } catch (e) {
    state.listening = false;
    state.busy = false;
    setMood('error');
    showBubble(String(e.message || e), 'Voice', {autoHideMs: 6000});
    setTimeout(refreshIdleMood, 2500);
    return;
  }
  await ask(transcript);
}

function askMicApproval(approvalId) {
  setMood('alert');
  showBubble('Allow the assistant to listen to your microphone for this request?', 'Microphone approval');
  actions.hidden = false;
  const decide = async (approved, e) => {
    e.stopPropagation();
    if (!e.isTrusted || actions.hidden) return; // consent comes only from a real click on a visible prompt
    actions.hidden = true;
    $('agent-allow').onclick = $('agent-deny').onclick = null;
    try {
      await api(`/approvals/${encodeURIComponent(approvalId)}`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({approved})});
    } catch (err) {
      showBubble(String(err.message || err), 'Approval', {autoHideMs: 6000});
      return refreshIdleMood();
    }
    if (approved) talk();
    else { bubble.hidden = true; refreshIdleMood(); }
  };
  $('agent-allow').onclick = (e) => decide(true, e);
  $('agent-deny').onclick = (e) => decide(false, e);
  $('agent-allow').focus();
}

async function ask(text) {
  state.busy = true;
  setMood('thinking');
  showBubble('', `You: ${text}`);
  const controller = new AbortController();
  state.controller = controller;
  let answer = '', current = '';
  try {
    const res = await fetch('/chat/stream', {
      method: 'POST', signal: controller.signal,
      headers: {'Content-Type': 'application/json', Accept: 'text/event-stream', ...(token ? {Authorization: `Bearer ${token}`} : {})},
      body: JSON.stringify({message: text, session_id: 'desktop-agent'}),
    });
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
    const reader = res.body.getReader(), decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {stream: true});
      const blocks = buffer.split('\n\n');
      buffer = blocks.pop() || '';
      for (const block of blocks) {
        const row = block.split('\n').find((l) => l.startsWith('data:'));
        if (!row) continue;
        let ev; try { ev = JSON.parse(row.slice(5).trim()); } catch (_) { continue; }
        if (ev.type === 'status' && ev.status === 'generating') { current = ''; setMood('thinking'); }
        else if (ev.type === 'token') { current += ev.text || ''; bubbleText.textContent = current; bubbleText.scrollTop = bubbleText.scrollHeight; }
        else if (ev.type === 'tool' && ev.status === 'started') { setMood('working'); bubbleMeta.textContent = `Working: ${ev.tool}…`; }
        else if (ev.type === 'tool' && ev.approval_id) { bubbleMeta.textContent = 'Needs your approval — right-click › Open dashboard'; }
        else if (ev.type === 'final') { answer = ev.text || current; }
        else if (ev.type === 'error') throw new Error(ev.error || 'Assistant error');
      }
    }
    answer = answer || current;
    setMood('happy');
    showBubble(plain(answer), `You: ${text}`);
    if (state.speakReplies && answer) {
      api('/voice/speak', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text: plain(answer).slice(0, 4000)})}).catch(() => {});
    }
    scheduleHide(Math.min(45000, 12000 + answer.length * 40));
  } catch (e) {
    if (e.name === 'AbortError') showBubble('Stopped.', '', {autoHideMs: 3000});
    else { setMood('error'); showBubble(String(e.message || e), 'Assistant', {autoHideMs: 8000}); }
  } finally {
    state.busy = false;
    state.controller = null;
    setTimeout(refreshIdleMood, 2500);
  }
}

function plain(markdown) {
  return String(markdown || '').replace(/```[\s\S]*?```/g, '[code]').replace(/[*_`#>]/g, '').trim();
}

// ---- drag / click / menu ----------------------------------------------------------

let drag = null;
face.addEventListener('pointerdown', (e) => {
  if (e.button !== 0) return;
  drag = {x: e.screenX, y: e.screenY, moved: false};
  face.setPointerCapture(e.pointerId);
});
face.addEventListener('pointermove', (e) => {
  if (!drag) return;
  const dx = e.screenX - drag.x, dy = e.screenY - drag.y;
  if (!drag.moved && Math.hypot(dx, dy) < 4) return;
  drag.moved = true;
  drag.x = e.screenX; drag.y = e.screenY;
  if (shell) shell.moveBy(dx, dy);
});
face.addEventListener('pointerup', (e) => {
  // Only a press that started on the orb counts; a stray release must never start listening.
  if (!drag) return;
  const wasDrag = drag.moved;
  drag = null;
  try { face.releasePointerCapture(e.pointerId); } catch (_) {}
  if (!wasDrag) talk();
});
face.addEventListener('pointercancel', (e) => {
  drag = null;
  try { face.releasePointerCapture(e.pointerId); } catch (_) {}
});
face.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); talk(); } });
face.addEventListener('contextmenu', (e) => {
  e.preventDefault();
  if (shell && shell.menu) shell.menu({speakReplies: state.speakReplies});
  else window.open('/dashboard', '_blank');
});
if (shell && shell.onMenuAction) {
  shell.onMenuAction((action) => {
    if (action === 'toggle-speak') {
      state.speakReplies = !state.speakReplies;
      try { localStorage.setItem('agent_speak_replies', state.speakReplies ? '1' : '0'); } catch (_) {}
      showBubble('', state.speakReplies ? 'Spoken replies on' : 'Spoken replies off', {autoHideMs: 2500});
    }
  });
}
bubble.addEventListener('mouseenter', () => { state.hoverBubble = true; clearTimeout(state.hideTimer); });
bubble.addEventListener('mouseleave', () => { state.hoverBubble = false; if (!state.busy) scheduleHide(4000); });
bubble.addEventListener('click', () => { if (!state.busy) bubble.hidden = true; });

// Transparent areas of the window let clicks pass through to the desktop underneath.
function updateClickThrough(e) {
  if (!shell || !shell.setClickThrough) return;
  const el = document.elementFromPoint(e.clientX, e.clientY);
  const interactive = !!(el && (face.contains(el) || (!bubble.hidden && bubble.contains(el))));
  if (interactive !== updateClickThrough.last) {
    updateClickThrough.last = interactive;
    shell.setClickThrough(!interactive);
  }
}
document.addEventListener('mousemove', updateClickThrough, {passive: true});
document.addEventListener('mouseleave', () => { if (shell && shell.setClickThrough) { updateClickThrough.last = false; shell.setClickThrough(true); } });

// ---- background status ------------------------------------------------------------

async function pollStatus() {
  try {
    const approvals = await api('/approvals');
    const n = Array.isArray(approvals) ? approvals.length : 0;
    if (n && !state.approvals && !state.busy && actions.hidden) showBubble('', `${n} approval${n === 1 ? '' : 's'} waiting — right-click › Open dashboard`, {autoHideMs: 8000});
    state.approvals = n;
    state.online = true;
  } catch (_) {
    state.online = false;
  }
  refreshIdleMood();
}
pollStatus();
setInterval(pollStatus, 6000);
