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
  return state.token ? { Authorization: state.token, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' }
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

async function refreshStatus() {
  try {
    const status = await api('/status')
    const project = status.personal?.focus?.label || status.profile || 'your workspace'
    const provider = status.model_provider || status.model_runtime?.model_provider || {}
    const providerName = provider.name || 'Provider unavailable'
    const local = provider.local === true
    $('provider-badge').textContent = local
      ? `Local model · ${providerName}`
      : `External model · ${providerName} · credentials required`
    $('provider-badge').classList.toggle('external', !local)
    $('provider-badge').title = local
      ? `${providerName} runs on this machine. No model API key or token is required.`
      : `${providerName} is an external provider. Credentials are required before use.`
    $('context').textContent = `Watching assistant activity in ${project}. Screen reading stays user-approved.`
    $('connection-error').textContent = ''
  } catch (error) {
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
    for (const event of events) {
      state.activityId = Math.max(state.activityId, Number(event.id))
      const description = describeEvent(event)
      if (description) showQuestion(description)
      $('activity').textContent = `${event.type.replaceAll('.', ' ')} · ${new Date(event.created_at).toLocaleTimeString()}`
    }
    localStorage.setItem('assistantActivityId', String(state.activityId))
  } catch (error) {
    $('activity').textContent = `Activity unavailable: ${error.message}`
  }
}

async function askAssistant(message) {
  const answer = await api('/ask', { method: 'POST', body: JSON.stringify({ message, context: 'The user is working with the hovering desktop companion.', session_id: 'desktop-companion' }) })
  $('headline').textContent = answer.answer || 'I am ready when you are.'
  hideQuestion()
}

$('settings-button').addEventListener('click', () => $('settings').classList.toggle('hidden'))
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
  const message = window.prompt('What would you like help with?')
  if (message?.trim()) askAssistant(message.trim()).catch((error) => { $('connection-error').textContent = error.message })
})
$('screen-button').addEventListener('click', async () => {
  try {
    const result = await api('/desktop/analyze-screen', { method: 'POST', body: JSON.stringify({ prompt: 'Summarize what is currently visible and identify anything related to the active project.' }) })
    $('headline').textContent = result.answer || result.error || 'Screen analysis completed.'
  } catch (error) {
    $('connection-error').textContent = error.message
  }
})

loadConfig().then(() => {
  $('api-url').value = state.baseUrl
  refreshStatus()
  refreshActivity()
  setInterval(refreshStatus, 15000)
  setInterval(refreshActivity, 3000)
})
