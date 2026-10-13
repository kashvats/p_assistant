/* AI companies control center: all companies and projects, one company's org chart and skills,
   and a project command center (task board, who works on what, evidence, verification, live timeline).
   Everything shown comes from the persisted company store and its live events. */
import { Badge, Button, Card, Drawer, Empty, Field, Icon, Spinner, cx, describeTool, input, json, timeAgo } from './kit.js';

const React = globalThis.React;
const h = React.createElement;
const { useState, useEffect, useRef, useMemo } = React;

const PROJECT_TONE = { planning: 'sky', awaiting_plan_approval: 'amber', running: 'indigo', paused: 'zinc', needs_user_input: 'amber',
  delivered: 'green', failed: 'red', cancelled: 'zinc' };
const PROJECT_WORDS = { planning: 'Planning', awaiting_plan_approval: 'Plan waits for you', running: 'Running', paused: 'Paused',
  needs_user_input: 'Needs you', delivered: 'Delivered', failed: 'Failed', cancelled: 'Cancelled' };
const COLUMNS = [
  ['waiting', 'Waiting', ['draft', 'blocked']], ['ready', 'Ready', ['ready']], ['working', 'Working', ['assigned', 'in_progress']],
  ['checking', 'Being verified', ['review', 'verification']], ['needs', 'Needs you', ['needs_user_input', 'failed']], ['done', 'Done', ['completed', 'cancelled']],
];
const STATE_WORDS = { draft: 'waiting on others', blocked: 'blocked', ready: 'ready', assigned: 'assigned', in_progress: 'working',
  review: 'automated checks', verification: 'being verified', completed: 'verified', cancelled: 'cancelled', needs_user_input: 'needs you', failed: 'failed' };
const MODES = [['supervised', 'Supervised', 'You approve the plan before work starts'], ['balanced', 'Balanced', 'Starts right away; risky actions still ask you'],
  ['autonomous', 'Autonomous', 'No approvals inside the project folder: build/test commands, test runs and package installs into the project\'s own environment. Anything outside the folder, system, admin or destructive still asks or is blocked.']];

function initials(name) { return String(name || '?').split(/\s+/).map(s => s[0]).join('').slice(0, 2).toUpperCase(); }
function Person({ p, size = 26, stacked = false }) {
  if (!p) return h('span', { className: 'text-zinc-500' }, '—');
  const avatar = h('span', { className: 'grid shrink-0 place-items-center rounded-full bg-zinc-700 text-[10px] font-semibold text-zinc-100', style: { width: size, height: size } }, initials(p.name));
  if (stacked) return h('span', { className: 'flex min-w-0 items-center gap-2' }, avatar,
    h('span', { className: 'min-w-0' }, h('span', { className: 'block truncate text-sm' }, p.name), h('span', { className: 'block truncate text-[11px] text-zinc-500' }, p.title)));
  return h('span', { className: 'inline-flex min-w-0 items-center gap-1.5' }, avatar,
    h('span', { className: 'truncate' }, p.name, p.title ? h('span', { className: 'text-zinc-500' }, ` · ${p.title}`) : null));
}
function Progress({ progress }) {
  const pct = progress && progress.total ? Math.round(100 * progress.completed / progress.total) : 0;
  return h('div', { className: 'flex items-center gap-2' },
    h('div', { className: 'h-1.5 flex-1 overflow-hidden rounded-full bg-zinc-800' }, h('div', { className: 'h-full rounded-full bg-indigo-400', style: { width: `${pct}%` } })),
    h('span', { className: 'w-16 text-right text-[11px] text-zinc-400' }, progress && progress.total ? `${progress.completed}/${progress.total}` : '—'));
}
function SkillChip({ s }) {
  const tone = s.tier === 'learning' || s.available === false ? 'border-dashed border-amber-500/50 text-amber-200'
    : s.tier === 'core' ? 'border-indigo-500/40 bg-indigo-500/10 text-indigo-100' : 'border-zinc-700 text-zinc-300';
  return h('span', { className: cx('rounded-md border px-1.5 py-0.5 text-[10px]', tone),
    title: `${s.tier}${s.layer ? ` · ${s.layer} skill` : ''}${s.available === false || s.tier === 'learning' ? ' · not installed yet' : ''}` }, s.name);
}

// ---- event wording ----------------------------------------------------------------------------

export function describeCompanyEvent(type, d) {
  switch (type) {
    case 'company.planning_started': return { icon: 'brain', text: `${d.name} is planning the project`, tone: 'sky', live: true };
    case 'company.blueprint_used': return { icon: 'layers', text: `Using the ${String(d.blueprint || '').replace('blueprint-', '')} product blueprint`, tone: 'sky' };
    case 'company.plan_rejected': return { icon: 'refresh', text: `Plan rejected by checks, redoing it (${(d.problems || [])[0] || ''})`, tone: 'amber' };
    case 'company.plan_ready': return { icon: 'layers', text: `Plan ready: ${d.tasks} tasks`, tone: 'green' };
    case 'company.plan_approved': return { icon: 'check', text: 'Plan approved, work starts', tone: 'green' };
    case 'company.employee_started': return { icon: d.role === 'verifier' ? 'shield' : 'bot', text: `${d.name} (${d.title}) ${d.role === 'verifier' ? 'started verifying' : 'started working'}`, tone: 'sky', live: true };
    case 'company.employee_step': return { icon: d.ok ? describeTool(d.tool).icon : 'x', text: `${d.name}: ${describeTool(d.tool).words}${d.ok ? '' : ' (failed)'}`, tone: d.ok ? 'zinc' : 'red' };
    case 'company.employee_finished': return { icon: 'clock', text: `${d.name} finished (${d.seconds}s)`, tone: 'zinc' };
    case 'company.verification': return { icon: d.verdict === 'pass' ? 'check' : 'x', text: `${d.name}: ${d.verdict === 'pass' ? 'verified' : `rejected - ${(d.problems || [])[0] || ''}`}`, tone: d.verdict === 'pass' ? 'green' : 'red' };
    case 'company.task_state': return { icon: d.state === 'completed' ? 'check' : 'activity', text: `${d.title}: ${STATE_WORDS[d.state] || d.state}${d.reason && d.state !== 'completed' ? ` - ${String(d.reason).slice(0, 120)}` : ''}`,
      tone: d.state === 'completed' ? 'green' : ['failed', 'needs_user_input'].includes(d.state) ? 'amber' : 'zinc' };
    case 'company.project_status': return { icon: 'target', text: `Project ${PROJECT_WORDS[d.status] || d.status}`, tone: PROJECT_TONE[d.status] === 'green' ? 'green' : 'indigo' };
    case 'company.project_created': return { icon: 'rocket', text: `Project created: ${d.name}`, tone: 'indigo' };
    case 'company.company_created': return { icon: 'briefcase', text: `Company created: ${d.name}`, tone: 'indigo' };
    case 'company.employee_hired': return { icon: 'users', text: `Hired ${d.name} (${d.title})`, tone: 'zinc' };
    case 'company.record_added': return { icon: 'file', text: `${d.title} written`, tone: 'zinc' };
    case 'company.task_error': case 'company.scheduler_error': return { icon: 'x', text: `Error: ${String(d.error || '').slice(0, 140)}`, tone: 'red' };
    default: return null;
  }
}
const TONE = { indigo: 'text-indigo-300', green: 'text-emerald-300', red: 'text-rose-300', sky: 'text-sky-300', amber: 'text-amber-300', zinc: 'text-zinc-400' };

function Timeline({ rows }) {
  const items = [];
  for (let i = rows.length - 1; i >= 0 && items.length < 150; i -= 1) {
    const ev = rows[i]; const w = describeCompanyEvent(`company.${ev.type}`, ev.data || {});
    if (w) items.push(h('div', { key: ev.id, className: 'flex gap-2 py-1.5 text-xs' },
      h('span', { className: cx('mt-0.5 shrink-0', TONE[w.tone]) }, h(Icon, { name: w.icon, size: 13 })),
      h('div', { className: 'min-w-0 flex-1' }, h('div', { className: 'break-words text-zinc-200' }, w.text),
        h('div', { className: 'text-[10px] text-zinc-500' }, timeAgo(ev.created_at)))));
  }
  return items.length ? h('div', { className: 'divide-y divide-zinc-800/60' }, items) : h('div', { className: 'py-6 text-center text-xs text-zinc-500' }, 'Nothing yet.');
}

// ---- dialogs ----------------------------------------------------------------------------------

function NewCompany({ open, onClose, api, notify, templates, onCreated }) {
  const [mode, setMode] = useState('template');
  const [template, setTemplate] = useState('software');
  const [description, setDescription] = useState('');
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  async function create() {
    setBusy(true);
    try {
      const body = mode === 'template' ? { template, name } : { description, name };
      const c = await api('/companies', json('POST', body));
      notify(`${c.name} is ready with ${c.employees.length} employees.`); onCreated(c);
    } catch (e) { notify(e.message, true); } finally { setBusy(false); }
  }
  return h(Drawer, { open, onClose, title: 'New company', footer: [
    h(Button, { key: 'c', variant: 'ghost', onClick: onClose }, 'Cancel'),
    h(Button, { key: 'o', variant: 'primary', icon: busy ? null : 'plus', disabled: busy || (mode === 'describe' && description.trim().length < 10), onClick: create },
      busy ? h(Spinner, {}) : null, busy && mode === 'describe' ? 'Designing the company…' : 'Create company')] },
    h('div', { className: 'space-y-4' },
      h('div', { className: 'flex gap-1 rounded-xl bg-zinc-900 p-1' }, [['template', 'From a template'], ['describe', 'Describe it']].map(([id, label]) =>
        h('button', { key: id, onClick: () => setMode(id), className: cx('flex-1 rounded-lg px-3 py-1.5 text-sm', mode === id ? 'bg-zinc-700 text-white' : 'text-zinc-400') }, label))),
      mode === 'template' ? h('div', { className: 'space-y-2' }, (templates || []).map(t => h('button', { key: t.id, onClick: () => setTemplate(t.id),
        className: cx('block w-full rounded-xl border p-3 text-left', template === t.id ? 'border-indigo-400 bg-indigo-500/10' : 'border-zinc-800 hover:border-zinc-600') },
        h('div', { className: 'flex items-center gap-2' }, h('span', { className: 'flex-1 text-sm font-semibold' }, t.name), h(Badge, {}, `${t.employees} employees`)),
        h('div', { className: 'mt-1 text-xs text-zinc-400' }, t.description),
        h('div', { className: 'mt-2 flex flex-wrap gap-1' }, t.departments.map(d => h('span', { key: d, className: 'rounded-md bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-300' }, d))))))
        : h(Field, { label: 'What should this company do?', hint: 'The local model drafts departments, employees and skills from the installed skills. You can edit everything afterwards.' },
          h('textarea', { className: cx(input, 'h-32'), value: description, onChange: e => setDescription(e.target.value),
            placeholder: 'e.g. A marketing agency that researches my market, writes blog posts and plans social media' })),
      h(Field, { label: 'Name (optional)' }, h('input', { className: input, value: name, onChange: e => setName(e.target.value) }))));
}

function NewProject({ open, onClose, api, notify, companies, preset, onCreated }) {
  const [request, setRequest] = useState('');
  const [company, setCompany] = useState(preset || '');
  const [partners, setPartners] = useState([]);
  const [mode, setMode] = useState('balanced');
  const [trust, setTrust] = useState(false);
  const [folder, setFolder] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) setCompany(preset || (companies[0] && companies[0].id) || ''); }, [open, preset]);
  async function start() {
    setBusy(true);
    try {
      const p = await api('/companies/projects', json('POST', { request, company, partners, mode, trust_commands: trust, folder }));
      notify('Project started. The project director is planning it now.'); setRequest(''); onCreated(p);
    } catch (e) { notify(e.message, true); } finally { setBusy(false); }
  }
  return h(Drawer, { open, onClose, title: 'New project', footer: [
    h(Button, { key: 'c', variant: 'ghost', onClick: onClose }, 'Cancel'),
    h(Button, { key: 'o', variant: 'primary', icon: 'rocket', disabled: busy || request.trim().length < 8 || !company, onClick: start }, 'Start project')] },
    h('div', { className: 'space-y-4' },
      h(Field, { label: 'What should be delivered?', hint: 'Be concrete: what it must do, technology preferences, what "done" means.' },
        h('textarea', { className: cx(input, 'h-40'), value: request, onChange: e => setRequest(e.target.value),
          placeholder: 'e.g. A Python command-line expense tracker that stores entries in SQLite, with tests and a README' })),
      h(Field, { label: 'Lead company' }, h('select', { className: input, value: company, onChange: e => setCompany(e.target.value) },
        companies.map(c => h('option', { key: c.id, value: c.id }, c.name)))),
      companies.length > 1 ? h(Field, { label: 'Partner companies (optional)', hint: 'Only companies you add here may work on the project or see it.' },
        h('div', { className: 'flex flex-wrap gap-2' }, companies.filter(c => c.id !== company).map(c => h('label', { key: c.id,
          className: cx('flex cursor-pointer items-center gap-1.5 rounded-lg border px-2 py-1 text-xs', partners.includes(c.id) ? 'border-indigo-400 text-white' : 'border-zinc-700 text-zinc-400') },
          h('input', { type: 'checkbox', checked: partners.includes(c.id), onChange: e => setPartners(p => e.target.checked ? [...p, c.id] : p.filter(x => x !== c.id)) }), c.name)))) : null,
      h(Field, { label: 'How much freedom?' }, h('div', { className: 'space-y-1.5' }, MODES.map(([id, label, text]) => h('button', { key: id, onClick: () => setMode(id),
        className: cx('block w-full rounded-xl border px-3 py-2 text-left', mode === id ? 'border-indigo-400 bg-indigo-500/10' : 'border-zinc-800') },
        h('div', { className: 'text-sm' }, label), h('div', { className: 'text-[11px] text-zinc-400' }, text))))),
      h('label', { className: cx('flex cursor-pointer items-start gap-3 rounded-xl border px-3 py-2.5 text-left', trust ? 'border-amber-500/50 bg-amber-500/10' : 'border-zinc-800') },
        h('input', { type: 'checkbox', className: 'mt-1', checked: trust, onChange: e => setTrust(e.target.checked) }),
        h('span', null, h('span', { className: 'block text-sm' }, 'Let employees run build and test commands in the project folder without asking'),
          h('span', { className: 'block text-[11px] text-zinc-400' }, 'Only ordinary commands inside this project\'s folder. Installing packages, network, system, privileged and destructive commands still ask you; blocked commands stay blocked.'))),
      h(Field, { label: 'Improve an existing project instead (optional)', hint: 'A registered project name or a folder inside your workspace. Leave empty to build something new in its own folder. Files are snapshotted before changes.' },
        h('input', { className: input, value: folder, onChange: e => setFolder(e.target.value), placeholder: 'e.g. my-shop or C:\\Users\\you\\projects\\my-shop' }))));
}

function EmployeeDrawer({ open, onClose, api, notify, company, employee, department, skills, onSaved }) {
  const blank = { name: '', title: '', level: 'specialist', responsibilities: '', instructions: '', mbti: '', skills: [] };
  const [form, setForm] = useState(blank);
  const [add, setAdd] = useState('');
  useEffect(() => { if (open) setForm(employee ? { ...blank, ...employee, skills: employee.skills || [] } : { ...blank, department_id: department && department.id }); }, [open, employee && employee.id]);
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));
  async function save() {
    try {
      const body = { name: form.name, title: form.title, level: form.level, responsibilities: form.responsibilities, instructions: form.instructions,
        mbti: form.mbti, skills: form.skills, department_id: form.department_id || null };
      if (employee) await api(`/companies/${company.id}/employees/${employee.id}`, json('PATCH', body));
      else await api(`/companies/${company.id}/employees`, json('POST', body));
      notify(employee ? 'Saved.' : `${form.name} hired.`); onSaved();
    } catch (e) { notify(e.message, true); }
  }
  async function remove() {
    if (!confirm(`Remove ${employee.name} from ${company.name}?`)) return;
    try { await api(`/companies/${company.id}/employees/${employee.id}`, { method: 'DELETE' }); notify('Removed.'); onSaved(); } catch (e) { notify(e.message, true); }
  }
  return h(Drawer, { open, onClose, title: employee ? `${employee.name} · ${employee.title}` : `Hire into ${department ? department.name : company && company.name}`, footer: [
    employee ? h(Button, { key: 'd', variant: 'danger', icon: 'trash', onClick: remove }, 'Remove') : null,
    h('div', { key: 's', className: 'flex-1' }),
    h(Button, { key: 'c', variant: 'ghost', onClick: onClose }, 'Cancel'),
    h(Button, { key: 'o', variant: 'primary', disabled: !form.name || !form.title, onClick: save }, employee ? 'Save' : 'Hire')] },
    h('div', { className: 'space-y-3' },
      h('div', { className: 'grid grid-cols-2 gap-3' },
        h(Field, { label: 'Name' }, h('input', { className: input, value: form.name, onChange: e => set('name', e.target.value) })),
        h(Field, { label: 'Title' }, h('input', { className: input, value: form.title, onChange: e => set('title', e.target.value) })),
        h(Field, { label: 'Level' }, h('select', { className: input, value: form.level, onChange: e => set('level', e.target.value) },
          ['director', 'lead', 'specialist'].map(l => h('option', { key: l, value: l }, l)))),
        h(Field, { label: 'Department' }, h('select', { className: input, value: form.department_id || '', onChange: e => set('department_id', e.target.value) },
          (company ? company.departments : []).map(d => h('option', { key: d.id, value: d.id }, d.name))))),
      h(Field, { label: 'Responsibilities' }, h('textarea', { className: cx(input, 'h-20'), value: form.responsibilities, onChange: e => set('responsibilities', e.target.value) })),
      h(Field, { label: 'Extra instructions', hint: 'Added to every task this employee does. They never override safety rules or approvals.' },
        h('textarea', { className: cx(input, 'h-24'), value: form.instructions, onChange: e => set('instructions', e.target.value) })),
      h(Field, { label: 'Skills', hint: 'Core and specialist skills are loaded into every task; supporting ones are known in outline. Learning = not installed yet.' },
        h('div', { className: 'space-y-1.5' },
          form.skills.map((s, i) => h('div', { key: s.name, className: 'flex items-center gap-2' },
            h('span', { className: 'flex-1 text-sm' }, s.name),
            h('select', { className: 'rounded-lg border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs', value: s.tier,
              onChange: e => set('skills', form.skills.map((x, j) => j === i ? { ...x, tier: e.target.value } : x)) },
              ['core', 'specialist', 'supporting', 'learning'].map(t => h('option', { key: t, value: t }, t))),
            h(Button, { variant: 'ghost', size: 'icon', icon: 'x', onClick: () => set('skills', form.skills.filter((_, j) => j !== i)) }))),
          h('div', { className: 'flex gap-2' },
            h('select', { className: input, value: add, onChange: e => setAdd(e.target.value) },
              h('option', { value: '' }, 'Add a skill…'), (skills || []).filter(n => !form.skills.some(s => s.name === n)).map(n => h('option', { key: n, value: n }, n))),
            h(Button, { disabled: !add, onClick: () => { set('skills', [...form.skills, { name: add, tier: 'specialist' }]); setAdd(''); } }, 'Add'))))));
}

function TaskDrawer({ task, people, onClose, api, notify, reload }) {
  const [note, setNote] = useState('');
  if (!task) return null;
  const ev = task.evidence || {};
  const v = ev.verification || {};
  async function retry() {
    try { await api(`/companies/tasks/${task.id}/retry`, json('POST', { note })); notify('Sent back to work.'); setNote(''); reload(); onClose(); }
    catch (e) { notify(e.message, true); }
  }
  const section = (title, body) => body ? h('div', { className: 'space-y-1.5' }, h('div', { className: 'text-[11px] font-semibold uppercase tracking-wider text-zinc-500' }, title), body) : null;
  return h(Drawer, { open: true, onClose, title: task.title, width: 'max-w-2xl' },
    h('div', { className: 'space-y-5 text-sm' },
      h('div', { className: 'flex flex-wrap items-center gap-2' }, h(Badge, { tone: task.state === 'completed' ? 'green' : ['failed', 'needs_user_input'].includes(task.state) ? 'amber' : 'indigo' }, STATE_WORDS[task.state] || task.state),
        h(Badge, {}, `attempt ${task.attempts}`), task.running ? h(Badge, { tone: 'sky' }, h(Spinner, { size: 10 }), 'running now') : null),
      h('div', { className: 'grid grid-cols-2 gap-3 text-xs' },
        h('div', null, h('div', { className: 'mb-1 text-zinc-500' }, 'Does the work'), h(Person, { p: people[task.assignee] })),
        h('div', null, h('div', { className: 'mb-1 text-zinc-500' }, 'Verifies it'), h(Person, { p: people[task.verifier] }))),
      section('Task', h('div', { className: 'whitespace-pre-wrap text-zinc-300' }, task.description)),
      section('Acceptance criteria', h('ul', { className: 'list-disc space-y-0.5 pl-5 text-zinc-300' }, task.acceptance.map((a, i) => h('li', { key: i }, a)))),
      task.deliverables.length ? section('Files to deliver', h('div', { className: 'flex flex-wrap gap-1' }, task.deliverables.map(d => h('code', { key: d, className: 'rounded bg-zinc-800 px-1.5 py-0.5 text-xs' }, d)))) : null,
      task.depends.length ? section('Waits for', h('div', { className: 'text-zinc-300' }, task.depends.join(', '), task.unmet && task.unmet.length ? h('span', { className: 'text-amber-300' }, ` (still open: ${task.unmet.join(', ')})`) : null)) : null,
      task.feedback && task.state !== 'completed' ? section('Last feedback', h('div', { className: 'whitespace-pre-wrap rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-amber-100' }, task.feedback)) : null,
      ['failed', 'needs_user_input', 'blocked'].includes(task.state) ? section('Send it back', h('div', { className: 'space-y-2' },
        task.approval_id ? h('div', { className: 'text-xs text-amber-200' }, 'This task waits for an approval - approve it with the bell at the top; it continues on its own.') : null,
        h('textarea', { className: cx(input, 'h-20'), value: note, onChange: e => setNote(e.target.value), placeholder: 'Optional guidance for the next attempt' }),
        h(Button, { variant: 'primary', icon: 'refresh', onClick: retry }, 'Retry task'))) : null,
      ev.checks ? section('Automated evidence checks', h('div', { className: 'space-y-1' }, ev.checks.map((c, i) => h('div', { key: i, className: 'flex items-start gap-2 text-xs' },
        h(Icon, { name: c.ok ? 'check' : 'x', size: 13, className: c.ok ? 'text-emerald-300' : 'text-rose-300' }),
        h('span', { className: 'flex-1' }, c.name, h('span', { className: 'text-zinc-500' }, ` - ${c.detail}`)))),
        (ev.warnings || []).map((w, i) => h('div', { key: `w${i}`, className: 'text-xs text-amber-300' }, `Note: ${w}`)))) : null,
      v.criteria && v.criteria.length ? section(`Verification by ${(people[ev.verified_by] || {}).name || 'the verifier'}`, h('div', { className: 'space-y-1.5' }, v.criteria.map((c, i) => h('div', { key: i, className: 'rounded-lg border border-zinc-800 p-2 text-xs' },
        h('div', { className: 'flex items-center gap-1.5' }, h(Icon, { name: c.ok ? 'check' : 'x', size: 13, className: c.ok ? 'text-emerald-300' : 'text-rose-300' }), h('span', { className: 'font-medium' }, c.criterion)),
        h('div', { className: 'mt-1 text-zinc-400' }, String(c.evidence || '')))))) : null,
      ev.tool_calls && ev.tool_calls.length ? section('What the worker did', h('div', { className: 'space-y-0.5' }, ev.tool_calls.map((c, i) => h('div', { key: i, className: 'flex items-center gap-2 text-xs' },
        h(Icon, { name: c.ok ? describeTool(c.tool).icon : 'x', size: 12, className: c.ok ? 'text-zinc-400' : 'text-rose-300' }),
        h('span', { className: 'shrink-0 text-zinc-200' }, describeTool(c.tool).words), h('span', { className: 'truncate text-zinc-500' }, c.args))))) : null,
      task.result ? section('Worker report', h('div', { className: 'max-h-72 overflow-y-auto whitespace-pre-wrap rounded-xl bg-zinc-900 p-3 text-xs text-zinc-300' }, task.result)) : null));
}

// ---- pages ------------------------------------------------------------------------------------

function Overview({ api, notify, data, reload }) {
  const [newCompany, setNewCompany] = useState(false);
  const [newProject, setNewProject] = useState(false);
  if (!data) return h('div', { className: 'grid h-64 place-items-center' }, h(Spinner, {}));
  const companies = data.companies;
  return h('div', { className: 'mx-auto max-w-6xl space-y-6 p-6' },
    h('div', { className: 'flex flex-wrap items-end gap-3' },
      h('div', { className: 'flex-1' }, h('h1', { className: 'text-xl font-semibold' }, 'Companies'),
        h('p', { className: 'mt-1 max-w-2xl text-sm text-zinc-400' }, 'Give a project to a company: its project director plans it, employees with the right skills do each task, and a different employee verifies every result with real evidence before it counts as done.')),
      h(Button, { icon: 'plus', onClick: () => setNewCompany(true) }, 'New company'),
      h(Button, { variant: 'primary', icon: 'rocket', disabled: !companies.length, onClick: () => setNewProject(true) }, 'New project')),
    companies.length ? h('div', { className: 'grid gap-3 sm:grid-cols-2 lg:grid-cols-3' }, companies.map(c => h('a', { key: c.id, href: `#/companies/${c.id}`,
      className: 'block rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 transition hover:border-zinc-600' },
      h('div', { className: 'flex items-center gap-2' }, h('span', { className: 'rounded-xl bg-indigo-500/15 p-2 text-indigo-300' }, h(Icon, { name: 'briefcase', size: 18 })),
        h('div', { className: 'min-w-0 flex-1' }, h('div', { className: 'truncate font-semibold' }, c.name), h('div', { className: 'text-[11px] text-zinc-500' }, `${c.departments} departments · ${c.employees} employees`)),
        c.status !== 'active' ? h(Badge, { tone: 'amber' }, c.status) : null),
      h('p', { className: 'mt-2 line-clamp-2 text-xs text-zinc-400' }, c.description))))
      : h(Card, {}, h(Empty, { icon: 'briefcase', title: 'No companies yet', text: 'Start from a template - the Software Development Company has every department from product to verification - or describe your own.',
        action: h(Button, { variant: 'primary', icon: 'plus', onClick: () => setNewCompany(true) }, 'Create a company') })),
    h(Card, { title: 'Projects', pad: true }, data.projects.length ? h('div', { className: 'divide-y divide-zinc-800' }, data.projects.map(p => h('div', { key: p.id,
      className: 'group flex items-center gap-3 py-2.5 hover:bg-zinc-900/60' },
      h('a', { href: `#/companies/${p.id}`, className: 'min-w-0 flex-1' },
        h('div', { className: 'truncate text-sm hover:underline' }, p.name),
        h('div', { className: 'text-[11px] text-zinc-500' }, `${(companies.find(c => c.id === p.lead_company) || {}).name || 'company'} · ${p.mode} · ${timeAgo(p.updated_at)}`)),
      h('div', { className: 'w-40' }, h(Progress, { progress: p.progress })),
      h(Badge, { tone: PROJECT_TONE[p.status] }, PROJECT_WORDS[p.status] || p.status),
      h(Button, { variant: 'ghost', size: 'icon', icon: 'trash', title: 'Delete project', className: 'opacity-0 group-hover:opacity-100',
        onClick: async (e) => {
          e.stopPropagation();
          if (!confirm(`Delete project "${p.name}"?`)) return;
          try {
            try {
              await api(`/companies/projects/${p.id}`, { method: 'DELETE' });
            } catch (err) {
              if (String(err.message || '').includes('405')) {
                await api(`/companies/projects/${p.id}/delete`, { method: 'POST' });
              } else {
                throw err;
              }
            }
            notify('Project deleted.'); reload();
          } catch (err) { notify(err.message, true); }
        } })))) : h('div', { className: 'py-4 text-center text-sm text-zinc-500' }, 'No projects yet.')),
    h(NewCompany, { open: newCompany, onClose: () => setNewCompany(false), api, notify, templates: data.templates, onCreated: c => { setNewCompany(false); reload(); location.hash = `/companies/${c.id}`; } }),
    h(NewProject, { open: newProject, onClose: () => setNewProject(false), api, notify, companies, onCreated: p => { setNewProject(false); reload(); location.hash = `/companies/${p.id}`; } }));
}

function CompanyPage({ api, notify, id, skills, companies, reloadAll, tick }) {
  const [c, setC] = useState(null);
  const [edit, setEdit] = useState(null);
  const [newProject, setNewProject] = useState(false);
  const load = () => api(`/companies/${id}`).then(setC).catch(e => notify(e.message, true));
  useEffect(() => { load(); }, [id, tick]);
  if (!c) return h('div', { className: 'grid h-64 place-items-center' }, h(Spinner, {}));
  const people = Object.fromEntries(c.employees.map(e => [e.id, e]));
  async function setStatus(status) { try { await api(`/companies/${id}`, json('PATCH', { status })); load(); reloadAll(); } catch (e) { notify(e.message, true); } }
  async function addDepartment() {
    const name = prompt('Department name'); if (!name) return;
    try { await api(`/companies/${id}/departments`, json('POST', { name })); load(); } catch (e) { notify(e.message, true); }
  }
  return h('div', { className: 'mx-auto max-w-7xl space-y-5 p-6' },
    h('a', { href: '#/companies', className: 'text-xs text-zinc-500 hover:text-zinc-300' }, '← All companies'),
    h('div', { className: 'flex flex-wrap items-start gap-3' },
      h('div', { className: 'min-w-0 flex-1' }, h('h1', { className: 'text-xl font-semibold' }, c.name),
        h('p', { className: 'mt-1 max-w-3xl text-sm text-zinc-400' }, c.mission || c.description),
        h('div', { className: 'mt-2 flex flex-wrap gap-1' }, h('span', { className: 'text-[11px] text-zinc-500' }, 'Company skills:'), (c.skills || []).map(s => h(SkillChip, { key: s, s: { name: s, tier: 'supporting' } })))),
      c.status === 'active' ? h(Button, { icon: 'stop', onClick: () => setStatus('paused') }, 'Pause') : h(Button, { icon: 'check', onClick: () => setStatus('active') }, 'Activate'),
      h(Button, { icon: 'plus', onClick: addDepartment }, 'Department'),
      h(Button, { variant: 'primary', icon: 'rocket', disabled: c.status !== 'active', onClick: () => setNewProject(true) }, 'New project')),
    h('div', { className: 'grid gap-3 md:grid-cols-2 xl:grid-cols-3' }, c.departments.map(d => {
      const staff = c.employees.filter(e => e.department_id === d.id);
      return h('section', { key: d.id, className: 'rounded-2xl border border-zinc-800 bg-zinc-900/50 p-3' },
        h('div', { className: 'mb-2 flex items-start gap-2' },
          h('div', { className: 'min-w-0 flex-1' }, h('div', { className: 'text-sm font-semibold' }, d.name), h('div', { className: 'line-clamp-2 text-[11px] text-zinc-500' }, d.mission)),
          h(Button, { variant: 'ghost', size: 'icon', icon: 'plus', title: 'Hire', onClick: () => setEdit({ dep: d }) })),
        h('div', { className: 'space-y-1.5' }, staff.map(e => h('div', { key: e.id,
          className: 'group flex items-center gap-2 rounded-xl border border-zinc-800 bg-zinc-950/60 p-2 hover:border-zinc-600' },
          h('button', { onClick: () => setEdit({ emp: e, dep: d }), className: 'min-w-0 flex-1 text-left' },
            h('div', { className: 'flex items-center gap-2 text-sm' }, h(Person, { p: e, stacked: true }),
              h('span', { className: 'flex-1' }), e.level !== 'specialist' ? h(Badge, { tone: e.level === 'director' ? 'indigo' : 'sky' }, e.level) : null,
              e.workload ? h(Badge, { tone: 'amber' }, `${e.workload} task${e.workload > 1 ? 's' : ''}`) : null),
            e.reports_to && people[e.reports_to] ? h('div', { className: 'mt-0.5 pl-8 text-[10px] text-zinc-500' }, `reports to ${people[e.reports_to].name}`) : null,
            h('div', { className: 'mt-1.5 flex flex-wrap gap-1 pl-8' }, (e.portfolio || e.skills).filter(s => s.layer !== 'company').map(s => h(SkillChip, { key: s.name, s })))),
          h(Button, { variant: 'ghost', size: 'icon', icon: 'trash', title: 'Remove', className: 'opacity-0 group-hover:opacity-100',
            onClick: async (ev) => {
              ev.stopPropagation();
              if (!confirm(`Remove ${e.name} from ${c.name}?`)) return;
              try { await api(`/companies/${id}/employees/${e.id}`, { method: 'DELETE' }); notify('Removed.'); load(); reloadAll(); } catch (err) { notify(err.message, true); }
            } })))),
        staff.length ? null : h('div', { className: 'py-3 text-center text-xs text-zinc-500' }, 'Nobody yet.'));
    })),
    h('div', { className: 'grid gap-4 lg:grid-cols-[1fr_22rem]' },
      h(Card, { title: 'Projects' }, c.projects.length ? h('div', { className: 'divide-y divide-zinc-800' }, c.projects.map(p => h('div', { key: p.id,
        className: 'group flex items-center gap-3 py-2 hover:bg-zinc-900/60' },
        h('a', { href: `#/companies/${p.id}`, className: 'flex-1 truncate text-sm hover:underline' }, p.name),
        h('div', { className: 'w-32' }, h(Progress, { progress: p.progress })),
        h(Badge, { tone: PROJECT_TONE[p.status] }, PROJECT_WORDS[p.status]),
        h(Button, { variant: 'ghost', size: 'icon', icon: 'trash', title: 'Delete project', className: 'opacity-0 group-hover:opacity-100',
          onClick: async (e) => {
            e.stopPropagation();
            if (!confirm(`Delete project "${p.name}"?`)) return;
            try {
              try {
                await api(`/companies/projects/${p.id}`, { method: 'DELETE' });
              } catch (err) {
                if (String(err.message || '').includes('405')) {
                  await api(`/companies/projects/${p.id}/delete`, { method: 'POST' });
                } else {
                  throw err;
                }
              }
              notify('Project deleted.'); load(); reloadAll();
            } catch (err) { notify(err.message, true); }
          } })))) : h('div', { className: 'text-sm text-zinc-500' }, 'No projects yet.')),
      h(Card, { title: 'Recent activity' }, h(Timeline, { rows: c.events }))),
    h(EmployeeDrawer, { open: !!edit, onClose: () => setEdit(null), api, notify, company: c, employee: edit && edit.emp, department: edit && edit.dep, skills,
      onSaved: () => { setEdit(null); load(); reloadAll(); } }),
    h(NewProject, { open: newProject, onClose: () => setNewProject(false), api, notify, companies, preset: id,
      onCreated: p => { setNewProject(false); reloadAll(); location.hash = `/companies/${p.id}`; } }));
}

function ProjectPage({ api, notify, id, tick }) {
  const [v, setV] = useState(null);
  const [open, setOpen] = useState(null);
  const [tab, setTab] = useState('board');
  const load = () => api(`/companies/projects/${id}`).then(setV).catch(e => notify(e.message, true));
  useEffect(() => { load(); }, [id, tick]);
  useEffect(() => { const t = setInterval(load, 5000); return () => clearInterval(t); }, [id]);  // also catches work in other processes
  if (!v) return h('div', { className: 'grid h-64 place-items-center' }, h(Spinner, {}));
  const p = v.project;
  const act = async (a) => { try { await api(`/companies/projects/${id}/${a}`, { method: 'POST' }); load(); } catch (e) { notify(e.message, true); } };
  const running = v.tasks.filter(t => t.running);
  const records = Object.fromEntries(v.records.map(r => [r.kind, r]));
  const openTask = open && v.tasks.find(t => t.id === open);
  return h('div', { className: 'flex h-full min-h-0' },
    h('div', { className: 'min-w-0 flex-1 overflow-y-auto' }, h('div', { className: 'space-y-4 p-6' },
      h('a', { href: '#/companies', className: 'text-xs text-zinc-500 hover:text-zinc-300' }, '← Companies'),
      h('div', { className: 'flex flex-wrap items-start gap-3' },
        h('div', { className: 'min-w-0 flex-1' },
          h('div', { className: 'flex items-center gap-2' }, h('h1', { className: 'truncate text-xl font-semibold' }, p.name), h(Badge, { tone: PROJECT_TONE[p.status] }, PROJECT_WORDS[p.status] || p.status), h(Badge, {}, p.mode),
            p.mode === 'autonomous' ? h(Badge, { tone: 'amber', className: 'whitespace-nowrap' }, 'no approvals in folder') : p.trust_commands ? h(Badge, { tone: 'amber' }, 'commands trusted') : null, p.existing_folder ? h(Badge, { tone: 'sky' }, 'existing project') : null),
          h('div', { className: 'mt-1 text-xs text-zinc-500' }, v.companies.map(c => c.name).join(' + '), ' · ', h('code', { className: 'text-zinc-400' }, p.workspace))),
        !['delivered', 'cancelled'].includes(p.status) ? h('select', { className: 'rounded-xl border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm', value: p.mode,
          title: 'How much freedom the company has (changes apply from the next step)',
          onChange: async e => { try { await api(`/companies/projects/${id}/mode`, json('PUT', { mode: e.target.value })); notify(`Mode: ${e.target.value}.`); load(); } catch (err) { notify(err.message, true); } } },
          MODES.map(([mid, label]) => h('option', { key: mid, value: mid }, label))) : null,
        p.status === 'awaiting_plan_approval' ? h(Button, { variant: 'success', icon: 'check', onClick: () => act('approve') }, 'Approve plan') : null,
        p.status === 'running' ? h(Button, { icon: 'stop', onClick: () => act('pause') }, 'Pause') : null,
        ['paused', 'needs_user_input', 'failed'].includes(p.status) ? h(Button, { variant: 'primary', icon: 'refresh', onClick: () => act('resume') }, 'Resume') : null,
        !['delivered', 'cancelled'].includes(p.status) ? h(Button, { variant: 'danger', icon: 'x', onClick: () => confirm('Cancel this project?') && act('cancel') }, 'Cancel') : null,
        h(Button, { variant: 'danger', icon: 'trash', title: 'Delete project', onClick: async () => {
          if (!confirm(`Delete project "${p.name}"? This cannot be undone.`)) return;
          try {
            try {
              await api(`/companies/projects/${id}`, { method: 'DELETE' });
            } catch (err) {
              if (String(err.message || '').includes('405')) {
                await api(`/companies/projects/${id}/delete`, { method: 'POST' });
              } else {
                throw err;
              }
            }
            notify('Project deleted.'); location.hash = '/companies';
          } catch (err) { notify(err.message, true); }
        } }, 'Delete')),
      h(Progress, { progress: p.progress }),
      p.error ? h('div', { className: 'rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-100' }, p.error) : null,
      p.status === 'planning' ? h('div', { className: 'flex items-center gap-2 rounded-xl border border-sky-500/30 bg-sky-500/10 px-3 py-2 text-sm text-sky-100' }, h(Spinner, {}), 'The project director is writing the specification and plan…') : null,
      running.length ? h('div', { className: 'flex flex-wrap gap-2' }, running.map(t => h('div', { key: t.id, className: 'flex items-center gap-2 rounded-xl border border-indigo-500/40 bg-indigo-500/10 px-3 py-1.5 text-sm text-indigo-100' },
        h(Spinner, { size: 12 }), `${(v.people[t.state === 'verification' ? t.verifier : t.assignee] || {}).name || 'Someone'} · ${t.title} · ${STATE_WORDS[t.state]}`))) : null,
      h('div', { className: 'flex gap-1 border-b border-zinc-800' }, [['board', 'Task board'], ['spec', 'Specification'], ['plan', 'Plan'], ['report', 'Delivery report']].map(([k, label]) =>
        h('button', { key: k, onClick: () => setTab(k), className: cx('border-b-2 px-3 pb-2 text-sm', tab === k ? 'border-indigo-400 text-white' : 'border-transparent text-zinc-400') }, label))),
      tab === 'board' ? (v.tasks.length ? h('div', { className: 'grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6' }, COLUMNS.map(([key, label, states]) => {
        const items = v.tasks.filter(t => states.includes(t.state));
        return h('div', { key, className: 'min-w-0 rounded-2xl border border-zinc-800 bg-zinc-900/40 p-2' },
          h('div', { className: 'mb-2 flex items-center px-1 text-xs font-semibold text-zinc-400' }, h('span', { className: 'flex-1' }, label), items.length),
          h('div', { className: 'space-y-2' }, items.map(t => h('button', { key: t.id, onClick: () => setOpen(t.id),
            className: cx('block w-full rounded-xl border bg-zinc-950 p-2.5 text-left text-xs hover:border-zinc-500', t.running ? 'border-indigo-500/60' : 'border-zinc-800') },
            h('div', { className: 'flex items-start gap-1.5' }, t.running ? h(Spinner, { size: 11 }) : null, h('span', { className: 'flex-1 text-[13px] text-zinc-100' }, t.title)),
            h('div', { className: 'mt-1.5 text-zinc-400' }, h(Person, { p: v.people[t.assignee], size: 18 })),
            h('div', { className: 'mt-1 flex items-center gap-1 text-[10px] text-zinc-500' }, h(Icon, { name: 'shield', size: 10 }), `verified by ${(v.people[t.verifier] || {}).name || '—'}`),
            t.attempts > 1 ? h('div', { className: 'mt-1 text-[10px] text-amber-300' }, `attempt ${t.attempts}`) : null,
            t.unmet && t.unmet.length && t.state === 'draft' ? h('div', { className: 'mt-1 text-[10px] text-zinc-500' }, `after ${t.unmet.join(', ')}`) : null))));
      })) : h(Card, {}, h(Empty, { icon: 'layers', title: p.status === 'planning' ? 'Planning…' : 'No tasks', text: 'Tasks appear here once the plan is ready.' })))
        : h(Card, {}, records[tab] ? h('div', { className: 'whitespace-pre-wrap text-sm leading-relaxed text-zinc-200' }, records[tab].body)
          : h('div', { className: 'text-sm text-zinc-500' }, tab === 'report' ? 'Written when every task is verified.' : 'Not written yet.')),
      h('div', { className: 'grid gap-4 2xl:block' },
        h(Card, { title: 'Live timeline', className: '2xl:hidden' }, h('div', { className: 'max-h-96 overflow-y-auto' }, h(Timeline, { rows: v.events }))),
        h(Card, { title: 'Request' }, h('div', { className: 'whitespace-pre-wrap text-sm text-zinc-300' }, p.request))))),
    h('aside', { className: 'hidden w-80 shrink-0 flex-col border-l border-zinc-800 2xl:flex' },
      h('div', { className: 'border-b border-zinc-800 px-4 py-3 text-sm font-semibold' }, 'Live timeline'),
      h('div', { className: 'flex-1 overflow-y-auto px-4' }, h(Timeline, { rows: v.events }))),
    openTask ? h(TaskDrawer, { task: openTask, people: v.people, onClose: () => setOpen(null), api, notify, reload: load }) : null);
}

export function CompaniesView({ api, notify, sub, events }) {
  const [data, setData] = useState(null);
  const reload = () => api('/companies').then(setData).catch(e => notify(`Companies: ${e.message}`, true));
  useEffect(() => { reload(); }, []);
  // refresh when company events arrive (throttled)
  const lastCompanyEvent = useMemo(() => { for (let i = events.length - 1; i >= 0; i -= 1) if (/^company\./.test(events[i].type)) return events[i].id; return 0; }, [events]);
  const [tick, setTick] = useState(0);
  const timer = useRef(null);
  useEffect(() => {
    if (!lastCompanyEvent) return;
    clearTimeout(timer.current); timer.current = setTimeout(() => { setTick(t => t + 1); if (!sub) reload(); }, 600);
  }, [lastCompanyEvent]);
  if (sub && sub.startsWith('prj_')) return h(ProjectPage, { api, notify, id: sub, tick });
  if (sub && sub.startsWith('co_')) return h('div', { className: 'h-full overflow-y-auto' },
    h(CompanyPage, { api, notify, id: sub, skills: data && data.skills, companies: (data && data.companies) || [], reloadAll: reload, tick }));
  return h('div', { className: 'h-full overflow-y-auto' }, h(Overview, { api, notify, data, reload }));
}
