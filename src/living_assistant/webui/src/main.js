/* Living Assistant dashboard — React SPA. No model-controlled HTML is injected. */
import { loadPlotly } from './chart_loader.js';
import { ACCEPT, extractFiles, fileChip, kindOf, mediaList, uploadFile } from './chatmedia.js';
import { Markdown } from './markdown.js';
import { SkillLibraryPanel } from './skill_library.js';
import { makeResourceSample, resourceSampleLabel, resourceSeries } from './resource_chart_data.js';
const React = globalThis.React;
const ReactDOM = globalThis.ReactDOM;
const Prism = globalThis.Prism;
const h = React.createElement;

const NAV = [
  ['overview', '🏠 Overview'], ['models', 'Models'], ['chat', '💬 Chat'], ['career', '💼 Career & Jobs'], ['skills', '⚡ Skills'], ['agents', '🧠 Agents'], ['approvals', '✅ Approvals'], ['organize', '📅 Calendar & Todos'], ['security', '🔒 Security'], ['activity', '📊 Activity'], ['tools', '🔧 Tools'],
];

function cx(...parts) { return parts.filter(Boolean).join(' '); }
// Hosts DOM built by chatmedia.js (file chips, media cards) inside the React tree; rebuilt when `depKey` changes.
function DomNode({make, depKey, className}) {
  const ref = React.useRef(null);
  React.useEffect(() => { if (ref.current) ref.current.replaceChildren(make()); }, [depKey]);
  return h('div', {ref, className});
}
function safeText(value) { return value == null ? '' : String(value); }
function fmtBytes(bytes) {
  const n = Number(bytes || 0);
  if (!Number.isFinite(n) || n <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let v = n, i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i += 1; }
  return `${v >= 10 || i === 0 ? v.toFixed(0) : v.toFixed(1)} ${units[i]}`;
}
function hashPage() {
  const raw = location.hash.replace(/^#\/?/, '').split('/')[0].trim().toLowerCase();
  return NAV.some(([id]) => id === raw) ? raw : 'overview';
}
function initialToken() {
  const stored = sessionStorage.getItem('assistant_token');
  if (stored) return stored;
  const meta = document.querySelector('meta[name="assistant-token"]');
  return meta ? meta.getAttribute('content') || '' : '';
}
function readFlag(key) {
  try { return localStorage.getItem(key) === '1'; } catch (_) { return false; }
}
function makeSessionId() {
  if (globalThis.crypto && typeof globalThis.crypto.randomUUID === 'function') {
    return globalThis.crypto.randomUUID().replaceAll('-', '').slice(0, 12);
  }
  return `session${Date.now().toString(36)}`.slice(0, 12);
}

class AgentFace extends React.Component {
  constructor(props) {
    super(props);
    this.root = null;
    this.pupils = [];
    this.onMove = (e) => this.look(e.clientX, e.clientY);
  }
  componentDidMount() { if (this.props.track) document.addEventListener('pointermove', this.onMove, {passive: true}); }
  componentWillUnmount() { document.removeEventListener('pointermove', this.onMove); }
  look(x, y) {
    if (!this.root) return;
    const r = this.root.getBoundingClientRect();
    const dx = x - (r.left + r.width / 2);
    const dy = y - (r.top + r.height / 2);
    const dist = Math.hypot(dx, dy) || 1;
    const reach = Math.min(1, dist / 240);
    const tx = (dx / dist) * 38 * reach;
    const ty = (dy / dist) * 30 * reach;
    this.pupils.forEach((p) => { if (p) p.style.transform = `translate(${tx}%, ${ty}%)`; });
  }
  render() {
    const {size = 'md', mood = 'idle', title} = this.props;
    const eye = (k) => h('span', {key: k, className: 'eye'}, h('span', {className: 'pupil', ref: (el) => { this.pupils[k] = el; }}));
    return h('div', {
      ref: (el) => { this.root = el; },
      className: cx('agent-face', size, `mood-${mood}`),
      role: 'img',
      'aria-label': title || `Assistant is ${mood}`,
      title,
    }, h('span', {className: 'agent-ring'}), eye(0), eye(1));
  }
}

// Live microphone spectrum shown while the assistant is listening (polls /voice/meter).
class MicSpectrum extends React.Component {
  constructor(props) {
    super(props);
    this.bars = [];
    this.alive = false;
  }
  componentDidMount() { this.alive = true; this.poll(); }
  componentWillUnmount() { this.alive = false; }
  async poll() {
    while (this.alive) {
      try {
        const m = await this.props.api('/voice/meter');
        const bands = m && m.active && Array.isArray(m.bands) ? m.bands : [];
        this.bars.forEach((el, i) => { if (el) el.style.height = `${Math.round(12 + (bands[i] || 0) * 88)}%`; });
      } catch (_) {}
      await new Promise((r) => setTimeout(r, 70));
    }
  }
  render() {
    return h('div', {className: 'mic-spectrum', 'aria-hidden': 'true'},
      Array.from({length: 16}, (_, i) => h('i', {key: i, ref: (el) => { this.bars[i] = el; }})));
  }
}

class App extends React.Component {
  constructor(props) {
    super(props);
    // The conversation is the server's shared active one (also used by the floating agent and voice).
    const sessionId = null;
    this.state = {
      page: hashPage(), token: initialToken(), tokenInput: '',
      sessionId, status: null, desktop: null, usage: null, models: null, approvals: [], todos: [], calendar: [],
      security: {summary: null, findings: [], sensors: null}, activity: [], lastEvent: 0,
      messages: [], chatInput: '', streaming: false, chatTools: [], resourceHistory: [],
      todoTitle: '', todoDue: '', calTitle: '', calStart: '', modelPullName: '', modelBusy: false,
      skills: [], selectedSkill: null, skillDraftPrompt: '', skillSearch: '', skillBusy: false, skillTrace: null, skillDryRun: true, skillCollections: null,
      agents: [], selectedAgent: null, agentDraftPrompt: '', agentSearch: '', agentBusy: false, agentTrace: null, agentDryRun: true,
      toast: '', error: '',
      voiceRecording: false, attachedFile: null, pendingFiles: [], uploading: 0, killOpen: false, killBusy: false, killed: null, speakReplies: readFlag('assistant_speak_replies'),
      toolsStatus: null, browserSessions: [],
      expandedTools: {},
      goals: [], goalText: '', goalCheck: '', goalCwd: '.', goalBusy: false,
      conversations: [], vision: null, careerProfile: null, careerApplications: [], careerJobUrl: '', careerBusy: false, careerOutreachDraft: null,
    };
    this.pollers = []; this.activityController = null; this.approvalSeen = new Set(); this.chatController = null;
  }
  componentDidMount() {
    // Embedded in the new shell (shell.js): the shell picks the page and runs the live streams.
    if (!this.props.embedded) { this.onHash = () => this.setState({page: hashPage()}); window.addEventListener('hashchange', this.onHash); }
    this.refreshAll(); if (!this.props.embedded) { this.startActivityStream(); this.loadActiveConversation(); }
    this.pollers.push(setInterval(() => this.loadStatus(), 2500));
    this.pollers.push(setInterval(() => this.loadApprovals(), 5000));
    this.pollers.push(setInterval(() => this.loadUsage(), 10000));
    this.pollers.push(setInterval(() => { if (this.state.page === 'chat') this.loadGoals(); }, 5000));
    this.loadGoals();
  }
  componentWillUnmount() { window.removeEventListener('hashchange', this.onHash); this.pollers.forEach(clearInterval); if (this.activityController) this.activityController.abort(); this.cancelChat(); }
  componentWillUpdate() {
    const el = this.chatScroll;
    this.stickToBottom = !!el && el.scrollHeight - el.scrollTop - el.clientHeight < 120;
  }
  componentDidUpdate(prevProps, prevState) {
    const el = this.chatScroll;
    if (el && prevState.messages !== this.state.messages && (this.stickToBottom || prevState.messages.length !== this.state.messages.length)) {
      el.scrollTop = el.scrollHeight;
    }
  }
  get apiFn() { return this._apiFn || (this._apiFn = (u, o) => this.api(u, o)); }
  get notifyFn() { return this._notifyFn || (this._notifyFn = (t, e) => this.notify(t, e)); }
  authHeaders(extra = {}) { return Object.assign({}, extra, this.state.token ? {Authorization: `Bearer ${this.state.token}`} : {}); }
  async api(url, opt = {}) {
    let response;
    try { response = await fetch(url, {...opt, headers: this.authHeaders(opt.headers || {})}); }
    catch (error) { throw new Error(`Network request failed: ${error instanceof Error ? error.message : String(error)}`); }
    if (!response.ok) { const body = (await response.text()).slice(0, 2000); throw new Error(body || `HTTP ${response.status}`); }
    const type = response.headers.get('content-type') || '';
    return type.includes('json') ? response.json() : response.text();
  }
  notify(message, error = false) {
    this.setState({toast: safeText(message), error: error ? safeText(message) : ''});
    clearTimeout(this.toastTimer); this.toastTimer = setTimeout(() => this.setState({toast: ''}), 3500);
  }
  async loadStatus() {
    try {
      const [status, desktop] = await Promise.all([this.api('/status'), this.api('/desktop/status').catch(() => null)]);
      const sample = makeResourceSample(status?.resources, status?.hardware);
      this.setState(prev => ({status, desktop, resourceHistory: [...prev.resourceHistory, sample].slice(-60)}));
    } catch (error) { this.setState({status: null}); }
  }
  async loadUsage() { try { this.setState({usage: await this.api('/models/usage?days=30')}); } catch (_) {} }
  async loadModels() {
    try { this.setState({models: await this.api('/models/local')}); } catch (e) { this.notify(`Unable to load models: ${e.message}`, true); }
    this.loadVision();
  }
  async loadVision() {
    // Vision is optional (vision.enabled=false answers 503): the page then shows no vision section.
    const [models, status, bench] = await Promise.allSettled([this.api('/vision/models'), this.api('/vision/status'), this.api('/vision/benchmark')]);
    this.setState({vision: models.status === 'fulfilled' ? {models: models.value.models || [], status: status.status === 'fulfilled' ? status.value : null,
      bench: bench.status === 'fulfilled' ? bench.value.results || [] : []} : null});
  }
  async setVisionDefault(model) {
    try { await this.api('/vision/default', {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({model})}); this.notify(`Vision model: ${model}`); }
    catch (e) { this.notify(e.message, true); }
    this.loadVision();
  }
  async downloadVision(model) {
    try { await this.api(`/vision/models/${encodeURIComponent(model)}/download`, {method: 'POST'}); this.notify(`Downloading ${model}…`); }
    catch (e) { this.notify(e.message, true); }
    setTimeout(() => this.loadVision(), 1500);
  }
  async loadApprovals() {
    try {
      const approvals = await this.api('/approvals');
      const fresh = approvals.filter(a => !this.approvalSeen.has(String(a.id)));
      approvals.forEach(a => this.approvalSeen.add(String(a.id)));
      this.setState({approvals});
      if (fresh.length && this.approvalSeen.size > fresh.length) this.notify(`${fresh.length} new approval${fresh.length === 1 ? '' : 's'} waiting`);
    } catch (_) {}
  }
  async loadTodos() { try { this.setState({todos: await this.api('/todos')}); } catch (_) {} }
  async loadCalendar() { try { this.setState({calendar: await this.api('/calendar')}); } catch (_) {} }
  async loadSecurity() {
    try {
      const [summary, findings, sensors] = await Promise.all([this.api('/security/summary'), this.api('/security/findings'), this.api('/security/sensors/status').catch(() => null)]);
      this.setState({security: {summary, findings, sensors}});
    } catch (_) {}
  }
  async loadActivity() {
    try {
      const activity = await this.api('/activity?limit=100');
      const lastEvent = activity.reduce((m, x) => Math.max(m, Number(x.id || 0)), this.state.lastEvent);
      this.setState({activity, lastEvent});
    } catch (_) {}
  }
  async loadSkills() {
    try {
      const res = await this.api('/skills');
      this.setState({skills: res.skills || []});
    } catch (_) {}
  }
  async createSkillDraft() {
    if (!this.state.skillDraftPrompt.trim()) return;
    this.setState({skillBusy: true});
    try {
      const res = await this.api('/skills/draft', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({description: this.state.skillDraftPrompt})});
      this.notify(`Draft skill '${res.manifest.name}' created!`);
      this.setState({skillDraftPrompt: '', selectedSkill: res});
      await this.loadSkills();
    } catch (e) { this.notify(`Draft failed: ${e.message}`, true); }
    finally { this.setState({skillBusy: false}); }
  }
  async activateSkill(id) {
    try {
      await this.api(`/skills/${id}/activate`, {method: 'POST'});
      this.notify(`Skill '${id}' activated!`);
      await this.loadSkills();
      if (this.state.selectedSkill?.lifecycle?.skill_id === id) {
        this.selectSkill(id);
      }
    } catch (e) { this.notify(`Activation failed: ${e.message}`, true); }
  }
  async disableSkill(id) {
    try {
      await this.api(`/skills/${id}/disable`, {method: 'POST'});
      this.notify(`Skill '${id}' disabled.`);
      await this.loadSkills();
    } catch (e) { this.notify(`Disable failed: ${e.message}`, true); }
  }
  async testSkill(id) {
    this.setState({skillBusy: true, skillTrace: null});
    try {
      const res = await this.api(`/skills/${id}/execute`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({inputs: {}, dry_run: this.state.skillDryRun}),
      });
      this.setState({skillTrace: res});
      this.notify(`Test finished (${res.status})`);
    } catch (e) { this.notify(`Test failed: ${e.message}`, true); }
    finally { this.setState({skillBusy: false}); }
  }
  async rollbackSkill(id, version) {
    try {
      await this.api(`/skills/${id}/rollback`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({version}),
      });
      this.notify(`Skill rolled back to ${version}!`);
      await this.loadSkills();
      await this.selectSkill(id);
    } catch (e) { this.notify(`Rollback failed: ${e.message}`, true); }
  }
  async selectSkill(id) {
    try {
      const res = await this.api(`/skills/${id}`);
      this.setState({selectedSkill: res, skillTrace: null});
    } catch (e) { this.notify(`Failed to load skill: ${e.message}`, true); }
  }
  async loadSkillCollections() {
    try {
      const res = await this.api('/skills/collections/browse');
      this.setState({skillCollections: res});
    } catch (e) { this.notify(`Collections browse failed: ${e.message}`, true); }
  }
  async importCollectionSkill(col, folder) {
    try {
      const res = await this.api('/skills/collections/import', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({collection: col, folder}),
      });
      this.notify(`Imported '${folder}' as draft!`);
      await this.loadSkills();
    } catch (e) { this.notify(`Import failed: ${e.message}`, true); }
  }
  async loadAgents() {
    try {
      const res = await this.api('/agents');
      this.setState({agents: res.agents || []});
    } catch (_) {}
  }
  async selectAgent(id) {
    try {
      const res = await this.api(`/agents/${id}`);
      this.setState({selectedAgent: res, agentTrace: null});
    } catch (e) { this.notify(`Failed to load agent: ${e.message}`, true); }
  }
  async createAgentDraft() {
    if (!this.state.agentDraftPrompt.trim()) return;
    this.setState({agentBusy: true});
    try {
      const res = await this.api('/agents/draft', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({description: this.state.agentDraftPrompt}),
      });
      this.notify(`Draft agent '${res.manifest.name}' created!`);
      this.setState({agentDraftPrompt: '', selectedAgent: res});
      await this.loadAgents();
    } catch (e) { this.notify(`Agent draft failed: ${e.message}`, true); }
    finally { this.setState({agentBusy: false}); }
  }
  async activateAgent(id) {
    try {
      const res = await this.api(`/agents/${id}/activate`, {method: 'POST'});
      if (res.ok) {
        this.notify(`Agent '${id}' activated!`);
        await this.loadAgents();
        this.selectAgent(id);
      }
    } catch (e) { this.notify(`Activation failed: ${e.message}`, true); }
  }
  async disableAgent(id) {
    try {
      await this.api(`/agents/${id}/disable`, {method: 'POST'});
      this.notify(`Agent '${id}' disabled.`);
      await this.loadAgents();
    } catch (e) { this.notify(`Disable failed: ${e.message}`, true); }
  }
  async testAgent(id) {
    this.setState({agentBusy: true, agentTrace: null});
    try {
      const res = await this.api(`/agents/${id}/execute`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({task: `Execute verification run for ${id}`, dry_run: this.state.agentDryRun}),
      });
      this.setState({agentTrace: res});
      this.notify(`Test finished (${res.status})`);
    } catch (e) { this.notify(`Test failed: ${e.message}`, true); }
    finally { this.setState({agentBusy: false}); }
  }
  async voiceAsk() {
    if (this.state.voiceRecording || this.state.streaming) return;
    this.setState({voiceRecording: true});
    try {
      const transcribe = () => this.api('/voice/transcribe', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({max_seconds: 15})});
      let res = await transcribe();
      if (res.approval_required && res.approval_id) {
        // Microphone use needs the user's consent for each listen.
        const approved = window.confirm('Allow the assistant to listen to your microphone for this request?');
        await this.api(`/approvals/${encodeURIComponent(res.approval_id)}`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({approved})});
        if (!approved) return;
        res = await transcribe();
      }
      if (!res.ok) throw new Error(res.error || res.message || `Voice ${res.stage || 'capture'} failed`);
      this.setState({voiceRecording: false});
      await this.sendChat(res.transcript, {viaVoice: true});
    } catch (e) {
      this.notify(`Voice: ${e.message}`, true);
    } finally {
      if (this.state.voiceRecording) this.setState({voiceRecording: false});
    }
  }
  async speakReply(text) {
    const plain = safeText(text).replace(/```[\s\S]*?```/g, ' code block omitted. ').replace(/[*_`#>]/g, '').trim();
    if (!plain) return;
    try { await this.api('/voice/speak', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text: plain.slice(0, 4000)})}); }
    catch (e) { this.notify(`Speech failed: ${e.message}`, true); }
  }
  toggleSpeakReplies() {
    const speakReplies = !this.state.speakReplies;
    try { localStorage.setItem('assistant_speak_replies', speakReplies ? '1' : '0'); } catch (_) {}
    this.setState({speakReplies});
  }
  async loadActiveConversation() {
    try {
      const active = await this.api('/conversations/active');
      if (active?.id) this.setState({sessionId: active.id}, () => this.loadChatHistory());
    } catch (_) {}
    this.loadConversations();
  }
  async loadConversations() {
    try {
      const res = await this.api('/conversations?limit=30');
      this.setState({conversations: Array.isArray(res?.conversations) ? res.conversations : []});
    } catch (_) {}
  }
  async loadChatHistory() {
    const sid = this.state.sessionId;
    if (!sid) return;
    try {
      const res = await this.api(`/conversations/${encodeURIComponent(sid)}/messages`);
      if (sid !== this.state.sessionId || this.state.streaming) return;
      const rows = Array.isArray(res?.messages) ? res.messages : [];
      this.setState({messages: rows.filter(r => r.role === 'user' || r.role === 'assistant').map(r => ({
        role: r.role, text: safeText(r.content), steps: [], viaVoice: r.source === 'voice', media: (r.meta && r.meta.media) || []}))});
      // A turn keeps running on the server when the page is refreshed; show that it is still coming.
      const busy = await this.api(`/chat/running/${encodeURIComponent(sid)}`).catch(() => null);
      if (busy?.running && sid === this.state.sessionId && !this.state.streaming) {
        this.setState(prev => ({messages: [...prev.messages, {role: 'assistant', text: '', steps: [],
          phase: 'Still working on your last request - it continues after a refresh'}]}));
      }
    } catch (_) {}
  }
  async switchConversation(sessionId) {
    if (!sessionId || sessionId === this.state.sessionId) return;
    if (this.state.streaming) this.cancelChat();
    try { await this.api('/conversations/active', {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({session_id: sessionId})}); } catch (e) { this.notify(e.message, true); return; }
    this.setState({sessionId, messages: [], chatTools: []}, () => this.loadChatHistory());
  }
  async newChat() {
    if (this.state.streaming) this.cancelChat();
    try {
      const created = await this.api('/conversations', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({})});
      this.setState({sessionId: created.id, messages: [], chatTools: [], chatInput: ''});
      this.loadConversations();
    } catch (e) { this.notify(`New chat failed: ${e.message}`, true); }
  }
  // Another interface (floating agent, voice) changed the conversation: follow it.
  onConversationEvent(event) {
    const data = event?.data || {};
    if (event.type === 'conversation.active' && data.session_id && data.session_id !== this.state.sessionId && !this.state.streaming) {
      this.setState({sessionId: data.session_id, messages: []}, () => this.loadChatHistory());
      this.loadConversations();
    } else if ((event.type === 'chat.completed' || event.type === 'chat.updated') && data.session_id) {
      if (data.session_id === this.state.sessionId && !this.state.streaming) this.loadChatHistory();
      this.loadConversations();
    }
  }
  async decideInline(approvalId, approved, retryText) {
    try {
      await this.api(`/approvals/${encodeURIComponent(approvalId)}`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({approved})});
      this.setState(prev => ({messages: prev.messages.map(m => ({...m, steps: (m.steps || []).map(s => s.approval_id === approvalId ? {...s, decided: approved ? 'approved' : 'denied'} : s)}))}));
      this.loadApprovals();
      if (approved && retryText) await this.sendChat(retryText);
    } catch (e) { this.notify(`Approval failed: ${e.message}`, true); }
  }
  async loadGoals() {
    try { this.setState({goals: await this.api('/goals?limit=10')}); } catch (_) {}
  }
  async startGoal() {
    const goal = this.state.goalText.trim();
    if (goal.length < 3 || this.state.goalBusy) return;
    this.setState({goalBusy: true});
    try {
      await this.api('/goals', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({goal, check_command: this.state.goalCheck.trim(), cwd: this.state.goalCwd.trim() || '.'})});
      this.setState({goalText: '', goalCheck: ''});
      this.notify('Goal started — it keeps working in the background');
      await this.loadGoals();
    } catch (e) { this.notify(`Goal failed to start: ${e.message}`, true); }
    finally { this.setState({goalBusy: false}); }
  }
  async goalAction(id, action) {
    try {
      if (action === 'delete') {
        try {
          await this.api(`/goals/${encodeURIComponent(id)}`, {method: 'DELETE'});
        } catch (_) {
          await this.api(`/goals/${encodeURIComponent(id)}/delete`, {method: 'POST'});
        }
      } else {
        await this.api(`/goals/${encodeURIComponent(id)}/${action}`, {method: 'POST'});
      }
      await this.loadGoals();
    }
    catch (e) { this.notify(`Goal ${action} failed: ${e.message}`, true); }
  }
  renderGoals() {
    const badge = {
      queued: 'border-sky-800 bg-sky-950 text-sky-300', running: 'border-sky-700 bg-sky-950 text-sky-200',
      completed: 'border-emerald-800 bg-emerald-950 text-emerald-300', blocked: 'border-amber-800 bg-amber-950 text-amber-300',
      paused: 'border-slate-600 bg-slate-800 text-slate-300', cancelled: 'border-slate-700 bg-slate-900 text-slate-500',
      cancelling: 'border-slate-700 bg-slate-900 text-slate-400',
    };
    const list = this.state.goals.length ? this.state.goals.map(g => {
      const last = (g.notes || [])[g.notes.length - 1];
      const check = g.last_check;
      const canResume = ['paused', 'blocked', 'cancelled'].includes(g.status);
      const canCancel = ['queued', 'running', 'cancelling'].includes(g.status);
      return h('div', {key: g.id, className: 'rounded-xl border border-slate-800 bg-slate-950 p-3 space-y-1.5'},
        h('div', {className: 'flex items-start gap-2'},
          h('div', {className: 'text-sm flex-1 min-w-0 break-words'}, g.goal),
          h('span', {className: cx('shrink-0 text-xs px-2 py-0.5 rounded-full border', badge[g.status] || badge.paused, g.status === 'running' && 'animate-pulse')}, g.status),
          h('button', {onClick: () => this.goalAction(g.id, 'delete'), title: 'Delete goal card', className: 'text-slate-500 hover:text-rose-400 text-xs px-1'}, '✕')),
        h('div', {className: 'text-xs text-slate-500 flex flex-wrap gap-x-3'},
          h('span', null, `round ${g.rounds}/${g.max_rounds}`),
          g.check_command ? h('span', {className: 'font-mono truncate'}, g.check_command) : null,
          check ? h('span', {className: check.passed ? 'text-emerald-400' : 'text-rose-400'}, check.passed ? 'check passed' : 'check failing') : null),
        last ? h('div', {className: 'text-xs text-slate-400'}, `Latest: ${last.summary}`) : null,
        g.last_error && !['completed', 'running', 'queued'].includes(g.status) ? h('div', {className: 'text-xs text-amber-300 break-words'}, g.last_error) : null,
        h('div', {className: 'flex gap-2 pt-1'},
          canResume ? h('button', {onClick: () => this.goalAction(g.id, 'resume'), className: 'px-2.5 py-1 rounded-lg border border-brand-500 bg-brand-600 hover:bg-brand-500 text-xs'}, 'Resume') : null,
          canCancel ? h('button', {onClick: () => this.goalAction(g.id, 'cancel'), className: 'px-2.5 py-1 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-xs'}, 'Cancel') : null,
          h('button', {onClick: () => this.goalAction(g.id, 'delete'), className: 'px-2.5 py-1 rounded-lg border border-rose-900 bg-rose-950/60 text-rose-300 hover:bg-rose-900 text-xs'}, 'Remove')
        ));
    }) : h('div', {className: 'text-sm text-slate-500'}, 'No goals yet.');
    const form = h('div', {className: 'space-y-2 mb-3'},
      h('textarea', {rows: 2, value: this.state.goalText, onChange: e => this.setState({goalText: e.target.value}), placeholder: 'e.g. Fix the failing tests in my project', className: 'w-full resize-none rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm'}),
      h('div', {className: 'grid grid-cols-2 gap-2'},
        h('input', {value: this.state.goalCheck, onChange: e => this.setState({goalCheck: e.target.value}), placeholder: 'Done when… (e.g. pytest -q)', className: 'rounded-xl border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs font-mono'}),
        h('input', {value: this.state.goalCwd, onChange: e => this.setState({goalCwd: e.target.value}), placeholder: 'Folder or project name', className: 'rounded-xl border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs font-mono'})),
      h('button', {onClick: () => this.startGoal(), disabled: this.state.goalBusy || this.state.goalText.trim().length < 3, className: 'w-full px-3 py-2 rounded-xl border border-brand-500 bg-brand-600 hover:bg-brand-500 disabled:opacity-40 text-sm'}, this.state.goalBusy ? 'Starting…' : 'Start long-running goal'));
    return this.card('Long-running goals', h('div', null, form, h('div', {className: 'space-y-2 max-h-[28rem] overflow-y-auto'}, list)));
  }
  async loadToolsStatus() {
    try {
      const [voiceStatus, browserSessions] = await Promise.allSettled([
        this.api('/voice/status'),
        this.api('/browser/sessions'),
      ]);
      this.setState({
        toolsStatus: voiceStatus.status === 'fulfilled' ? voiceStatus.value : {error: voiceStatus.reason?.message},
        browserSessions: browserSessions.status === 'fulfilled' ? (browserSessions.value || []) : [],
      });
    } catch (_) {}
  }
  async startBrowserSession() {
    try {
      const res = await this.api('/browser/sessions', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({})});
      this.notify(`Browser session started: ${res.session_id || res.id || 'ok'}`);
      await this.loadToolsStatus();
    } catch (e) { this.notify(`Failed to start browser session: ${e.message}`, true); }
  }
  async refreshAll() { await Promise.allSettled([this.loadStatus(), this.loadUsage(), this.loadModels(), this.loadSkills(), this.loadAgents(), this.loadApprovals(), this.loadTodos(), this.loadCalendar(), this.loadSecurity(), this.loadActivity(), this.loadToolsStatus(), this.loadCareer()]); }
  async startActivityStream() {
    if (this.activityController) this.activityController.abort();
    const controller = new AbortController(); this.activityController = controller;
    try {
      const response = await fetch(`/activity/stream?after_id=${this.state.lastEvent}`, {headers: this.authHeaders({'Accept':'text/event-stream'}), signal: controller.signal});
      if (!response.ok || !response.body) throw new Error(`Activity stream HTTP ${response.status}`);
      const reader = response.body.getReader(), decoder = new TextDecoder(); let buffer = '';
      while (true) {
        const {done, value} = await reader.read(); if (done) break;
        buffer += decoder.decode(value, {stream:true}); const chunks = buffer.split('\n\n'); buffer = chunks.pop() || '';
        for (const block of chunks) {
          const row = block.split('\n').find(line => line.startsWith('data:')); if (!row) continue;
          try {
            const event = JSON.parse(row.slice(5).trim());
            this.setState(prev => ({lastEvent: Math.max(prev.lastEvent, Number(event.id || 0)), activity: [...prev.activity, event].slice(-100)}));
            this.onConversationEvent(event);
          } catch (_) {}
        }
      }
    } catch (error) {
      if (error.name !== 'AbortError') setTimeout(() => { if (controller === this.activityController) this.startActivityStream(); }, 2500);
    }
  }
  useToken() {
    const token = this.state.tokenInput.trim();
    if (token) sessionStorage.setItem('assistant_token', token); else sessionStorage.removeItem('assistant_token');
    this.setState({token: token || initialToken(), tokenInput: ''}, () => { this.refreshAll(); this.startActivityStream(); });
  }
  navigate(page) { location.hash = `/${page}`; }
  async decideApproval(id, approved) { try { await this.api(`/approvals/${encodeURIComponent(id)}`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({approved})}); await this.loadApprovals(); } catch(e){ this.notify(e.message, true); } }
  async addTodo() { const title=this.state.todoTitle.trim(); if(!title)return; try { await this.api('/todos',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,due_at:this.state.todoDue||null})}); this.setState({todoTitle:'',todoDue:''}); await this.loadTodos(); } catch(e){this.notify(e.message,true);} }
  async completeTodo(id) { try { await this.api(`/todos/${id}/complete`,{method:'POST'}); await this.loadTodos(); } catch(e){this.notify(e.message,true);} }
  async addCalendar() { const title=this.state.calTitle.trim(), start=this.state.calStart; if(!title||!start)return; try { await this.api('/calendar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,start_at:start})}); this.setState({calTitle:'',calStart:''}); await this.loadCalendar(); } catch(e){this.notify(e.message,true);} }
  async deleteCalendar(id) { try { await this.api(`/calendar/${encodeURIComponent(id)}`,{method:'DELETE'}); await this.loadCalendar(); } catch(e){this.notify(e.message,true);} }
  async pullModel() { const model=this.state.modelPullName.trim(); if(!model||this.state.modelBusy)return; this.setState({modelBusy:true}); try { const r=await this.api('/models/pull',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model})}); if(r?.ok===false)throw new Error(r.error||'Model pull failed'); this.setState({modelPullName:''}); this.notify(`Pulled ${model}`); await this.loadModels(); } catch(e){this.notify(e.message,true);} finally{this.setState({modelBusy:false});} }
  async deleteModel(model) { if(!globalThis.confirm(`Delete local model "${model}"?`))return; try{const r=await this.api('/models/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model,confirm:true})});if(r?.ok===false)throw new Error(r.error||'Delete failed');this.notify(`Deleted ${model}`);await this.loadModels();}catch(e){this.notify(e.message,true);} }
  async attachFiles(list) {
    const files = [...(list || [])].filter(Boolean);
    for (const file of files) {
      const isImage = String(file.type || '').startsWith('image/');
      let name = file.name && file.name !== 'image.png' ? file.name : (isImage ? 'pasted image.png' : 'file');
      const pending = this.state.pendingFiles;
      const images = pending.filter(f => f.kind === 'image').length;
      if (kindOf(name) === 'image' ? images >= 4 : pending.length - images >= 8) {
        this.notify('That is the most files one message can carry (4 images, 8 other files).', true);
        break;
      }
      this.setState(prev => ({uploading: prev.uploading + 1}));
      try {
        const saved = await uploadFile(file, this.state.token, name);
        this.setState(prev => ({pendingFiles: [...prev.pendingFiles, {id: saved.id, ref: saved.id, name: saved.name, kind: saved.kind, bytes: saved.bytes}]}));
      } catch (e) {
        this.notify(`Could not attach ${name}: ${e.message}`, true);
      } finally {
        this.setState(prev => ({uploading: prev.uploading - 1}));
      }
    }
    if (this.chatBox) this.chatBox.focus();
  }
  removePending(id) { this.setState(prev => ({pendingFiles: prev.pendingFiles.filter(f => f.id !== id)})); }
  cancelChat() {
    if (this.chatController) {
      this.chatController.abort();
      this.chatController = null;
    }
    if (this.state.sessionId) {
      this.api('/chat/stop', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({session_id: this.state.sessionId})}).catch(() => {});
    }
  }
  regenerate() {
    const msgs = this.state.messages;
    const lastUser = [...msgs].reverse().find(m => m.role === 'user');
    if (!lastUser || this.state.streaming) return;
    const cut = msgs.lastIndexOf(lastUser);
    this.setState({messages: msgs.slice(0, cut)}, () => this.sendChat(lastUser.text, {viaVoice: lastUser.viaVoice, regenerate: true}));
  }
  updateLastAssistant(fn) {
    this.setState(prev => {
      const messages = prev.messages.slice();
      const idx = messages.length - 1;
      if (idx < 0 || messages[idx].role !== 'assistant') return null;
      messages[idx] = fn({...messages[idx], steps: (messages[idx].steps || []).slice()});
      return {messages};
    });
  }
  handleChatEvent(event, run) {
    if (event.type === 'status') {
      if (event.status === 'generating' && run.stepText.trim()) {
        const note = run.stepText.trim();
        this.updateLastAssistant(m => ({...m, steps: [...m.steps, {kind: 'note', text: note}], text: ''}));
      }
      if (event.status === 'generating') run.stepText = '';
      const phase = {generating: `Thinking (step ${event.step || 1})`, reading: 'Reading the attached files', looking: 'Looking at the images'}[event.status] || 'Starting';
      this.updateLastAssistant(m => ({...m, phase}));
    } else if (event.type === 'token') {
      run.stepText += event.text || '';
      const text = run.stepText;
      this.updateLastAssistant(m => ({...m, text, phase: 'Writing'}));
    } else if (event.type === 'tool') {
      if (event.status === 'started') {
        run.stepText = '';
        this.updateLastAssistant(m => ({...m, text: '', phase: `Running ${event.tool}`, steps: [...m.steps, {kind: 'tool', tool: event.tool, args: event.args || '', status: 'running'}]}));
        this.setState(prev => ({chatTools: [{tool: event.tool, status: 'started', at: Date.now()}, ...prev.chatTools].slice(0, 40)}));
      } else {
        if (event.media && event.media.length) this.updateLastAssistant(m => ({...m, media: [...(m.media || []), ...event.media]}));
        this.updateLastAssistant(m => {
          const steps = m.steps;
          for (let i = steps.length - 1; i >= 0; i -= 1) {
            if (steps[i].kind === 'tool' && steps[i].tool === event.tool && steps[i].status === 'running') {
              steps[i] = {...steps[i], status: event.ok ? 'ok' : (event.approval_id ? 'approval' : 'failed'), error: event.error || '', approval_id: event.approval_id || null};
              return {...m, steps};
            }
          }
          return {...m, steps: [...steps, {kind: 'tool', tool: event.tool, status: event.ok ? 'ok' : 'failed', error: event.error || '', approval_id: event.approval_id || null}]};
        });
        const status = event.ok ? 'ok' : (event.approval_id ? 'approval' : 'failed');
        this.setState(prev => {
          const idx = prev.chatTools.findIndex(t => t.tool === event.tool && t.status === 'started');
          if (idx < 0) return {chatTools: [{tool: event.tool, status, error: event.error || '', at: Date.now()}, ...prev.chatTools].slice(0, 40)};
          const chatTools = prev.chatTools.slice();
          chatTools[idx] = {...chatTools[idx], status, error: event.error || ''};
          return {chatTools};
        });
      }
    } else if (event.type === 'final') {
      run.finalText = event.text || run.stepText;
      const text = run.finalText;
      this.updateLastAssistant(m => ({...m, text, phase: null, media: event.media || m.media}));
    } else if (event.type === 'error') {
      throw new Error(event.error || 'Chat stream failed');
    }
  }
  async sendChat(textOverride, opts = {}) {
    let text = safeText(textOverride ?? this.state.chatInput).trim();
    const attached = opts.regenerate || textOverride != null ? [] : this.state.pendingFiles;
    if ((!text && !attached.length) || this.state.streaming || this.state.uploading) return;
    const images = attached.filter(f => f.kind === 'image').map(f => f.id);
    const files = attached.filter(f => f.kind !== 'image');
    if (!text) text = files.length ? 'Please look at the attached file.' : 'What is in this image?';
    const shown = opts.regenerate ? text : [text, ...images.map(id => `[image ${id}]`), ...files.map(f => `[file ${f.id} ${f.name}]`)].join('\n');
    const user = {role: 'user', text: shown, viaVoice: !!opts.viaVoice};
    const assistant = {role: 'assistant', text: '', steps: [], phase: 'Starting', retryText: text};
    this.setState(prev => ({chatInput: textOverride == null ? '' : prev.chatInput, pendingFiles: attached.length ? [] : prev.pendingFiles,
                            streaming: true, messages: [...prev.messages, user, assistant]}));
    const controller = new AbortController();
    this.chatController = controller;
    const run = {stepText: '', finalText: ''};
    try {
      const response = await fetch(opts.regenerate ? '/chat/regenerate' : '/chat/stream', {
        method: 'POST', signal: controller.signal,
        headers: this.authHeaders({'Content-Type': 'application/json', 'Accept': 'text/event-stream'}),
        body: JSON.stringify(opts.regenerate ? {session_id: this.state.sessionId}
          : {message: text, session_id: this.state.sessionId, source: opts.viaVoice ? 'voice' : 'text', images, files: files.map(f => f.id)}),
      });
      if (!response.ok || !response.body) throw new Error((await response.text()).slice(0, 2000) || `HTTP ${response.status}`);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, {stream: true});
        const blocks = buffer.split('\n\n');
        buffer = blocks.pop() || '';
        for (const block of blocks) {
          const row = block.split('\n').find(line => line.startsWith('data:'));
          if (!row) continue;
          let event;
          try { event = JSON.parse(row.slice(5).trim()); } catch (_) { continue; }
          this.handleChatEvent(event, run);
        }
      }
      if (!run.finalText && !run.stepText) this.updateLastAssistant(m => ({...m, text: '_No response was returned._', phase: null}));
      if (this.state.speakReplies && run.finalText) this.speakReply(run.finalText);
    } catch (e) {
      if (e.name === 'AbortError') {
        this.updateLastAssistant(m => ({...m, phase: null, stopped: true, steps: m.steps.map(s => s.status === 'running' ? {...s, status: 'stopped'} : s)}));
      } else {
        this.updateLastAssistant(m => ({...m, phase: null, error: e.message}));
        this.notify(`Chat failed: ${e.message}`, true);
      }
    } finally {
      if (this.chatController === controller) this.chatController = null;
      this.setState({streaming: false});
      Promise.allSettled([this.loadActivity(), this.loadStatus(), this.loadApprovals()]);
    }
  }
  async killSwitch(mode) {
    this.setState({killBusy: true});
    if (this.chatController) this.chatController.abort();
    try {
      const r = await this.api('/system/kill', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                               body: JSON.stringify({mode, reason: `kill switch (dashboard, ${mode})`})});
      const stopped = [r.chat_turns_stopped ? `${r.chat_turns_stopped} chat turn(s)` : '',
                       (r.goals_cancelled || []).length ? `${r.goals_cancelled.length} goal(s)` : '',
                       (r.research_runs_cancelled || []).length ? `${r.research_runs_cancelled.length} research run(s)` : '']
        .filter(Boolean).join(', ');
      this.setState({killOpen: false, killed: mode === 'shutdown'
        ? 'The assistant is shut down: backend, model servers and desktop app are closed. Start it again with run.bat.'
        : `Everything stopped${stopped ? `: ${stopped}` : ''}. Models and background processes are released; the assistant is idle.`});
    } catch (e) {
      // A shutdown can cut the connection before the answer arrives; anything else is a real failure.
      const cut = mode === 'shutdown' && /fetch|network|load failed/i.test(e.message);
      this.setState({killOpen: false, killed: cut ? 'The assistant has shut down.' : null});
      if (!cut) this.notify(/not found|404/i.test(e.message)
        ? 'The running backend is older than this page and has no kill switch yet: close its run.bat window, then start run.bat again.'
        : `Kill switch failed: ${e.message}`, true);
    } finally {
      this.setState({killBusy: false});
    }
  }
  renderKillDialog() {
    if (!this.state.killOpen) return null;
    const busy = this.state.killBusy;
    return h('div', {className: 'fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4', role: 'dialog', 'aria-modal': 'true', 'aria-label': 'Kill switch',
                     onClick: e => { if (e.target === e.currentTarget && !busy) this.setState({killOpen: false}); }},
      h('div', {className: 'w-full max-w-md rounded-2xl border border-rose-800 bg-slate-900 p-5 shadow-2xl'},
        h('div', {className: 'text-lg font-bold text-rose-200'}, '⏻ Kill switch'),
        h('p', {className: 'mt-2 text-sm text-slate-300'}, 'Stops running chats, background goals, research runs, scheduled routines, voice, browser sessions, model servers and every other process the assistant started.'),
        h('div', {className: 'mt-4 grid gap-2'},
          h('button', {disabled: busy, autoFocus: true, onClick: () => this.killSwitch('shutdown'),
                       className: 'rounded-xl border border-rose-600 bg-rose-700 px-4 py-3 text-left text-white hover:bg-rose-600 disabled:opacity-50'},
            h('div', {className: 'font-semibold'}, '⏻ Shut the assistant down'), h('div', {className: 'text-xs text-rose-100/90'}, 'Stops everything, ends every process it started, closes the desktop app and exits.')),
          h('button', {disabled: busy, onClick: () => this.killSwitch('stop'),
                       className: 'rounded-xl border border-amber-700 bg-amber-950 px-4 py-2 text-left text-amber-100 hover:bg-amber-900 disabled:opacity-50'},
            h('div', {className: 'text-sm font-semibold'}, 'Only stop what it is doing'), h('div', {className: 'text-xs text-amber-200/80'}, 'Halts all activity but keeps the assistant running, idle.')),
          h('button', {disabled: busy, onClick: () => this.setState({killOpen: false}),
                       className: 'rounded-xl border border-slate-700 px-4 py-2 text-sm hover:bg-slate-800 disabled:opacity-50'}, busy ? 'Stopping…' : 'Cancel'))));
  }
  renderShell(content) {
    const pageLabel = NAV.find(([id])=>id===this.state.page)?.[1] || 'Overview';
    const online = !!this.state.status;
    return h('div',{className:'min-h-screen lg:grid lg:grid-cols-[15rem_minmax(0,1fr)]'},
      h('aside',{className:'bg-slate-900/90 border-slate-800 border-b lg:border-b-0 lg:border-r sticky top-0 z-20 lg:h-screen p-4 backdrop-blur-xl flex lg:block gap-3 overflow-x-auto items-center'},
        h('div',{className:'shrink-0 whitespace-nowrap text-lg font-extrabold'},'Living ',h('span',{className:'text-brand-400'},'Assistant')),
        h('nav',{className:'flex lg:block gap-2 lg:mt-6'},
          NAV.map(([id,label])=>h('button',{key:id,onClick:()=>this.navigate(id),className:cx('shrink-0 lg:w-full text-left px-3 py-2 rounded-xl text-sm transition',this.state.page===id?'bg-slate-800 text-white':'text-slate-400 hover:bg-slate-800 hover:text-white')},label)),
        )),
      h('main',{className:'px-4 py-5 md:px-6 lg:px-8 min-w-0 max-w-[1600px] mx-auto w-full'},
        h('header',{className:'flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-5'},
          h('div',null,h('h1',{className:'text-2xl font-bold'},pageLabel),h('p',{className:'text-sm text-slate-400'},'Local-first control center')),
          h('div',{className:'flex flex-wrap gap-2 items-center'},
            h('span',{className:'inline-flex items-center gap-2 rounded-full border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-400'},h('span',{className:cx('h-2 w-2 rounded-full',online?'bg-emerald-400':'bg-rose-400')}),online?`online · ${this.state.status.profile}`:'offline'),
            h('input',{type:'password',value:this.state.tokenInput,onChange:e=>this.setState({tokenInput:e.target.value}),placeholder:'API token',className:'w-48 sm:w-64 rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-brand-400'}),
            h('button',{className:'px-3 py-2 rounded-xl border border-slate-700 bg-slate-800 hover:bg-slate-700',onClick:()=>this.useToken()},'Use token'),
            h('button',{title:'Kill switch: stop everything the assistant is doing',onClick:()=>this.setState({killOpen:true}),
                        className:'px-3 py-2 rounded-xl border border-rose-800 bg-rose-950 text-rose-200 hover:bg-rose-900 font-semibold'},'⏻ Kill switch'))),
        this.state.killed ? h('div',{role:'status',className:'mb-4 rounded-xl border border-rose-800 bg-rose-950/60 px-4 py-3 text-sm text-rose-100 flex items-start gap-3'},
          h('span',{className:'flex-1'},this.state.killed),
          h('button',{onClick:()=>this.setState({killed:null}),className:'text-rose-300 hover:text-white','aria-label':'Dismiss'},'✕')) : null,
        content),
      this.renderKillDialog(),
      this.state.toast ? h('div',{role:'status',className:cx('fixed left-1/2 -translate-x-1/2 bottom-4 z-50 max-w-md rounded-xl border px-4 py-3 shadow-xl text-sm',this.state.error?'border-rose-800 bg-rose-950 text-rose-100':'border-slate-700 bg-slate-900')},this.state.toast):null);
  }
  render() {
    // Only the visible page is built, inside an error boundary: one broken page must not blank the app.
    const pages={overview:()=>this.renderOverview(),models:()=>this.renderModels(),chat:()=>this.renderChat(),skills:()=>this.renderSkills(),agents:()=>this.renderAgents(),approvals:()=>this.renderApprovals(),organize:()=>this.renderOrganize(),security:()=>this.renderSecurity(),activity:()=>this.renderActivity(),career:()=>this.renderCareer(),tools:()=>this.renderTools()};
    const want = this.props.embedded ? this.props.page : this.state.page;
    const page = pages[want] ? want : 'overview';
    const body = h(ErrorBoundary,{key:page,name:page},h(PageBody,{render:pages[page]}));
    if (this.props.embedded) return h('div', null, body, this.state.toast ? h('div', {className: 'fixed bottom-4 right-4 z-50 rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm'}, this.state.toast) : null);
    return this.renderShell(body);
  }
  renderTools() {
    const s = this.state.status || {};
    const tools = (this.state.skills || []).flatMap(sk => (sk.manifest?.required_tools || []));
    const uniqueTools = Array.from(new Set(tools));
    return h('div', {className: 'space-y-4'},
      h('div', {className: 'flex items-center justify-between'},
        h('h2', {className: 'text-xl font-bold'}, 'Registered & Built-in Tools'),
        h('span', {className: 'text-xs text-slate-400'}, `${uniqueTools.length} tools detected`)
      ),
      this.card('Active Runtime Tools',
        uniqueTools.length ? h('div', {className: 'grid sm:grid-cols-2 md:grid-cols-3 gap-3'},
          uniqueTools.map(t => h('div', {key: t, className: 'p-3 bg-slate-950 border border-slate-800 rounded-xl'},
            h('div', {className: 'font-mono text-sm text-brand-300 font-semibold'}, t),
            h('div', {className: 'text-xs text-slate-400 mt-1'}, 'Living Assistant tool registry')
          ))
        ) : h('div', {className: 'text-sm text-slate-400'}, 'Tools are managed via Skills and Software Company roles.')
      )
    );
  }
  renderSkills() {
    const sel = this.state.selectedSkill;
    const m = sel?.manifest || {};
    const lc = sel?.lifecycle || {};
    const filtered = (this.state.skills || []).filter(s => {
      const q = (this.state.skillSearch || '').toLowerCase();
      return !q || (s.name || s.skill_id || '').toLowerCase().includes(q) || (s.description || '').toLowerCase().includes(q);
    });

    const statusBadge = (st) => {
      const colors = {
        ACTIVE: 'bg-emerald-950 text-emerald-300 border-emerald-800',
        DRAFT: 'bg-amber-950 text-amber-300 border-amber-800',
        DISABLED: 'bg-rose-950 text-rose-300 border-rose-800',
        ARCHIVED: 'bg-slate-800 text-slate-400 border-slate-700',
      };
      return h('span', {className: `text-xs px-2 py-0.5 rounded-full border ${colors[st] || colors.DRAFT}`}, st || 'DRAFT');
    };

    const leftCol = h('div', {className: 'space-y-3'},
      this.card('Create from Description', h('div', {className: 'space-y-2'},
        h('textarea', {
          rows: 2,
          value: this.state.skillDraftPrompt,
          onChange: e => this.setState({skillDraftPrompt: e.target.value}),
          placeholder: 'e.g. Create a skill that organizes my invoices by vendor and month',
          className: 'w-full resize-none rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm',
        }),
        h('div', {className: 'flex justify-end'},
          h('button', {
            disabled: this.state.skillBusy || !this.state.skillDraftPrompt.trim(),
            onClick: () => this.createSkillDraft(),
            className: 'px-3 py-2 rounded-xl border border-brand-500 bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-sm font-medium',
          }, this.state.skillBusy ? 'Creating Draft…' : 'Generate Draft'),
        ),
      )),
      this.card('Registered Skills', h('div', {className: 'space-y-3'},
        h('div', {className: 'flex gap-2'},
          h('input', {
            value: this.state.skillSearch,
            onChange: e => this.setState({skillSearch: e.target.value}),
            placeholder: 'Search skills…',
            className: 'w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm',
          }),
          h('button', {
            onClick: () => this.loadSkillCollections(),
            className: 'px-3 py-1.5 rounded-xl border border-slate-700 bg-slate-800 text-xs hover:bg-slate-700 whitespace-nowrap',
          }, 'Browse Collections'),
        ),
        h('div', {className: 'space-y-2 max-h-[30rem] overflow-y-auto'},
          filtered.length ? filtered.map((sk) => h('div', {
            key: sk.skill_id,
            onClick: () => this.selectSkill(sk.skill_id),
            className: cx(
              'p-3 rounded-xl border cursor-pointer transition',
              sel?.lifecycle?.skill_id === sk.skill_id ? 'border-brand-500 bg-slate-800/80' : 'border-slate-800 bg-slate-950 hover:bg-slate-800/50',
            ),
          },
            h('div', {className: 'flex items-center justify-between'},
              h('strong', {className: 'text-sm'}, sk.name || sk.skill_id),
              statusBadge(sk.state),
            ),
            h('div', {className: 'text-xs text-slate-400 mt-1 line-clamp-2'}, sk.description || 'No description'),
            h('div', {className: 'text-xs text-slate-500 mt-2 font-mono'}, `v${sk.current_version || sk.manifest?.version || '1.0.0'}`),
          )) : h('div', {className: 'text-slate-500 text-sm'}, 'No matching skills found.'),
        ),
      )),
    );

    const rightCol = sel ? h('div', {className: 'space-y-3'},
      this.card(null, h('div', {className: 'space-y-4'},
        h('div', {className: 'flex items-start justify-between flex-wrap gap-2'},
          h('div', null,
            h('h2', {className: 'text-lg font-bold'}, m.name || sel.lifecycle.skill_id),
            h('div', {className: 'text-xs text-slate-400 font-mono mt-0.5'}, `ID: ${sel.lifecycle.skill_id} · v${m.version || sel.lifecycle.current_version}`),
          ),
          h('div', {className: 'flex items-center gap-2'},
            statusBadge(sel.lifecycle.state),
            sel.lifecycle.state === 'ACTIVE'
              ? h('button', {onClick: () => this.disableSkill(sel.lifecycle.skill_id), className: 'px-3 py-1.5 rounded-xl border border-rose-800 bg-rose-950 text-rose-300 text-xs'}, 'Disable')
              : h('button', {onClick: () => this.activateSkill(sel.lifecycle.skill_id), className: 'px-3 py-1.5 rounded-xl border border-emerald-800 bg-emerald-950 text-emerald-300 text-xs'}, 'Review & Activate'),
          ),
        ),
        h('p', {className: 'text-sm text-slate-300'}, m.description || ''),
        h('div', {className: 'grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs'},
          h('div', {className: 'rounded-xl border border-slate-800 p-3 bg-slate-950'},
            h('div', {className: 'text-slate-500 uppercase font-semibold mb-1'}, 'Triggers'),
            h('div', {className: 'flex flex-wrap gap-1'}, (m.triggers || []).map(t => h('span', {key: t, className: 'px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono'}, t))),
          ),
          h('div', {className: 'rounded-xl border border-slate-800 p-3 bg-slate-950'},
            h('div', {className: 'text-slate-500 uppercase font-semibold mb-1'}, 'Required Tools'),
            h('div', {className: 'flex flex-wrap gap-1'}, (m.required_tools || []).map(t => h('span', {key: t, className: 'px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono'}, t))),
          ),
        ),
        h('div', {className: 'rounded-xl border border-slate-800 p-3 bg-slate-950 text-xs space-y-1'},
          h('div', {className: 'text-slate-500 uppercase font-semibold mb-1'}, 'Security & Permission Scopes'),
          h('div', null, `Allowed Filesystem: ${JSON.stringify(m.permissions?.filesystem || ['workspace'])}`),
          h('div', null, `Destructive File Changes: ${m.permissions?.destructive ? 'Yes' : 'No (Protected)'}`),
          h('div', null, `Network Access: ${m.permissions?.network ? 'Yes' : 'No (Offline)'}`),
          h('div', null, `Subprocess Execution: ${m.permissions?.subprocess ? 'Yes' : 'No'}`),
        ),
        h('div', {className: 'flex items-center gap-3 pt-2 border-t border-slate-800 flex-wrap'},
          h('label', {className: 'flex items-center gap-2 text-xs text-slate-300'},
            h('input', {type: 'checkbox', checked: this.state.skillDryRun, onChange: e => this.setState({skillDryRun: e.target.checked})}),
            'Dry Run (Suppress Disk Mutations)',
          ),
          h('button', {
            disabled: this.state.skillBusy,
            onClick: () => this.testSkill(sel.lifecycle.skill_id),
            className: 'px-4 py-2 rounded-xl border border-brand-500 bg-brand-600 hover:bg-brand-500 text-xs font-semibold disabled:opacity-50',
          }, this.state.skillBusy ? 'Running…' : (this.state.skillDryRun ? 'Preview Dry Run' : 'Execute Live')),
          h('a', {
            href: `/skills/${sel.lifecycle.skill_id}/export`,
            download: `skill_${sel.lifecycle.skill_id}.zip`,
            className: 'px-3 py-2 rounded-xl border border-slate-700 bg-slate-800 hover:bg-slate-700 text-xs text-slate-300',
          }, 'Export (.zip)'),
        ),
        this.state.skillTrace ? h('div', {className: 'space-y-2 pt-2 border-t border-slate-800'},
          h('h3', {className: 'text-xs font-semibold uppercase text-slate-400'}, `Execution Trace (${this.state.skillTrace.status})`),
          h('pre', {className: 'font-mono text-xs overflow-x-auto p-3 rounded-xl bg-slate-950 border border-slate-800 whitespace-pre-wrap'},
            JSON.stringify(this.state.skillTrace, null, 2),
          ),
        ) : null,
        sel.versions?.length > 1 ? h('div', {className: 'space-y-2 pt-2 border-t border-slate-800'},
          h('h3', {className: 'text-xs font-semibold uppercase text-slate-400'}, 'Version Snapshots & Rollback'),
          h('div', {className: 'space-y-1'}, sel.versions.map(v => h('div', {
            key: v.version,
            className: 'flex items-center justify-between text-xs p-2 rounded-lg bg-slate-950 border border-slate-800',
          },
            h('span', null, `v${v.version} · ${v.created_at}`),
            v.version !== sel.lifecycle.current_version
              ? h('button', {
                onClick: () => this.rollbackSkill(sel.lifecycle.skill_id, v.version),
                className: 'px-2 py-1 rounded border border-amber-800 bg-amber-950 text-amber-300 hover:bg-amber-900',
              }, 'Rollback')
              : h('span', {className: 'text-emerald-400 font-semibold'}, 'Active Version'),
          ))),
        ) : null,
        sel.skill_md ? h('div', {className: 'space-y-2 pt-2 border-t border-slate-800'},
          h('h3', {className: 'text-xs font-semibold uppercase text-slate-400'}, 'SKILL.md Documentation'),
          h('pre', {className: 'font-mono text-xs overflow-x-auto p-3 rounded-xl bg-slate-950 border border-slate-800 whitespace-pre-wrap'}, sel.skill_md),
        ) : null,
      ))) : this.card(null, h('div', {className: 'text-slate-500 py-12 text-center'}, 'Select a skill from the left or generate a new draft to inspect details.'));

    return h('div', null,
      h(SkillLibraryPanel, {api: this.apiFn, notify: this.notifyFn, card: (t, b) => this.card(t, b)}),
      h('h2', {className: 'text-sm font-semibold text-slate-400 mt-2 mb-2'}, 'Skill packages (manifest skills with steps and permissions)'),
      h('div', {className: 'grid md:grid-cols-12 gap-3'},
        h('div', {className: 'md:col-span-5'}, leftCol),
        h('div', {className: 'md:col-span-7'}, rightCol),
      ),
    );
  }
  renderAgents() {
    const sel = this.state.selectedAgent;
    const m = sel?.manifest || {};
    const lc = sel?.lifecycle || {};
    const filtered = (this.state.agents || []).filter(a => {
      const q = (this.state.agentSearch || '').toLowerCase();
      return !q || (a.name || a.agent_id || '').toLowerCase().includes(q) || (a.description || '').toLowerCase().includes(q) || (a.role || '').toLowerCase().includes(q);
    });

    const statusBadge = (st) => {
      const colors = {
        ACTIVE: 'bg-emerald-950 text-emerald-300 border-emerald-800',
        DRAFT: 'bg-amber-950 text-amber-300 border-amber-800',
        DISABLED: 'bg-rose-950 text-rose-300 border-rose-800',
        ARCHIVED: 'bg-slate-800 text-slate-400 border-slate-700',
      };
      return h('span', {className: `text-xs px-2 py-0.5 rounded-full border ${colors[st] || colors.DRAFT}`}, st || 'DRAFT');
    };

    const leftCol = h('div', {className: 'space-y-3'},
      this.card('Create Agent from Description', h('div', {className: 'space-y-2'},
        h('textarea', {
          rows: 2,
          value: this.state.agentDraftPrompt,
          onChange: e => this.setState({agentDraftPrompt: e.target.value}),
          placeholder: 'e.g. Create a research specialist that searches and summarizes technical documentation',
          className: 'w-full resize-none rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm',
        }),
        h('div', {className: 'flex justify-end'},
          h('button', {
            disabled: this.state.agentBusy || !this.state.agentDraftPrompt.trim(),
            onClick: () => this.createAgentDraft(),
            className: 'px-3 py-2 rounded-xl border border-brand-500 bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-sm font-medium',
          }, this.state.agentBusy ? 'Drafting…' : 'Generate Agent Draft'),
        ),
      )),
      this.card('Registered Custom Agents', h('div', {className: 'space-y-3'},
        h('input', {
          value: this.state.agentSearch,
          onChange: e => this.setState({agentSearch: e.target.value}),
          placeholder: 'Search agents…',
          className: 'w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm',
        }),
        h('div', {className: 'space-y-2 max-h-[30rem] overflow-y-auto'},
          filtered.length ? filtered.map((ag) => h('div', {
            key: ag.agent_id,
            onClick: () => this.selectAgent(ag.agent_id),
            className: cx(
              'p-3 rounded-xl border cursor-pointer transition',
              sel?.lifecycle?.agent_id === ag.agent_id ? 'border-brand-500 bg-slate-800/80' : 'border-slate-800 bg-slate-950 hover:bg-slate-800/50',
            ),
          },
            h('div', {className: 'flex items-center justify-between'},
              h('strong', {className: 'text-sm'}, ag.name || ag.agent_id),
              statusBadge(ag.state),
            ),
            h('div', {className: 'text-xs text-slate-400 mt-1 line-clamp-2'}, ag.description || 'No description'),
            h('div', {className: 'text-xs text-slate-500 mt-2 flex justify-between font-mono'},
              h('span', null, `Role: ${ag.role || 'specialist'}`),
              h('span', null, `v${ag.current_version || ag.manifest?.version || '1.0.0'}`),
            ),
          )) : h('div', {className: 'text-slate-500 text-sm'}, 'No matching agents found.'),
        ),
      )),
    );

    const rightCol = sel ? h('div', {className: 'space-y-3'},
      this.card(null, h('div', {className: 'space-y-4'},
        h('div', {className: 'flex items-start justify-between flex-wrap gap-2'},
          h('div', null,
            h('h2', {className: 'text-lg font-bold'}, m.name || sel.lifecycle.agent_id),
            h('div', {className: 'text-xs text-slate-400 font-mono mt-0.5'}, `ID: ${sel.lifecycle.agent_id} · Role: ${sel.lifecycle.role || m.role} · v${m.version || sel.lifecycle.current_version}`),
          ),
          h('div', {className: 'flex items-center gap-2'},
            statusBadge(sel.lifecycle.state),
            sel.lifecycle.state === 'ACTIVE'
              ? h('button', {onClick: () => this.disableAgent(sel.lifecycle.agent_id), className: 'px-3 py-1.5 rounded-xl border border-rose-800 bg-rose-950 text-rose-300 text-xs'}, 'Disable')
              : h('button', {onClick: () => this.activateAgent(sel.lifecycle.agent_id), className: 'px-3 py-1.5 rounded-xl border border-emerald-800 bg-emerald-950 text-emerald-300 text-xs'}, 'Review & Activate'),
          ),
        ),
        h('p', {className: 'text-sm text-slate-300'}, m.description || ''),
        h('div', {className: 'grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs'},
          h('div', {className: 'rounded-xl border border-slate-800 p-3 bg-slate-950'},
            h('div', {className: 'text-slate-500 uppercase font-semibold mb-1'}, 'Allowed Tools'),
            h('div', {className: 'flex flex-wrap gap-1'}, (m.allowed_tools || []).map(t => h('span', {key: t, className: 'px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono'}, t))),
          ),
          h('div', {className: 'rounded-xl border border-slate-800 p-3 bg-slate-950'},
            h('div', {className: 'text-slate-500 uppercase font-semibold mb-1'}, 'Allowed Skills'),
            h('div', {className: 'flex flex-wrap gap-1'}, (m.allowed_skills || []).map(s => h('span', {key: s, className: 'px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono'}, s))),
          ),
        ),
        h('div', {className: 'rounded-xl border border-slate-800 p-3 bg-slate-950 text-xs space-y-1'},
          h('div', {className: 'text-slate-500 uppercase font-semibold mb-1'}, 'Governance & Bounding Limits'),
          h('div', null, `Max Steps: ${m.limits?.max_steps || 15} · Loop Detection Threshold: ${m.limits?.loop_detection_threshold || 3}`),
          h('div', null, `Timeout: ${m.limits?.timeout_seconds || 120}s · Delegation: ${m.delegation_policy?.can_delegate ? 'Enabled' : 'Disabled'}`),
          h('div', null, `Memory Scope: [${(m.memory_scope?.readable_namespaces || []).join(', ')}]`),
        ),
        h('div', {className: 'flex items-center gap-3 pt-2 border-t border-slate-800 flex-wrap'},
          h('label', {className: 'flex items-center gap-2 text-xs text-slate-300'},
            h('input', {type: 'checkbox', checked: this.state.agentDryRun, onChange: e => this.setState({agentDryRun: e.target.checked})}),
            'Dry Run (Tool Simulation)',
          ),
          h('button', {
            disabled: this.state.agentBusy,
            onClick: () => this.testAgent(sel.lifecycle.agent_id),
            className: 'px-4 py-2 rounded-xl border border-brand-500 bg-brand-600 hover:bg-brand-500 text-xs font-semibold disabled:opacity-50',
          }, this.state.agentBusy ? 'Executing…' : (this.state.agentDryRun ? 'Run Dry-Run Test' : 'Execute Agent Live')),
          h('a', {
            href: `/agents/${sel.lifecycle.agent_id}/export`,
            download: `agent_${sel.lifecycle.agent_id}.zip`,
            className: 'px-3 py-2 rounded-xl border border-slate-700 bg-slate-800 hover:bg-slate-700 text-xs text-slate-300',
          }, 'Export (.zip)'),
        ),
        this.state.agentTrace ? h('div', {className: 'space-y-2 pt-2 border-t border-slate-800'},
          h('h3', {className: 'text-xs font-semibold uppercase text-slate-400'}, `Execution Trace (${this.state.agentTrace.status})`),
          h('pre', {className: 'font-mono text-xs overflow-x-auto p-3 rounded-xl bg-slate-950 border border-slate-800 whitespace-pre-wrap'},
            JSON.stringify(this.state.agentTrace, null, 2),
          ),
        ) : null,
        sel.agent_md ? h('div', {className: 'space-y-2 pt-2 border-t border-slate-800'},
          h('h3', {className: 'text-xs font-semibold uppercase text-slate-400'}, 'AGENT.md Specification'),
          h('pre', {className: 'font-mono text-xs overflow-x-auto p-3 rounded-xl bg-slate-950 border border-slate-800 whitespace-pre-wrap'}, sel.agent_md),
        ) : null,
      ))) : this.card(null, h('div', {className: 'text-slate-500 py-12 text-center'}, 'Select an agent from the left or generate a draft to view details.'));

    return h('div', {className: 'grid md:grid-cols-12 gap-3'},
      h('div', {className: 'md:col-span-5'}, leftCol),
      h('div', {className: 'md:col-span-7'}, rightCol),
    );
  }
  card(title, body, className='') { return h('section',{className:cx('rounded-2xl border border-slate-800 bg-slate-900/75 p-4 shadow-2xl shadow-black/20',className)},title?h('h2',{className:'text-base font-semibold mb-3'},title):null,body); }
  metric(label,value){return this.card(null,h('div',null,h('div',{className:'text-xs uppercase tracking-wider text-slate-500'},label),h('div',{className:'text-2xl font-semibold mt-1'},value)));}
  renderOverview(){
    const s=this.state.status, r=s?.resources||{}, hw=s?.hardware||{}; const usage=this.state.usage||{};
    return h('div',{className:'space-y-3'},
      h('div',{className:'grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3'},this.metric('CPU',s?`${r.cpu_percent}%`:'--'),this.metric('RAM',s?`${r.ram_percent}%`:'--'),this.metric('Available RAM',s?`${r.available_ram_gb} GB`:'--'),this.metric('Active model',s?.active_model||'sleeping')),
      h('div',{className:'grid md:grid-cols-12 gap-3'},this.card('Resource history',h(ResourceChart,{history:this.state.resourceHistory}),'md:col-span-6'),this.card('System',h('div',{className:'text-sm text-slate-400 space-y-2'},h('div',null,`${hw.os||'Unknown'} ${hw.machine||''}`),h('div',null,`RAM ${hw.ram_gb||'--'} GB`),h('div',null,`GPU ${hw.gpu_name||'not detected'}`),h('div',null,`Desktop ${this.state.desktop?.semantic_backend||'unavailable'}`)),'md:col-span-6')),
      this.card('Model usage',h(UsageTable,{usage})),
      h('div',{className:'grid md:grid-cols-12 gap-3'},this.card('Pending approvals',h(ApprovalList,{rows:this.state.approvals.slice(0,4),decide:(id,v)=>this.decideApproval(id,v)}),'md:col-span-6'),this.card('Recent activity',h(ActivityList,{rows:this.state.activity.slice(-8)}),'md:col-span-6')));
  }
  renderVision() {
    const v = this.state.vision;
    if (!v) return null;
    const cats = ['ocr', 'ui', 'symbols', 'charts', 'diagrams', 'photo'];
    const running = v.status?.running?.model;
    const models = h('div', {className: 'overflow-x-auto'}, h('table', {className: 'w-full text-sm'},
      h('thead', null, h('tr', {className: 'text-left text-xs uppercase tracking-wider text-slate-500'},
        ['Model', 'Mode', 'State', ''].map(t => h('th', {key: t, className: 'py-2 pr-3 font-medium'}, t)))),
      h('tbody', null, v.models.map(m => h('tr', {key: m.name, className: 'border-t border-slate-800'},
        h('td', {className: 'py-2 pr-3'}, h('div', {className: 'font-medium'}, m.name, m.default ? h('span', {className: 'ml-2 text-xs text-brand-300'}, 'default') : null),
          h('div', {className: 'text-xs text-slate-500'}, m.notes)),
        h('td', {className: 'py-2 pr-3 text-slate-400'}, m.mode === 'swap' ? 'pauses chat model' : 'runs alongside'),
        h('td', {className: 'py-2 pr-3 text-slate-400'}, m.name === running ? 'loaded' : m.downloaded ? 'downloaded'
          : m.download?.status === 'downloading' ? `downloading ${m.download.total ? Math.round(100 * m.download.done / m.download.total) : 0}%` : 'not downloaded'),
        h('td', {className: 'py-2 text-right whitespace-nowrap'},
          m.downloaded ? (m.default ? null : h('button', {onClick: () => this.setVisionDefault(m.name), className: 'px-2.5 py-1 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-xs'}, 'Make default'))
            : h('button', {onClick: () => this.downloadVision(m.name), disabled: m.download?.status === 'downloading', className: 'px-2.5 py-1 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-xs disabled:opacity-50'}, 'Download')))))));
    const bench = v.bench.length ? h('div', {className: 'overflow-x-auto'}, h('table', {className: 'w-full text-xs'},
      h('thead', null, h('tr', {className: 'text-left uppercase tracking-wider text-slate-500'},
        ['Model', 'Mode', 'Passed', ...cats, 'Median s', 'RAM MB'].map(t => h('th', {key: t, className: 'py-2 pr-3 font-medium'}, t)))),
      h('tbody', null, v.bench.map(r => h('tr', {key: r.model + r.variant, className: 'border-t border-slate-800'},
        h('td', {className: 'py-1.5 pr-3 font-medium'}, r.model), h('td', {className: 'py-1.5 pr-3 text-slate-400'}, r.variant),
        h('td', {className: 'py-1.5 pr-3'}, `${r.passed}/${r.total}`),
        ...cats.map(c => h('td', {key: c, className: 'py-1.5 pr-3 text-slate-400'}, r.categories[c] ? `${r.categories[c][0]}/${r.categories[c][1]}` : '–')),
        h('td', {className: 'py-1.5 pr-3 text-slate-400'}, r.median_seconds ?? '–'), h('td', {className: 'py-1.5 text-slate-400'}, r.peak_rss_mb ?? '–'))))))
      : h('div', {className: 'text-sm text-slate-500'}, 'No benchmark results yet (python benchmarks/vision/run.py).');
    return h('div', {className: 'space-y-3'},
      this.card('Vision models', h('div', {className: 'space-y-2'},
        h('p', {className: 'text-sm text-slate-400'}, 'Used for attached images, screen questions, research figures and camera frames. Each runs in its own local llama.cpp server, loaded on demand.'),
        models)),
      this.card('Vision benchmark (this machine)', bench));
  }
  renderModels(){ return h('div',{className:'space-y-3'},this.renderLlmModels(),this.renderVision()); }
  renderLlmModels(){ const data=this.state.models||{}; return this.card('Local model manager',h('div',{className:'space-y-3'},h('div',{className:'flex flex-wrap gap-2 text-sm text-slate-400'},h('span',{className:'rounded-full border border-slate-700 px-3 py-2'},`GPU ${data.gpu?.name||'not detected'}`),h('span',{className:'rounded-full border border-slate-700 px-3 py-2'},`Free VRAM ${data.gpu?.free_vram_gb??'--'} GB`),h('span',{className:'rounded-full border border-slate-700 px-3 py-2'},`Disk ${fmtBytes(data.total_disk_bytes)}`)),h('div',{className:'grid grid-cols-[minmax(0,1fr)_auto] gap-2'},h('input',{value:this.state.modelPullName,onChange:e=>this.setState({modelPullName:e.target.value}),onKeyDown:e=>{if(e.key==='Enter')this.pullModel();},placeholder:'e.g. qwen2.5:7b',className:'w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2'}),h('button',{disabled:this.state.modelBusy,onClick:()=>this.pullModel(),className:'px-3 py-2 rounded-xl border border-brand-500 bg-brand-600 hover:bg-brand-500 disabled:opacity-50'},this.state.modelBusy?'Pulling…':'Pull model')),h(ModelTable,{models:data.models||[],onDelete:m=>this.deleteModel(m)}))); }
  renderStep(step, i, retryText) {
    if (step.kind === 'note') {
      return h('div', {key: i, className: 'text-xs text-slate-400 italic border-l-2 border-slate-700 pl-3 py-1'}, step.text);
    }
    const tone = {
      running: 'border-sky-800 bg-sky-950/60 text-sky-200',
      ok: 'border-emerald-900 bg-emerald-950/50 text-emerald-200',
      failed: 'border-rose-900 bg-rose-950/50 text-rose-200',
      approval: 'border-amber-800 bg-amber-950/60 text-amber-200',
      stopped: 'border-slate-700 bg-slate-900 text-slate-400',
    }[step.status] || 'border-slate-700 bg-slate-900 text-slate-300';
    const icon = {running: '◌', ok: '✓', failed: '✕', approval: '⚠', stopped: '■'}[step.status] || '•';
    return h('div', {key: i, className: cx('rounded-xl border px-3 py-2 text-xs', tone)},
      h('div', {className: 'flex items-center gap-2 min-w-0'},
        h('span', {className: cx('shrink-0 font-bold', step.status === 'running' && 'animate-spin inline-block')}, icon),
        h('span', {className: 'font-mono font-semibold shrink-0'}, step.tool),
        step.args && step.args !== '{}' ? h('span', {className: 'font-mono text-slate-400 truncate'}, step.args) : null),
      step.error && step.status !== 'approval' ? h('div', {className: 'mt-1 text-rose-300 break-words'}, step.error) : null,
      step.status === 'approval' ? h('div', {className: 'mt-2 flex flex-wrap items-center gap-2'},
        h('span', {className: 'text-amber-200'}, step.decided ? `Request ${step.decided}.` : 'This action needs your approval.'),
        step.decided ? null : h('button', {onClick: () => this.decideInline(step.approval_id, true, retryText), className: 'px-2.5 py-1 rounded-lg border border-emerald-700 bg-emerald-900 text-emerald-100 hover:bg-emerald-800'}, 'Approve & retry'),
        step.decided ? null : h('button', {onClick: () => this.decideInline(step.approval_id, false), className: 'px-2.5 py-1 rounded-lg border border-rose-800 bg-rose-950 text-rose-200 hover:bg-rose-900'}, 'Deny'),
      ) : null);
  }
  renderMessage(m, i) {
    if (m.role === 'user') {
      // Images attached from the floating agent are kept in the text as [image img_…] markers.
      const {text, files} = extractFiles(m.text);
      const images = [...text.matchAll(/\[image (img_[0-9a-f]{16})\]/g)].map(x => x[1]);
      const tokenQuery = this.state.token ? `?token=${encodeURIComponent(this.state.token)}` : '';
      return h('div', {key: i, className: 'flex justify-end'},
        h('div', {className: 'max-w-[85%] rounded-2xl rounded-br-md bg-brand-600 px-4 py-2.5 text-white whitespace-pre-wrap break-words'},
          images.length ? h('div', {className: 'flex flex-wrap gap-2 mb-2'}, images.map(id => h('img', {
            key: id, src: `/attachments/${id}${tokenQuery}`, alt: 'Attached image', loading: 'lazy',
            className: 'max-h-48 max-w-full rounded-lg border border-white/20'}))) : null,
          files.length ? h(DomNode, {className: 'chat-file-chips', depKey: files.map(f => f.ref).join(','),
            make: () => { const frag = document.createDocumentFragment(); files.forEach(f => frag.appendChild(fileChip(f, this.state.token))); return frag; }}) : null,
          m.viaVoice ? h('span', {className: 'mr-2 text-xs opacity-75', title: 'Spoken'}, '🎙') : null,
          text.replace(/\[image img_[0-9a-f]{16}\]/g, '').trim()));
    }
    const steps = m.steps || [];
    return h('div', {key: i, className: 'flex gap-3 items-start'},
      h(AgentFace, {size: 'sm', mood: m.error ? 'error' : m.phase ? 'thinking' : 'idle'}),
      h('div', {className: 'min-w-0 flex-1 max-w-[85%] space-y-2'},
        steps.length ? h('div', {className: 'space-y-1.5'}, steps.map((s, idx) => this.renderStep(s, idx, m.retryText))) : null,
        m.text ? h('div', {className: 'rounded-2xl rounded-tl-md border border-slate-700 bg-slate-800/80 px-4 py-3'}, h(Markdown, {text: m.text})) : null,
        m.media && m.media.length ? h(DomNode, {depKey: m.media.map(x => x.ref).join(','), make: () => mediaList(m.media, this.state.token)}) : null,
        m.phase ? h('div', {className: 'flex items-center gap-2 text-xs text-slate-400'},
          h('span', {className: 'typing-dots'}, h('i'), h('i'), h('i')), m.phase) : null,
        m.stopped ? h('div', {className: 'text-xs text-slate-500'}, 'Stopped.') : null,
        m.error ? h('div', {className: 'rounded-xl border border-rose-900 bg-rose-950/50 px-3 py-2 text-sm text-rose-200 flex flex-wrap items-center gap-2'},
          h('span', {className: 'break-words'}, m.error),
          m.retryText && !this.state.streaming ? h('button', {onClick: () => this.sendChat(m.retryText), className: 'px-2.5 py-1 rounded-lg border border-rose-700 hover:bg-rose-900 text-xs'}, 'Retry') : null) : null,
        i === this.state.messages.length - 1 && !m.phase && !this.state.streaming && (m.text || m.error)
          ? h('button', {onClick: () => this.regenerate(), title: 'Ask again and replace this answer',
                         className: 'text-xs text-slate-400 hover:text-slate-200'}, '↻ Regenerate') : null));
  }
  renderChat() {
    const {messages, streaming, voiceRecording, chatInput, speakReplies} = this.state;
    const suggestions = [
      ['🔎', 'Search the web', 'Search the web for the latest news about '],
      ['🖼', 'Find & download an image', 'Find and download a picture of '],
      ['🎬', 'Download a video', 'Download this video: '],
      ['🖥', 'Scan my screen', 'Look at my screen and tell me what is wrong'],
      ['📜', 'Check logs for errors', 'Check the log files for errors and summarize them'],
      ['🧪', 'Audit a project', 'Analyze this project for bugs and code-quality problems: '],
    ];
    const empty = h('div', {className: 'h-full flex flex-col items-center justify-center text-center gap-5 py-8'},
      h(AgentFace, {size: 'lg', mood: voiceRecording ? 'listening' : 'idle', track: true}),
      h('div', null,
        h('div', {className: 'text-lg font-semibold'}, 'What should we do?'),
        h('div', {className: 'text-sm text-slate-400'}, 'Type, or press the mic and just say it.')),
      h('div', {className: 'grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-xl'}, suggestions.map(([icon, label, prompt]) => h('button', {
        key: label,
        onClick: () => { this.setState({chatInput: prompt}); if (this.chatBox) this.chatBox.focus(); },
        className: 'flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-900 hover:border-brand-500 hover:bg-slate-800 px-3 py-2.5 text-left text-sm transition',
      }, h('span', {className: 'text-lg'}, icon), label))));

    const thread = h('div', {
      ref: el => { this.chatScroll = el; },
      className: 'flex-1 min-h-0 overflow-y-auto space-y-4 pr-1',
      'aria-live': 'polite',
    }, messages.length ? messages.map((m, i) => this.renderMessage(m, i)) : empty);

    const pendingFiles = this.state.pendingFiles;
    const composer = h('div', {
      className: 'mt-3 rounded-2xl border border-slate-700 bg-slate-950 focus-within:border-brand-500 transition',
      onDragOver: e => { if ([...(e.dataTransfer?.items || [])].some(it => it.kind === 'file')) e.preventDefault(); },
      onDrop: e => { const f = [...(e.dataTransfer?.files || [])]; if (f.length) { e.preventDefault(); this.attachFiles(f); } },
    },
      pendingFiles.length || this.state.uploading ? h('div', {className: 'flex flex-wrap items-center gap-2 px-3 pt-3'},
        h(DomNode, {className: 'chat-file-chips', depKey: pendingFiles.map(f => f.id).join(','), make: () => {
          const frag = document.createDocumentFragment();
          pendingFiles.forEach(f => frag.appendChild(fileChip(f, this.state.token, {onRemove: () => this.removePending(f.id)})));
          return frag;
        }}),
        this.state.uploading ? h('span', {className: 'text-xs text-slate-400'}, 'Uploading…') : null) : null,
      h('input', {type: 'file', multiple: true, accept: ACCEPT, hidden: true, ref: el => { this.fileInput = el; },
        onChange: e => { this.attachFiles(e.target.files); e.target.value = ''; }}),
      h('textarea', {
        onPaste: e => {
          const f = [...(e.clipboardData?.items || [])].filter(it => it.kind === 'file').map(it => it.getAsFile()).filter(Boolean);
          if (f.length) { e.preventDefault(); this.attachFiles(f); }
        },
        ref: el => { this.chatBox = el; },
        rows: 2,
        value: chatInput,
        disabled: voiceRecording,
        onChange: e => this.setState({chatInput: e.target.value}),
        onKeyDown: e => {
          if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.sendChat(); }
          else if (e.key === 'Escape' && streaming) { e.preventDefault(); this.cancelChat(); }
        },
        placeholder: voiceRecording ? 'Listening… speak now' : 'Message your assistant  (Enter to send, Shift+Enter for a new line)',
        className: 'block w-full resize-none bg-transparent px-4 pt-3 pb-1 outline-none placeholder:text-slate-500',
      }),
      h('div', {className: 'flex items-center gap-2 px-2 pb-2'},
        h('button', {
          onClick: () => this.voiceAsk(),
          disabled: voiceRecording || streaming,
          title: 'Speak your request',
          'aria-label': 'Speak your request',
          className: cx('h-9 w-9 rounded-full border flex items-center justify-center transition disabled:opacity-50',
            voiceRecording ? 'border-rose-500 bg-rose-600 text-white animate-pulse' : 'border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-200'),
        }, '🎙'),
        h('button', {
          onClick: () => this.fileInput && this.fileInput.click(),
          disabled: streaming,
          title: 'Attach files (images, video, audio, PDF, CSV/XLSX, documents)',
          'aria-label': 'Attach files',
          className: 'h-9 w-9 rounded-full border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-200 flex items-center justify-center transition disabled:opacity-50',
        }, '📎'),
        voiceRecording ? h(MicSpectrum, {api: (path) => this.api(path)}) : null,
        h('button', {
          onClick: () => this.toggleSpeakReplies(),
          title: speakReplies ? 'Spoken replies on' : 'Spoken replies off',
          'aria-pressed': !!speakReplies,
          className: cx('h-9 px-3 rounded-full border text-xs transition', speakReplies ? 'border-brand-500 bg-brand-600/30 text-brand-200' : 'border-slate-700 bg-slate-900 text-slate-400 hover:bg-slate-800'),
        }, speakReplies ? '🔊 Speak replies' : '🔈 Speak replies'),
        h('div', {className: 'flex-1'}),
        streaming
          ? h('button', {onClick: () => this.cancelChat(), title: 'Stop (Esc)', className: 'h-9 px-4 rounded-full border border-rose-700 bg-rose-950 text-rose-200 hover:bg-rose-900 transition'}, '■ Stop')
          : h('button', {onClick: () => this.sendChat(), disabled: (!chatInput.trim() && !pendingFiles.length) || !!this.state.uploading, className: 'h-9 px-4 rounded-full border border-brand-500 bg-brand-600 hover:bg-brand-500 disabled:opacity-40 transition font-medium'}, 'Send ➤')));

    const chatPanel = h('div', {className: 'flex flex-col h-[calc(100vh-11rem)] min-h-[26rem]'},
      h('div', {className: 'flex items-center justify-between mb-3'},
        h('div', {className: 'flex items-center gap-2'},
          h('select', {
            value: this.state.sessionId || '', onChange: e => this.switchConversation(e.target.value),
            'aria-label': 'Conversation',
            className: 'max-w-xs truncate rounded-lg border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-300'},
            (this.state.conversations.some(c => c.id === this.state.sessionId) ? [] : [h('option', {key: 'cur', value: this.state.sessionId || ''}, 'Current conversation')])
              .concat(this.state.conversations.map(c => h('option', {key: c.id, value: c.id}, `${c.title || 'Untitled'} (${c.message_count || 0})`)))),
          this.state.chatTools.some(t => t.status === 'started') ? h('span', {className: 'inline-flex items-center gap-1.5 text-xs text-sky-400 font-mono px-2 py-0.5 bg-sky-950/70 border border-sky-800 rounded-full'},
            h('span', {className: 'h-1.5 w-1.5 rounded-full bg-sky-400 animate-pulse'}), 'tool executing...') : null),
        h('button', {onClick: () => this.newChat(), className: 'px-3 py-1.5 rounded-xl border border-slate-700 bg-slate-800 hover:bg-slate-700 text-xs'}, '+ New chat')),
      thread, composer);

    const pending = this.state.approvals || [];
    const activity = this.state.chatTools.length
      ? this.state.chatTools.slice(0, 20).map((x, i) => h('div', {key: i, className: 'py-2 border-b border-slate-800 space-y-1'},
          h('div', {className: 'flex items-center gap-2 text-xs'},
            h('span', {className: cx('h-2 w-2 rounded-full shrink-0', x.status === 'started' ? 'bg-sky-400 animate-pulse' : x.status === 'ok' ? 'bg-emerald-400' : x.status === 'approval' ? 'bg-amber-400' : 'bg-rose-400')}),
            h('span', {className: 'font-mono font-semibold truncate text-slate-200'}, x.tool),
            h('span', {className: cx('ml-auto shrink-0 font-medium', x.status === 'started' ? 'text-sky-400' : x.status === 'ok' ? 'text-emerald-400' : x.status === 'failed' ? 'text-rose-400' : 'text-amber-400')}, x.status === 'started' ? 'running' : x.status)),
          x.error ? h('div', {className: 'text-xs text-rose-300 bg-rose-950/60 border border-rose-900/60 rounded px-2 py-1 font-mono break-all'}, x.error) : null))
      : h('div', {className: 'text-slate-500 text-sm'}, 'Tool calls will appear here as they run.');

    const history = this.state.conversations.length
      ? h('div', {className: 'space-y-1 max-h-72 overflow-y-auto pr-1'}, this.state.conversations.slice(0, 30).map(c => h('button', {
          key: c.id, onClick: () => this.switchConversation(c.id),
          className: cx('w-full text-left rounded-lg px-2.5 py-2 text-xs border transition',
            c.id === this.state.sessionId ? 'border-brand-500 bg-brand-600/15' : 'border-transparent hover:bg-slate-800')},
          h('div', {className: 'font-medium text-slate-200 truncate'}, c.title || 'Untitled'),
          h('div', {className: 'text-slate-500 truncate'},
            `${c.message_count || 0} messages · ${String(c.updated_at || '').slice(0, 16).replace('T', ' ')}`))))
      : h('div', {className: 'text-slate-500 text-sm'}, 'No conversations yet.');

    const side = h('div', {className: 'space-y-3'},
      pending.length ? this.card(`Waiting for you (${pending.length})`, h(ApprovalList, {rows: pending.slice(0, 3), decide: (id, v) => this.decideApproval(id, v)})) : null,
      this.card('Conversations', history),
      this.card('Live tool activity', h('div', null, activity)),
      this.renderGoals(),
      this.card('What I can do', h('ul', {className: 'text-sm text-slate-400 space-y-1.5'},
        h('li', null, '🔎 Web search, article reading, image search & download'),
        h('li', null, '🎬 Video/audio download from YouTube and 1000+ sites'),
        h('li', null, '🖥 Screen reading (vision model or on-device OCR)'),
        h('li', null, '📜 Log analysis & live monitoring, project audits'),
        h('li', null, '🗂 Files, shell, git, calendar, reminders, memory'))));

    // The side panel only sits beside the chat on wide screens; narrower, it goes below so the chat keeps its width.
    return h('div', {className: 'grid xl:grid-cols-12 gap-3'},
      this.card(null, chatPanel, 'xl:col-span-8 min-w-0'),
      h('div', {className: 'xl:col-span-4 min-w-0'}, side));
  }
  renderApprovals(){return this.card('Pending approvals',h(ApprovalList,{rows:this.state.approvals,decide:(id,v)=>this.decideApproval(id,v)}));}
  renderOrganize(){return h('div',{className:'grid md:grid-cols-12 gap-3'},this.card('Todos',h('div',{className:'space-y-3'},h('div',{className:'grid grid-cols-1 sm:grid-cols-2 gap-2'},h('input',{value:this.state.todoTitle,onChange:e=>this.setState({todoTitle:e.target.value}),placeholder:'Add a todo',className:'rounded-xl border border-slate-700 bg-slate-950 px-3 py-2'}),h('input',{type:'datetime-local',value:this.state.todoDue,onChange:e=>this.setState({todoDue:e.target.value}),className:'rounded-xl border border-slate-700 bg-slate-950 px-3 py-2'})),h('button',{onClick:()=>this.addTodo(),className:'px-3 py-2 rounded-xl border border-brand-500 bg-brand-600'},'Add'),h(ItemList,{rows:this.state.todos,kind:'todo',onAction:id=>this.completeTodo(id)})),'md:col-span-6'),this.card('Calendar',h('div',{className:'space-y-3'},h('div',{className:'grid grid-cols-1 sm:grid-cols-2 gap-2'},h('input',{value:this.state.calTitle,onChange:e=>this.setState({calTitle:e.target.value}),placeholder:'Event title',className:'rounded-xl border border-slate-700 bg-slate-950 px-3 py-2'}),h('input',{type:'datetime-local',value:this.state.calStart,onChange:e=>this.setState({calStart:e.target.value}),className:'rounded-xl border border-slate-700 bg-slate-950 px-3 py-2'})),h('button',{onClick:()=>this.addCalendar(),className:'px-3 py-2 rounded-xl border border-brand-500 bg-brand-600'},'Add'),h(ItemList,{rows:this.state.calendar,kind:'calendar',onAction:id=>this.deleteCalendar(id)})),'md:col-span-6'));}
  renderSecurity(){const sec=this.state.security;return h('div',{className:'grid md:grid-cols-12 gap-3'},this.card('Guardian summary',h('pre',{className:'font-mono text-xs overflow-x-auto whitespace-pre-wrap'},JSON.stringify(sec.summary,null,2)),'md:col-span-4'),this.card('Sensor platform',h('pre',{className:'font-mono text-xs overflow-x-auto whitespace-pre-wrap'},JSON.stringify(sec.sensors,null,2)),'md:col-span-4'),this.card('Open findings',h('div',{className:'space-y-2'},sec.findings.length?sec.findings.map((x,i)=>h('div',{key:i,className:'rounded-xl border border-slate-800 p-3'},h('strong',null,`${x.severity||''} · ${x.kind||x.title||'Finding'}`),h('div',{className:'text-sm text-slate-400'},x.summary||x.details||JSON.stringify(x)))):h('div',{className:'text-slate-500'},'No open findings.')),'md:col-span-4'));}

    async loadCareer() {
      try {
        const p = await this.api("/api/v1/career/profile");
        const a = await this.api("/api/v1/career/applications");
        this.setState({careerProfile: p.profile, careerApplications: a.applications || []});
      } catch (_) {}
    }

    async analyzeCareerJob(apply = false) {
      const url = this.state.careerJobUrl.trim();
      if (!url) return;
      this.setState({careerBusy: true});
      try {
        if (apply) {
          const res = await this.api("/api/v1/career/jobs/apply", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({url}),
          });
          this.notify("Application pre-filled & staged! Awaiting review.");
        } else {
          const res = await this.api("/api/v1/career/jobs/analyze", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({url}),
          });
          this.notify(`Analyzed ${res.company || "Job"}! ${res.recruiter_emails?.length || 0} emails found.`);
        }
        await this.loadCareer();
      } catch (err) {
        this.notify(err.message, true);
      } finally {
        this.setState({careerBusy: false});
      }
    }

    async generateCareerOutreach(appId) {
      try {
        const res = await this.api(`/api/v1/career/applications/${encodeURIComponent(appId)}/outreach`, {method: "POST"});
        if (res.outreach_email) {
          this.setState({careerOutreachDraft: res.outreach_email});
          this.notify("Cold outreach email draft ready!");
        }
      } catch (err) {
        this.notify(err.message, true);
      }
    }

    renderCareer() {
      const p = this.state.careerProfile || {};
      const screener = p.screener || {};
      const apps = this.state.careerApplications || [];
      const draft = this.state.careerOutreachDraft;

      return h("div", {className: "space-y-4"},
        h("div", {className: "grid md:grid-cols-12 gap-3"},
          this.card("Candidate Profile & Resume", h("div", {className: "space-y-2 text-sm"},
            h("div", {className: "flex justify-between border-b border-slate-800 pb-2"},
              h("span", {className: "text-slate-400"}, "Full Name:"),
              h("strong", null, p.full_name || "Not configured")
            ),
            h("div", {className: "flex justify-between border-b border-slate-800 pb-2"},
              h("span", {className: "text-slate-400"}, "Email:"),
              h("span", null, p.email || "Not set")
            ),
            h("div", {className: "flex justify-between border-b border-slate-800 pb-2"},
              h("span", {className: "text-slate-400"}, "Master Resume:"),
              h("span", {className: p.resume_file_path ? "text-emerald-400" : "text-slate-500"}, p.resume_file_path ? "Attached & Parsed" : "None")
            ),
            h("div", {className: "flex justify-between border-b border-slate-800 pb-2"},
              h("span", {className: "text-slate-400"}, "Work Authorization:"),
              h("span", null, screener.legally_authorized ? "Authorized" : "No")
            ),
            h("div", {className: "pt-1"},
              h("span", {className: "text-slate-400 block mb-1"}, "Skills:"),
              h("div", {className: "flex flex-wrap gap-1"},
                (p.skills && p.skills.length ? p.skills : ["No skills listed"]).map((s, idx) =>
                  h("span", {key: idx, className: "px-2 py-0.5 rounded-full text-xs bg-slate-800 text-slate-300"}, s)
                )
              )
            )
          ), "md:col-span-5"),

          this.card("Job Opportunity Actions", h("div", {className: "space-y-3"},
            h("p", {className: "text-xs text-slate-400"}, "Paste any job posting URL (Greenhouse, Lever, Ashby, LinkedIn, Indeed, etc.) to analyze requirements, extract recruiter emails, and pre-fill applications."),
            h("input", {
              value: this.state.careerJobUrl,
              onChange: (e) => this.setState({careerJobUrl: e.target.value}),
              placeholder: "https://boards.greenhouse.io/... or https://jobs.lever.co/...",
              className: "w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100",
            }),
            h("div", {className: "flex gap-2"},
              h("button", {
                disabled: this.state.careerBusy || !this.state.careerJobUrl.trim(),
                onClick: () => this.analyzeCareerJob(false),
                className: "px-3 py-2 rounded-xl border border-slate-600 bg-slate-800 text-sm hover:bg-slate-700 disabled:opacity-50"
              }, this.state.careerBusy ? "Processing..." : "Analyze & Harvest Emails"),
              h("button", {
                disabled: this.state.careerBusy || !this.state.careerJobUrl.trim(),
                onClick: () => this.analyzeCareerJob(true),
                className: "px-3 py-2 rounded-xl border border-brand-500 bg-brand-600 text-sm hover:bg-brand-500 disabled:opacity-50"
              }, "Pre-fill Application")
            )
          ), "md:col-span-7")
        ),

        draft ? this.card("Generated Cold Outreach Email Draft", h("div", {className: "space-y-2 text-sm font-mono bg-slate-950 p-3 rounded-xl border border-slate-800"},
          h("div", null, h("strong", {className: "text-brand-400"}, "To: "), draft.recipient),
          h("div", null, h("strong", {className: "text-brand-400"}, "Subject: "), draft.subject),
          h("div", {className: "border-t border-slate-800 pt-2 whitespace-pre-wrap text-slate-300"}, draft.body),
          h("button", {
            onClick: () => this.setState({careerOutreachDraft: null}),
            className: "mt-2 text-xs px-2 py-1 bg-slate-800 rounded hover:bg-slate-700"
          }, "Close Draft")
        )) : null,

        this.card("Applications Pipeline", h("div", {className: "overflow-x-auto"},
          apps.length === 0 ? h("div", {className: "text-sm text-slate-500 py-3"}, "No applications tracked yet.") :
          h("table", {className: "w-full text-left text-sm border-collapse"},
            h("thead", null,
              h("tr", {className: "border-b border-slate-800 text-slate-400 text-xs"},
                h("th", {className: "py-2 px-3"}, "Company"),
                h("th", {className: "py-2 px-3"}, "Role"),
                h("th", {className: "py-2 px-3"}, "Platform"),
                h("th", {className: "py-2 px-3"}, "Status"),
                h("th", {className: "py-2 px-3"}, "Recruiter Emails"),
                h("th", {className: "py-2 px-3"}, "Actions")
              )
            ),
            h("tbody", null,
              apps.map((a) =>
                h("tr", {key: a.id, className: "border-b border-slate-800/50 hover:bg-slate-900/40"},
                  h("td", {className: "py-2.5 px-3 font-semibold text-slate-200"}, a.company),
                  h("td", {className: "py-2.5 px-3 text-cyan-300"}, a.title),
                  h("td", {className: "py-2.5 px-3 text-yellow-400 text-xs uppercase"}, a.platform),
                  h("td", {className: "py-2.5 px-3"},
                    h("span", {className: "px-2 py-0.5 rounded-full text-xs font-medium " + (
                      a.status === "applied" ? "bg-emerald-950 text-emerald-300 border border-emerald-800" :
                      a.status === "ready_for_review" ? "bg-amber-950 text-amber-300 border border-amber-800" :
                      "bg-slate-800 text-slate-300"
                    )}, a.status)
                  ),
                  h("td", {className: "py-2.5 px-3 text-xs text-slate-300"},
                    (a.recruiter_emails && a.recruiter_emails.length) ? a.recruiter_emails.join(", ") : h("span", {className: "text-slate-600"}, "None found")
                  ),
                  h("td", {className: "py-2.5 px-3"},
                    h("button", {
                      onClick: () => this.generateCareerOutreach(a.id),
                      className: "px-2.5 py-1 text-xs rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-200"
                    }, "Draft Outreach")
                  )
                )
              )
            )
          )
        ))
      );
    }

  renderActivity(){return this.card('Activity timeline',h(ActivityList,{rows:this.state.activity}));}
}

// Renders a page from inside the error boundary, so errors thrown while building it are caught too.
function PageBody({render}) { return render(); }

class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = {error: null}; }
  static getDerivedStateFromError(error) { return {error}; }
  componentDidCatch(error, info) { console.error(`Page "${this.props.name}" failed:`, error, info && info.componentStack); }
  render() {
    if (!this.state.error) return this.props.children;
    return h('div', {role: 'alert', className: 'rounded-2xl border border-rose-800 bg-rose-950/60 p-5 space-y-3'},
      h('div', {className: 'font-semibold text-rose-100'}, `The ${this.props.name} page hit an error.`),
      h('pre', {className: 'font-mono text-xs text-rose-200 whitespace-pre-wrap'}, String(this.state.error && (this.state.error.stack || this.state.error.message) || this.state.error).slice(0, 1500)),
      h('button', {onClick: () => this.setState({error: null}), className: 'px-3 py-2 rounded-xl border border-rose-700 bg-rose-900 hover:bg-rose-800 text-sm'}, 'Try again'));
  }
}

class ResourceChart extends React.Component {
  constructor(props) {
    super(props);
    this.plot = React.createRef();
    this.plotly = null;
    this.mounted = false;
    this.state = {chartError: ''};
  }
  componentDidMount() { this.mounted = true; this.renderChart(); }
  componentDidUpdate(prevProps) { if (prevProps.history !== this.props.history) this.renderChart(); }
  componentWillUnmount() { this.mounted = false; this.destroyChart(); }
  destroyChart() {
    if (!this.plot.current || !this.plotly) return;
    try { this.plotly.purge(this.plot.current); } catch (_) {}
    this.plotly = null;
  }
  async renderChart() {
    const history = Array.isArray(this.props.history) ? this.props.history : [];
    if (!history.length || !this.plot.current) return;
    try {
      const Plotly = await loadPlotly();
      if (!this.mounted || !this.plot.current) return;
      const labels = history.map((_, i) => i + 1);
      const series = resourceSeries(history);
      const trace = (name, y, color) => ({
        name, x: labels, y, type: 'scatter', mode: 'lines', connectgaps: true,
        line: {color, width: 2, shape: 'spline', smoothing: .45},
        hovertemplate: `${name} %{y:.0f}%<extra></extra>`,
      });
      const traces = [
        trace('CPU', series.cpu, '#8ba8ff'),
        trace('RAM', series.ram, '#34d399'),
      ];
      if (series.hasVram) traces.push(trace('VRAM', series.vram, '#f59e0b'));
      this.plotly = Plotly;
      await Plotly.react(this.plot.current, traces, {
        autosize: true,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        margin: {l: 38, r: 10, t: 28, b: 14},
        showlegend: true,
        legend: {orientation: 'h', x: 0, y: 1.15, font: {color: '#94a3b8', size: 10}},
        xaxis: {visible: false, fixedrange: true},
        yaxis: {
          range: [0, 100], fixedrange: true, ticksuffix: '%', tickfont: {color: '#64748b', size: 10},
          gridcolor: 'rgba(51,65,85,.35)', zeroline: false,
        },
        hovermode: 'x unified',
      }, {responsive: true, displayModeBar: false, scrollZoom: false});
      if (this.state.chartError) this.setState({chartError: ''});
    } catch (error) {
      this.destroyChart();
      if (this.mounted) this.setState({chartError: error instanceof Error ? error.message : String(error)});
    }
  }
  render() {
    const history = Array.isArray(this.props.history) ? this.props.history : [];
    if (!history.length) return h('div',{className:'h-36 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-center text-slate-500'},'Waiting for samples…');
    const latest = history[history.length - 1] || {};
    const label = resourceSampleLabel(latest);
    const hasVram = resourceSeries(history).hasVram;
    return h('div',{className:'relative h-36 rounded-xl bg-slate-950 border border-slate-800 overflow-hidden p-1'},
      h('div',{ref:this.plot,className:'h-full w-full','aria-label':hasVram?'CPU, RAM and VRAM resource history chart':'CPU and RAM resource history chart',role:'img'}),
      h('div',{className:'absolute top-2 right-3 text-xs text-slate-400 pointer-events-none'},label),
      this.state.chartError ? h('div',{className:'absolute inset-x-2 bottom-2 rounded-lg bg-slate-950/90 border border-slate-800 text-xs text-slate-500 px-3 py-2 text-center'},`Chart unavailable. ${label}`) : null
    );
  }
}

function UsageTable({usage}) {
  const rows = usage.models || usage.by_model || [];
  const header = h('tr', null, ['Model', 'Calls', 'Prompt', 'Completion', 'Latency'].map((label) =>
    h('th', {key: label, className: 'py-2 px-2 border-b border-slate-800 text-slate-500'}, label),
  ));
  const body = rows.length
    ? rows.map((row, i) => h(
        'tr',
        {key: `${row.model || 'model'}-${i}`},
        h('td', {className: 'py-2 px-2 border-b border-slate-800'}, row.model || 'unknown'),
        h('td', {className: 'py-2 px-2 border-b border-slate-800'}, row.calls || 0),
        h('td', {className: 'py-2 px-2 border-b border-slate-800'}, row.prompt_tokens || 0),
        h('td', {className: 'py-2 px-2 border-b border-slate-800'}, row.completion_tokens || 0),
        h('td', {className: 'py-2 px-2 border-b border-slate-800'}, `${Math.round(row.avg_latency_ms || 0)} ms`),
      ))
    : [h('tr', {key: 'empty'}, h('td', {colSpan: 5, className: 'py-4 text-slate-500'}, 'No usage data yet.'))];
  return h('div', {className: 'overflow-x-auto'}, h('table', {className: 'w-full border-collapse text-left text-sm'}, h('thead', null, header), h('tbody', null, body)));
}

function ModelTable({models, onDelete}) {
  const header = h('tr', null, ['Model', 'Disk', 'VRAM', 'State', ''].map((label) =>
    h('th', {key: label || 'actions', className: 'py-2 px-2 border-b border-slate-800'}, label),
  ));
  const body = models.length
    ? models.map((model, i) => h(
        'tr',
        {key: model.name || i},
        h('td', {className: 'py-2 px-2 border-b border-slate-800 font-mono'}, model.name),
        h('td', {className: 'py-2 px-2 border-b border-slate-800'}, fmtBytes(model.size || model.disk_bytes)),
        h('td', {className: 'py-2 px-2 border-b border-slate-800'}, `${fmtBytes(model.vram_bytes)}${model.vram_kind === 'estimated_from_disk' ? ' estimated requirement' : ''}`),
        h('td', {className: 'py-2 px-2 border-b border-slate-800'}, model.loaded ? 'loaded' : 'unloaded'),
        h('td', {className: 'py-2 px-2 border-b border-slate-800 text-right'},
          h('button', {onClick: () => onDelete(model.name), className: 'px-3 py-2 rounded-xl border border-rose-800 bg-rose-950 text-rose-300'}, 'Delete'),
        ),
      ))
    : [h('tr', {key: 'empty'}, h('td', {colSpan: 5, className: 'py-4 text-slate-500'}, 'No local models.'))];
  return h('div', {className: 'overflow-x-auto'}, h('table', {className: 'w-full border-collapse text-left text-sm'}, h('thead', null, header), h('tbody', null, body)));
}

function ApprovalList({rows, decide}) {
  if (!rows.length) return h('div', {className: 'text-slate-500'}, 'No pending approvals.');
  return h('div', {className: 'space-y-2'}, rows.map((approval, i) => h(
    'div',
    {key: approval.id || i, className: 'rounded-xl border border-slate-800 bg-slate-950 p-3'},
    h('strong', null, approval.kind || 'Approval'),
    h('div', {className: 'text-sm text-slate-400 mt-1'}, approval.reason || approval.action || ''),
    h('div', {className: 'flex justify-end flex-wrap gap-2 mt-3'},
      h('button', {onClick: () => decide(approval.id, false), className: 'px-3 py-2 rounded-xl border border-rose-800 bg-rose-950 text-rose-300'}, 'Deny'),
      h('button', {onClick: () => decide(approval.id, true), className: 'px-3 py-2 rounded-xl border border-emerald-800 bg-emerald-950 text-emerald-300'}, 'Approve'),
    ),
  )));
}

function ActivityList({rows}) {
  if (!rows.length) return h('div', {className: 'text-slate-500'}, 'No recent activity.');
  return h('div', {className: 'max-h-[26rem] overflow-y-auto space-y-2'}, rows.slice().reverse().map((event, i) => h(
    'div',
    {key: event.id || i, className: 'border-l-2 border-slate-700 pl-3 py-2 text-xs text-slate-300'},
    h('strong', null, event.type || 'event'),
    ' ',
    h('span', {className: 'text-slate-500'}, event.created_at || ''),
    h('div', {className: 'text-slate-400'}, JSON.stringify(event.data || {})),
  )));
}

function ItemList({rows, kind, onAction}) {
  if (!rows.length) return h('div', {className: 'text-slate-500'}, kind === 'todo' ? 'No todos.' : 'No events.');
  return h('div', {className: 'space-y-2'}, rows.map((item, i) => h(
    'div',
    {key: item.id || i, className: 'rounded-xl border border-slate-800 p-3'},
    h('strong', null, item.title),
    h('div', {className: 'text-sm text-slate-400'}, kind === 'todo' ? (item.due_at || 'No due date') : `${item.start_at || ''} ${item.location || ''}`),
    kind === 'todo' && item.done
      ? h('div', {className: 'text-emerald-300 text-sm mt-1'}, 'Completed')
      : h(
          'button',
          {
            onClick: () => onAction(item.id),
            className: cx(
              'mt-3 px-3 py-2 rounded-xl border',
              kind === 'todo' ? 'border-emerald-800 bg-emerald-950 text-emerald-300' : 'border-rose-800 bg-rose-950 text-rose-300',
            ),
          },
          kind === 'todo' ? 'Complete' : 'Cancel',
        ),
  )));
}

if (!React || !ReactDOM) throw new Error('React runtime is unavailable.');
// The classic dashboard mounts itself only on its own page; the new shell imports App for its system pages.
export { App as ClassicApp };
const classicRoot = document.getElementById('root');
if (classicRoot && classicRoot.dataset.app !== 'shell') ReactDOM.render(h(App), classicRoot);
