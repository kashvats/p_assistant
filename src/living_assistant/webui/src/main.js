/* Living Assistant dashboard — React SPA. No model-controlled HTML is injected. */
import { loadPlotly } from './chart_loader.js';
import { makeResourceSample, resourceSampleLabel, resourceSeries } from './resource_chart_data.js';
const React = globalThis.React;
const ReactDOM = globalThis.ReactDOM;
const Prism = globalThis.Prism;
const h = React.createElement;

const NAV = [
  ['overview', '🏠 Overview'], ['models', 'Models'], ['chat', '💬 Chat'], ['skills', '⚡ Skills'], ['agents', '🧠 Agents'], ['approvals', '✅ Approvals'],
  ['organize', '📅 Calendar & Todos'], ['security', '🔒 Security'], ['activity', '📊 Activity'], ['tools', '🔧 Tools'],
];

function cx(...parts) { return parts.filter(Boolean).join(' '); }
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

function tokenizeInline(text, keyPrefix) {
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;
  const out = []; let cursor = 0; let i = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > cursor) out.push(text.slice(cursor, match.index));
    const token = match[0]; const key = `${keyPrefix}-${i++}`;
    if (token.startsWith('**')) out.push(h('strong', {key}, token.slice(2, -2)));
    else if (token.startsWith('`')) out.push(h('code', {key}, token.slice(1, -1)));
    else {
      const parsed = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      const label = parsed ? parsed[1] : token; const href = parsed ? parsed[2].trim() : '';
      let safe = false;
      try { safe = ['http:', 'https:', 'mailto:'].includes(new URL(href, location.href).protocol); } catch (_) {}
      out.push(safe ? h('a', {key, href, target: '_blank', rel: 'noopener noreferrer'}, label) : label);
    }
    cursor = match.index + token.length;
  }
  if (cursor < text.length) out.push(text.slice(cursor));
  return out;
}

function renderPrismToken(token, key) {
  if (typeof token === 'string') return token;
  const content = Array.isArray(token.content)
    ? token.content.map((part, idx) => renderPrismToken(part, `${key}-${idx}`))
    : renderPrismToken(token.content, `${key}-c`);
  const aliases = Array.isArray(token.alias) ? token.alias : token.alias ? [token.alias] : [];
  return h('span', {key, className: ['token', token.type, ...aliases].join(' ')}, content);
}
function CodeBlock({language, source}) {
  const lang = (language || '').toLowerCase();
  const grammar = Prism && Prism.languages ? (Prism.languages[lang] || Prism.languages.plain) : null;
  const tokens = grammar && Prism.tokenize ? Prism.tokenize(source, grammar) : [source];
  return h('pre', {className: 'font-mono text-xs overflow-x-auto rounded-xl bg-slate-950 p-3 border border-slate-800'},
    h('code', {className: lang ? `language-${lang}` : ''}, tokens.map((t, i) => renderPrismToken(t, `tok-${i}`))));
}
function Markdown({text}) {
  const source = safeText(text).replace(/\r\n?/g, '\n');
  const lines = source.split('\n'); const nodes = []; let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const fence = line.match(/^```\s*([A-Za-z0-9_+-]*)\s*$/);
    if (fence) {
      const language = fence[1] || ''; const code = []; i += 1;
      while (i < lines.length && !/^```\s*$/.test(lines[i])) code.push(lines[i++]);
      if (i < lines.length) i += 1;
      nodes.push(h(CodeBlock, {key: `code-${i}`, language, source: code.join('\n')})); continue;
    }
    if (!line.trim()) { i += 1; continue; }
    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) { const tag = `h${heading[1].length}`; nodes.push(h(tag, {key: `h-${i}`}, tokenizeInline(heading[2], `h-${i}`))); i += 1; continue; }
    const bullet = line.match(/^\s*[-*]\s+(.+)$/);
    if (bullet) {
      const items = [];
      while (i < lines.length) { const m = lines[i].match(/^\s*[-*]\s+(.+)$/); if (!m) break; items.push(h('li', {key: `li-${i}`}, tokenizeInline(m[1], `li-${i}`))); i += 1; }
      nodes.push(h('ul', {key: `ul-${i}`}, items)); continue;
    }
    const numbered = line.match(/^\s*\d+\.\s+(.+)$/);
    if (numbered) {
      const items = [];
      while (i < lines.length) { const m = lines[i].match(/^\s*\d+\.\s+(.+)$/); if (!m) break; items.push(h('li', {key: `oli-${i}`}, tokenizeInline(m[1], `oli-${i}`))); i += 1; }
      nodes.push(h('ol', {key: `ol-${i}`}, items)); continue;
    }
    const quote = line.match(/^>\s?(.*)$/);
    if (quote) { nodes.push(h('blockquote', {key: `q-${i}`}, tokenizeInline(quote[1], `q-${i}`))); i += 1; continue; }
    const para = [line]; i += 1;
    while (i < lines.length && lines[i].trim() && !/^```/.test(lines[i]) && !/^(#{1,4})\s+/.test(lines[i]) && !/^\s*[-*]\s+/.test(lines[i]) && !/^\s*\d+\.\s+/.test(lines[i]) && !/^>\s?/.test(lines[i])) para.push(lines[i++]);
    nodes.push(h('p', {key: `p-${i}`}, tokenizeInline(para.join('\n'), `p-${i}`)));
  }
  return h('div', {className: 'markdown-body'}, nodes);
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

class FloatingAgent extends React.Component {
  constructor(props) {
    super(props);
    let pos = null;
    try { pos = JSON.parse(localStorage.getItem('assistant_agent_pos') || 'null'); } catch (_) {}
    this.state = {pos, dragging: false, hover: false};
    this.drag = null;
    this.el = null;
    this.onResize = () => this.setState(({pos: p}) => ({pos: p ? this.clamp(p.x, p.y) : p}));
    // React 16.0 has no synthetic pointer events, so native listeners drive dragging.
    this.down = (e) => this.onPointerDown(e);
    this.move = (e) => this.onPointerMove(e);
    this.up = (e) => this.onPointerUp(e);
  }
  componentDidMount() {
    window.addEventListener('resize', this.onResize);
    if (this.el) this.el.addEventListener('pointerdown', this.down);
  }
  componentWillUnmount() {
    window.removeEventListener('resize', this.onResize);
    if (this.el) this.el.removeEventListener('pointerdown', this.down);
    window.removeEventListener('pointermove', this.move);
    window.removeEventListener('pointerup', this.up);
  }
  clamp(x, y) {
    const size = 64, pad = 8;
    return {
      x: Math.min(Math.max(pad, x), window.innerWidth - size - pad),
      y: Math.min(Math.max(pad, y), window.innerHeight - size - pad),
    };
  }
  current() { return this.state.pos || {x: window.innerWidth - 96, y: window.innerHeight - 110}; }
  onPointerDown(e) {
    if (e.button !== 0) return;
    const p = this.current();
    this.drag = {sx: e.clientX, sy: e.clientY, ox: p.x, oy: p.y, moved: false};
    window.addEventListener('pointermove', this.move);
    window.addEventListener('pointerup', this.up);
  }
  onPointerMove(e) {
    if (!this.drag) return;
    const dx = e.clientX - this.drag.sx, dy = e.clientY - this.drag.sy;
    if (!this.drag.moved && Math.hypot(dx, dy) < 5) return;
    this.drag.moved = true;
    this.setState({dragging: true, pos: this.clamp(this.drag.ox + dx, this.drag.oy + dy)});
  }
  onPointerUp() {
    const drag = this.drag;
    this.drag = null;
    window.removeEventListener('pointermove', this.move);
    window.removeEventListener('pointerup', this.up);
    if (!drag) return;
    if (drag.moved) {
      this.setState({dragging: false});
      try { localStorage.setItem('assistant_agent_pos', JSON.stringify(this.current())); } catch (_) {}
    } else if (this.props.onActivate) {
      this.props.onActivate();
    }
  }
  onKeyDown(e) {
    if ((e.key === 'Enter' || e.key === ' ') && this.props.onActivate) { e.preventDefault(); this.props.onActivate(); }
  }
  render() {
    const {mood, label} = this.props;
    const p = this.current();
    const showBubble = label && (mood !== 'idle' || this.state.hover) && !this.state.dragging;
    return h('div', {
      className: cx('floating-agent', this.state.dragging && 'dragging', p.x < window.innerWidth / 2 && 'left'),
      ref: (el) => { this.el = el; if (el) { el.style.left = `${p.x}px`; el.style.top = `${p.y}px`; } },
      role: 'button',
      tabIndex: 0,
      'aria-label': label || 'Assistant',
      onMouseEnter: () => this.setState({hover: true}),
      onMouseLeave: () => this.setState({hover: false}),
      onKeyDown: (e) => this.onKeyDown(e),
    },
      h(AgentFace, {size: 'md', mood, track: true, title: label}),
      showBubble ? h('div', {className: 'agent-bubble'}, label) : null);
  }
}

class App extends React.Component {
  constructor(props) {
    super(props);
    const sessionId = localStorage.getItem('assistant_session') || makeSessionId();
    localStorage.setItem('assistant_session', sessionId);
    this.state = {
      page: hashPage(), token: initialToken(), tokenInput: '',
      sessionId, status: null, desktop: null, usage: null, models: null, approvals: [], todos: [], calendar: [],
      security: {summary: null, findings: [], sensors: null}, activity: [], lastEvent: 0,
      messages: [], chatInput: '', streaming: false, chatTools: [], resourceHistory: [],
      todoTitle: '', todoDue: '', calTitle: '', calStart: '', modelPullName: '', modelBusy: false,
      skills: [], selectedSkill: null, skillDraftPrompt: '', skillSearch: '', skillBusy: false, skillTrace: null, skillDryRun: true, skillCollections: null,
      agents: [], selectedAgent: null, agentDraftPrompt: '', agentSearch: '', agentBusy: false, agentTrace: null, agentDryRun: true,
      toast: '', error: '',
      voiceRecording: false, attachedFile: null, speakReplies: readFlag('assistant_speak_replies'),
      toolsStatus: null, browserSessions: [],
      expandedTools: {},
      goals: [], goalText: '', goalCheck: '', goalCwd: '.', goalBusy: false,
    };
    this.pollers = []; this.activityController = null; this.approvalSeen = new Set(); this.chatController = null;
  }
  componentDidMount() {
    this.onHash = () => this.setState({page: hashPage()}); window.addEventListener('hashchange', this.onHash);
    this.refreshAll(); this.startActivityStream(); this.loadChatHistory();
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
  agentMood() {
    const {voiceRecording, streaming, messages, approvals} = this.state;
    const last = messages[messages.length - 1];
    if (voiceRecording) return ['listening', 'Listening…'];
    if (streaming) {
      const running = last && (last.steps || []).find(s => s.status === 'running');
      return running ? ['working', `Running ${running.tool}…`] : ['thinking', (last && last.phase) || 'Thinking…'];
    }
    if (approvals.length) return ['alert', `${approvals.length} approval${approvals.length === 1 ? '' : 's'} waiting`];
    if (last && last.error) return ['error', 'Something went wrong'];
    if (!this.state.status) return ['error', 'Assistant offline'];
    return ['idle', 'Click to talk · drag to move'];
  }
  activateAgent() {
    if (this.state.streaming) { this.navigate('chat'); return; }
    if (this.state.approvals.length && this.state.page !== 'chat') { this.navigate('approvals'); return; }
    this.navigate('chat');
    this.voiceAsk();
  }
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
  async loadModels() { try { this.setState({models: await this.api('/models/local')}); } catch (e) { this.notify(`Unable to load models: ${e.message}`, true); } }
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
  async loadChatHistory() {
    try {
      const res = await this.api(`/sessions/${encodeURIComponent(this.state.sessionId)}`);
      const rows = Array.isArray(res?.messages) ? res.messages : [];
      if (!this.state.messages.length && rows.length) {
        this.setState({messages: rows.filter(r => r.role === 'user' || r.role === 'assistant').map(r => ({role: r.role, text: safeText(r.content), steps: []}))});
      }
    } catch (_) {}
  }
  newChat() {
    if (this.state.streaming) this.cancelChat();
    const sessionId = makeSessionId();
    localStorage.setItem('assistant_session', sessionId);
    this.setState({sessionId, messages: [], chatTools: [], chatInput: ''});
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
    try { await this.api(`/goals/${encodeURIComponent(id)}/${action}`, {method: 'POST'}); await this.loadGoals(); }
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
      const canCancel = ['queued', 'running'].includes(g.status);
      return h('div', {key: g.id, className: 'rounded-xl border border-slate-800 bg-slate-950 p-3 space-y-1.5'},
        h('div', {className: 'flex items-start gap-2'},
          h('div', {className: 'text-sm flex-1 min-w-0 break-words'}, g.goal),
          h('span', {className: cx('shrink-0 text-xs px-2 py-0.5 rounded-full border', badge[g.status] || badge.paused, g.status === 'running' && 'animate-pulse')}, g.status)),
        h('div', {className: 'text-xs text-slate-500 flex flex-wrap gap-x-3'},
          h('span', null, `round ${g.rounds}/${g.max_rounds}`),
          g.check_command ? h('span', {className: 'font-mono truncate'}, g.check_command) : null,
          check ? h('span', {className: check.passed ? 'text-emerald-400' : 'text-rose-400'}, check.passed ? 'check passed' : 'check failing') : null),
        last ? h('div', {className: 'text-xs text-slate-400'}, `Latest: ${last.summary}`) : null,
        g.last_error && !['completed', 'running', 'queued'].includes(g.status) ? h('div', {className: 'text-xs text-amber-300 break-words'}, g.last_error) : null,
        (canResume || canCancel) ? h('div', {className: 'flex gap-2 pt-1'},
          canResume ? h('button', {onClick: () => this.goalAction(g.id, 'resume'), className: 'px-2.5 py-1 rounded-lg border border-brand-500 bg-brand-600 hover:bg-brand-500 text-xs'}, 'Resume') : null,
          canCancel ? h('button', {onClick: () => this.goalAction(g.id, 'cancel'), className: 'px-2.5 py-1 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-xs'}, 'Cancel') : null) : null);
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
  async refreshAll() { await Promise.allSettled([this.loadStatus(), this.loadUsage(), this.loadModels(), this.loadSkills(), this.loadAgents(), this.loadApprovals(), this.loadTodos(), this.loadCalendar(), this.loadSecurity(), this.loadActivity(), this.loadToolsStatus()]); }
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
  cancelChat() {
    if (this.chatController) {
      this.chatController.abort();
      this.chatController = null;
    }
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
      this.updateLastAssistant(m => ({...m, phase: event.status === 'generating' ? `Thinking (step ${event.step || 1})` : 'Starting'}));
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
          if (idx < 0) return {chatTools: [{tool: event.tool, status, at: Date.now()}, ...prev.chatTools].slice(0, 40)};
          const chatTools = prev.chatTools.slice();
          chatTools[idx] = {...chatTools[idx], status};
          return {chatTools};
        });
      }
    } else if (event.type === 'final') {
      run.finalText = event.text || run.stepText;
      const text = run.finalText;
      this.updateLastAssistant(m => ({...m, text, phase: null}));
    } else if (event.type === 'error') {
      throw new Error(event.error || 'Chat stream failed');
    }
  }
  async sendChat(textOverride, opts = {}) {
    const text = safeText(textOverride ?? this.state.chatInput).trim();
    if (!text || this.state.streaming) return;
    const user = {role: 'user', text, viaVoice: !!opts.viaVoice};
    const assistant = {role: 'assistant', text: '', steps: [], phase: 'Starting', retryText: text};
    this.setState(prev => ({chatInput: textOverride == null ? '' : prev.chatInput, streaming: true, messages: [...prev.messages, user, assistant]}));
    const controller = new AbortController();
    this.chatController = controller;
    const run = {stepText: '', finalText: ''};
    try {
      const response = await fetch('/chat/stream', {
        method: 'POST', signal: controller.signal,
        headers: this.authHeaders({'Content-Type': 'application/json', 'Accept': 'text/event-stream'}),
        body: JSON.stringify({message: text, session_id: this.state.sessionId}),
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
            h('button',{className:'px-3 py-2 rounded-xl border border-slate-700 bg-slate-800 hover:bg-slate-700',onClick:()=>this.useToken()},'Use token'))),
        content),
      h(FloatingAgent,{mood:this.agentMood()[0],label:this.agentMood()[1],onActivate:()=>this.activateAgent()}),
      this.state.toast ? h('div',{role:'status',className:cx('fixed left-1/2 -translate-x-1/2 bottom-4 z-50 max-w-md rounded-xl border px-4 py-3 shadow-xl text-sm',this.state.error?'border-rose-800 bg-rose-950 text-rose-100':'border-slate-700 bg-slate-900')},this.state.toast):null);
  }
  render() {
    const pages={overview:this.renderOverview(),models:this.renderModels(),chat:this.renderChat(),skills:this.renderSkills(),agents:this.renderAgents(),approvals:this.renderApprovals(),organize:this.renderOrganize(),security:this.renderSecurity(),activity:this.renderActivity()};
    return this.renderShell(pages[this.state.page]||pages.overview);
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

    return h('div', {className: 'grid md:grid-cols-12 gap-3'},
      h('div', {className: 'md:col-span-5'}, leftCol),
      h('div', {className: 'md:col-span-7'}, rightCol),
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
  renderModels(){ const data=this.state.models||{}; return this.card('Local model manager',h('div',{className:'space-y-3'},h('div',{className:'flex flex-wrap gap-2 text-sm text-slate-400'},h('span',{className:'rounded-full border border-slate-700 px-3 py-2'},`GPU ${data.gpu?.name||'not detected'}`),h('span',{className:'rounded-full border border-slate-700 px-3 py-2'},`Free VRAM ${data.gpu?.free_vram_gb??'--'} GB`),h('span',{className:'rounded-full border border-slate-700 px-3 py-2'},`Disk ${fmtBytes(data.total_disk_bytes)}`)),h('div',{className:'grid grid-cols-[minmax(0,1fr)_auto] gap-2'},h('input',{value:this.state.modelPullName,onChange:e=>this.setState({modelPullName:e.target.value}),onKeyDown:e=>{if(e.key==='Enter')this.pullModel();},placeholder:'e.g. qwen2.5:7b',className:'w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2'}),h('button',{disabled:this.state.modelBusy,onClick:()=>this.pullModel(),className:'px-3 py-2 rounded-xl border border-brand-500 bg-brand-600 hover:bg-brand-500 disabled:opacity-50'},this.state.modelBusy?'Pulling…':'Pull model')),h(ModelTable,{models:data.models||[],onDelete:m=>this.deleteModel(m)}))); }
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
      return h('div', {key: i, className: 'flex justify-end'},
        h('div', {className: 'max-w-[85%] rounded-2xl rounded-br-md bg-brand-600 px-4 py-2.5 text-white whitespace-pre-wrap break-words'},
          m.viaVoice ? h('span', {className: 'mr-2 text-xs opacity-75', title: 'Spoken'}, '🎙') : null, m.text));
    }
    const steps = m.steps || [];
    return h('div', {key: i, className: 'flex gap-3 items-start'},
      h(AgentFace, {size: 'sm', mood: m.error ? 'error' : m.phase ? 'thinking' : 'idle'}),
      h('div', {className: 'min-w-0 flex-1 max-w-[85%] space-y-2'},
        steps.length ? h('div', {className: 'space-y-1.5'}, steps.map((s, idx) => this.renderStep(s, idx, m.retryText))) : null,
        m.text ? h('div', {className: 'rounded-2xl rounded-tl-md border border-slate-700 bg-slate-800/80 px-4 py-3'}, h(Markdown, {text: m.text})) : null,
        m.phase ? h('div', {className: 'flex items-center gap-2 text-xs text-slate-400'},
          h('span', {className: 'typing-dots'}, h('i'), h('i'), h('i')), m.phase) : null,
        m.stopped ? h('div', {className: 'text-xs text-slate-500'}, 'Stopped.') : null,
        m.error ? h('div', {className: 'rounded-xl border border-rose-900 bg-rose-950/50 px-3 py-2 text-sm text-rose-200 flex flex-wrap items-center gap-2'},
          h('span', {className: 'break-words'}, m.error),
          m.retryText && !this.state.streaming ? h('button', {onClick: () => this.sendChat(m.retryText), className: 'px-2.5 py-1 rounded-lg border border-rose-700 hover:bg-rose-900 text-xs'}, 'Retry') : null) : null));
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

    const composer = h('div', {className: 'mt-3 rounded-2xl border border-slate-700 bg-slate-950 focus-within:border-brand-500 transition'},
      h('textarea', {
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
          : h('button', {onClick: () => this.sendChat(), disabled: !chatInput.trim(), className: 'h-9 px-4 rounded-full border border-brand-500 bg-brand-600 hover:bg-brand-500 disabled:opacity-40 transition font-medium'}, 'Send ➤')));

    const chatPanel = h('div', {className: 'flex flex-col h-[calc(100vh-11rem)] min-h-[26rem]'},
      h('div', {className: 'flex items-center justify-between mb-3'},
        h('div', {className: 'text-xs text-slate-500 font-mono'}, `session ${this.state.sessionId}`),
        h('button', {onClick: () => this.newChat(), className: 'px-3 py-1.5 rounded-xl border border-slate-700 bg-slate-800 hover:bg-slate-700 text-xs'}, '+ New chat')),
      thread, composer);

    const pending = this.state.approvals || [];
    const activity = this.state.chatTools.length
      ? this.state.chatTools.slice(0, 20).map((x, i) => h('div', {key: i, className: 'flex items-center gap-2 text-xs py-1.5 border-b border-slate-800'},
          h('span', {className: cx('h-2 w-2 rounded-full shrink-0', x.status === 'started' ? 'bg-sky-400 animate-pulse' : x.status === 'ok' ? 'bg-emerald-400' : x.status === 'approval' ? 'bg-amber-400' : 'bg-rose-400')}),
          h('span', {className: 'font-mono truncate'}, x.tool),
          h('span', {className: 'ml-auto text-slate-500 shrink-0'}, x.status === 'started' ? 'running' : x.status)))
      : h('div', {className: 'text-slate-500 text-sm'}, 'Tool calls will appear here as they run.');

    const side = h('div', {className: 'space-y-3'},
      pending.length ? this.card(`Waiting for you (${pending.length})`, h(ApprovalList, {rows: pending.slice(0, 3), decide: (id, v) => this.decideApproval(id, v)})) : null,
      this.card('Live tool activity', h('div', null, activity)),
      this.renderGoals(),
      this.card('What I can do', h('ul', {className: 'text-sm text-slate-400 space-y-1.5'},
        h('li', null, '🔎 Web search, article reading, image search & download'),
        h('li', null, '🎬 Video/audio download from YouTube and 1000+ sites'),
        h('li', null, '🖥 Screen reading (vision model or on-device OCR)'),
        h('li', null, '📜 Log analysis & live monitoring, project audits'),
        h('li', null, '🗂 Files, shell, git, calendar, reminders, memory'))));

    return h('div', {className: 'grid lg:grid-cols-12 gap-3'},
      this.card(null, chatPanel, 'lg:col-span-8'),
      h('div', {className: 'lg:col-span-4'}, side));
  }
  renderApprovals(){return this.card('Pending approvals',h(ApprovalList,{rows:this.state.approvals,decide:(id,v)=>this.decideApproval(id,v)}));}
  renderOrganize(){return h('div',{className:'grid md:grid-cols-12 gap-3'},this.card('Todos',h('div',{className:'space-y-3'},h('div',{className:'grid grid-cols-1 sm:grid-cols-2 gap-2'},h('input',{value:this.state.todoTitle,onChange:e=>this.setState({todoTitle:e.target.value}),placeholder:'Add a todo',className:'rounded-xl border border-slate-700 bg-slate-950 px-3 py-2'}),h('input',{type:'datetime-local',value:this.state.todoDue,onChange:e=>this.setState({todoDue:e.target.value}),className:'rounded-xl border border-slate-700 bg-slate-950 px-3 py-2'})),h('button',{onClick:()=>this.addTodo(),className:'px-3 py-2 rounded-xl border border-brand-500 bg-brand-600'},'Add'),h(ItemList,{rows:this.state.todos,kind:'todo',onAction:id=>this.completeTodo(id)})),'md:col-span-6'),this.card('Calendar',h('div',{className:'space-y-3'},h('div',{className:'grid grid-cols-1 sm:grid-cols-2 gap-2'},h('input',{value:this.state.calTitle,onChange:e=>this.setState({calTitle:e.target.value}),placeholder:'Event title',className:'rounded-xl border border-slate-700 bg-slate-950 px-3 py-2'}),h('input',{type:'datetime-local',value:this.state.calStart,onChange:e=>this.setState({calStart:e.target.value}),className:'rounded-xl border border-slate-700 bg-slate-950 px-3 py-2'})),h('button',{onClick:()=>this.addCalendar(),className:'px-3 py-2 rounded-xl border border-brand-500 bg-brand-600'},'Add'),h(ItemList,{rows:this.state.calendar,kind:'calendar',onAction:id=>this.deleteCalendar(id)})),'md:col-span-6'));}
  renderSecurity(){const sec=this.state.security;return h('div',{className:'grid md:grid-cols-12 gap-3'},this.card('Guardian summary',h('pre',{className:'font-mono text-xs overflow-x-auto whitespace-pre-wrap'},JSON.stringify(sec.summary,null,2)),'md:col-span-4'),this.card('Sensor platform',h('pre',{className:'font-mono text-xs overflow-x-auto whitespace-pre-wrap'},JSON.stringify(sec.sensors,null,2)),'md:col-span-4'),this.card('Open findings',h('div',{className:'space-y-2'},sec.findings.length?sec.findings.map((x,i)=>h('div',{key:i,className:'rounded-xl border border-slate-800 p-3'},h('strong',null,`${x.severity||''} · ${x.kind||x.title||'Finding'}`),h('div',{className:'text-sm text-slate-400'},x.summary||x.details||JSON.stringify(x)))):h('div',{className:'text-slate-500'},'No open findings.')),'md:col-span-4'));}
  renderActivity(){return this.card('Activity timeline',h(ActivityList,{rows:this.state.activity}));}
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
ReactDOM.render(h(App), document.getElementById('root'));
