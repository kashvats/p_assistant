/* Floating desktop agent: a round face with eyes that hovers over the desktop, and the
   main daily chat. Click the orb to open the chat panel, double-click to ask by voice,
   drag to move, right-click for options.

   The panel continues the server's shared active conversation - the same one the
   dashboard shows - and follows changes made elsewhere through the activity stream.
   Runs inside the Electron shell (window.agentShell) or any browser tab (degrades gracefully). */

import {ACCEPT, extractFiles, fileChip, kindOf, mediaList, uploadFile} from './chatmedia.js';

const shell = window.agentShell || null;
const token = document.querySelector('meta[name="assistant-token"]')?.getAttribute('content') || '';
const $ = (id) => document.getElementById(id);
const face = $('agent-face');
const bubble = $('agent-bubble');
const bubbleText = $('agent-bubble-text');
const bubbleMeta = $('agent-bubble-meta');
const actions = $('agent-bubble-actions');
const canvas = $('agent-spectrum');
const ctx = canvas.getContext('2d');
const pupils = [...document.querySelectorAll('#agent-face .pupil')];
const panel = $('agent-panel');
const list = $('agent-messages');
const input = $('agent-input');
const convoSelect = $('agent-convo');
const micMeter = $('agent-mic-meter');

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
  panelOpen: false,
  sessionId: null,
  messages: [],
  lastEvent: 0,
  pending: [],  // files attached to the next message: {id, name, kind, bytes}
};
const IMAGE_MARKER = /\[image (img_[0-9a-f]{16})\]/g;
const imageUrl = (id) => `/attachments/${id}${token ? `?token=${encodeURIComponent(token)}` : ''}`;

function readFlag(key, fallback) {
  try { const v = localStorage.getItem(key); return v === null ? fallback : v === '1'; } catch (_) { return fallback; }
}

function authHeaders(extra = {}) {
  return Object.assign({}, extra, token ? {Authorization: `Bearer ${token}`} : {});
}

async function api(path, options = {}) {
  const res = await fetch(path, {...options, headers: authHeaders(options.headers || {})});
  if (!res.ok) throw new Error((await res.text()).slice(0, 300) || `HTTP ${res.status}`);
  return (res.headers.get('content-type') || '').includes('json') ? res.json() : res.text();
}

const jsonBody = (body) => ({method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});

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
  bubble.hidden = state.panelOpen && !meta.startsWith('Microphone') ? true : (!text && !meta);
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

// ---- spectrum ring (and the small meter in the composer) ---------------------------

for (let i = 0; i < 16; i += 1) micMeter.appendChild(document.createElement('i'));
const meterBars = [...micMeter.children];

function drawSpectrum() {
  const w = canvas.width, h = canvas.height, cx = w / 2, cy = h / 2;
  ctx.clearRect(0, 0, w, h);
  const live = state.listening || state.micActive;
  const target = live ? state.bands : state.bands.map(() => 0);
  let energy = 0;
  for (let i = 0; i < 16; i += 1) {
    state.smooth[i] += (target[i] - state.smooth[i]) * 0.35;
    energy += state.smooth[i];
  }
  micMeter.hidden = !live;
  if (live) meterBars.forEach((el, i) => { el.style.height = `${Math.round(12 + state.smooth[i] * 88)}%`; });
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
        if (state.panelOpen) input.placeholder = label;
        else if (state.listening) bubbleMeta.textContent = label;
        else showBubble('', label);
      } else if (!active && !state.busy && bubble.hidden === false && !bubbleText.textContent && /^Listening|^Hearing/.test(bubbleMeta.textContent)) {
        bubble.hidden = true;
      }
      if (!active) input.placeholder = 'Message your assistant…  (Enter to send)';
    } catch (_) {
      state.bands = new Array(16).fill(0);
    }
    await new Promise((r) => setTimeout(r, active || state.listening ? 70 : 500));
  }
}
meterLoop();

// ---- conversation --------------------------------------------------------------

async function loadConversation(sessionId) {
  try {
    const active = sessionId ? {id: sessionId} : await api('/conversations/active');
    state.sessionId = active.id;
    const res = await api(`/conversations/${encodeURIComponent(active.id)}/messages`);
    if (state.busy) return;
    state.messages = (res.messages || []).filter((m) => m.role === 'user' || m.role === 'assistant')
      .map((m) => ({role: m.role, text: m.content, voice: m.source === 'voice', media: (m.meta && m.meta.media) || []}));
    // A turn keeps running on the server after a reload; show that the answer is still coming.
    const busy = await api(`/chat/running/${encodeURIComponent(active.id)}`).catch(() => null);
    if (busy && busy.running && !state.busy) state.messages.push({role: 'assistant', text: '', phase: 'Still working on it…'});
    renderMessages();
  } catch (_) {}
  loadConversationList();
}

async function loadConversationList() {
  try {
    const res = await api('/conversations?limit=30');
    convoSelect.replaceChildren(...(res.conversations || []).map((c) => {
      const opt = document.createElement('option');
      opt.value = c.id;
      opt.textContent = `${c.title || 'New conversation'}${c.message_count ? ` (${c.message_count})` : ''}`;
      return opt;
    }));
    if (state.sessionId && ![...convoSelect.options].some((o) => o.value === state.sessionId)) {
      const opt = document.createElement('option');
      opt.value = state.sessionId;
      opt.textContent = 'New conversation';
      convoSelect.prepend(opt);
    }
    convoSelect.value = state.sessionId || '';
  } catch (_) {}
}

convoSelect.addEventListener('change', async () => {
  if (state.busy) stopTurn();
  try { await api('/conversations/active', {...jsonBody({session_id: convoSelect.value}), method: 'PUT'}); } catch (_) { return; }
  loadConversation(convoSelect.value);
});

$('agent-new').addEventListener('click', async () => {
  if (state.busy) stopTurn();
  try {
    const created = await api('/conversations', jsonBody({}));
    state.sessionId = created.id;
    state.messages = [];
    renderMessages();
    loadConversationList();
    input.focus();
  } catch (e) { showNote(`Could not start a new conversation: ${e.message}`); }
});

// Safe rendering: text only (no HTML from the model), code fences as <pre>.
function renderText(el, text) {
  el.replaceChildren();
  String(text || '').split(/```[\w-]*\n?/).forEach((part, i) => {
    if (!part) return;
    const node = document.createElement(i % 2 ? 'pre' : 'div');
    node.className = i % 2 ? 'desk-code' : 'desk-text';
    node.textContent = i % 2 ? part.replace(/\n$/, '') : part;
    el.appendChild(node);
  });
}

function renderMessages() {
  list.replaceChildren(...state.messages.map((m, i) => {
    const row = document.createElement('div');
    row.className = `desk-msg ${m.role}`;
    const body = document.createElement('div');
    body.className = 'desk-msg-body';
    const {text, files} = extractFiles(m.text);
    const images = [...text.matchAll(IMAGE_MARKER)].map((x) => x[1]);
    renderText(body, (m.voice && m.role === 'user' ? '🎙 ' : '') + text.replace(IMAGE_MARKER, '').trim());
    if (files.length) {
      const chips = document.createElement('div');
      chips.className = 'chat-file-chips';
      files.forEach((f) => chips.appendChild(fileChip(f, token)));
      body.prepend(chips);
    }
    if (m.media && m.media.length) body.appendChild(mediaList(m.media, token));
    if (images.length) {
      const strip = document.createElement('div');
      strip.className = 'desk-msg-images';
      images.forEach((id) => {
        const img = document.createElement('img');
        img.src = imageUrl(id); img.alt = 'Attached image'; img.loading = 'lazy';
        strip.appendChild(img);
      });
      body.prepend(strip);
    }
    row.appendChild(body);
    if (m.phase) {
      const phase = document.createElement('div');
      phase.className = 'desk-msg-phase';
      phase.textContent = m.phase;
      row.appendChild(phase);
    }
    if (m.approvalId) row.appendChild(approvalButtons(m, i));
    return row;
  }));
  if (!state.messages.length) {
    const empty = document.createElement('div');
    empty.className = 'desk-empty';
    empty.textContent = 'Ask anything - type below, or press 🎙 and just say it.';
    list.appendChild(empty);
  }
  list.scrollTop = list.scrollHeight;
  const last = state.messages[state.messages.length - 1];
  $('agent-regen').hidden = state.busy || !last || last.role !== 'assistant';
  $('agent-stop').hidden = !state.busy;
  $('agent-send').hidden = state.busy;
}

function approvalButtons(m, index) {
  const wrap = document.createElement('div');
  wrap.className = 'desk-bubble-actions';
  const ok = document.createElement('button');
  ok.type = 'button'; ok.className = 'desk-btn primary'; ok.textContent = 'Approve & retry';
  const no = document.createElement('button');
  no.type = 'button'; no.className = 'desk-btn'; no.textContent = 'Deny';
  const decide = async (approved, e) => {
    if (!e.isTrusted) return;  // consent comes only from a real click
    try { await api(`/approvals/${encodeURIComponent(m.approvalId)}`, jsonBody({approved})); } catch (err) { return showNote(err.message); }
    state.messages[index] = {...m, approvalId: null, phase: approved ? 'Approved' : 'Denied'};
    renderMessages();
    if (approved && m.retryText) send(m.retryText, {voice: m.retryVoice});
  };
  ok.addEventListener('click', (e) => decide(true, e));
  no.addEventListener('click', (e) => decide(false, e));
  wrap.append(ok, no);
  return wrap;
}

function showNote(text) {
  if (state.panelOpen) {
    state.messages.push({role: 'assistant', text, phase: 'Note'});
    renderMessages();
  } else {
    showBubble(text, 'Assistant', {autoHideMs: 7000});
  }
}

// ---- one turn: stream the answer into the panel (and the bubble when the panel is closed) ----

async function send(text, {voice = false, regenerate = false} = {}) {
  text = String(text || '').trim();
  const attached = regenerate ? [] : state.pending.slice();
  const images = attached.filter((p) => p.kind === 'image').map((p) => p.id);
  const files = attached.filter((p) => p.kind !== 'image');
  if ((!text && !attached.length && !regenerate) || state.busy) return;
  if (!text && attached.length) text = files.length ? 'Please look at the attached file.' : 'What is in this image?';
  state.busy = true;
  setMood('thinking');
  state.pending = [];
  renderPending();
  if (!regenerate) {
    state.messages.push({role: 'user', voice, text: [text, ...images.map((id) => `[image ${id}]`),
      ...files.map((f) => `[file ${f.id} ${f.name}]`)].join('\n')});
  }
  const reply = {role: 'assistant', text: '', phase: 'Thinking…', retryText: text, retryVoice: voice};
  state.messages.push(reply);
  renderMessages();
  if (!state.panelOpen) showBubble('', `You: ${text}`);
  const controller = new AbortController();
  state.controller = controller;
  let answer = '', current = '';
  try {
    const res = await fetch(regenerate ? '/chat/regenerate' : '/chat/stream', {
      method: 'POST', signal: controller.signal,
      headers: authHeaders({'Content-Type': 'application/json', Accept: 'text/event-stream'}),
      body: JSON.stringify(regenerate ? {session_id: state.sessionId}
        : {message: text, session_id: state.sessionId, source: voice ? 'voice' : 'text', images, files: files.map((f) => f.id)}),
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
        if (ev.type === 'status' && ev.status === 'looking') { setMood('working'); reply.phase = 'Looking at the image…'; }
        else if (ev.type === 'status' && ev.status === 'reading') { setMood('working'); reply.phase = 'Reading the attached file…'; }
        else if (ev.type === 'tool' && ev.media && ev.media.length && ev.status === 'completed') { reply.media = [...(reply.media || []), ...ev.media]; }
        else if (ev.type === 'status' && ev.status === 'generating') { current = ''; setMood('thinking'); reply.phase = 'Thinking…'; }
        else if (ev.type === 'token') { current += ev.text || ''; reply.text = current; reply.phase = 'Writing…'; if (!state.panelOpen) { bubbleText.textContent = current; bubbleText.scrollTop = bubbleText.scrollHeight; } }
        else if (ev.type === 'tool' && ev.status === 'started') { setMood('working'); reply.phase = `Working: ${ev.tool}…`; if (!state.panelOpen) bubbleMeta.textContent = reply.phase; }
        else if (ev.type === 'tool' && ev.approval_id) { reply.approvalId = ev.approval_id; reply.phase = `Needs your approval: ${ev.tool}`; }
        else if (ev.type === 'final') { answer = ev.text || current; if (ev.media) reply.media = ev.media; }
        else if (ev.type === 'stopped') { reply.phase = 'Stopped'; }
        else if (ev.type === 'error') throw new Error(ev.error || 'Assistant error');
        renderMessages();
      }
    }
    answer = answer || current;
    reply.text = answer || reply.text;
    if (reply.phase !== 'Stopped' && !reply.approvalId) reply.phase = null;
    setMood('happy');
    if (!state.panelOpen) { showBubble(plain(answer), `You: ${text}`); scheduleHide(Math.min(45000, 12000 + answer.length * 40)); }
    if (state.speakReplies && answer && reply.phase !== 'Stopped') {
      api('/voice/speak', jsonBody({text: plain(answer).slice(0, 4000)})).catch(() => {});
    }
  } catch (e) {
    if (e.name === 'AbortError') reply.phase = 'Stopped';
    else { setMood('error'); reply.phase = null; reply.text = `⚠ ${e.message || e}`; if (!state.panelOpen) showBubble(String(e.message || e), 'Assistant', {autoHideMs: 8000}); }
  } finally {
    state.busy = false;
    state.controller = null;
    renderMessages();
    setTimeout(refreshIdleMood, 2500);
    loadConversationList();
  }
}

// ---- images: attach, paste, drop, or capture the screen -------------------------------

const attachStrip = $('agent-attachments');
const fileInput = $('agent-file');

function renderPending() {
  attachStrip.replaceChildren(...state.pending.map((p, i) => {
    const remove = () => { state.pending.splice(i, 1); renderPending(); };
    if (p.kind !== 'image') return fileChip({...p, ref: p.id}, token, {onRemove: remove});
    const chip = document.createElement('span');
    chip.className = 'desk-attachment';
    const img = document.createElement('img');
    img.src = imageUrl(p.id); img.alt = p.name || 'Attached image';
    const x = document.createElement('button');
    x.type = 'button'; x.textContent = '✕'; x.title = 'Remove'; x.setAttribute('aria-label', 'Remove image');
    x.addEventListener('click', remove);
    chip.append(img, x);
    return chip;
  }));
  attachStrip.hidden = !state.pending.length;
}

// Any supported file: images, video, audio, PDFs, spreadsheets, documents, text.
async function attachBlob(blob, name = '') {
  if (!blob) return;
  const isImage = String(blob.type || '').startsWith('image/');
  name = name || blob.name || (isImage ? 'pasted image.png' : 'file');
  if (isImage && !/\.[a-z0-9]{1,6}$/i.test(name)) name += '.png';
  const images = state.pending.filter((p) => p.kind === 'image').length;
  if (kindOf(name) === 'image' ? images >= 4 : state.pending.length - images >= 8) {
    return showNote('That is the most files one message can carry (4 images, 8 other files).');
  }
  attachStrip.hidden = false;
  attachStrip.dataset.uploading = name;
  try {
    const saved = await uploadFile(blob, token, name);
    state.pending.push({id: saved.id, name: saved.name, kind: saved.kind, bytes: saved.bytes});
    input.focus();
  } catch (e) {
    showNote(`Could not attach ${name}: ${e.message}`);
  } finally {
    delete attachStrip.dataset.uploading;
    renderPending();
  }
}

fileInput.setAttribute('accept', ACCEPT);
fileInput.multiple = true;
$('agent-attach').addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => {
  [...fileInput.files].forEach((f) => attachBlob(f, f.name));
  fileInput.value = '';
});
input.addEventListener('paste', (e) => {
  const files = [...(e.clipboardData?.items || [])].filter((it) => it.kind === 'file').map((it) => it.getAsFile()).filter(Boolean);
  if (files.length) { e.preventDefault(); files.forEach((f) => attachBlob(f, f.name && f.name !== 'image.png' ? f.name : '')); }
});
panel.addEventListener('dragover', (e) => { if ([...(e.dataTransfer?.items || [])].some((it) => it.kind === 'file')) e.preventDefault(); });
panel.addEventListener('drop', (e) => {
  const files = [...(e.dataTransfer?.files || [])];
  if (files.length) { e.preventDefault(); files.forEach((f) => attachBlob(f, f.name)); }
});

// Screen capture is done by the desktop shell (the agent window hides itself first),
// only when the user clicks the button.
const captureBtn = $('agent-capture');
if (shell && shell.captureScreen) {
  captureBtn.hidden = false;
  captureBtn.addEventListener('click', async (e) => {
    if (!e.isTrusted) return;
    try {
      const dataUrl = await shell.captureScreen();
      if (!dataUrl) return;
      const blob = await (await fetch(dataUrl)).blob();
      await attachBlob(blob, 'screen capture.png');
      if (!input.value.trim()) input.value = 'What is on my screen?';
    } catch (err) { showNote(`Screen capture failed: ${err.message || err}`); }
  });
}

// Kill switch (tray, right-click menu or Ctrl+Alt+Shift+K; the shell already asked for confirmation):
// the backend halts everything and exits, then the shell quits.
async function killSwitch() {
  setMood('error');
  showBubble('Stopping everything…', 'Kill switch');
  try { await api('/system/kill', jsonBody({mode: 'shutdown', reason: 'kill switch (desktop)'})); } catch (_) {}
  if (shell && shell.quitApp) shell.quitApp();
}

function stopTurn() {
  if (state.controller) state.controller.abort();
  if (state.sessionId) api('/chat/stop', jsonBody({session_id: state.sessionId})).catch(() => {});
}

function plain(markdown) {
  return String(markdown || '').replace(/```[\s\S]*?```/g, '[code]').replace(/[*_`#>]/g, '').trim();
}

// ---- voice: listen -> transcript -> the same conversation ----------------------------

async function talk() {
  if (state.busy) { stopTurn(); return; }
  state.busy = true;
  state.listening = true;
  setMood('listening');
  if (!state.panelOpen) showBubble('', 'Listening… speak now');
  let transcript = '';
  try {
    const res = await api('/voice/transcribe', jsonBody({max_seconds: 15}));
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
    showNote(String(e.message || e));
    setTimeout(refreshIdleMood, 2500);
    return;
  }
  state.busy = false;
  await send(transcript, {voice: true});
}

function askMicApproval(approvalId) {
  setMood('alert');
  showBubble('Allow the assistant to listen to your microphone for this request?', 'Microphone approval');
  bubble.hidden = false;
  actions.hidden = false;
  const decide = async (approved, e) => {
    e.stopPropagation();
    if (!e.isTrusted || actions.hidden) return; // consent comes only from a real click on a visible prompt
    actions.hidden = true;
    $('agent-allow').onclick = $('agent-deny').onclick = null;
    try {
      await api(`/approvals/${encodeURIComponent(approvalId)}`, jsonBody({approved}));
    } catch (err) {
      showBubble(String(err.message || err), 'Approval', {autoHideMs: 6000});
      return refreshIdleMood();
    }
    bubble.hidden = true;
    if (approved) talk();
    else refreshIdleMood();
  };
  $('agent-allow').onclick = (e) => decide(true, e);
  $('agent-deny').onclick = (e) => decide(false, e);
  $('agent-allow').focus();
}

// ---- panel ----------------------------------------------------------------------

async function openPanel(open) {
  if (open === state.panelOpen) return;
  state.panelOpen = open;
  if (shell && shell.setExpanded) await shell.setExpanded(open);
  panel.hidden = !open;
  if (open) {
    bubble.hidden = true;
    loadConversation();
    setTimeout(() => input.focus(), 50);
  }
}

$('agent-close').addEventListener('click', () => openPanel(false));
$('agent-dash').addEventListener('click', () => { if (shell && shell.openDashboard) shell.openDashboard(); else window.open('/dashboard', '_blank'); });
$('agent-mic').addEventListener('click', () => talk());
$('agent-stop').addEventListener('click', () => stopTurn());
$('agent-regen').addEventListener('click', () => {
  const lastUser = [...state.messages].reverse().find((m) => m.role === 'user');
  if (!lastUser || state.busy) return;
  state.messages = state.messages.slice(0, state.messages.lastIndexOf(lastUser) + 1);
  send(lastUser.text, {voice: lastUser.voice, regenerate: true});
});
const speakBtn = $('agent-speak');
function syncSpeak() { speakBtn.setAttribute('aria-pressed', String(state.speakReplies)); speakBtn.textContent = state.speakReplies ? '🔊' : '🔈'; }
function toggleSpeak() {
  state.speakReplies = !state.speakReplies;
  try { localStorage.setItem('agent_speak_replies', state.speakReplies ? '1' : '0'); } catch (_) {}
  syncSpeak();
}
speakBtn.addEventListener('click', toggleSpeak);
syncSpeak();

$('agent-form').addEventListener('submit', (e) => {
  e.preventDefault();
  const text = input.value;
  input.value = '';
  autosize();
  send(text);
});
input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('agent-form').requestSubmit(); }
  else if (e.key === 'Escape') { e.preventDefault(); if (state.busy) stopTurn(); else openPanel(false); }
});
function autosize() { input.style.height = 'auto'; input.style.height = `${Math.min(140, input.scrollHeight)}px`; }
input.addEventListener('input', autosize);

// ---- drag / click / menu ----------------------------------------------------------

let drag = null;
let clickTimer = null;
// Ends a drag however it finishes (release, cancel, lost capture, focus loss). Returns
// whether the orb actually moved. A drag must never outlive the button press, or merely
// hovering the orb later would keep moving the window.
function endDrag(pointerId) {
  if (!drag) return false;
  const moved = drag.moved;
  const id = pointerId ?? drag.pointerId;
  drag = null;
  try { face.releasePointerCapture(id); } catch (_) {}
  if (moved && shell) {
    if (shell.dragEnd) shell.dragEnd();
    else if (shell.savePosition) shell.savePosition();
  }
  return moved;
}
face.addEventListener('pointerdown', (e) => {
  if (e.button !== 0) return;
  drag = {x: e.screenX, y: e.screenY, moved: false, pointerId: e.pointerId};
  face.setPointerCapture(e.pointerId);
});
face.addEventListener('pointermove', (e) => {
  if (!drag) return;
  if ((e.buttons & 1) === 0) { endDrag(e.pointerId); return; }  // the release was missed
  const dx = e.screenX - drag.x, dy = e.screenY - drag.y;
  if (!drag.moved && Math.hypot(dx, dy) < 4) return;
  if (!drag.moved && shell && shell.dragStart) shell.dragStart();
  drag.moved = true;
  drag.x = e.screenX; drag.y = e.screenY;
  if (!shell) return;
  if (shell.dragMove) shell.dragMove();
  else shell.moveBy(dx, dy);
});
face.addEventListener('pointerup', (e) => {
  // Only a press that started on the orb counts; a stray release must never start listening.
  if (!drag) return;
  if (endDrag(e.pointerId)) return;
  // Single click toggles the chat; a second click within 280 ms makes it a quick voice question.
  if (clickTimer) { clearTimeout(clickTimer); clickTimer = null; talk(); return; }
  clickTimer = setTimeout(() => { clickTimer = null; openPanel(!state.panelOpen); }, 280);
});
face.addEventListener('pointercancel', (e) => endDrag(e.pointerId));
face.addEventListener('lostpointercapture', (e) => endDrag(e.pointerId));
window.addEventListener('blur', () => endDrag());
face.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openPanel(!state.panelOpen); }
});
face.addEventListener('contextmenu', (e) => {
  e.preventDefault();
  if (shell && shell.menu) shell.menu({speakReplies: state.speakReplies});
  else window.open('/dashboard', '_blank');
});
if (shell && shell.onMenuAction) {
  shell.onMenuAction((action) => {
    if (action === 'toggle-speak') { toggleSpeak(); showBubble('', state.speakReplies ? 'Spoken replies on' : 'Spoken replies off', {autoHideMs: 2500}); }
    else if (action === 'open-chat') openPanel(true);
    else if (action === 'toggle-chat') openPanel(!state.panelOpen);
    else if (action === 'talk') talk();
    else if (action === 'kill') killSwitch();
  });
}
bubble.addEventListener('mouseenter', () => { state.hoverBubble = true; clearTimeout(state.hideTimer); });
bubble.addEventListener('mouseleave', () => { state.hoverBubble = false; if (!state.busy) scheduleHide(4000); });
bubble.addEventListener('click', () => { if (!state.busy && actions.hidden) { bubble.hidden = true; openPanel(true); } });

// Transparent areas of the window let clicks pass through to the desktop underneath.
function updateClickThrough(e) {
  if (!shell || !shell.setClickThrough) return;
  // While dragging the cursor can briefly leave the orb; turning click-through on then would
  // send the button release to the desktop and leave the drag stuck.
  if (drag) return;
  const el = document.elementFromPoint(e.clientX, e.clientY);
  const interactive = !!(el && (face.contains(el) || (!bubble.hidden && bubble.contains(el)) || (!panel.hidden && panel.contains(el))));
  if (interactive !== updateClickThrough.last) {
    updateClickThrough.last = interactive;
    shell.setClickThrough(!interactive);
  }
}
document.addEventListener('mousemove', updateClickThrough, {passive: true});
document.addEventListener('mouseleave', () => { if (drag) return; if (shell && shell.setClickThrough) { updateClickThrough.last = false; shell.setClickThrough(true); } });

// ---- live sync with the dashboard and other interfaces ---------------------------------

async function followActivity() {
  while (true) {
    try {
      const res = await fetch(`/activity/stream?after_id=${state.lastEvent}`, {headers: authHeaders({Accept: 'text/event-stream'})});
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
          state.lastEvent = Math.max(state.lastEvent, Number(ev.id || 0));
          const sid = ev.data && ev.data.session_id;
          if (ev.type === 'conversation.active' && sid && sid !== state.sessionId && !state.busy) loadConversation(sid);
          else if ((ev.type === 'chat.completed' || ev.type === 'chat.updated') && sid === state.sessionId && !state.busy && state.panelOpen) loadConversation(sid);
          // The kill switch was used elsewhere (dashboard): quit the desktop shell too. Old events
          // replayed from history must not close a freshly started app.
          else if (ev.type === 'system.killed' && Date.now() - Date.parse(ev.created_at || 0) < 60000 && shell && shell.quitApp) shell.quitApp();
        }
      }
    } catch (_) {}
    await new Promise((r) => setTimeout(r, 3000));  // reconnect (the backend may be restarting)
  }
}
followActivity();

// ---- background status: approvals and backend reachability ---------------------------

async function pollStatus() {
  const wasOnline = state.online;
  try {
    const approvals = await api('/approvals');
    const n = Array.isArray(approvals) ? approvals.length : 0;
    if (n && !state.approvals && !state.busy && actions.hidden) showBubble('', `${n} approval${n === 1 ? '' : 's'} waiting — right-click › Open dashboard`, {autoHideMs: 8000});
    state.approvals = n;
    state.online = true;
  } catch (_) {
    state.online = false;
  }
  $('agent-offline').hidden = state.online;
  if (state.online && !wasOnline && state.panelOpen) loadConversation();  // back after a restart
  refreshIdleMood();
}
pollStatus();
setInterval(pollStatus, 6000);
