/* The chat: a live timeline of what the agent does in each turn (every tool step, team members'
   work, files it shows), approval requests as cards right where they happen, and a composer that
   picks which agent or team you talk to. */
import { ACCEPT, extractFiles, fileChip, mediaList, uploadFile } from './chatmedia.js';
import { Avatar, Badge, Button, Icon, Spinner, argSummary, cx, describeTool, json } from './kit.js';
import { Markdown } from './markdown.js';

const React = globalThis.React;
const h = React.createElement;
const { useState, useEffect, useRef, useCallback } = React;

function DomNode({ make, depKey, className }) {
  const ref = useRef(null);
  useEffect(() => { if (ref.current) ref.current.replaceChildren(make()); }, [depKey]);
  return h('div', { ref, className });
}

async function readSSE(response, onEvent) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split('\n\n');
    buffer = blocks.pop() || '';
    for (const block of blocks) {
      const row = block.split('\n').find(line => line.startsWith('data:'));
      if (!row) continue;
      let event;
      try { event = JSON.parse(row.slice(5).trim()); } catch (_) { continue; }
      onEvent(event);
    }
  }
}

// ---- one step of the timeline ---------------------------------------------------------------

function StepIcon({ status }) {
  if (status === 'running') return h('span', { className: 'flex h-5 w-5 items-center justify-center text-indigo-300' }, h(Spinner, { size: 12 }));
  const map = { ok: ['check', 'text-emerald-300 bg-emerald-500/15'], failed: ['x', 'text-rose-300 bg-rose-500/15'],
    approval: ['hand', 'text-amber-200 bg-amber-500/20'], stopped: ['stop', 'text-zinc-400 bg-zinc-700/50'],
    denied: ['x', 'text-zinc-400 bg-zinc-700/50'] };
  const [icon, tone] = map[status] || map.ok;
  return h('span', { className: cx('flex h-5 w-5 items-center justify-center rounded-full', tone) }, h(Icon, { name: icon, size: 12, strokeWidth: 2.4 }));
}

function ApprovalInline({ step, onDecide }) {
  const [busy, setBusy] = useState('');
  if (step.decided) {
    return h('div', { className: 'mt-1.5 text-xs text-zinc-400' }, step.decided === 'approved' ? 'You approved this - the agent continued.'
      : step.decided === 'old' ? 'Approval was asked for here (see the approvals bell for anything still waiting).' : 'You denied this.');
  }
  const go = async (approved) => { setBusy(approved ? 'yes' : 'no'); try { await onDecide(step, approved); } finally { setBusy(''); } };
  return h('div', { className: 'mt-2 rounded-xl border border-amber-500/40 bg-amber-500/10 p-3' },
    h('div', { className: 'flex items-start gap-2' },
      h(Icon, { name: 'hand', size: 16, className: 'mt-0.5 text-amber-300' }),
      h('div', { className: 'min-w-0 flex-1' },
        h('div', { className: 'text-sm font-medium text-amber-100' }, 'The agent needs your approval to continue'),
        h('div', { className: 'mt-0.5 break-words text-xs text-amber-200/80' }, step.approval_message || step.error || describeTool(step.tool).words))),
    h('div', { className: 'mt-2.5 flex gap-2' },
      h(Button, { variant: 'success', size: 'sm', icon: 'check', disabled: !!busy, onClick: () => go(true) }, busy === 'yes' ? 'Approving…' : 'Approve & continue'),
      h(Button, { variant: 'default', size: 'sm', icon: 'x', disabled: !!busy, onClick: () => go(false) }, 'Deny')));
}

function Step({ step, onDecide }) {
  if (step.kind === 'note') {
    return h('div', { className: 'flex gap-2.5 py-1' }, h('span', { className: 'mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-zinc-600 ml-[7px]' }),
      h('div', { className: 'min-w-0 text-xs italic text-zinc-400 line-clamp-3' }, step.text));
  }
  if (step.kind === 'member') {
    return h('div', { className: 'flex items-start gap-2.5 py-1 pl-6' }, h(StepIcon, { status: step.status }),
      h('div', { className: 'min-w-0 flex-1 text-xs' },
        h('span', { className: 'font-medium text-sky-200' }, step.name), h('span', { className: 'text-zinc-400' }, ` · ${step.text}`)));
  }
  const d = describeTool(step.tool);
  const detail = argSummary(step.args);
  return h('div', { className: 'py-1' },
    h('div', { className: 'flex items-start gap-2.5' }, h(StepIcon, { status: step.status }),
      h('div', { className: 'min-w-0 flex-1' },
        h('div', { className: 'flex flex-wrap items-center gap-x-2 text-[13px]' },
          h(Icon, { name: d.icon, size: 13, className: 'text-zinc-500' }),
          h('span', { className: step.status === 'running' ? 'text-zinc-100' : 'text-zinc-300' }, d.words),
          h('span', { className: 'font-mono text-[10.5px] text-zinc-600' }, step.tool)),
        detail ? h('div', { className: 'truncate text-xs text-zinc-500', title: detail }, detail) : null,
        step.status === 'failed' && step.error ? h('div', { className: 'mt-0.5 break-words text-xs text-rose-300/90' }, step.error) : null)),
    step.status === 'approval' && step.approval_id ? h('div', { className: 'pl-7' }, h(ApprovalInline, { step, onDecide })) : null);
}

function ProcessCard({ msg, onDecide }) {
  const steps = msg.steps || [];
  const live = !!msg.phase;
  const [open, setOpen] = useState(true);
  useEffect(() => { if (!live && steps.length > 3 && !steps.some(s => s.status === 'approval' && !s.decided)) setOpen(false); }, [live]);
  if (!steps.length && !live) return null;
  const tools = steps.filter(s => s.kind === 'tool');
  const failed = tools.filter(s => s.status === 'failed').length;
  const waiting = steps.some(s => s.status === 'approval' && !s.decided);
  const secs = msg.startedAt ? Math.max(1, Math.round(((msg.endedAt || Date.now()) - msg.startedAt) / 1000)) : null;
  const head = live ? msg.phase : waiting ? 'Waiting for your approval'
    : `Worked${secs ? ` for ${secs}s` : ''} · ${tools.length} step${tools.length === 1 ? '' : 's'}${failed ? ` · ${failed} failed` : ''}`;
  return h('div', { className: cx('mb-2 rounded-xl border bg-zinc-950/60', waiting ? 'border-amber-500/40' : 'border-zinc-800') },
    h('button', { onClick: () => setOpen(!open), className: 'flex w-full items-center gap-2 px-3 py-2 text-left text-xs' },
      live ? h(Spinner, { size: 12, className: 'text-indigo-300' }) : h(Icon, { name: waiting ? 'hand' : 'activity', size: 13, className: waiting ? 'text-amber-300' : 'text-zinc-500' }),
      h('span', { className: cx('flex-1', live ? 'text-indigo-200' : waiting ? 'text-amber-200' : 'text-zinc-400') }, head),
      steps.length ? h(Icon, { name: open ? 'chevronDown' : 'chevronRight', size: 14, className: 'text-zinc-500' }) : null),
    open && steps.length ? h('div', { className: 'border-t border-zinc-800/80 px-3 py-1.5' }, steps.map((s, i) => h(Step, { key: i, step: s, onDecide }))) : null);
}

function Message({ msg, agent, token, onDecide, onRetry }) {
  if (msg.role === 'user') {
    const { text, files } = extractFiles(msg.text);
    return h('div', { className: 'flex justify-end' },
      h('div', { className: 'max-w-[80%] space-y-1.5' },
        files.length ? h(DomNode, { depKey: files.map(f => f.ref).join(','), className: 'flex flex-wrap justify-end gap-1.5',
          make: () => { const frag = document.createDocumentFragment(); files.forEach(f => frag.appendChild(fileChip(f, token))); return frag; } }) : null,
        text ? h('div', { className: 'whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-indigo-500/90 px-4 py-2.5 text-sm text-white' }, text) : null));
  }
  return h('div', { className: 'flex gap-3' },
    h(Avatar, { agent, size: 30, team: agent && agent.team }),
    h('div', { className: 'min-w-0 flex-1' },
      h('div', { className: 'mb-1 text-xs font-medium text-zinc-400' }, (agent && agent.name) || 'Assistant'),
      h(ProcessCard, { msg, onDecide }),
      msg.text ? h('div', { className: 'markdown-body text-[14.5px] leading-relaxed text-zinc-100' }, h(Markdown, { text: msg.text })) : null,
      msg.media && msg.media.length ? h(DomNode, { depKey: msg.media.map(x => x.ref).join(','), make: () => mediaList(msg.media, token), className: 'mt-2' }) : null,
      msg.error ? h('div', { className: 'mt-2 flex items-center gap-2 rounded-xl border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-200' },
        h(Icon, { name: 'x', size: 14 }), h('span', { className: 'flex-1' }, msg.error),
        msg.retryText ? h(Button, { size: 'sm', icon: 'refresh', onClick: () => onRetry(msg.retryText) }, 'Retry') : null) : null,
      msg.stopped ? h('div', { className: 'mt-1 text-xs text-zinc-500' }, 'Stopped.') : null));
}

// ---- the composer -----------------------------------------------------------------------------

function AgentPicker({ targets, current, onPick, disabled }) {
  const [open, setOpen] = useState(false);
  const cur = targets.find(t => t.target === current) || targets[0];
  return h('div', { className: 'relative' },
    h('button', { disabled, onClick: () => setOpen(!open), className: 'flex items-center gap-2 rounded-lg px-2 py-1 text-xs text-zinc-300 hover:bg-zinc-800 disabled:opacity-50' },
      cur ? h(Avatar, { agent: cur, size: 20, team: cur.team }) : null, h('span', { className: 'max-w-[10rem] truncate' }, cur ? cur.name : 'Assistant'),
      h(Icon, { name: 'chevronDown', size: 12 })),
    open ? h('div', { className: 'absolute bottom-full left-0 z-30 mb-2 max-h-80 w-72 overflow-y-auto rounded-xl border border-zinc-700 bg-zinc-900 p-1 shadow-2xl' },
      ['Agents', 'Teams'].map(group => {
        const rows = targets.filter(t => (group === 'Teams') === !!t.team);
        return rows.length ? h('div', { key: group },
          h('div', { className: 'px-2 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-zinc-500' }, group),
          rows.map(t => h('button', { key: t.target, onClick: () => { setOpen(false); onPick(t.target); },
            className: cx('flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm hover:bg-zinc-800', t.target === current && 'bg-zinc-800') },
            h(Avatar, { agent: t, size: 22, team: t.team }), h('div', { className: 'min-w-0 flex-1' },
              h('div', { className: 'truncate' }, t.name), t.description ? h('div', { className: 'truncate text-[11px] text-zinc-500' }, t.description) : null)))) : null;
      })) : null);
}

// ---- the view ---------------------------------------------------------------------------------

export function ChatView({ api, token, notify, sessionId, target, targets, onPickTarget, onBusy, teamEvents, onNewChat }) {
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState('');
  const [pending, setPending] = useState([]);
  const [uploading, setUploading] = useState(0);
  const [streaming, setStreaming] = useState(false);
  const controller = useRef(null);
  const busy = useRef(false);  // set before a new conversation exists, so its (empty) history never wipes the turn
  const listRef = useRef(null);
  const boxRef = useRef(null);
  const stick = useRef(true);
  const agent = targets.find(t => t.target === target) || targets[0] || { name: 'Assistant' };

  const updateLast = (fn) => setMessages(prev => {
    const idx = prev.length - 1;
    if (idx < 0 || prev[idx].role !== 'assistant') return prev;
    const next = prev.slice();
    next[idx] = fn({ ...prev[idx], steps: (prev[idx].steps || []).slice() });
    return next;
  });

  const loadHistory = useCallback(async () => {
    if (!sessionId) { setMessages([]); return; }
    try {
      const res = await api(`/conversations/${encodeURIComponent(sessionId)}/messages`);
      if (busy.current) return;
      const rows = (res && res.messages) || [];
      setMessages(rows.filter(r => r.role === 'user' || r.role === 'assistant').map(r => ({ role: r.role, text: String(r.content || ''),
        steps: ((r.meta && r.meta.steps) || []).map(st => ({ kind: 'tool', ...st, status: st.status === 'running' ? 'stopped' : st.status, decided: st.status === 'approval' ? 'old' : undefined })),
        media: (r.meta && r.meta.media) || [] })));
      const running = await api(`/chat/running/${encodeURIComponent(sessionId)}`).catch(() => null);
      if (running && running.running && !busy.current) setMessages(prev => [...prev, { role: 'assistant', text: '', steps: [], phase: 'Still working on your last request…', startedAt: Date.now() }]);
    } catch (e) { notify(`Could not load the conversation: ${e.message}`, true); }
  }, [sessionId]);
  useEffect(() => { if (!busy.current) loadHistory(); }, [sessionId]);

  // team members report their work through the activity feed: show it inside the running turn
  const seenTeam = useRef(0);
  useEffect(() => {
    const fresh = teamEvents.slice(seenTeam.current);
    seenTeam.current = teamEvents.length;
    if (!fresh.length) return;
    updateLast(m => {
      const steps = m.steps;
      for (const ev of fresh) {
        const d = ev.data || {};
        if (ev.type === 'team.member_started') steps.push({ kind: 'member', name: d.name, status: 'running', text: `started: ${String(d.task || '').slice(0, 120)}` });
        else if (ev.type === 'team.member_step' && d.status === 'started') steps.push({ kind: 'member', name: d.name, status: 'running', text: describeTool(d.tool).words + (d.args ? ` - ${argSummary(d.args)}` : '') });
        else if (ev.type === 'team.member_step') {
          for (let i = steps.length - 1; i >= 0; i -= 1) if (steps[i].kind === 'member' && steps[i].name === d.name && steps[i].status === 'running' && !steps[i].text.startsWith('started')) { steps[i] = { ...steps[i], status: d.ok ? 'ok' : 'failed' }; break; }
        } else if (ev.type === 'team.member_finished') {
          for (let i = steps.length - 1; i >= 0; i -= 1) if (steps[i].kind === 'member' && steps[i].name === d.name && steps[i].status === 'running') steps[i] = { ...steps[i], status: d.ok ? 'ok' : 'failed' };
          steps.push({ kind: 'member', name: d.name, status: d.ok ? 'ok' : 'failed', text: d.ok ? `finished in ${d.seconds}s` : 'could not finish' });
        }
      }
      return { ...m, steps };
    });
  }, [teamEvents]);

  useEffect(() => {
    const el = listRef.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [messages]);

  useEffect(() => {
    const last = messages[messages.length - 1];
    const running = last && last.role === 'assistant' && last.phase;
    const step = running ? [...(last.steps || [])].reverse().find(s => s.status === 'running') : null;
    onBusy(running ? { phase: step ? (step.kind === 'member' ? `${step.name}: ${step.text}` : describeTool(step.tool).words) : last.phase, agent: agent.name }
      : null);
  }, [messages]);

  const handle = (event, run) => {
    if (event.type === 'status') {
      if (event.status === 'generating' && run.stepText.trim()) {
        const note = run.stepText.trim();
        updateLast(m => ({ ...m, steps: [...m.steps, { kind: 'note', text: note }], text: '' }));
      }
      if (event.status === 'generating') run.stepText = '';
      const phase = { generating: 'Thinking…', reading: 'Reading the attached files…', looking: 'Looking at the images…', compacting_context: 'Tidying up the context…' }[event.status] || 'Starting…';
      updateLast(m => ({ ...m, phase }));
    } else if (event.type === 'token') {
      run.stepText += event.text || '';
      const text = run.stepText;
      updateLast(m => ({ ...m, text, phase: 'Writing…' }));
    } else if (event.type === 'tool') {
      if (event.status === 'started') {
        run.stepText = '';
        updateLast(m => ({ ...m, text: '', phase: describeTool(event.tool).words + '…', steps: [...m.steps, { kind: 'tool', tool: event.tool, args: event.args || '', status: 'running' }] }));
      } else {
        if (event.media && event.media.length) updateLast(m => ({ ...m, media: [...(m.media || []), ...event.media] }));
        const status = event.ok ? 'ok' : (event.approval_id ? 'approval' : 'failed');
        updateLast(m => {
          const steps = m.steps;
          for (let i = steps.length - 1; i >= 0; i -= 1) {
            if (steps[i].kind === 'tool' && steps[i].tool === event.tool && steps[i].status === 'running') {
              steps[i] = { ...steps[i], status, error: event.error || '', approval_id: event.approval_id || null, approval_message: event.approval_message || '' };
              return { ...m, steps };
            }
          }
          return { ...m, steps: [...steps, { kind: 'tool', tool: event.tool, status, error: event.error || '', approval_id: event.approval_id || null }] };
        });
      }
    } else if (event.type === 'final') {
      run.finalText = event.text || run.stepText;
      const text = run.finalText;
      updateLast(m => ({ ...m, text, phase: null, endedAt: Date.now(), media: event.media || m.media }));
    } else if (event.type === 'stopped') {
      updateLast(m => ({ ...m, phase: null, stopped: true, endedAt: Date.now() }));
    } else if (event.type === 'error') {
      throw new Error(event.error || 'The turn failed');
    }
  };

  async function send(textOverride) {
    let text = String(textOverride ?? draft).trim();
    const attached = textOverride != null ? [] : pending;
    if ((!text && !attached.length) || busy.current || uploading) return;
    busy.current = true;
    const images = attached.filter(f => f.kind === 'image').map(f => f.id);
    const files = attached.filter(f => f.kind !== 'image');
    if (!text) text = files.length ? 'Please look at the attached file.' : 'What is in this image?';
    const shown = [text, ...images.map(id => `[image ${id}]`), ...files.map(f => `[file ${f.id} ${f.name}]`)].join('\n');
    let sid = sessionId;
    if (!sid) { try { sid = await onNewChat(); } catch (e) { busy.current = false; notify(e.message, true); return; } }
    stick.current = true;
    setDraft(textOverride == null ? '' : draft);
    if (attached.length) setPending([]);
    setStreaming(true);
    setMessages(prev => [...prev, { role: 'user', text: shown }, { role: 'assistant', text: '', steps: [], phase: 'Starting…', retryText: text, startedAt: Date.now() }]);
    const ctl = new AbortController();
    controller.current = ctl;
    const run = { stepText: '', finalText: '' };
    try {
      const response = await fetch('/chat/stream', { method: 'POST', signal: ctl.signal,
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ message: text, session_id: sid, source: 'text', images, files: files.map(f => f.id), agent: target }) });
      if (!response.ok || !response.body) throw new Error((await response.text()).slice(0, 600) || `HTTP ${response.status}`);
      await readSSE(response, ev => handle(ev, run));
      if (!run.finalText && !run.stepText) updateLast(m => (m.stopped ? m : { ...m, text: m.text || '_No response was returned._', phase: null, endedAt: Date.now() }));
    } catch (e) {
      if (e.name === 'AbortError') updateLast(m => ({ ...m, phase: null, stopped: true, endedAt: Date.now(), steps: m.steps.map(s => s.status === 'running' ? { ...s, status: 'stopped' } : s) }));
      else updateLast(m => ({ ...m, phase: null, endedAt: Date.now(), error: String(e.message || e).replace(/^\{"detail":"?|"?\}$/g, ''), steps: m.steps.map(s => s.status === 'running' ? { ...s, status: 'stopped' } : s) }));
    } finally {
      if (controller.current === ctl) controller.current = null;
      busy.current = false;
      setStreaming(false);
    }
  }

  function stop() {
    if (controller.current) controller.current.abort();
    if (sessionId) api('/chat/stop', json('POST', { session_id: sessionId })).catch(() => {});
  }

  async function decide(step, approved) {
    try {
      await api(`/approvals/${encodeURIComponent(step.approval_id)}`, json('POST', { approved }));
      setMessages(prev => prev.map(m => m.role !== 'assistant' ? m : { ...m, steps: (m.steps || []).map(s => s.approval_id === step.approval_id ? { ...s, decided: approved ? 'approved' : 'denied', status: approved ? 'ok' : 'denied' } : s) }));
      if (approved) send('I approved it - please continue with the same action.');
    } catch (e) { notify(e.message, true); }
  }

  async function attach(list) {
    for (const file of [...(list || [])]) {
      setUploading(n => n + 1);
      try {
        const saved = await uploadFile(file, token, file.name || 'file');
        setPending(prev => [...prev, { id: saved.id, ref: saved.id, name: saved.name, kind: saved.kind, bytes: saved.bytes }]);
      } catch (e) { notify(`Could not attach ${file.name}: ${e.message}`, true); }
      finally { setUploading(n => n - 1); }
    }
    if (boxRef.current) boxRef.current.focus();
  }

  const welcome = !messages.length;
  return h('div', { className: 'flex h-full min-h-0 flex-col' },
    h('div', { ref: listRef, onScroll: e => { const el = e.currentTarget; stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80; },
      className: 'flex-1 overflow-y-auto' },
      welcome ? h('div', { className: 'mx-auto flex max-w-2xl flex-col items-center px-6 pt-16 text-center' },
        h(Avatar, { agent, size: 56, team: agent.team }),
        h('div', { className: 'mt-4 text-2xl font-semibold text-zinc-100' }, agent.name),
        h('div', { className: 'mt-1 text-sm text-zinc-400' }, agent.welcome || agent.description || 'What can I do for you?'),
        (agent.quick_prompts || []).length ? h('div', { className: 'mt-8 grid w-full gap-2.5 sm:grid-cols-2' },
          agent.quick_prompts.map((q, i) => h('button', { key: i, onClick: () => { setDraft(q.prompt || q.title); setTimeout(() => boxRef.current && boxRef.current.focus(), 0); },
            className: 'rounded-xl border border-zinc-800 bg-zinc-900/60 px-4 py-3 text-left transition hover:border-zinc-600 hover:bg-zinc-800/60' },
            h('div', { className: 'text-sm font-medium text-zinc-100' }, q.title), q.description ? h('div', { className: 'mt-0.5 text-xs text-zinc-500' }, q.description) : null))) : null)
        : h('div', { className: 'mx-auto max-w-3xl space-y-6 px-4 py-6 sm:px-6' },
          messages.map((m, i) => h(Message, { key: i, msg: m, agent, token, onDecide: decide, onRetry: t => send(t) })))),
    h('div', { className: 'border-t border-zinc-800/80 bg-zinc-950/80 px-4 pb-4 pt-3 sm:px-6' },
      h('div', { className: 'mx-auto max-w-3xl' },
        h('div', { className: 'rounded-2xl border border-zinc-700 bg-zinc-900 focus-within:border-indigo-400/70 focus-within:ring-2 focus-within:ring-indigo-500/15' },
          pending.length || uploading ? h('div', { className: 'flex flex-wrap items-center gap-1.5 px-3 pt-3' },
            h(DomNode, { depKey: pending.map(f => f.id).join(','), className: 'flex flex-wrap gap-1.5',
              make: () => { const frag = document.createDocumentFragment(); pending.forEach(f => frag.appendChild(fileChip(f, token, { onRemove: () => setPending(p => p.filter(x => x.id !== f.id)) }))); return frag; } }),
            uploading ? h('span', { className: 'flex items-center gap-1.5 text-xs text-zinc-400' }, h(Spinner, { size: 11 }), 'Uploading…') : null) : null,
          h('textarea', { ref: boxRef, rows: 1, value: draft, placeholder: `Message ${agent.name}…`,
            onChange: e => { setDraft(e.target.value); e.target.style.height = 'auto'; e.target.style.height = `${Math.min(220, e.target.scrollHeight)}px`; },
            onKeyDown: e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } },
            onPaste: e => { const files = [...(e.clipboardData && e.clipboardData.files || [])]; if (files.length) { e.preventDefault(); attach(files); } },
            className: 'block max-h-56 w-full resize-none bg-transparent px-4 pt-3 text-[14.5px] text-zinc-100 placeholder:text-zinc-500 outline-none' }),
          h('div', { className: 'flex items-center gap-1 px-2 pb-2 pt-1' },
            h(AgentPicker, { targets, current: target, onPick: onPickTarget, disabled: streaming }),
            h('label', { className: 'cursor-pointer rounded-lg p-2 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100', title: 'Attach files' },
              h(Icon, { name: 'paperclip', size: 16 }),
              h('input', { type: 'file', multiple: true, accept: ACCEPT, className: 'hidden', onChange: e => { attach(e.target.files); e.target.value = ''; } })),
            h('div', { className: 'flex-1' }),
            streaming ? h(Button, { variant: 'danger', size: 'sm', icon: 'stop', onClick: stop }, 'Stop')
              : h(Button, { variant: 'primary', size: 'sm', icon: 'send', disabled: !draft.trim() && !pending.length, onClick: () => send() }, 'Send'))),
        h('div', { className: 'mt-1.5 text-center text-[11px] text-zinc-600' }, 'Enter to send · Shift+Enter for a new line · actions that change things ask for your approval first'))));
}
