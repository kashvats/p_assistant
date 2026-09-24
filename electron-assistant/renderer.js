const $ = (id) => document.getElementById(id)
const state = {
  baseUrl: localStorage.getItem('assistantUrl') || 'http://127.0.0.1:8787',
  token: localStorage.getItem('assistantToken') || '',
  activityId: Number(localStorage.getItem('assistantActivityId') || 0),
  question: '',
  observing: localStorage.getItem('companionObserving') !== 'false',
  learning: localStorage.getItem('companionLearning') !== 'false',
  patterns: JSON.parse(localStorage.getItem('companionPatterns') || '{}'),
  lastIdle: 0,
  lastSignalAt: 0,
  expanded: false,
  chatSessionId: 'desktop-companion',
  sending: false,
  faceDrag: null,
  suppressFaceClick: false,
}

async function loadConfig() {
  if (!window.assistantDesktop?.getConfig) return
  const config = await window.assistantDesktop.getConfig()
  if (!localStorage.getItem('assistantUrl') && config.baseUrl) state.baseUrl = config.baseUrl
  if (config.token) {
    state.token = config.token
    localStorage.setItem('assistantToken', config.token)
  }
  if (state.token) {
    $('api-token').placeholder = 'Automatically supplied by run.bat'
    $('connection-error').textContent = ''
  }
}

function headers() {
  if (!state.token) return { 'Content-Type': 'application/json' }
  const authorization = /^Bearer\s+/i.test(state.token) ? state.token : `Bearer ${state.token}`
  return { Authorization: authorization, 'Content-Type': 'application/json' }
}

async function api(path, options = {}, retried = false) {
  const response = await fetch(`${state.baseUrl.replace(/\/$/, '')}${path}`, { ...options, headers: { ...headers(), ...(options.headers || {}) } })
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

function showQuestion(question) {
  state.question = question
  $('question').textContent = question
  $('question-card').classList.remove('hidden')
}

function hideQuestion() {
  state.question = ''
  $('question-card').classList.add('hidden')
}

function setExpression(expression) {
  const avatar = document.querySelector('.avatar')
  if (!avatar) return
  avatar.dataset.expression = expression
}

function learnPattern(kind) {
  if (!state.learning || !kind || typeof kind !== 'string') return
  const safeKind = kind.replace(/[^a-z0-9_.-]/gi, '').slice(0, 60)
  if (!safeKind) return
  state.patterns[safeKind] = Math.min(1000, Number(state.patterns[safeKind] || 0) + 1)
  localStorage.setItem('companionPatterns', JSON.stringify(state.patterns))
}

function updatePrivacyLabels() {
  $('pause-observation').textContent = state.observing ? 'Pause observing' : 'Resume observing'
  $('toggle-learning').textContent = state.learning ? 'Learning on' : 'Learning off'
  $('observation-toggle').checked = state.observing
  $('learning-toggle').checked = state.learning
}

function setObserving(enabled) {
  state.observing = enabled
  localStorage.setItem('companionObserving', String(enabled))
  updatePrivacyLabels()
  setExpression(enabled ? 'observing' : 'idle')
  $('privacy-status').textContent = enabled
    ? 'Observed: local cursor and idle signals enabled. Content is not captured.'
    : 'Observation paused. No local activity signals are being used.'
}

function setLearning(enabled) {
  state.learning = enabled
  localStorage.setItem('companionLearning', String(enabled))
  updatePrivacyLabels()
  $('privacy-status').textContent = enabled
    ? 'Inferred: repeated activity patterns may be counted locally.'
    : 'Learning disabled. Existing learned behavior is retained until cleared.'
}

function clearLearning() {
  state.patterns = {}
  localStorage.removeItem('companionPatterns')
  $('privacy-status').textContent = 'Confirmed: learned behavior was cleared.'
  setExpression('observing')
}

function setExpanded(expanded) {
  state.expanded = expanded
  localStorage.setItem('companionExpanded', String(expanded))
  $('assistant').classList.toggle('compact-mode', !expanded)
  $('mode-button').textContent = expanded ? '↙' : '↗'
  $('mode-button').title = expanded ? 'Collapse to eyes' : 'Expand assistant'
  window.assistantDesktop?.setExpanded(expanded)
}

function handleSignal(signal) {
  if (!state.observing || !signal?.cursor) return
  const bounds = signal.windowBounds
  const eyes = document.querySelectorAll('.eye')
  if (bounds && eyes.length) {
    const x = Math.max(0, Math.min(1, (signal.cursor.x - bounds.x) / Math.max(1, bounds.width)))
    const y = Math.max(0, Math.min(1, (signal.cursor.y - bounds.y) / Math.max(1, bounds.height)))
    const dx = (x - 0.5) * 7
    const dy = (y - 0.5) * 4
    eyes.forEach((eye) => { eye.style.transform = `translate(${dx}px, ${dy}px)` })
  }
  const idle = Number(signal.idleSeconds || 0)
  const now = Date.now()
  const active = idle < 4
  if (active !== (state.lastIdle < 4)) learnPattern(active ? 'input.active' : 'input.idle')
  state.lastIdle = idle
  state.lastSignalAt = now
  setExpression(active ? 'observing' : 'idle')
  $('privacy-status').textContent = active
    ? 'Observed: recent local activity signal. Content is not captured.'
    : 'Observed: you appear to be idle. No screen content is captured.'
}

function blink() {
  const avatar = document.querySelector('.avatar')
  if (!avatar || !state.observing) return
  avatar.classList.add('blink')
  window.setTimeout(() => avatar.classList.remove('blink'), 160)
}

function setConnectionState(connected, message = '') {
  $('status-dot').classList.toggle('offline', !connected)
  $('activity-dot').style.background = connected ? '#55d68b' : '#f08a8a'
  $('activity-dot').style.boxShadow = connected ? '0 0 8px #55d68b' : '0 0 8px #f08a8a'
  if (connected) {
    $('connection-card').classList.add('hidden')
    return
  }
  $('connection-title').textContent = 'I can’t reach the local assistant yet'
  $('connection-message').textContent = message || 'Check that the assistant is running, then connect again.'
  $('connection-card').classList.remove('hidden')
}

async function refreshStatus() {
  try {
    const status = await api('/status')
    setConnectionState(true)
    const project = status.personal?.focus?.label || status.profile || 'your workspace'
    const provider = status.model_provider || status.model_runtime?.model_provider || {}
    const providerName = provider.name || 'Provider unavailable'
    if (provider.model) $('provider-badge').dataset.model = provider.model
    const local = provider.mode === 'local' || provider.local === true
    const unknown = provider.mode === 'unknown'
    const credentialsMissing = provider.mode === 'online' && provider.credentials_required && !provider.credentials_configured
    $('provider-badge').textContent = local
      ? `Local model · ${providerName}`
      : unknown
        ? 'Model not selected'
        : credentialsMissing
          ? `Online model · ${providerName} · credentials required`
          : `Online model · ${providerName}`
    $('provider-badge').classList.toggle('external', !local && !unknown)
    $('provider-badge').title = local
      ? `${providerName} runs on this machine. No model API key or token is required.`
      : unknown
        ? 'No model is currently selected.'
        : credentialsMissing
          ? `${providerName} is an external provider. ${provider.credential_label} is required before use.`
          : `${providerName} is configured and selected, but this installation does not provide external inference.`
    const credentialPrompt = $('provider-credential-prompt')
    if (provider.mode === 'online' && provider.credentials_required && !provider.credentials_configured) {
      credentialPrompt.textContent = `${providerName} requires ${provider.credential_label}. Configure ${provider.credential_env} before using this online model. Switching to a local model removes this requirement.`
      credentialPrompt.classList.remove('hidden')
    } else {
      credentialPrompt.textContent = ''
      credentialPrompt.classList.add('hidden')
    }
    const providerSettings = $('provider-settings')
    providerSettings.className = `provider-settings ${provider.mode || ''}`
    providerSettings.textContent = provider.mode === 'local'
      ? `${providerName} · Local · no provider key required.`
      : provider.mode === 'online'
        ? `${providerName} · Online · ${provider.credentials_configured ? `configured via ${provider.credential_env}` : `requires ${provider.credential_label} (${provider.credential_env})`}.`
        : 'No model selected.'
    $('context').textContent = `Watching assistant activity in ${project}. Screen reading stays user-approved.`
    $('connection-error').textContent = ''
  } catch (error) {
    setConnectionState(false, error.message)
    $('provider-badge').textContent = 'Provider unavailable'
    $('provider-badge').title = error.message
    $('context').textContent = 'Connect me to the local assistant to begin.'
    $('connection-error').textContent = error.message
    $('provider-settings').textContent = 'Provider settings unavailable until the local assistant connects.'
  }
}

async function refreshVoiceStatus() {
    try {
      const voice = await api('/voice/status')
      const enabled = Boolean(voice.enabled)
      const ready = enabled && voice.hands_free_enabled
      $('voice-enabled-toggle').checked = enabled
      $('hands-free-toggle').checked = Boolean(voice.hands_free_running)
      $('hands-free-toggle').disabled = !enabled
      $('voice-chat').disabled = !enabled
      $('voice-status').textContent = ready
        ? `Ready for “Hey Jarvis” · ${voice.dependencies?.openwakeword ? 'wake model available' : 'install voice/wakeword extras'}`
        : 'Hands-free voice is disabled in the assistant configuration.'
    } catch (error) {
      $('voice-status').textContent = `Voice unavailable: ${error.message}`
    }
  }

  async function refreshDesktopStatus() {
    try {
      const desktop = await api('/desktop/status')
      $('screen-access-toggle').checked = Boolean(desktop.vision_enabled)
    } catch (error) {
      $('screen-access-toggle').checked = false
    }
  }

async function refreshModelCatalog() {
    try {
      const catalog = await api('/models/local')
      const select = $('model-name')
      const current = select.value
      select.replaceChildren()
      for (const model of catalog.models || []) {
        const option = document.createElement('option')
        option.value = model.name
        option.textContent = `${model.name}${model.loaded ? ' · loaded' : ''}`
        select.appendChild(option)
      }
      const active = current || document.querySelector('#provider-badge')?.dataset?.model
      if (active && [...select.options].some((option) => option.value === active)) select.value = active
      $('model-catalog-status').textContent = catalog.models?.length
        ? `${catalog.models.length} local Ollama model${catalog.models.length === 1 ? '' : 's'} available.`
        : 'No local Ollama models are installed. Pull one with Ollama first.'
    } catch (error) {
      $('model-catalog-status').textContent = `Local model catalog unavailable: ${error.message}`
      $('model-name').replaceChildren(new Option('Ollama unavailable', ''))
  }
}

function describeEvent(event) {
  const data = event.data || {}
  if (event.type.includes('failed') || event.type.includes('error')) {
    return `I noticed a failure${data.tool ? ` in ${data.tool}` : ''}. Do you want me to investigate it?`
  }
  if (event.type === 'evaluation.completed' && data.ok === false) {
    return 'An evaluation did not pass. Should I help inspect the failing checks?'
  }
  return ''
}

async function refreshActivity() {
  try {
    const events = await api(`/activity?after_id=${state.activityId}&limit=20`)
    $('activity-dot').style.background = '#55d68b'
    for (const event of events) {
      state.activityId = Math.max(state.activityId, Number(event.id))
      learnPattern(`assistant.${event.type}`)
      const description = describeEvent(event)
      if (description) showQuestion(description)
      $('activity').textContent = `${event.type.replaceAll('.', ' ')} · ${new Date(event.created_at).toLocaleTimeString()}`
      setExpression(event.type.includes('failed') || event.type.includes('error') ? 'confused' : 'learning')
    }
    localStorage.setItem('assistantActivityId', String(state.activityId))
  } catch (error) {
    setConnectionState(false, error.message)
    $('activity').textContent = `Activity unavailable: ${error.message}`
  }
}

async function askAssistant(message) {
  const text = message?.trim()
  if (!text || state.sending) return
  state.sending = true
  $('chat-panel').classList.remove('hidden')
  $('chat-panel').setAttribute('aria-busy', 'true')
  const input = $('chat-input')
  const button = $('send-chat')
  input.value = ''
  input.style.height = ''
  button.disabled = true
  button.textContent = '…'
  $('chat-status').textContent = 'Sending…'
  appendChatMessage('user', text)
  const pending = appendChatMessage('assistant', '', { pending: true, streaming: true })
  const pendingBody = pending.querySelector('.chat-body')
  let accumulated = ''
  try {
    const response = await fetch(`${state.baseUrl.replace(/\/$/, '')}/chat/stream`, {
      method: 'POST',
      headers: { ...headers() },
      body: JSON.stringify({
        message: text,
        context: 'The user is working with the hovering desktop companion.',
        session_id: state.chatSessionId,
      }),
    })
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}))
      throw new Error(payload.detail || `Assistant API returned ${response.status}`)
    }
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
        const eventLine = block.split('\n').find((l) => l.startsWith('event:'))
        const dataLine = block.split('\n').find((l) => l.startsWith('data:'))
        if (!dataLine) continue
        let event
        try { event = JSON.parse(dataLine.slice(5).trim()) } catch (_) { continue }
        const eventType = eventLine ? eventLine.slice(6).trim() : ''
        if (eventType === 'error' || event.type === 'error') {
          throw new Error(event.error || 'Stream error')
        }
                if (event.type === 'token') {
          const token =
            typeof event.text === 'string'
              ? event.text
              : typeof event.token === 'string'
                ? event.token
                : ''

          if (token) {
            accumulated += token
            pendingBody.textContent = accumulated
            $('chat-history').scrollTop = $('chat-history').scrollHeight
          }
        } else if (
          event.type === 'final' ||
          event.type === 'done' ||
          event.type === 'finish'
        ) {
          const finalText =
            typeof event.text === 'string'
              ? event.text
              : typeof event.answer === 'string'
                ? event.answer
                : ''

          if (finalText) {
            accumulated = finalText
            pendingBody.textContent = accumulated
          }
        }
      }
    }

    pending.classList.remove('pending', 'streaming')

    if (!accumulated.trim()) {
      throw new Error(
        'Assistant completed the request but returned no readable response.'
      )
    }
    setConnectionState(false, error.message)
  } finally {
    state.sending = false
    $('chat-panel').setAttribute('aria-busy', 'false')
    button.disabled = false
    button.textContent = '\u2191'
    input.focus()
  }
}

function appendChatMessage(role, content, options = {}) {
  const empty = $('chat-empty')
  if (empty) empty.remove()
  const message = document.createElement('article')
  const classes = ['chat-message', role]
  if (options.pending) classes.push('pending')
  if (options.streaming) classes.push('streaming')
  message.className = classes.join(' ')
  const meta = document.createElement('div')
  meta.className = 'chat-meta'
  meta.textContent = role === 'user' ? 'You' : 'Assistant'
  const body = document.createElement('div')
  body.className = 'chat-body'
  body.textContent = content
  message.append(meta, body)
  $('chat-history').appendChild(message)
  $('chat-history').scrollTop = $('chat-history').scrollHeight
  return message
}

async function loadChatHistory() {
  try {
    const result = await api(`/sessions/${encodeURIComponent(state.chatSessionId)}`)
    $('chat-history').replaceChildren()
    const messages = (result.messages || []).filter((item) => item.role === 'user' || item.role === 'assistant')
    if (!messages.length) {
      const empty = document.createElement('div')
      empty.id = 'chat-empty'
      empty.className = 'chat-empty'
      empty.textContent = 'Your conversation history will appear here.'
      $('chat-history').appendChild(empty)
      return
    }
    messages.forEach((item) => appendChatMessage(item.role, item.content))
  } catch (error) {
    $('chat-status').textContent = `History unavailable: ${error.message}`
  }
}

$('open-chat-quick').addEventListener('click', () => {
  $('chat-panel').classList.remove('hidden')
  $('chat-input').focus()
})
$('settings-button').addEventListener('click', () => $('settings').classList.toggle('hidden'))
$('mode-button').addEventListener('click', () => setExpanded(!state.expanded))
$('face-toggle').addEventListener('click', () => {
  if (state.suppressFaceClick) {
    state.suppressFaceClick = false
    return
  }
  if (!state.expanded && !state.faceDrag?.moved) setExpanded(true)
})
$('avatar').addEventListener('click', () => {
  if (!state.expanded && !state.suppressFaceClick && !state.faceDrag?.moved) setExpanded(true)
})
$('face-toggle').addEventListener('pointerdown', (event) => {
  if (state.expanded || event.button !== 0) return
  state.faceDrag = {
    pointerId: event.pointerId,
    lastX: event.screenX,
    lastY: event.screenY,
    moved: false,
  }
  $('face-toggle').setPointerCapture(event.pointerId)
})
$('face-toggle').addEventListener('pointermove', (event) => {
  const drag = state.faceDrag
  if (state.expanded || !drag || drag.pointerId !== event.pointerId) return
  const deltaX = event.screenX - drag.lastX
  const deltaY = event.screenY - drag.lastY
  if (!drag.moved && Math.hypot(event.screenX - drag.lastX, event.screenY - drag.lastY) >= 4) {
    drag.moved = true
    $('face-toggle').classList.add('dragging')
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
  if ($('face-toggle').hasPointerCapture(event.pointerId)) $('face-toggle').releasePointerCapture(event.pointerId)
  $('face-toggle').classList.remove('dragging')
  window.setTimeout(() => { state.faceDrag = null }, 0)
}
$('face-toggle').addEventListener('pointerup', finishFaceDrag)
$('face-toggle').addEventListener('pointercancel', finishFaceDrag)
$('close-settings').addEventListener('click', () => $('settings').classList.add('hidden'))
$('connect-button').addEventListener('click', () => {
  $('settings').classList.remove('hidden')
  $('api-token').focus()
})
$('observation-toggle').addEventListener('change', (event) => {
  setObserving(event.target.checked)
})
$('learning-toggle').addEventListener('change', (event) => {
  setLearning(event.target.checked)
})
$('clear-learning').addEventListener('click', () => {
  clearLearning()
})
$('hide-assistant').addEventListener('click', () => window.assistantDesktop?.hide())
$('hands-free-toggle').addEventListener('change', async (event) => {
  try {
    const result = await api('/voice/hands-free', {
      method: 'POST',
      body: JSON.stringify({ enabled: event.target.checked }),
    })
    if (!result.ok) throw new Error(result.error || 'Hands-free voice could not start.')
    $('voice-status').textContent = event.target.checked
      ? 'Listening locally for “Hey Jarvis”…'
      : 'Wake-word listening stopped.'
  } catch (error) {
    event.target.checked = false
    $('voice-status').textContent = error.message
    setExpression('confused')
  }
})
$('voice-enabled-toggle').addEventListener('change', async (event) => {
  try {
    const result = await api('/voice/enabled', {
      method: 'POST',
      body: JSON.stringify({ enabled: event.target.checked }),
    })
    $('hands-free-toggle').disabled = !event.target.checked
    if (!event.target.checked) $('hands-free-toggle').checked = false
    $('voice-status').textContent = result.enabled
      ? 'Voice features enabled. You can start “Hey Jarvis” listening.'
      : 'Voice features disabled.'
  } catch (error) {
    event.target.checked = !event.target.checked
    $('connection-error').textContent = error.message
  }
})
$('select-model').addEventListener('click', async () => {
  const model = $('model-name').value
  if (!model) return
  try {
    const result = await api('/models/select', {
      method: 'POST',
      body: JSON.stringify({ model }),
    })
    $('headline').textContent = `Using ${result.model}.`
    await refreshStatus()
    await refreshVoiceStatus()
    await refreshModelCatalog()
  } catch (error) {
    $('connection-error').textContent = error.message
    setExpression('confused')
  }
})
$('pause-observation').addEventListener('click', () => setObserving(!state.observing))
$('toggle-learning').addEventListener('click', () => setLearning(!state.learning))
$('clear-learning-quick').addEventListener('click', clearLearning)
$('hide-assistant-quick').addEventListener('click', () => window.assistantDesktop?.hide())
$('save-settings').addEventListener('click', () => {
  state.baseUrl = $('api-url').value.trim() || state.baseUrl
  state.token = $('api-token').value.trim()
  localStorage.setItem('assistantUrl', state.baseUrl)
  localStorage.setItem('assistantToken', state.token)
  $('settings').classList.add('hidden')
  refreshStatus()
  refreshVoiceStatus()
  refreshDesktopStatus()
  refreshModelCatalog()
})
$('dismiss-button').addEventListener('click', hideQuestion)
$('ask-button').addEventListener('click', () => askAssistant(state.question).catch((error) => { $('connection-error').textContent = error.message }))
$('close-chat').addEventListener('click', () => $('chat-panel').classList.add('hidden'))
$('chat-form').addEventListener('submit', (event) => {
  event.preventDefault()
  askAssistant($('chat-input').value)
})
$('chat-input').addEventListener('input', (event) => {
  event.target.style.height = 'auto'
  event.target.style.height = `${Math.min(event.target.scrollHeight, 110)}px`
})
$('chat-input').addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    $('chat-form').requestSubmit()
  }
})
$('voice-chat').addEventListener('click', async () => {
  const button = $('voice-chat')
  const original = button.innerHTML
  button.disabled = true
  $('voice-status').textContent = 'Listening…'
  setExpression('observing')
  try {
    const result = await api('/voice/ask', {
      method: 'POST',
      body: JSON.stringify({ max_seconds: 15, speak: true }),
    })
    if (!result.ok) throw new Error(result.error || 'Voice command did not complete.')
    $('voice-status').textContent = 'Speaking…'
    $('headline').textContent = result.answer || 'I heard you.'
    $('context').textContent = `Heard: “${result.transcript}”`
    setExpression('learning')
    await loadChatHistory()
    $('voice-status').textContent = 'Idle'
  } catch (error) {
    $('connection-error').textContent = error.message
    $('headline').textContent = 'I could not complete that voice request.'
    setExpression('confused')
  } finally {
    button.innerHTML = original
    button.disabled = false
    if ($('voice-status').textContent !== 'Speaking…') $('voice-status').textContent = 'Idle'
  }
})

$('screen-access-toggle').addEventListener('change', async (event) => {
  try {
    const result = await api('/desktop/screen-access', {
      method: 'POST',
      body: JSON.stringify({ enabled: event.target.checked }),
    })
    event.target.checked = Boolean(result.vision_enabled)
  } catch (error) {
    event.target.checked = !event.target.checked
    $('connection-error').textContent = error.message
  }
})

loadConfig().then(() => {
  $('api-url').value = state.baseUrl
  $('observation-toggle').checked = state.observing
  $('learning-toggle').checked = state.learning
  updatePrivacyLabels()
  setExpanded(state.expanded)
  window.assistantDesktop?.onSignal(handleSignal)
  window.setInterval(blink, 5200)
  refreshStatus()
  refreshVoiceStatus()
  refreshModelCatalog()
  refreshActivity()
  loadChatHistory()
  setInterval(refreshStatus, 15000)
  setInterval(refreshVoiceStatus, 5000)
  setInterval(refreshDesktopStatus, 15000)
  setInterval(refreshModelCatalog, 30000)
  setInterval(refreshActivity, 3000)
})

window.assistantDesktop?.onOpenSettings?.(() => $('settings').classList.remove('hidden'))
