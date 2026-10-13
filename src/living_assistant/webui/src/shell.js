/* The app shell: sidebar (new chat, agents and teams, recent conversations, pages), a header that
   always shows what the assistant is doing and what waits for your approval, a live activity panel,
   and the pages. System pages from the classic dashboard are shown inside it. */
import { AgentsView } from './agents_view.js';
import { ChatView } from './chat.js';
import { CompaniesView, describeCompanyEvent } from './companies_view.js';
import { Avatar, Badge, Button, Empty, Icon, Spinner, cx, describeTool, json, timeAgo } from './kit.js';
import { ClassicApp } from './main.js';
import { SkillLibraryPanel } from './skill_library.js';

const React = globalThis.React;
const ReactDOM = globalThis.ReactDOM;
const h = React.createElement;
const { useState, useEffect, useRef, useCallback, useMemo } = React;

function readToken() {
  try { const s = sessionStorage.getItem('assistant_token'); if (s) return s; } catch (_) {}
  const meta = document.querySelector('meta[name="assistant-token"]');
  return meta ? meta.getAttribute('content') || '' : '';
}

const PAGES = [
  ['chat', 'Chat', 'message'], ['agents', 'Agents & teams', 'users'], ['companies', 'Companies', 'briefcase'], ['skills', 'Skills', 'book'], ['tasks', 'Tasks & calendar', 'calendar'],
];
const SYSTEM = [['overview', 'Overview', 'activity'], ['models', 'Models', 'cpu'], ['tools', 'Tools', 'wrench'], ['career', 'Career & jobs', 'briefcase'],
  ['security', 'Security', 'shield'], ['activity', 'Activity log', 'clock']];

function route() {
  const [page, sub] = location.hash.replace(/^#\/?/, '').split('/');
  const known = [...PAGES, ['system']].some(([id]) => id === page);
  return { page: known ? page : 'chat', sub: sub || '' };
}

// ---- activity wording -------------------------------------------------------------------------

const QUIET = /^(model\.|tool\.telemetry|tools\.routed|chat\.started|system\.killed|shell\.|resource\.|heartbeat|status\.|conversation\.|thermal\.|scheduler\.)/;
function describeEvent(ev) {
  const d = ev.data || {};
  switch (ev.type) {
    case 'tool.started': return { icon: describeTool(d.tool).icon, text: describeTool(d.tool).words, tone: 'indigo', live: true };
    case 'tool.completed': return { icon: d.ok ? 'check' : 'x', text: `${describeTool(d.tool).words} ${d.ok ? 'done' : 'failed'}`, tone: d.ok ? 'green' : 'red' };
    case 'tool.blocked': case 'tool.loop_blocked': return { icon: 'shield', text: `Blocked ${describeTool(d.tool).words.toLowerCase()}`, tone: 'red' };
    case 'team.member_started': return { icon: 'users', text: `${d.name} started: ${String(d.task || '').slice(0, 80)}`, tone: 'sky', live: true };
    case 'team.member_step': return d.status === 'started' ? { icon: describeTool(d.tool).icon, text: `${d.name}: ${describeTool(d.tool).words}`, tone: 'sky' } : null;
    case 'team.member_finished': return { icon: d.ok ? 'check' : 'x', text: `${d.name} finished`, tone: d.ok ? 'green' : 'red' };
    case 'chat.completed': return { icon: 'message', text: 'Reply finished', tone: 'zinc' };
    case 'chat.updated': return d.stopped ? { icon: 'stop', text: 'A reply was stopped', tone: 'zinc' } : null;
    case 'chat.error': return { icon: 'x', text: 'A reply failed', tone: 'red' };
    case 'system.halted': return { icon: 'power', text: 'Everything was stopped (kill switch)', tone: 'red' };
    default:
      if (QUIET.test(ev.type)) return null;
      if (/^company\./.test(ev.type)) return /^company\.(employee_step|employee_hired|department_added|employee_updated)$/.test(ev.type) ? null : describeCompanyEvent(ev.type, d);
      if (/^goal\./.test(ev.type)) return { icon: 'target', text: `Goal ${ev.type.slice(5).replace(/_/g, ' ')}${d.title ? `: ${d.title}` : ''}`, tone: 'amber' };
      if (/approval/.test(ev.type)) return { icon: 'hand', text: 'Approval requested', tone: 'amber' };
      return { icon: 'activity', text: ev.type.replace(/[._]/g, ' '), tone: 'zinc' };
  }
}
const TONE = { indigo: 'text-indigo-300', green: 'text-emerald-300', red: 'text-rose-300', sky: 'text-sky-300', amber: 'text-amber-300', zinc: 'text-zinc-400' };

function ActivityPanel({ events, onClose }) {
  const rows = [];
  for (let i = events.length - 1; i >= 0 && rows.length < 120; i -= 1) {
    const d = describeEvent(events[i]);
    if (d) rows.push({ ...d, ev: events[i] });
  }
  return h('aside', { className: 'flex w-80 shrink-0 flex-col border-l border-zinc-800 bg-zinc-950' },
    h('div', { className: 'flex items-center gap-2 border-b border-zinc-800 px-4 py-3' },
      h(Icon, { name: 'activity', size: 15, className: 'text-indigo-300' }), h('div', { className: 'flex-1 text-sm font-semibold' }, 'Live activity'),
      h(Button, { variant: 'ghost', size: 'icon', icon: 'x', onClick: onClose })),
    rows.length ? h('div', { className: 'flex-1 overflow-y-auto px-3 py-2' }, rows.map((r, i) => h('div', { key: r.ev.id || i, className: 'flex items-start gap-2.5 rounded-lg px-1.5 py-1.5 hover:bg-zinc-900' },
      h(Icon, { name: r.icon, size: 14, className: cx('mt-0.5', TONE[r.tone]) }),
      h('div', { className: 'min-w-0 flex-1' }, h('div', { className: 'text-[13px] text-zinc-200' }, r.text),
        h('div', { className: 'text-[11px] text-zinc-600' }, timeAgo(r.ev.created_at), r.ev.data && r.ev.data.session_id ? ' · chat' : '')))))
      : h(Empty, { icon: 'activity', title: 'Quiet for now', text: 'Every step the assistant, its agents and background goals take shows up here as it happens.' }));
}

// ---- approvals bell ---------------------------------------------------------------------------

function ApprovalsBell({ rows, decide }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const close = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);
  return h('div', { ref, className: 'relative' },
    h('button', { onClick: () => setOpen(!open), title: 'Approvals',
      className: cx('relative flex items-center gap-1.5 rounded-xl border px-2.5 py-1.5 text-sm transition', rows.length ? 'border-amber-500/50 bg-amber-500/15 text-amber-100 hover:bg-amber-500/25' : 'border-zinc-800 text-zinc-400 hover:bg-zinc-900') },
      h(Icon, { name: rows.length ? 'hand' : 'bell', size: 15 }),
      rows.length ? h('span', { className: 'font-medium' }, `${rows.length} waiting`) : null),
    open ? h('div', { className: 'absolute right-0 top-full z-40 mt-2 w-[26rem] overflow-hidden rounded-2xl border border-zinc-700 bg-zinc-900 shadow-2xl' },
      h('div', { className: 'border-b border-zinc-800 px-4 py-2.5 text-sm font-semibold' }, 'Waiting for your approval'),
      rows.length ? h('div', { className: 'max-h-96 overflow-y-auto' }, rows.map(a => h('div', { key: a.id, className: 'border-b border-zinc-800/70 px-4 py-3 last:border-0' },
        h('div', { className: 'flex items-center gap-2' }, h(Badge, { tone: 'amber' }, a.kind || 'action'), h('span', { className: 'text-[11px] text-zinc-500' }, timeAgo(a.created_at))),
        h('div', { className: 'mt-1.5 break-words text-sm text-zinc-100' }, a.action),
        a.reason ? h('div', { className: 'mt-0.5 break-words text-xs text-zinc-400' }, a.reason) : null,
        h('div', { className: 'mt-2 flex gap-2' },
          h(Button, { variant: 'success', size: 'sm', icon: 'check', onClick: () => decide(a.id, true) }, 'Approve'),
          h(Button, { size: 'sm', icon: 'x', onClick: () => decide(a.id, false) }, 'Deny')))))
        : h('div', { className: 'px-4 py-6 text-center text-sm text-zinc-500' }, 'Nothing is waiting. When an agent wants to do something that changes things, it asks here and in the chat.')) : null);
}

// ---- kill switch ------------------------------------------------------------------------------

function KillDialog({ onClose, api, notify }) {
  const [busy, setBusy] = useState('');
  const [done, setDone] = useState('');
  const kill = async (mode) => {
    setBusy(mode);
    try {
      await api('/system/kill', json('POST', { mode, reason: `kill switch (dashboard, ${mode})` }));
      setDone(mode === 'shutdown' ? 'The assistant has shut down. Start it again with run.bat.' : 'Everything stopped. The assistant is idle.');
    } catch (e) {
      if (mode === 'shutdown' && /fetch|network|load failed/i.test(e.message)) setDone('The assistant has shut down.');
      else notify(`Kill switch failed: ${e.message}`, true);
    } finally { setBusy(''); }
  };
  return h('div', { className: 'fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4' },
    h('div', { className: 'w-full max-w-md rounded-2xl border border-zinc-700 bg-zinc-900 p-5 shadow-2xl' },
      h('div', { className: 'flex items-center gap-2 text-lg font-semibold' }, h(Icon, { name: 'power', size: 18, className: 'text-rose-300' }), 'Kill switch'),
      done ? h('div', { className: 'mt-3 text-sm text-zinc-300' }, done) : h('div', { className: 'mt-2 text-sm text-zinc-400' },
        'Stops every chat, agent, team, goal and background job right now and frees the models.'),
      h('div', { className: 'mt-5 flex flex-wrap justify-end gap-2' },
        done ? h(Button, { onClick: onClose }, 'Close') : [
          h(Button, { key: 'c', variant: 'ghost', onClick: onClose }, 'Cancel'),
          h(Button, { key: 's', disabled: !!busy, onClick: () => kill('stop') }, busy === 'stop' ? 'Stopping…' : 'Only stop what it is doing'),
          h(Button, { key: 'k', variant: 'danger', icon: 'power', disabled: !!busy, onClick: () => kill('shutdown') }, busy === 'shutdown' ? 'Shutting down…' : 'Shut the assistant down')])));
}

// ---- the app ----------------------------------------------------------------------------------

function Shell() {
  const token = useRef(readToken()).current;
  const [loc, setLoc] = useState(route());
  const [toast, setToast] = useState(null);
  const [experts, setExperts] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [target, setTarget] = useState('assistant');
  const [approvals, setApprovals] = useState([]);
  const [events, setEvents] = useState([]);
  const [busy, setBusy] = useState(null);
  const [showActivity, setShowActivity] = useState(() => { try { return localStorage.getItem('shell_activity') !== '0' && innerWidth > 1300; } catch (_) { return false; } });
  const [killOpen, setKillOpen] = useState(false);
  const [sidebar, setSidebar] = useState(innerWidth > 900);
  const toastTimer = useRef(null);

  const api = useCallback(async (url, opt = {}) => {
    let response;
    try { response = await fetch(url, { ...opt, headers: { ...(opt.headers || {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) } }); }
    catch (error) { throw new Error(`Cannot reach the assistant (${error.message || error}). Is it running?`); }
    if (!response.ok) {
      let detail = '';
      try { const b = await response.json(); detail = typeof b.detail === 'string' ? b.detail : JSON.stringify(b.detail || b); } catch (_) { detail = await response.text().catch(() => ''); }
      throw new Error(detail || `HTTP ${response.status}`);
    }
    const type = response.headers.get('content-type') || '';
    return type.includes('json') ? response.json() : response.text();
  }, [token]);
  const notify = useCallback((text, error = false) => {
    setToast({ text: String(text == null ? '' : text), error });
    clearTimeout(toastTimer.current); toastTimer.current = setTimeout(() => setToast(null), error ? 7000 : 3500);
  }, []);

  const loadExperts = useCallback(() => api('/experts').then(setExperts).catch(e => notify(`Agents: ${e.message}`, true)), [api]);
  // background goal runs keep their own conversations; the sidebar lists only chats you started
  const loadConversations = useCallback(() => api('/conversations?limit=60').then(r => setConversations(((r && r.conversations) || [])
    .filter(c => !/^(goal-|desktop-agent|speedtest)/.test(c.id) && (c.message_count == null || c.message_count > 0)).slice(0, 40))).catch(() => {}), [api]);
  const loadApprovals = useCallback(() => api('/approvals').then(r => setApprovals(Array.isArray(r) ? r : [])).catch(() => {}), [api]);

  useEffect(() => {
    const onHash = () => setLoc(route());
    addEventListener('hashchange', onHash);
    loadExperts(); loadConversations(); loadApprovals();
    api('/conversations/active').then(a => a && a.id && openConversation(a.id, false)).catch(() => {});
    const t = setInterval(loadApprovals, 3000);
    return () => { removeEventListener('hashchange', onHash); clearInterval(t); };
  }, []);

  // live activity feed (SSE), reconnecting
  useEffect(() => {
    let stop = false, ctl = null, last = 0;
    const run = async () => {
      while (!stop) {
        ctl = new AbortController();
        try {
          const res = await fetch(`/activity/stream?after_id=${last}`, { headers: { Accept: 'text/event-stream', ...(token ? { Authorization: `Bearer ${token}` } : {}) }, signal: ctl.signal });
          const reader = res.body.getReader(), decoder = new TextDecoder(); let buf = '';
          while (!stop) {
            const { done, value } = await reader.read(); if (done) break;
            buf += decoder.decode(value, { stream: true }); const blocks = buf.split('\n\n'); buf = blocks.pop() || '';
            for (const b of blocks) {
              const row = b.split('\n').find(l => l.startsWith('data:')); if (!row) continue;
              try {
                const ev = JSON.parse(row.slice(5).trim()); last = Math.max(last, Number(ev.id || 0));
                setEvents(prev => (prev.length > 400 ? prev.slice(-300) : prev).concat(ev));
                if (ev.type === 'chat.completed' || ev.type === 'chat.updated') loadConversations();
                if (/approval/.test(ev.type) || ev.type === 'tool.completed') loadApprovals();
              } catch (_) {}
            }
          }
        } catch (_) {}
        if (!stop) await new Promise(r => setTimeout(r, 2500));
      }
    };
    run();
    return () => { stop = true; if (ctl) ctl.abort(); };
  }, []);

  const targets = useMemo(() => {
    if (!experts) return [{ target: 'assistant', name: 'Assistant', icon: 'sparkles', color: '#6366f1' }];
    return [...experts.agents.map(a => ({ ...a, target: a.id })),
            ...experts.teams.map(t => ({ ...t, target: `team:${t.id}`, team: true, welcome: t.description,
              quick_prompts: [{ title: 'Give the team a job', description: 'The lead splits it between the members', prompt: '' }] }))];
  }, [experts]);

  async function openConversation(id, go = true) {
    setSessionId(id);
    api('/conversations/active', json('PUT', { session_id: id })).catch(() => {});
    api(`/experts/conversations/${encodeURIComponent(id)}`).then(r => setTarget(r.target || 'assistant')).catch(() => setTarget('assistant'));
    if (go) location.hash = '/chat';
  }
  async function newChat(withTarget) {
    const created = await api('/conversations', json('POST', {}));
    const t = withTarget || target;
    setSessionId(created.id); setTarget(t);
    if (t !== 'assistant') await api(`/experts/conversations/${encodeURIComponent(created.id)}`, json('PUT', { target: t })).catch(() => {});
    loadConversations();
    return created.id;
  }
  async function startWith(t) { try { await newChat(t); location.hash = '/chat'; } catch (e) { notify(e.message, true); } }
  async function pickTarget(t) {
    setTarget(t);
    if (sessionId) api(`/experts/conversations/${encodeURIComponent(sessionId)}`, json('PUT', { target: t })).catch(e => notify(e.message, true));
  }
  async function decide(id, approved) {
    try { await api(`/approvals/${encodeURIComponent(id)}`, json('POST', { approved })); notify(approved ? 'Approved. The agent can now go ahead.' : 'Denied.'); loadApprovals(); }
    catch (e) { notify(e.message, true); }
  }
  const toggleActivity = () => { const v = !showActivity; setShowActivity(v); try { localStorage.setItem('shell_activity', v ? '1' : '0'); } catch (_) {} };

  const teamEvents = useMemo(() => events.filter(e => /^team\.member_/.test(e.type) && e.data && e.data.session_id === sessionId), [events, sessionId]);
  // background work (goals, other chats, agents) also counts as "working"
  const recent = events.filter(e => Date.now() - Date.parse(e.created_at) < 15000);
  const lastTool = [...recent].reverse().find(e => e.type === 'tool.started' || e.type === 'tool.completed');
  const background = !busy && lastTool && lastTool.type === 'tool.started' ? describeTool(lastTool.data.tool).words : null;
  const current = targets.find(t => t.target === target) || targets[0];

  const nav = (id, label, icon, href) => h('a', { key: id, href: href || `#/${id}`,
    className: cx('flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-sm transition', (href ? location.hash === href : loc.page === id) ? 'bg-zinc-800 text-white' : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100') },
    h(Icon, { name: icon, size: 15 }), label);

  let pageBody, pageTitle;
  if (loc.page === 'chat') {
    pageTitle = h('div', { className: 'flex min-w-0 items-center gap-2.5' }, h(Avatar, { agent: current, size: 28, team: current && current.team }),
      h('div', { className: 'min-w-0' }, h('div', { className: 'truncate text-sm font-semibold' }, current ? current.name : 'Assistant'),
        h('div', { className: 'truncate text-[11px] text-zinc-500' }, current && current.team ? `Team · ${(current.members || []).length} members` : (current && current.description) || '')));
    pageBody = h(ChatView, { api, token, notify, sessionId, target, targets, onPickTarget: pickTarget, onBusy: setBusy, teamEvents, onNewChat: () => newChat() });
  } else if (loc.page === 'agents') {
    pageTitle = h('div', { className: 'text-sm font-semibold' }, 'Agents & teams');
    pageBody = h('div', { className: 'h-full overflow-y-auto' }, h(AgentsView, { api, notify, data: experts, reload: loadExperts, onChat: startWith }));
  } else if (loc.page === 'companies') {
    pageTitle = h('div', { className: 'text-sm font-semibold' }, 'Companies');
    pageBody = h(CompaniesView, { api, notify, sub: loc.sub, events });
  } else if (loc.page === 'skills') {
    pageTitle = h('div', { className: 'text-sm font-semibold' }, 'Skills');
    pageBody = h('div', { className: 'h-full overflow-y-auto' }, h('div', { className: 'mx-auto max-w-6xl space-y-4 p-6' },
      h('div', null, h('h1', { className: 'text-xl font-semibold' }, 'Skills'),
        h('p', { className: 'mt-1 text-sm text-zinc-400' }, 'Skills teach your agents how to do a kind of task well. Install them from the SkillHub market or GitHub, or let the assistant learn one from your notes or a finished chat.')),
      h(SkillLibraryPanel, { api, notify, card: (title, body) => h('section', { className: 'rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4' },
        title ? h('h3', { className: 'mb-3 text-sm font-semibold' }, title) : null, body) }),
      h('details', { className: 'rounded-2xl border border-zinc-800 bg-zinc-900/40' },
        h('summary', { className: 'cursor-pointer px-4 py-3 text-sm text-zinc-400' }, 'Advanced: step-by-step skill packages'),
        h('div', { className: 'p-4' }, h(ClassicApp, { embedded: true, page: 'skills' })))));
  } else if (loc.page === 'tasks') {
    pageTitle = h('div', { className: 'text-sm font-semibold' }, 'Tasks & calendar');
    pageBody = h('div', { className: 'h-full overflow-y-auto p-6' }, h(ClassicApp, { embedded: true, page: 'organize' }));
  } else {
    const sub = SYSTEM.some(([id]) => id === loc.sub) ? loc.sub : 'overview';
    pageTitle = h('div', { className: 'text-sm font-semibold' }, `System · ${SYSTEM.find(([id]) => id === sub)[1]}`);
    pageBody = h('div', { className: 'flex h-full min-h-0 flex-col' },
      h('div', { className: 'flex gap-1 border-b border-zinc-800 px-6 pt-3' }, SYSTEM.map(([id, label, icon]) => h('a', { key: id, href: `#/system/${id}`,
        className: cx('flex items-center gap-1.5 border-b-2 px-3 pb-2.5 text-sm', sub === id ? 'border-indigo-400 text-white' : 'border-transparent text-zinc-400 hover:text-zinc-200') }, h(Icon, { name: icon, size: 14 }), label))),
      h('div', { className: 'flex-1 overflow-y-auto p-6' }, h(ClassicApp, { key: sub, embedded: true, page: sub })));
  }

  const agentsShort = targets.slice(0, 8);
  return h('div', { className: 'flex h-screen overflow-hidden bg-zinc-950 text-zinc-100' },
    sidebar ? h('aside', { className: 'flex w-64 shrink-0 flex-col border-r border-zinc-800 bg-zinc-950' },
      h('div', { className: 'flex items-center gap-2 px-4 pb-2 pt-4' },
        h('span', { className: 'rounded-lg bg-gradient-to-br from-indigo-500 to-sky-500 p-1.5' }, h(Icon, { name: 'sparkles', size: 15, className: 'text-white' })),
        h('div', { className: 'flex-1 font-semibold tracking-tight' }, 'Living Assistant'),
        h(Button, { variant: 'ghost', size: 'icon', icon: 'menu', onClick: () => setSidebar(false), title: 'Hide sidebar' })),
      h('div', { className: 'px-3 py-2' }, h(Button, { variant: 'primary', icon: 'plus', className: 'w-full', onClick: () => startWith(target) }, 'New chat')),
      h('nav', { className: 'space-y-0.5 px-3' }, PAGES.map(([id, label, icon]) => nav(id, label, icon))),
      h('div', { className: 'mt-4 flex items-center px-5 text-[10px] font-semibold uppercase tracking-wider text-zinc-500' },
        h('span', { className: 'flex-1' }, 'Talk to'), h('a', { href: '#/agents', className: 'normal-case tracking-normal text-zinc-500 hover:text-zinc-300' }, 'all')),
      h('div', { className: 'space-y-0.5 px-3 pt-1' }, agentsShort.map(t => h('button', { key: t.target, onClick: () => startWith(t.target),
        className: cx('flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm hover:bg-zinc-900', t.target === target && loc.page === 'chat' && 'bg-zinc-900') },
        h(Avatar, { agent: t, size: 22, team: t.team }), h('span', { className: 'flex-1 truncate text-zinc-300' }, t.name),
        t.team ? h(Icon, { name: 'users', size: 12, className: 'text-zinc-600' }) : null))),
      h('div', { className: 'mt-4 px-5 text-[10px] font-semibold uppercase tracking-wider text-zinc-500' }, 'Recent chats'),
      h('div', { className: 'mt-1 flex-1 space-y-0.5 overflow-y-auto px-3' }, conversations.map(c => h('button', { key: c.id, onClick: () => openConversation(c.id),
        className: cx('block w-full truncate rounded-lg px-2.5 py-1.5 text-left text-[13px] hover:bg-zinc-900', c.id === sessionId ? 'bg-zinc-900 text-white' : 'text-zinc-400'), title: c.title },
        c.title || 'New chat'))),
      h('div', { className: 'border-t border-zinc-800 p-3' }, nav('system', 'System', 'settings', `#/system/${loc.page === 'system' ? loc.sub || 'overview' : 'overview'}`))) : null,
    h('main', { className: 'flex min-w-0 flex-1 flex-col' },
      h('header', { className: 'flex h-14 shrink-0 items-center gap-3 border-b border-zinc-800 px-4' },
        sidebar ? null : h(Button, { variant: 'ghost', size: 'icon', icon: 'menu', onClick: () => setSidebar(true), title: 'Show sidebar' }),
        h('div', { className: 'min-w-0 flex-1' }, pageTitle),
        busy || background ? h('div', { className: 'flex max-w-[22rem] items-center gap-2 rounded-xl border border-indigo-500/40 bg-indigo-500/10 px-3 py-1.5 text-sm text-indigo-100' },
          h(Spinner, { size: 12 }), h('span', { className: 'truncate' }, busy ? `${busy.agent}: ${busy.phase}` : `Working: ${background}`))
          : h('div', { className: 'hidden items-center gap-1.5 text-xs text-zinc-500 sm:flex' }, h('span', { className: 'h-2 w-2 rounded-full bg-emerald-400' }), 'Ready'),
        h(ApprovalsBell, { rows: approvals, decide }),
        h(Button, { variant: showActivity ? 'default' : 'ghost', size: 'icon', icon: 'activity', onClick: toggleActivity, title: 'Live activity' }),
        h(Button, { variant: 'ghost', size: 'icon', icon: 'power', onClick: () => setKillOpen(true), title: 'Kill switch', className: 'text-rose-300 hover:text-rose-200' })),
      h('div', { className: 'flex min-h-0 flex-1' },
        h('div', { className: 'min-w-0 flex-1' }, pageBody),
        showActivity ? h(ActivityPanel, { events, onClose: toggleActivity }) : null)),
    killOpen ? h(KillDialog, { api, notify, onClose: () => setKillOpen(false) }) : null,
    toast ? h('div', { className: cx('fixed bottom-5 left-1/2 z-50 max-w-xl -translate-x-1/2 rounded-xl border px-4 py-2.5 text-sm shadow-2xl', toast.error ? 'border-rose-500/50 bg-rose-950 text-rose-100' : 'border-zinc-700 bg-zinc-900 text-zinc-100') }, toast.text) : null);
}

ReactDOM.render(h(Shell), document.getElementById('root'));
