/* Agents & teams: your agents, ready-made templates to hire (Octop's expert library), teams
   ("agent companies") of member agents with a lead, and the editors for each. */
import { Avatar, Badge, Button, Card, Drawer, Empty, Field, Icon, cx, input, json } from './kit.js';

const React = globalThis.React;
const h = React.createElement;
const { useState, useEffect } = React;

const COLORS = ['#6366f1', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#8b5cf6', '#14b8a6', '#64748b'];
const ICON_CHOICES = ['bot', 'sparkles', 'brain', 'code', 'briefcase', 'book', 'globe', 'search', 'edit', 'calendar', 'shield', 'trendingUp', 'heart', 'graduation', 'terminal', 'users'];

function AgentEditor({ open, value, personalities, skills, onClose, onSave, onDelete }) {
  const [f, setF] = useState(value);
  const [saving, setSaving] = useState(false);
  useEffect(() => { setF(value); }, [value, open]);
  if (!open || !f) return null;
  const set = (k, v) => setF({ ...f, [k]: v });
  const toggleSkill = (name) => set('skills', (f.skills || []).includes(name) ? f.skills.filter(s => s !== name) : [...(f.skills || []), name]);
  const save = async () => { setSaving(true); try { await onSave(f); } finally { setSaving(false); } };
  return h(Drawer, { open, title: f.id ? `Edit ${f.name}` : 'New agent', onClose, footer: [
    f.id && !f.builtin && onDelete ? h(Button, { key: 'd', variant: 'danger', icon: 'trash', onClick: () => { onClose(); onDelete(f); } }, 'Delete') : null,
    h('div', { key: 'sp', className: 'flex-1' }),
    h(Button, { key: 'c', onClick: onClose }, 'Cancel'),
    h(Button, { key: 's', variant: 'primary', icon: 'check', disabled: !String(f.name || '').trim() || saving, onClick: save }, saving ? 'Saving…' : 'Save agent')] },
    h('div', { className: 'space-y-5' },
      h('div', { className: 'flex items-center gap-3' }, h(Avatar, { agent: f, size: 48 }),
        h('div', { className: 'flex-1 space-y-2' },
          h('div', { className: 'flex flex-wrap gap-1.5' }, COLORS.map(c => h('button', { key: c, onClick: () => set('color', c), title: c,
            className: cx('h-5 w-5 rounded-full ring-offset-2 ring-offset-zinc-950', f.color === c && 'ring-2 ring-white'), style: { background: c } }))),
          h('div', { className: 'flex flex-wrap gap-1' }, ICON_CHOICES.map(i => h('button', { key: i, onClick: () => set('icon', i),
            className: cx('rounded-md p-1 text-zinc-400 hover:bg-zinc-800 hover:text-white', f.icon === i && 'bg-zinc-800 text-white') }, h(Icon, { name: i, size: 15 })))))),
      h(Field, { label: 'Name' }, h('input', { className: input, value: f.name || '', onChange: e => set('name', e.target.value), placeholder: 'e.g. Inbox helper' })),
      h(Field, { label: 'What it is for', hint: 'Shown on its card and used by team leads to pick who does what.' },
        h('input', { className: input, value: f.description || '', onChange: e => set('description', e.target.value), placeholder: 'e.g. Drafts replies and sorts my email' })),
      h(Field, { label: 'Personality', hint: 'Optional: how it talks and decides (MBTI types, from Octop).' },
        h('div', { className: 'grid grid-cols-4 gap-1.5' },
          [{ code: '', name: 'None' }, ...personalities].map(p => h('button', { key: p.code || 'none', title: p.summary || '', onClick: () => set('mbti', p.code),
            className: cx('rounded-lg border px-2 py-1.5 text-left text-xs transition', (f.mbti || '') === p.code ? 'border-indigo-400 bg-indigo-500/15 text-indigo-100' : 'border-zinc-800 text-zinc-400 hover:border-zinc-600') },
            h('div', { className: 'font-semibold' }, p.code || '—'), h('div', { className: 'truncate text-[10px] opacity-80' }, p.name))))),
      h(Field, { label: 'Instructions', hint: 'How it should work: rules, tone, steps, what to always check. Safety rules and approvals still apply.' },
        h('textarea', { className: input + ' font-mono text-xs', rows: 8, value: f.instructions || '', onChange: e => set('instructions', e.target.value),
          placeholder: 'You help me keep my inbox under control. Always draft replies, never send without asking…' })),
      h(Field, { label: `Skills (${(f.skills || []).length} picked)`, hint: 'Installed SKILL.md skills it should use. Get more on the Skills page.' },
        skills.length ? h('div', { className: 'flex max-h-48 flex-wrap gap-1.5 overflow-y-auto' }, skills.map(s => h('button', { key: s.name, title: s.description, onClick: () => toggleSkill(s.name),
          className: cx('rounded-full border px-2.5 py-1 text-xs', (f.skills || []).includes(s.name) ? 'border-emerald-400/60 bg-emerald-500/15 text-emerald-100' : 'border-zinc-700 text-zinc-400 hover:border-zinc-500') }, s.name)))
          : h('div', { className: 'text-xs text-zinc-500' }, 'No skills installed yet.')),
      h(Field, { label: 'Welcome line', hint: 'Shown when you start a chat with it.' },
        h('input', { className: input, value: f.welcome || '', onChange: e => set('welcome', e.target.value) }))));
}

function TeamEditor({ open, value, agents, onClose, onSave, onDelete }) {
  const [f, setF] = useState(value);
  const [saving, setSaving] = useState(false);
  useEffect(() => { setF(value); }, [value, open]);
  if (!open || !f) return null;
  const set = (k, v) => setF({ ...f, [k]: v });
  const toggle = (id) => set('members', (f.members || []).includes(id) ? f.members.filter(m => m !== id) : [...(f.members || []), id]);
  const save = async () => { setSaving(true); try { await onSave(f); } finally { setSaving(false); } };
  return h(Drawer, { open, title: f.id ? `Edit ${f.name}` : 'New team', onClose, footer: [
    f.id && onDelete ? h(Button, { key: 'd', variant: 'danger', icon: 'trash', onClick: () => { onClose(); onDelete(f); } }, 'Delete') : null,
    h('div', { key: 'sp', className: 'flex-1' }),
    h(Button, { key: 'c', onClick: onClose }, 'Cancel'),
    h(Button, { key: 's', variant: 'primary', icon: 'check', disabled: !String(f.name || '').trim() || (f.members || []).length < 2 || saving, onClick: save }, saving ? 'Saving…' : 'Save team')] },
    h('div', { className: 'space-y-5' },
      h('div', { className: 'rounded-xl border border-sky-500/30 bg-sky-500/10 p-3 text-xs text-sky-100' },
        'A team works like a small company: you talk to its lead, the lead splits the job, hands parts to the members (each with its own persona and skills) and combines their work. You see every member\'s steps live in the chat.'),
      h(Field, { label: 'Team name' }, h('input', { className: input, value: f.name || '', onChange: e => set('name', e.target.value), placeholder: 'e.g. Content studio' })),
      h(Field, { label: 'What it does' }, h('input', { className: input, value: f.description || '', onChange: e => set('description', e.target.value), placeholder: 'e.g. Researches, writes and edits articles' })),
      h(Field, { label: `Members (${(f.members || []).length} picked, at least 2)` },
        h('div', { className: 'grid gap-1.5 sm:grid-cols-2' }, agents.map(a => h('button', { key: a.id, onClick: () => toggle(a.id),
          className: cx('flex items-center gap-2 rounded-xl border px-2.5 py-2 text-left', (f.members || []).includes(a.id) ? 'border-sky-400/60 bg-sky-500/10' : 'border-zinc-800 hover:border-zinc-600') },
          h(Avatar, { agent: a, size: 26 }), h('div', { className: 'min-w-0 flex-1' }, h('div', { className: 'truncate text-sm' }, a.name),
            h('div', { className: 'truncate text-[11px] text-zinc-500' }, a.description || '')),
          (f.members || []).includes(a.id) ? h(Icon, { name: 'check', size: 14, className: 'text-sky-300' }) : null)))),
      h(Field, { label: 'Lead instructions', hint: 'Optional: how the lead should plan, review and combine work.' },
        h('textarea', { className: input, rows: 5, value: f.lead_instructions || '', onChange: e => set('lead_instructions', e.target.value),
          placeholder: 'Have the researcher gather facts first, then the writer drafts, then the editor checks…' }))));
}

// Template groups. Octop ships several templates built for services in mainland China; they are kept in
// their own group (shown on request) so the main list stays useful everywhere.
const TEMPLATE_GROUPS = [
  ['work', 'Work & knowledge', 'briefcase'], ['coding', 'Coding', 'code'], ['ops', 'Ops & security', 'shield'],
  ['life', 'Life', 'heart'], ['china', 'China services', 'globe'],
];
const TEMPLATE_GROUP_OF = {
  'ai-coding-coach': 'coding', 'superpowers-methodology': 'coding', 'multi-agent-orchestrator': 'coding',
  'ops-engineer': 'ops', 'cvm-ai-doctor': 'ops', 'ai-safety-guardian': 'ops',
  'office-automation': 'work', 'general-assistant': 'work', default: 'work', 'karpathy-knowledge-base': 'work',
  'parenting-companion': 'life',
  'meituan-living-assistant': 'china', 'tencentcloud-api': 'china', 'cvm-cluster-doctor': 'china', 'stock-assistant': 'china',
  'news-trend': 'china', 'wechat-ops': 'china', 'clinical-learning-subscription': 'china',
};
const groupOf = t => TEMPLATE_GROUP_OF[t.id] || 'work';

function TemplateCard({ t, hired, hiring, onHire, onDetails }) {
  const prompts = (t.quick_prompts || []).slice(0, 3);
  const skills = t.skills || [];
  return h('div', { className: 'flex flex-col rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 transition hover:border-zinc-700' },
    h('div', { className: 'flex items-start gap-3' }, h(Avatar, { agent: t, size: 40 }),
      h('div', { className: 'min-w-0 flex-1' },
        h('div', { className: 'flex items-center gap-2' },
          h('div', { className: 'truncate font-semibold text-zinc-100', title: t.name }, t.name),
          hired ? h(Badge, { tone: 'green' }, h(Icon, { name: 'check', size: 10 }), 'hired') : null),
        h('div', { className: 'mt-0.5 text-[11px] text-zinc-500' }, (TEMPLATE_GROUPS.find(g => g[0] === groupOf(t)) || [])[1]))),
    h('p', { className: 'mt-3 line-clamp-3 text-xs leading-relaxed text-zinc-400' }, t.description || 'No description'),
    prompts.length ? h('ul', { className: 'mt-3 space-y-1' }, prompts.map(q => h('li', { key: q.title, className: 'flex items-start gap-1.5 text-xs text-zinc-300' },
      h(Icon, { name: 'check', size: 12, className: 'mt-0.5 shrink-0 text-indigo-300' }), h('span', { className: 'line-clamp-1' }, q.title)))) : null,
    h('div', { className: 'mt-auto flex items-center gap-2 pt-4' },
      h('span', { className: 'text-[11px] text-zinc-500' }, skills.length ? `${skills.length} skill${skills.length > 1 ? 's' : ''} included` : 'No extra skills'),
      h('div', { className: 'flex-1' }),
      h(Button, { variant: 'ghost', size: 'sm', onClick: onDetails }, 'Details'),
      h(Button, { variant: hired ? 'default' : 'primary', size: 'sm', icon: 'plus', disabled: hiring, onClick: onHire }, hiring ? 'Hiring…' : hired ? 'Hire again' : 'Hire')));
}

function TemplateDetails({ t, hired, hiring, onHire, onClose }) {
  if (!t) return null;
  return h(Drawer, { open: true, onClose, title: t.name, footer: [
    h(Button, { key: 'c', variant: 'ghost', onClick: onClose }, 'Close'),
    h(Button, { key: 'h', variant: 'primary', icon: 'plus', disabled: hiring, onClick: onHire }, hiring ? 'Hiring…' : hired ? 'Hire again' : 'Hire this agent')] },
    h('div', { className: 'space-y-5 text-sm' },
      h('div', { className: 'flex items-center gap-3' }, h(Avatar, { agent: t, size: 48 }),
        h('div', null, h('div', { className: 'font-semibold' }, t.name),
          h('div', { className: 'text-xs text-zinc-500' }, (TEMPLATE_GROUPS.find(g => g[0] === groupOf(t)) || [])[1], hired ? ' · already hired' : ''))),
      h('p', { className: 'leading-relaxed text-zinc-300' }, t.description),
      groupOf(t) === 'china' ? h('div', { className: 'rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-100' },
        'Built for services in mainland China (its skills call Chinese platforms). It may not be useful elsewhere.') : null,
      t.welcome ? h('div', null, h('div', { className: 'mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-zinc-500' }, 'Says hello with'),
        h('div', { className: 'rounded-xl bg-zinc-900 p-3 text-zinc-300' }, t.welcome)) : null,
      (t.quick_prompts || []).length ? h('div', null, h('div', { className: 'mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-zinc-500' }, 'What you can ask it'),
        h('div', { className: 'space-y-2' }, t.quick_prompts.map(q => h('div', { key: q.title, className: 'rounded-xl border border-zinc-800 p-3' },
          h('div', { className: 'font-medium text-zinc-100' }, q.title),
          q.description ? h('div', { className: 'mt-0.5 text-xs text-zinc-400' }, q.description) : null)))) : null,
      (t.skills || []).length ? h('div', null, h('div', { className: 'mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-zinc-500' }, `Skills it brings (${t.skills.length})`),
        h('div', { className: 'flex flex-wrap gap-1' }, t.skills.map(s => h(Badge, { key: s }, s))),
        h('div', { className: 'mt-1.5 text-[11px] text-zinc-500' }, 'Hiring copies these skills into your skill library; nothing is run.')) : null));
}

function TemplateGallery({ templates, agents, hiring, onHire }) {
  const [group, setGroup] = useState('all');
  const [details, setDetails] = useState(null);
  const hiredIds = new Set(agents.map(a => a.template).filter(Boolean));
  const inGroup = (t, g) => (g === 'all' ? groupOf(t) !== 'china' : groupOf(t) === g);
  const rows = templates.filter(t => inGroup(t, group));
  const hire = async (t) => { await onHire(t); setDetails(null); };
  return h('div', { className: 'space-y-4' },
    h('div', { className: 'flex flex-wrap gap-1.5' }, [['all', 'All', 'sparkles'], ...TEMPLATE_GROUPS].map(([id, label, icon]) => h('button', { key: id, onClick: () => setGroup(id),
      className: cx('flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition', group === id ? 'border-indigo-400 bg-indigo-500/15 text-white' : 'border-zinc-800 text-zinc-400 hover:border-zinc-600 hover:text-zinc-200') },
      h(Icon, { name: icon, size: 12 }), label, h('span', { className: 'text-zinc-500' }, templates.filter(t => inGroup(t, id)).length)))),
    group === 'china' ? h('div', { className: 'rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100' },
      'These templates come from Octop and are built for services in mainland China (Meituan, Tencent Cloud, WeChat, A-share markets, Chinese medical guidelines).') : null,
    rows.length ? h('div', { className: 'grid gap-3 sm:grid-cols-2 xl:grid-cols-3' }, rows.map(t => h(TemplateCard, { key: t.id, t, hired: hiredIds.has(t.id),
      hiring: hiring === t.id, onHire: () => hire(t), onDetails: () => setDetails(t) })))
      : h(Empty, { icon: 'search', title: 'No templates match', text: 'Try another group or search word.' }),
    h(TemplateDetails, { t: details, hired: details && hiredIds.has(details.id), hiring: details && hiring === details.id,
      onHire: () => hire(details), onClose: () => setDetails(null) }));
}

function AgentCard({ a, onChat, onEdit, onDelete, extra }) {
  return h('div', { className: 'group flex flex-col rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 transition hover:border-zinc-700' },
    h('div', { className: 'flex items-start gap-3' }, h(Avatar, { agent: a, size: 40, team: a.team }),
      h('div', { className: 'min-w-0 flex-1' },
        h('div', { className: 'flex items-center gap-2' }, h('div', { className: 'truncate font-semibold text-zinc-100' }, a.name),
          a.mbti ? h(Badge, { tone: 'indigo' }, a.mbti) : null, a.builtin ? h(Badge, null, 'default') : null),
        h('div', { className: 'mt-0.5 line-clamp-2 text-xs text-zinc-400' }, a.description || 'No description'))),
    extra || null,
    (a.skills || []).length ? h('div', { className: 'mt-3 flex flex-wrap gap-1' }, a.skills.slice(0, 6).map(s => h(Badge, { key: s }, s)),
      a.skills.length > 6 ? h(Badge, null, `+${a.skills.length - 6}`) : null) : null,
    h('div', { className: 'mt-auto flex gap-2 pt-4' },
      onChat ? h(Button, { variant: 'primary', size: 'sm', icon: 'message', onClick: onChat }, 'Chat') : null,
      onEdit ? h(Button, { size: 'sm', icon: 'edit', onClick: onEdit }, 'Edit') : null,
      h('div', { className: 'flex-1' }),
      onDelete ? h(Button, { variant: 'ghost', size: 'icon', icon: 'trash', onClick: onDelete, title: 'Delete', className: 'opacity-0 group-hover:opacity-100' }) : null));
}

export function AgentsView({ api, notify, data, reload, onChat }) {
  const [tab, setTab] = useState('mine');
  const [skills, setSkills] = useState([]);
  const [editAgent, setEditAgent] = useState(null);
  const [editTeam, setEditTeam] = useState(null);
  const [hiring, setHiring] = useState('');
  const [query, setQuery] = useState('');
  useEffect(() => { api('/skill-library').then(r => setSkills((r.skills || []).filter(s => s.valid))).catch(() => {}); }, [editAgent]);

  if (!data) return h(Empty, { icon: 'bot', title: 'Loading agents…' });
  const agents = data.agents || [], teams = data.teams || [], templates = data.templates || [];
  const q = query.toLowerCase();
  const match = x => !q || `${x.name} ${x.description}`.toLowerCase().includes(q);

  const saveAgent = async (f) => {
    try {
      const body = { name: f.name, description: f.description || '', icon: f.icon || 'bot', color: f.color || '#6366f1', mbti: f.mbti || '',
        instructions: f.instructions || '', skills: f.skills || [], welcome: f.welcome || '', quick_prompts: f.quick_prompts || [] };
      await api(f.id ? `/experts/agents/${encodeURIComponent(f.id)}` : '/experts/agents', json(f.id ? 'PUT' : 'POST', body));
      setEditAgent(null); notify(`Saved ${f.name}.`); reload();
    } catch (e) { notify(e.message, true); }
  };
  const saveTeam = async (f) => {
    try {
      await api(f.id ? `/experts/teams/${encodeURIComponent(f.id)}` : '/experts/teams', json(f.id ? 'PUT' : 'POST',
        { name: f.name, description: f.description || '', icon: 'users', color: f.color || '#0ea5e9', lead_instructions: f.lead_instructions || '', members: f.members || [] }));
      setEditTeam(null); notify(`Saved team ${f.name}.`); reload();
    } catch (e) { notify(e.message, true); }
  };
  const del = async (kind, x) => {
    if (!globalThis.confirm(`Delete ${kind === 'teams' ? 'team' : 'agent'} "${x.name}"?`)) return;
    try { await api(`/experts/${kind}/${encodeURIComponent(x.id)}`, { method: 'DELETE' }); reload(); } catch (e) { notify(e.message, true); }
  };
  const hire = async (t) => {
    setHiring(t.id);
    try {
      const a = await api('/experts/hire', json('POST', { template: t.id }));
      notify(`${a.name} joined your agents${a.skills_installed && a.skills_installed.length ? ` with ${a.skills_installed.length} skill(s)` : ''}.`);
      reload(); setTab('mine');
    } catch (e) { notify(e.message, true); } finally { setHiring(''); }
  };

  const tabs = [['mine', `My agents (${agents.length})`, 'bot'], ['teams', `Teams (${teams.length})`, 'users'], ['templates', `Templates (${templates.length})`, 'sparkles']];
  const grid = 'grid gap-3 sm:grid-cols-2 xl:grid-cols-3';
  let body;
  if (tab === 'mine') {
    const rows = agents.filter(match);
    body = h('div', { className: grid }, rows.map(a => h(AgentCard, { key: a.id, a, onChat: () => onChat(a.id),
      onEdit: a.builtin ? null : () => setEditAgent(a), onDelete: a.builtin ? null : () => del('agents', a) })));
  } else if (tab === 'teams') {
    const rows = teams.filter(match);
    body = rows.length ? h('div', { className: grid }, rows.map(t => h(AgentCard, { key: t.id, a: { ...t, team: true },
      extra: h('div', { className: 'mt-3 flex -space-x-1.5' }, (t.members || []).map(m => { const a = agents.find(x => x.id === m); return a ? h('span', { key: m, title: a.name, className: 'rounded-xl ring-2 ring-zinc-900' }, h(Avatar, { agent: a, size: 24 })) : null; })),
      onChat: () => onChat(`team:${t.id}`), onEdit: () => setEditTeam(t), onDelete: () => del('teams', t) })))
      : h(Empty, { icon: 'users', title: 'No teams yet', text: 'A team is an agent company: a lead hands parts of a job to member agents. Create one from your agents.',
        action: h(Button, { variant: 'primary', icon: 'plus', onClick: () => setEditTeam({ members: [] }) }, 'New team') });
  } else {
    // search also covers what a template can do (its quick prompts)
    const findable = t => match({ ...t, description: `${t.description} ${(t.quick_prompts || []).map(p => p.title).join(' ')}` });
    body = h(TemplateGallery, { templates: templates.filter(findable), agents, hiring, onHire: hire });
  }

  return h('div', { className: 'mx-auto max-w-6xl space-y-5 p-6' },
    h('div', { className: 'flex flex-wrap items-end gap-3' },
      h('div', { className: 'flex-1' }, h('h1', { className: 'text-xl font-semibold' }, 'Agents & teams'),
        h('p', { className: 'mt-1 text-sm text-zinc-400' }, 'Pick who you work with. Agents have their own personality, instructions and skills; teams split bigger jobs between agents.')),
      h(Button, { icon: 'users', onClick: () => setEditTeam({ members: [] }) }, 'New team'),
      h(Button, { variant: 'primary', icon: 'plus', onClick: () => setEditAgent({ name: '', color: '#6366f1', icon: 'bot', skills: [] }) }, 'New agent')),
    h('div', { className: 'flex flex-wrap items-center gap-2' },
      h('div', { className: 'flex rounded-xl border border-zinc-800 bg-zinc-900/60 p-1' }, tabs.map(([id, label, icon]) => h('button', { key: id, onClick: () => setTab(id),
        className: cx('flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm', tab === id ? 'bg-zinc-800 text-white' : 'text-zinc-400 hover:text-zinc-200') }, h(Icon, { name: icon, size: 14 }), label))),
      h('div', { className: 'flex-1' }),
      h('div', { className: 'relative w-64' }, h(Icon, { name: 'search', size: 14, className: 'absolute left-3 top-2.5 text-zinc-500' }),
        h('input', { className: input + ' pl-8', value: query, onChange: e => setQuery(e.target.value), placeholder: 'Search…' }))),
    body,
    h(AgentEditor, { open: !!editAgent, value: editAgent, personalities: data.personalities || [], skills, onClose: () => setEditAgent(null), onSave: saveAgent, onDelete: a => del('agents', a) }),
    h(TeamEditor, { open: !!editTeam, value: editTeam, agents, onClose: () => setEditTeam(null), onSave: saveTeam, onDelete: t => del('teams', t) }));
}
