const $ = (id) => document.getElementById(id)
const state = {
  baseUrl: localStorage.getItem('assistantUrl') || 'http://127.0.0.1:8787',
  token: localStorage.getItem('assistantToken') || '',
  activityId: Number(localStorage.getItem('assistantActivityId') || 0),
  question: '',
}

async function loadConfig() {
  if (!window.assistantDesktop?.getConfig) return
  const config = await window.assistantDesktop.getConfig()
  if (!localStorage.getItem('assistantUrl') && config.baseUrl) state.baseUrl = config.baseUrl
  if (!state.token && config.token) state.token = config.token
}

function headers() {
  if (!state.token) return { 'Content-Type': 'application/json' }
  const authorization = /^Bearer\s+/i.test(state.token) ? state.token : `Bearer ${state.token}`
  return { Authorization: authorization, 'Content-Type': 'application/json' }
}

async function api(path, options = {}) {
  const response = await fetch(`${state.baseUrl.replace(/\/$/, '')}${path}`, { ...options, headers: { ...headers(), ...(options.headers || {}) } })
  const payload = await response.json().catch(() => ({}))
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
    $('context').textContent = `Watching assistant activity in ${project}. Screen reading stays user-approved.`
    $('connection-error').textContent = ''
  } catch (error) {
    setConnectionState(false, error.message)
    $('provider-badge').textContent = 'Provider unavailable'
    $('provider-badge').title = error.message
    $('context').textContent = 'Connect me to the local assistant to begin.'
    $('connection-error').textContent = error.message
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
      const description = describeEvent(event)
      if (description) showQuestion(description)
      $('activity').textContent = `${event.type.replaceAll('.', ' ')} · ${new Date(event.created_at).toLocaleTimeString()}`
    }
    localStorage.setItem('assistantActivityId', String(state.activityId))
  } catch (error) {
    setConnectionState(false, error.message)
    $('activity').textContent = `Activity unavailable: ${error.message}`
  }
}

async function askAssistant(message) {
  if (!message?.trim()) return
  $('headline').textContent = 'Thinking about that…'
  $('send-chat').disabled = true
  const answer = await api('/ask', { method: 'POST', body: JSON.stringify({ message, context: 'The user is working with the hovering desktop companion.', session_id: 'desktop-companion' }) })
  $('headline').textContent = answer.answer || 'I am ready when you are.'
  $('chat-input').value = ''
  $('chat-panel').classList.add('hidden')
  $('send-chat').disabled = false
  setConnectionState(true)
  hideQuestion()
}

$('settings-button').addEventListener('click', () => $('settings').classList.toggle('hidden'))
$('close-settings').addEventListener('click', () => $('settings').classList.add('hidden'))
$('connect-button').addEventListener('click', () => {
  $('settings').classList.remove('hidden')
  $('api-token').focus()
})
$('save-settings').addEventListener('click', () => {
  state.baseUrl = $('api-url').value.trim() || state.baseUrl
  state.token = $('api-token').value.trim()
  localStorage.setItem('assistantUrl', state.baseUrl)
  localStorage.setItem('assistantToken', state.token)
  $('settings').classList.add('hidden')
  refreshStatus()
})
$('dismiss-button').addEventListener('click', hideQuestion)
$('ask-button').addEventListener('click', () => askAssistant(state.question).catch((error) => { $('connection-error').textContent = error.message }))
$('chat-button').addEventListener('click', () => {
  $('chat-panel').classList.remove('hidden')
  $('chat-input').focus()
})
$('close-chat').addEventListener('click', () => $('chat-panel').classList.add('hidden'))
$('send-chat').addEventListener('click', () => askAssistant($('chat-input').value).catch((error) => {
  $('send-chat').disabled = false
  setConnectionState(false, error.message)
}))
$('chat-input').addEventListener('keydown', (event) => {
  if (event.key === 'Enter') $('send-chat').click()
})
$('screen-button').addEventListener('click', async () => {
  try {
    $('headline').textContent = 'Taking a careful look…'
    const result = await api('/desktop/analyze-screen', { method: 'POST', body: JSON.stringify({ prompt: 'Summarize what is currently visible and identify anything related to the active project.' }) })
    $('headline').textContent = result.answer || result.error || 'Screen analysis completed.'
    setConnectionState(true)
  } catch (error) {
    $('connection-error').textContent = error.message
    setConnectionState(false, error.message)
  }
})

loadConfig().then(() => {
  $('api-url').value = state.baseUrl
  refreshStatus()
  refreshActivity()
  setInterval(refreshStatus, 15000)
  setInterval(refreshActivity, 3000)
})
