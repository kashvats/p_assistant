/* Living Assistant dashboard — React SPA. No model-controlled HTML is injected. */
import { loadPlotly } from './chart_loader.js';
import { makeResourceSample, resourceSampleLabel, resourceSeries } from './resource_chart_data.js';
const React = globalThis.React;
const ReactDOM = globalThis.ReactDOM;
const Prism = globalThis.Prism;
const h = React.createElement;

const NAV = [
  ['overview', 'Overview'], ['models', 'Models'], ['chat', 'Chat'], ['approvals', 'Approvals'],
  ['organize', 'Calendar & Todos'], ['security', 'Security'], ['activity', 'Activity'],
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

class App extends React.Component {
  constructor(props) {
    super(props);
    const sessionId = localStorage.getItem('assistant_session') || makeSessionId();
    localStorage.setItem('assistant_session', sessionId);
    this.state = {
      page: hashPage(), token: sessionStorage.getItem('assistant_token') || '', tokenInput: sessionStorage.getItem('assistant_token') || '',
      sessionId, status: null, desktop: null, usage: null, models: null, approvals: [], todos: [], calendar: [],
      security: {summary: null, findings: [], sensors: null}, activity: [], lastEvent: 0,
      messages: [], chatInput: '', streaming: false, chatTools: [], resourceHistory: [],
      todoTitle: '', todoDue: '', calTitle: '', calStart: '', modelPullName: '', modelBusy: false,
      toast: '', error: '',
    };
    this.pollers = []; this.activityController = null; this.approvalSeen = new Set();
  }
  componentDidMount() {
    this.onHash = () => this.setState({page: hashPage()}); window.addEventListener('hashchange', this.onHash);
    this.refreshAll(); this.startActivityStream();
    this.pollers.push(setInterval(() => this.loadStatus(), 2500));
    this.pollers.push(setInterval(() => this.loadApprovals(), 5000));
    this.pollers.push(setInterval(() => this.loadUsage(), 10000));
  }
  componentWillUnmount() { window.removeEventListener('hashchange', this.onHash); this.pollers.forEach(clearInterval); if (this.activityController) this.activityController.abort(); }
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
  async refreshAll() { await Promise.allSettled([this.loadStatus(), this.loadUsage(), this.loadModels(), this.loadApprovals(), this.loadTodos(), this.loadCalendar(), this.loadSecurity(), this.loadActivity()]); }
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
    this.setState({token}, () => { this.refreshAll(); this.startActivityStream(); });
  }
  navigate(page) { location.hash = `/${page}`; }
  async decideApproval(id, approved) { try { await this.api(`/approvals/${encodeURIComponent(id)}`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({approved})}); await this.loadApprovals(); } catch(e){ this.notify(e.message, true); } }
  async addTodo() { const title=this.state.todoTitle.trim(); if(!title)return; try { await this.api('/todos',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,due_at:this.state.todoDue||null})}); this.setState({todoTitle:'',todoDue:''}); await this.loadTodos(); } catch(e){this.notify(e.message,true);} }
  async completeTodo(id) { try { await this.api(`/todos/${id}/complete`,{method:'POST'}); await this.loadTodos(); } catch(e){this.notify(e.message,true);} }
  async addCalendar() { const title=this.state.calTitle.trim(), start=this.state.calStart; if(!title||!start)return; try { await this.api('/calendar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,start_at:start})}); this.setState({calTitle:'',calStart:''}); await this.loadCalendar(); } catch(e){this.notify(e.message,true);} }
  async deleteCalendar(id) { try { await this.api(`/calendar/${encodeURIComponent(id)}`,{method:'DELETE'}); await this.loadCalendar(); } catch(e){this.notify(e.message,true);} }
  async pullModel() { const model=this.state.modelPullName.trim(); if(!model||this.state.modelBusy)return; this.setState({modelBusy:true}); try { const r=await this.api('/models/pull',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model})}); if(r?.ok===false)throw new Error(r.error||'Model pull failed'); this.setState({modelPullName:''}); this.notify(`Pulled ${model}`); await this.loadModels(); } catch(e){this.notify(e.message,true);} finally{this.setState({modelBusy:false});} }
  async deleteModel(model) { if(!globalThis.confirm(`Delete local Ollama model "${model}"?`))return; try{const r=await this.api('/models/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model,confirm:true})});if(r?.ok===false)throw new Error(r.error||'Delete failed');this.notify(`Deleted ${model}`);await this.loadModels();}catch(e){this.notify(e.message,true);} }
  async sendChat() {
    const text=this.state.chatInput.trim(); if(!text||this.state.streaming)return;
    const user={role:'user',text}, assistant={role:'assistant',text:''};
    this.setState(prev=>({chatInput:'',streaming:true,messages:[...prev.messages,user,assistant]}));
    let assistantText='';
    try {
      const response=await fetch('/chat/stream',{method:'POST',headers:this.authHeaders({'Content-Type':'application/json','Accept':'text/event-stream'}),body:JSON.stringify({message:text,session_id:this.state.sessionId})});
      if(!response.ok||!response.body)throw new Error((await response.text()).slice(0,2000)||`HTTP ${response.status}`);
      const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='';
      while(true){const {done,value}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});const blocks=buffer.split('\n\n');buffer=blocks.pop()||'';for(const block of blocks){const row=block.split('\n').find(line=>line.startsWith('data:'));if(!row)continue;let event;try{event=JSON.parse(row.slice(5).trim());}catch(_){continue;}if(event.type==='token'){assistantText+=event.text||'';this.setState(prev=>({messages:prev.messages.map((m,idx)=>idx===prev.messages.length-1?{...m,text:assistantText}:m)}));}else if(event.type==='final'&&!assistantText){assistantText=event.text||'';this.setState(prev=>({messages:prev.messages.map((m,idx)=>idx===prev.messages.length-1?{...m,text:assistantText}:m)}));}else if(event.type==='tool'){this.setState(prev=>({chatTools:[{tool:event.tool||'tool',status:event.status||''},...prev.chatTools].slice(0,30)}));}else if(event.type==='error')throw new Error(event.error||'Chat stream failed');}}
    } catch(e) { assistantText=`**Error:** ${e.message}`; this.setState(prev=>({messages:prev.messages.map((m,idx)=>idx===prev.messages.length-1?{...m,text:assistantText}:m)})); this.notify(`Chat failed: ${e.message}`,true); }
    finally { this.setState({streaming:false}); Promise.allSettled([this.loadActivity(),this.loadStatus()]); }
  }
  renderShell(content) {
    const pageLabel = NAV.find(([id])=>id===this.state.page)?.[1] || 'Overview';
    const online = !!this.state.status;
    return h('div',{className:'min-h-screen lg:grid lg:grid-cols-[15rem_minmax(0,1fr)]'},
      h('aside',{className:'bg-slate-900/90 border-slate-800 border-b lg:border-b-0 lg:border-r sticky top-0 z-20 lg:h-screen p-4 backdrop-blur-xl flex lg:block gap-3 overflow-x-auto items-center'},
        h('div',{className:'shrink-0 whitespace-nowrap text-lg font-extrabold'},'Living ',h('span',{className:'text-brand-400'},'Assistant')),
        h('nav',{className:'flex lg:block gap-2 lg:mt-6'},NAV.map(([id,label])=>h('button',{key:id,onClick:()=>this.navigate(id),className:cx('shrink-0 w-full text-left px-3 py-2 rounded-xl text-sm transition',this.state.page===id?'bg-slate-800 text-white':'text-slate-400 hover:bg-slate-800 hover:text-white')},label)))),
      h('main',{className:'px-4 py-5 md:px-6 lg:px-8 min-w-0 max-w-[1600px] mx-auto w-full'},
        h('header',{className:'flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-5'},
          h('div',null,h('h1',{className:'text-2xl font-bold'},pageLabel),h('p',{className:'text-sm text-slate-400'},'Local-first control center')),
          h('div',{className:'flex flex-wrap gap-2 items-center'},
            h('span',{className:'inline-flex items-center gap-2 rounded-full border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-400'},h('span',{className:cx('h-2 w-2 rounded-full',online?'bg-emerald-400':'bg-rose-400')}),online?`online · ${this.state.status.profile}`:'offline'),
            h('input',{type:'password',value:this.state.tokenInput,onChange:e=>this.setState({tokenInput:e.target.value}),placeholder:'API token',className:'w-48 sm:w-64 rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-brand-400'}),
            h('button',{className:'px-3 py-2 rounded-xl border border-slate-700 bg-slate-800 hover:bg-slate-700',onClick:()=>this.useToken()},'Use token'))),
        content),
      this.state.toast ? h('div',{className:'fixed right-4 bottom-4 z-50 max-w-sm rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 shadow-xl text-sm'},this.state.toast):null);
  }
  render() {
    const pages={overview:this.renderOverview(),models:this.renderModels(),chat:this.renderChat(),approvals:this.renderApprovals(),organize:this.renderOrganize(),security:this.renderSecurity(),activity:this.renderActivity()};
    return this.renderShell(pages[this.state.page]||pages.overview);
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
  renderChat() {
    const messages = this.state.messages.length
      ? this.state.messages.map((m, i) => h(
          'div',
          {
            key: i,
            className: cx(
              'max-w-3xl rounded-2xl px-4 py-3',
              m.role === 'user' ? 'ml-auto bg-brand-600' : 'bg-slate-800 border border-slate-700',
            ),
          },
          m.role === 'assistant' ? h(Markdown, {text: m.text}) : m.text,
        ))
      : h('div', {className: 'text-slate-500 py-4'}, 'Start a conversation.');

    const chatPanel = h(
      'div',
      null,
      h('div', {className: 'h-64 md:h-[58vh] overflow-y-auto space-y-3'}, messages),
      h(
        'div',
        {className: 'grid grid-cols-[minmax(0,1fr)_auto] gap-2 mt-3 items-end'},
        h('textarea', {
          rows: 2,
          value: this.state.chatInput,
          onChange: e => this.setState({chatInput: e.target.value}),
          onKeyDown: e => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              this.sendChat();
            }
          },
          placeholder: 'Ask your assistant…',
          className: 'w-full resize-none rounded-xl border border-slate-700 bg-slate-950 px-3 py-2',
        }),
        h(
          'button',
          {
            disabled: this.state.streaming,
            onClick: () => this.sendChat(),
            className: 'px-3 py-2 rounded-xl border border-brand-500 bg-brand-600 hover:bg-brand-500 disabled:opacity-50',
          },
          this.state.streaming
            ? h('span', null, 'Generating', h('span', {className: 'h-3 w-1.5 rounded-full bg-brand-400 inline-block ml-1 animate-pulse'}))
            : 'Send',
        ),
      ),
    );

    const toolRows = this.state.chatTools.length
      ? this.state.chatTools.map((x, i) => h(
          'div',
          {key: i, className: 'border-l-2 border-slate-700 pl-3 py-2 text-xs text-slate-300'},
          `${x.status === 'started' ? 'Running' : 'Finished'} ${x.tool}`,
        ))
      : h('div', {className: 'text-slate-500'}, 'No tool activity yet.');

    return h(
      'div',
      {className: 'grid md:grid-cols-12 gap-3'},
      this.card(null, chatPanel, 'md:col-span-8'),
      this.card('Live execution', h('div', {className: 'space-y-2'}, toolRows), 'md:col-span-4'),
    );
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
