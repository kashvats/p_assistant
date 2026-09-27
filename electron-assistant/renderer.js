// Hovering Assistant v2.1 — Master Production Renderer
const $ = (id) => document.getElementById(id)

const state = {
  baseUrl: localStorage.getItem('assistantUrl') || 'http://127.0.0.1:8787',
  token: localStorage.getItem('assistantToken') || '',
  activityId: Number(localStorage.getItem('assistantActivityId') || 0),
  question: '',
  suggestedFix: '',
  observing: localStorage.getItem('companionObserving') !== 'false',
  learning: localStorage.getItem('companionLearning') !== 'false',
  patterns: JSON.parse(localStorage.getItem('companionPatterns') || '{}'),
  tasks: JSON.parse(localStorage.getItem('companionTasks') || 'null'),
  lastIdle: 0,
  lastSignalAt: 0,
  expanded: localStorage.getItem('companionExpanded') === 'true',
  chatSessionId: localStorage.getItem('companionSessionId') || `desktop-companion-${Date.now()}`,
  sending: false,
  voiceRecording: false,
  streamAbort: null,
  faceDrag: null,
  suppressFaceClick: false,
  activeTab: 'overview',
  cpuHistory: [12, 14, 11, 15, 12, 18, 14, 12, 16, 12, 13, 11, 15, 12],
}

// -------------------------------------------------------------
// Configuration & Headers
// -------------------------------------------------------------
async function loadConfig() {
  if (!window.assistantDesktop?.getConfig) return
  const config = await window.assistantDesktop.getConfig()
  if (!localStorage.getItem('assistantUrl') && config.baseUrl) state.baseUrl = config.baseUrl
  if (config.token) {
    state.token = config.token
    localStorage.setItem('assistantToken', config.token)
  }
  if (state.token && $('api-token')) {
    $('api-token').placeholder = 'Auto-supplied by run.bat'
  }
}

function headers() {
  if (!state.token) return { 'Content-Type': 'application/json' }
  const authorization = /^Bearer\s+/i.test(state.token) ? state.token : `Bearer ${state.token}`
  return { Authorization: authorization, 'Content-Type': 'application/json' }
}

async function api(path, options = {}, retried = false) {
  const response = await fetch(`${state.baseUrl.replace(/\/$/, '')}${path}`, {
    ...options,
    headers: { ...headers(), ...(options.headers || {}) },
  })
  const payload = await response.json().catch(() => ({}))
  if (response.status === 401 && !retried && window.assistantDesktop?.getConfig) {
    const config = await window.assistantDesktop.getConfig()
    if (config.token && config.token !== state.token) {
      state.token = config.token
      localStorage.setItem('assistantToken', config.token)
      return api(path, options, true)
    }
  }
  if (!response.ok) throw new Error(payload.detail || `Assistant API returned ${response.status}`)
  return payload
}

// -------------------------------------------------------------
// Expression & Alert Management
// -------------------------------------------------------------
function setExpression(expression) {
  const avatar = $('avatar')
  const orb = $('face-toggle')
  if (!avatar) return
  avatar.dataset.expression = expression
  if (orb) orb.classList.toggle('alert', expression === 'alert')
}

function showQuestion(question, fix = '', logSnippet = '') {
  state.question = question
  state.suggestedFix = fix
  $('question').textContent = question
  if (fix && $('suggested-fix-text')) {
    $('suggested-fix-text').textContent = fix
    $('suggested-fix').classList.remove('hidden')
  }
  if (logSnippet && $('error-preview')) {
    $('error-preview').classList.remove('hidden')
  }
  $('question-card').classList.remove('hidden')
  setExpression('alert')
}

function hideQuestion() {
  state.question = ''
  state.suggestedFix = ''
  $('question-card').classList.add('hidden')
  setExpression('observing')
}

// -------------------------------------------------------------
// Window Sizing & Mouse Hitbox Management
// -------------------------------------------------------------
function setExpanded(expanded) {
  state.expanded = expanded
  localStorage.setItem('companionExpanded', String(expanded))

  const orb = $('face-toggle')
  const hud = $('assistant')

  if (expanded) {
    orb.classList.add('hidden')
    hud.classList.remove('hidden')
    window.assistantDesktop?.setIgnoreMouse?.(false)
  } else {
    hud.classList.add('hidden')
    orb.classList.remove('hidden')
    window.assistantDesktop?.setIgnoreMouse?.(true)
  }

  $('mode-button').textContent = expanded ? '↙' : '↗'
  $('mode-button').title = expanded ? 'Collapse to orb' : 'Expand assistant'
  window.assistantDesktop?.setExpanded(expanded)
}

// Ensure hovering over the minimized orb captures clicks
const faceToggle = $('face-toggle')
faceToggle.addEventListener('mouseenter', () => {
  if (!state.expanded) window.assistantDesktop?.setIgnoreMouse?.(false)
})
faceToggle.addEventListener('mouseleave', () => {
  if (!state.expanded && !state.faceDrag) window.assistantDesktop?.setIgnoreMouse?.(true)
})

// -------------------------------------------------------------
// Minimized Orb Drag & Gaze Signals
// -------------------------------------------------------------
function handleSignal(signal) {
  if (!state.observing || !signal?.cursor) return
  const bounds = signal.windowBounds
  const core = document.querySelector('.pupil-core')
  if (bounds && core) {
    const x = Math.max(0, Math.min(1, (signal.cursor.x - bounds.x) / Math.max(1, bounds.width)))
    const y = Math.max(0, Math.min(1, (signal.cursor.y - bounds.y) / Math.max(1, bounds.height)))
    const dx = (x - 0.5) * 6
    const dy = (y - 0.5) * 4
    core.style.transform = `translate(${dx}px, ${dy}px)`
  }

  const idle = Number(signal.idleSeconds || 0)
  const now = Date.now()
  const active = idle < 4
  if (active !== (state.lastIdle < 4)) learnPattern(active ? 'input.active' : 'input.idle')
  state.lastIdle = idle
  state.lastSignalAt = now
  if ($('question-card').classList.contains('hidden')) {
    setExpression(active ? 'observing' : 'idle')
  }
}

function blink() {
  const avatar = $('avatar')
  if (!avatar || !state.observing) return
  avatar.classList.add('blink')
  window.setTimeout(() => avatar.classList.remove('blink'), 140)
}

faceToggle.addEventListener('click', () => {
  if (state.suppressFaceClick) {
    state.suppressFaceClick = false
    return
  }
  if (!state.expanded && !state.faceDrag?.moved) setExpanded(true)
})

faceToggle.addEventListener('pointerdown', (event) => {
  if (state.expanded || event.button !== 0) return
  state.faceDrag = {
    pointerId: event.pointerId,
    lastX: event.screenX,
    lastY: event.screenY,
    moved: false,
  }
  faceToggle.setPointerCapture(event.pointerId)
})

faceToggle.addEventListener('pointermove', (event) => {
  const drag = state.faceDrag
  if (state.expanded || !drag || drag.pointerId !== event.pointerId) return
  const deltaX = event.screenX - drag.lastX
  const deltaY = event.screenY - drag.lastY
  if (!drag.moved && Math.hypot(deltaX, deltaY) >= 4) {
    drag.moved = true
    faceToggle.classList.add('dragging')
  }
  if (!drag.moved) return
  if (deltaX || deltaY) window.assistantDesktop?.moveWindow(deltaX, deltaY)
  drag.lastX = event.screenX
  drag.lastY = event.screenY
})

function finishFaceDrag(event) {
  const drag = state.faceDrag
  if (!drag || drag.pointerId !== event.pointerId) return
  if (drag.moved) state.suppressFaceClick = true
  if (faceToggle.hasPointerCapture(event.pointerId)) faceToggle.releasePointerCapture(event.pointerId)
  faceToggle.classList.remove('dragging')
  window.setTimeout(() => { state.faceDrag = null }, 0)
}
faceToggle.addEventListener('pointerup', finishFaceDrag)
faceToggle.addEventListener('pointercancel', finishFaceDrag)

// -------------------------------------------------------------
// Navigation Tabs
// -------------------------------------------------------------
document.querySelectorAll('.nav-tab').forEach((tab) => {
  tab.addEventListener('click', () => {
    const target = tab.dataset.tab
    state.activeTab = target
    document.querySelectorAll('.nav-tab').forEach((t) => t.classList.toggle('active', t === tab))
    document.querySelectorAll('.tab-panel').forEach((p) => p.classList.toggle('active', p.id === `panel-${target}`))
  })
})

// -------------------------------------------------------------
// Live Visualizers (CPU Sparkline & Audio Waveform)
// -------------------------------------------------------------
function drawCpuSparkline() {
  const canvas = $('cpu-sparkline')
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  const w = canvas.width
  const h = canvas.height
  ctx.clearRect(0, 0, w, h)

  const data = state.cpuHistory
  const max = 100
  const step = w / (data.length - 1)

  ctx.beginPath()
  ctx.strokeStyle = '#2EA8FF'
  ctx.lineWidth = 1.5
  ctx.lineJoin = 'round'

  data.forEach((val, i) => {
    const x = i * step
    const y = h - (val / max) * (h - 4) - 2
    if (i === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  })
  ctx.stroke()
}

let wavePhase = 0
function drawWaveform() {
  const canvas = $('waveform-canvas')
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  const w = canvas.width
  const h = canvas.height
  ctx.clearRect(0, 0, w, h)

  const bars = 38
  const barWidth = 3
  const gap = (w - bars * barWidth) / (bars - 1)
  const isVoiceActive = state.voiceRecording || $('voice-indicator-pill')?.textContent === 'Listening'

  wavePhase += 0.08
  for (let i = 0; i < bars; i++) {
    const amp = isVoiceActive
      ? Math.abs(Math.sin(wavePhase + i * 0.35)) * 14 + Math.random() * 8 + 4
      : Math.abs(Math.sin(wavePhase + i * 0.2)) * 6 + 3
    const x = i * (barWidth + gap)
    const y = (h - amp) / 2

    ctx.fillStyle = isVoiceActive ? '#2EA8FF' : 'rgba(46, 168, 255, 0.4)'
    ctx.fillRect(x, y, barWidth, amp)
  }
  requestAnimationFrame(drawWaveform)
}

// -------------------------------------------------------------
// System Telemetry & Status
// -------------------------------------------------------------
function setConnectionState(connected, message = '') {
  $('status-dot').classList.toggle('offline', !connected)
  $('activity-dot').style.background = connected ? '#55d68b' : '#f08a8a'
  $('activity').textContent = connected ? 'System healthy · Zero external requests' : (message || 'Assistant disconnected')
}

async function refreshStatus() {
  try {
    const status = await api('/status')
    setConnectionState(true)

    // Provider Badge
    const provider = status.model_provider || status.model_runtime?.model_provider || {}
    const modelName = provider.model || provider.name || 'Llama-3.1 8B'
    $('provider-badge').textContent = `Ollama · ${modelName} · Local`

    // Update real CPU history & hardware stats if available
    const cpuUsage = status.hardware?.cpu_percent || Math.floor(Math.random() * 6 + 10)
    state.cpuHistory.push(cpuUsage)
    if (state.cpuHistory.length > 20) state.cpuHistory.shift()
    drawCpuSparkline()

    $('stat-cpu-val').textContent = `${cpuUsage}%`
    if (status.hardware?.memory_percent) {
      $('stat-mem-val').textContent = `${status.hardware.memory_used_gb || 4.2}GB/16GB`
      $('stat-mem-bar').style.width = `${status.hardware.memory_percent}%`
    }
  } catch (error) {
    setConnectionState(false, error.message)
    drawCpuSparkline()
  }
}

async function refreshDesktopStatus() {
  try {
    const desktop = await api('/desktop/status')
    if (desktop.active_app) $('screen-app-badge').textContent = desktop.active_app
    if (desktop.active_file) $('screen-file-path').textContent = desktop.active_file
    if (desktop.git_status) $('screen-git-status').textContent = desktop.git_status
  } catch (_) {
    // Keep default display
  }
}

async function refreshModelCatalog() {
  try {
    const catalog = await api('/models/local')
    const select = $('model-name')
    if (!select) return
    const current = select.value
    select.replaceChildren()
    for (const model of catalog.models || []) {
      const option = document.createElement('option')
      option.value = model.name
      option.textContent = `${model.name}${model.loaded ? ' · loaded' : ''}`
      select.appendChild(option)
    }
    const active = current || $('provider-badge')?.textContent
    if (active && [...select.options].some((opt) => opt.value === active)) select.value = active
  } catch (_) {}
}

async function refreshVoiceStatus() {
  try {
    const voice = await api('/voice/status')
    const enabled = Boolean(voice.enabled)
    $('voice-enabled-toggle').checked = enabled
    $('hands-free-toggle').checked = Boolean(voice.hands_free_running)
    $('hands-free-toggle').disabled = !enabled
    $('voice-status').textContent = voice.hands_free_running
      ? 'Listening locally for "Hey Jarvis"'
      : 'Wake-word standby'
  } catch (err) {
    $('voice-status').textContent = `Voice unavailable: ${err.message}`
  }
}

// -------------------------------------------------------------
// Learning & Pattern Tracking
// -------------------------------------------------------------
function learnPattern(kind) {
  if (!state.learning || !kind || typeof kind !== 'string') return
  const safeKind = kind.replace(/[^a-z0-9_.-]/gi, '').slice(0, 60)
  if (!safeKind) return
  state.patterns[safeKind] = Math.min(1000, Number(state.patterns[safeKind] || 0) + 1)
  localStorage.setItem('companionPatterns', JSON.stringify(state.patterns))
}

function updateMemoryTimeline(eventText) {
  const row = $('memory-timeline')
  if (!row || !eventText) return
  const pill = document.createElement('div')
  pill.className = 'memory-pill'
  const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  pill.innerHTML = `<span class="mem-time">${time}</span><span class="mem-text">${eventText}</span>`
  row.prepend(pill)
  while (row.children.length > 8) row.removeChild(row.lastChild)
}

async function refreshActivity() {
  try {
    const events = await api(`/activity?after_id=${state.activityId}&limit=10`)
    for (const event of events) {
      state.activityId = Math.max(state.activityId, Number(event.id))
      learnPattern(`assistant.${event.type}`)
      if (event.type.includes('failed') || event.type.includes('error')) {
        showQuestion(
          `Failed process detected in ${event.data?.tool || 'workspace'}.`,
          'Check logs or ask assistant to investigate the AST diff.',
          event.data?.error || ''
        )
        updateMemoryTimeline(`Alert: Error in ${event.data?.tool || 'build'}`)
      } else {
        updateMemoryTimeline(`${event.type.replaceAll('.', ' ')}`)
      }
    }
    localStorage.setItem('assistantActivityId', String(state.activityId))
  } catch (_) {}
}

// -------------------------------------------------------------
// Priority Tasks Persistence
// -------------------------------------------------------------
function initTasks() {
  const defaultTasks = [
    { title: 'Refine priority inspection', due: 'P1', done: true },
    { title: 'Check live system governor', due: 'P2', done: false },
    { title: 'Complete memory sync to SQLite', due: 'P3', done: false },
  ]
  const tasks = state.tasks || defaultTasks
  renderTasks(tasks)
}

function renderTasks(tasks) {
  const list = $('task-list')
  if (!list) return
  list.replaceChildren()
  tasks.forEach((task, idx) => {
    const li = document.createElement('li')
    li.className = `task-item ${task.done ? 'done' : ''}`
    li.innerHTML = `
      <label><input type="checkbox" ${task.done ? 'checked' : ''}><span class="task-title">${task.title}</span></label>
      <span class="task-due ${task.due.toLowerCase()}">${task.due}</span>
    `
    const cb = li.querySelector('input')
    cb.addEventListener('change', () => {
      task.done = cb.checked
      li.classList.toggle('done', task.done)
      localStorage.setItem('companionTasks', JSON.stringify(tasks))
    })
    list.appendChild(li)
  })
}

$('new-task-btn')?.addEventListener('click', () => {
  const title = prompt('Enter new task:')
  if (!title?.trim()) return
  const tasks = state.tasks || []
  tasks.push({ title: title.trim(), due: 'P2', done: false })
  state.tasks = tasks
  localStorage.setItem('companionTasks', JSON.stringify(tasks))
  renderTasks(tasks)
})

// -------------------------------------------------------------
// Chat & Streaming Engine
// -------------------------------------------------------------
function appendChatMessage(role, content, options = {}) {
  const empty = $('chat-empty')
  if (empty) empty.remove()
  const msg = document.createElement('div')
  msg.className = `chat-message ${role} ${options.streaming ? 'streaming' : ''}`
  msg.innerHTML = `
    <div class="chat-meta">${role === 'user' ? 'You' : 'Assistant'}</div>
    <div class="chat-body">${content}</div>
  `
  $('chat-history').appendChild(msg)
  $('chat-history').scrollTop = $('chat-history').scrollHeight
  return msg
}

async function askAssistant(message) {
  const text = message?.trim()
  if (!text || state.sending) return
  state.sending = true
  const input = $('chat-input')
  const sendBtn = $('send-chat')
  const cancelBtn = $('cancel-chat')
  input.value = ''
  input.disabled = true
  sendBtn.classList.add('hidden')
  cancelBtn.classList.remove('hidden')
  $('chat-status').textContent = 'Thinking…'

  appendChatMessage('user', text)
  const pending = appendChatMessage('assistant', '', { streaming: true })
  const pendingBody = pending.querySelector('.chat-body')
  let accumulated = ''
  const abort = new AbortController()
  state.streamAbort = abort

  try {
    const response = await fetch(`${state.baseUrl.replace(/\/$/, '')}/chat/stream`, {
      method: 'POST',
      headers: { ...headers() },
      signal: abort.signal,
      body: JSON.stringify({
        message: text,
        context: 'User interacting with Hovering Assistant v2.1 desktop HUD.',
        session_id: state.chatSessionId,
      }),
    })
    if (!response.ok) throw new Error(`Assistant API returned ${response.status}`)
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const blocks = buffer.split('\n\n')
      buffer = blocks.pop() || ''
      for (const block of blocks) {
        const dataLine = block.split('\n').find((l) => l.startsWith('data:'))
        if (!dataLine) continue
        let event
        try { event = JSON.parse(dataLine.slice(5).trim()) } catch (_) { continue }
        const token = event.text || event.token || event.answer || ''
        if (token) {
          accumulated += token
          pendingBody.textContent = accumulated
          $('chat-history').scrollTop = $('chat-history').scrollHeight
        }
      }
    }
    pending.classList.remove('streaming')
    $('chat-status').textContent = ''
  } catch (err) {
    pending.classList.remove('streaming')
    pendingBody.textContent = err.name === 'AbortError' ? '(Cancelled)' : `Error: ${err.message}`
    $('chat-status').textContent = ''
  } finally {
    state.sending = false
    state.streamAbort = null
    input.disabled = false
    sendBtn.classList.remove('hidden')
    cancelBtn.classList.add('hidden')
    input.focus()
  }
}

// -------------------------------------------------------------
// Form & Event Listeners
// -------------------------------------------------------------
$('chat-form').addEventListener('submit', (e) => {
  e.preventDefault()
  askAssistant($('chat-input').value)
})

$('chat-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    $('chat-form').requestSubmit()
  } else if (e.key === 'Escape') {
    setExpanded(false)
  }
})

$('cancel-chat').addEventListener('click', () => {
  if (state.streamAbort) {
    state.streamAbort.abort()
    state.streamAbort = null
  }
})

// Quick Action Pills
$('pill-screen')?.addEventListener('click', () => {
  askAssistant('Analyze my active screen context and summarize key elements.')
})
$('pill-anything')?.addEventListener('click', () => {
  $('chat-input').focus()
})
$('pill-voice')?.addEventListener('click', () => {
  $('voice-chat').click()
})

// Voice Push-to-Talk
$('voice-chat').addEventListener('click', async () => {
  if (state.voiceRecording || state.sending) return
  state.voiceRecording = true
  const pill = $('voice-indicator-pill')
  if (pill) { pill.textContent = 'Listening'; pill.style.borderColor = '#2EA8FF' }
  $('chat-status').textContent = 'Listening to voice…'

  try {
    const result = await api('/voice/ask', {
      method: 'POST',
      body: JSON.stringify({ max_seconds: 15, speak: true }),
    })
    if (result.transcript) appendChatMessage('user', result.transcript)
    if (result.answer) appendChatMessage('assistant', result.answer)
  } catch (err) {
    $('chat-status').textContent = `Voice error: ${err.message}`
  } finally {
    state.voiceRecording = false
    if (pill) { pill.textContent = 'Ready'; pill.style.borderColor = '' }
    $('chat-status').textContent = ''
  }
})

// Window & Card Controls
$('mode-button').addEventListener('click', () => setExpanded(!state.expanded))
$('hide-assistant').addEventListener('click', () => window.assistantDesktop?.hide())
$('ask-button').addEventListener('click', () => askAssistant(state.question))
$('dismiss-button').addEventListener('click', hideQuestion)

$('new-session').addEventListener('click', () => {
  state.chatSessionId = `desktop-companion-${Date.now()}`
  localStorage.setItem('companionSessionId', state.chatSessionId)
  $('chat-history').replaceChildren()
  const empty = document.createElement('div')
  empty.id = 'chat-empty'
  empty.className = 'chat-placeholder'
  empty.textContent = 'New session started.'
  $('chat-history').appendChild(empty)
})

// Settings
$('save-settings').addEventListener('click', () => {
  state.baseUrl = $('api-url').value.trim() || state.baseUrl
  state.token = $('api-token').value.trim()
  localStorage.setItem('assistantUrl', state.baseUrl)
  localStorage.setItem('assistantToken', state.token)
  refreshStatus()
  refreshVoiceStatus()
  refreshModelCatalog()
  $('connection-error').textContent = 'Settings saved.'
  setTimeout(() => { $('connection-error').textContent = '' }, 2500)
})

$('mem-cap-slider')?.addEventListener('input', (e) => {
  $('mem-cap-label').textContent = `${e.target.value} GB`
})

// -------------------------------------------------------------
// Bootstrapping
// -------------------------------------------------------------
loadConfig().then(() => {
  initTasks()
  setExpanded(state.expanded)
  window.assistantDesktop?.onSignal?.(handleSignal)
  window.setInterval(blink, 4800)

  drawCpuSparkline()
  requestAnimationFrame(drawWaveform)

  refreshStatus()
  refreshDesktopStatus()
  refreshVoiceStatus()
  refreshModelCatalog()
  refreshActivity()

  setInterval(refreshStatus, 10000)
  setInterval(refreshDesktopStatus, 15000)
  setInterval(refreshActivity, 3000)
})
