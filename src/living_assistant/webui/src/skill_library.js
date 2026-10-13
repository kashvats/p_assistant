/* SKILL.md skills: installed skills, search (installed + SkillHub market), install from a link,
   learn a new skill from notes or a page, read/edit, remove to trash and restore. Skill text is
   rendered as text, never HTML. */
const React = globalThis.React;
const h = React.createElement;
const { useState, useEffect } = React;

const btn = 'px-3 py-1.5 rounded-xl border border-slate-700 bg-slate-800 hover:bg-slate-700 text-xs disabled:opacity-50';
const btnPrimary = 'px-3 py-1.5 rounded-xl border border-brand-500 bg-brand-600 hover:bg-brand-500 text-xs font-medium disabled:opacity-50';
const input = 'w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm';
const json = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

export function SkillLibraryPanel({ api, notify, card }) {
  const [data, setData] = useState(null);
  const [query, setQuery] = useState('');
  const [found, setFound] = useState(null);
  const [source, setSource] = useState('');
  const [learn, setLearn] = useState({ name: '', goal: '', material: '' });
  const [open, setOpen] = useState(null);
  const [edit, setEdit] = useState(null);
  const [busy, setBusy] = useState('');

  // api/notify are new functions on every parent render: load once on mount, then after each change.
  const load = async () => {
    try { setData(await api('/skill-library')); } catch (e) { notify(`Skills: ${e.message}`, true); }
  };
  useEffect(() => { load(); }, []);

  const run = async (key, fn) => {
    setBusy(key);
    try { await fn(); } catch (e) { notify(e.message, true); } finally { setBusy(''); }
  };
  const search = () => run('search', async () => setFound(await api(`/skill-library/search?q=${encodeURIComponent(query)}`)));
  const install = (src, replace = false) => run(`install:${src}`, async () => {
    const r = await api('/skill-library/install', json('POST', { source: src, replace }));
    notify(`Installed: ${r.installed.map(s => s.name).join(', ')}`);
    setSource(''); await load();
  });
  const learnSkill = () => run('learn', async () => {
    const r = await api('/skill-library/learn', json('POST', learn));
    notify(`Learned skill ${r.name}.`);
    setLearn({ name: '', goal: '', material: '' }); await load(); openSkill(r.name);
  });
  const openSkill = (name) => run(`open:${name}`, async () => { setEdit(null); setOpen(await api(`/skill-library/${encodeURIComponent(name)}`)); });
  const saveEdit = () => run('save', async () => {
    await api(`/skill-library/${encodeURIComponent(open.skill)}`, json('PUT', { description: edit.description, instructions: edit.instructions }));
    notify('Skill saved.'); await load(); openSkill(open.skill);
  });
  const remove = (name) => {
    if (!globalThis.confirm(`Remove skill ${name}? It goes to the skill trash and can be restored.`)) return;
    run(`rm:${name}`, async () => { await api(`/skill-library/${encodeURIComponent(name)}`, { method: 'DELETE' }); setOpen(null); await load(); });
  };
  const restore = (t) => run(`restore:${t}`, async () => { await api(`/skill-library/trash/${encodeURIComponent(t)}/restore`, { method: 'POST' }); await load(); });

  const skills = (data && data.skills) || [];
  const installedNames = new Set(skills.map(s => s.name));

  const list = h('div', { className: 'space-y-2 max-h-[22rem] overflow-y-auto' },
    skills.length ? skills.map(s => h('div', { key: s.name, className: 'rounded-xl border border-slate-800 bg-slate-950 p-3' },
      h('div', { className: 'flex items-center gap-2' },
        h('button', { onClick: () => openSkill(s.name), className: 'flex-1 text-left text-sm font-semibold hover:underline' }, s.name),
        s.builtin ? h('span', { className: 'text-[10px] rounded-full border border-slate-700 px-2 text-slate-400' }, 'built-in') : null,
        s.valid ? null : h('span', { className: 'text-[10px] rounded-full border border-rose-800 px-2 text-rose-300' }, 'invalid'),
        s.builtin ? null : h('button', { onClick: () => remove(s.name), title: 'Remove', className: 'text-xs text-rose-300 hover:text-rose-100' }, '🗑')),
      h('div', { className: 'mt-1 text-xs text-slate-400 line-clamp-2' }, s.description || s.error || ''))) :
      h('div', { className: 'text-sm text-slate-500' }, 'No skills installed yet. Search the market below, paste a link, or learn one.'));

  const hubRows = (found && found.skillhub) || [];
  const finder = h('div', { className: 'space-y-2' },
    h('div', { className: 'flex gap-2' },
      h('input', { value: query, onChange: e => setQuery(e.target.value), onKeyDown: e => { if (e.key === 'Enter' && query.trim()) search(); },
        placeholder: 'Find a skill, e.g. excel, invoices, pdf forms…', className: input }),
      h('button', { onClick: search, disabled: !query.trim() || busy === 'search', className: btn }, busy === 'search' ? 'Searching…' : 'Search')),
    found ? h('div', { className: 'space-y-1 max-h-64 overflow-y-auto' },
      found.skillhub_error ? h('div', { className: 'text-xs text-rose-300' }, `SkillHub: ${found.skillhub_error}`) : null,
      hubRows.length ? hubRows.map(r => h('div', { key: r.source, className: 'flex items-start gap-2 rounded-lg border border-slate-800 px-2 py-1.5' },
        h('div', { className: 'min-w-0 flex-1' }, h('div', { className: 'text-sm' }, r.name, h('span', { className: 'ml-2 text-[11px] text-slate-500' }, r.source)),
          h('div', { className: 'text-xs text-slate-400 line-clamp-2' }, r.description)),
        h('button', { onClick: () => install(r.source), disabled: !!busy, className: btn }, busy === `install:${r.source}` ? 'Installing…' : 'Install')))
        : h('div', { className: 'text-xs text-slate-500' }, 'Nothing on SkillHub for that.')) : null,
    h('div', { className: 'flex gap-2 pt-1' },
      h('input', { value: source, onChange: e => setSource(e.target.value),
        placeholder: 'Or install from a GitHub link, ZIP URL, skillhub:<slug>, or a local folder path', className: input }),
      h('button', { onClick: () => install(source.trim()), disabled: !source.trim() || !!busy, className: btnPrimary },
        busy.startsWith('install:') ? 'Installing…' : 'Install')));

  const learner = h('div', { className: 'space-y-2' },
    h('div', { className: 'grid gap-2 md:grid-cols-2' },
      h('input', { value: learn.name, onChange: e => setLearn({ ...learn, name: e.target.value }), placeholder: 'Skill name, e.g. weekly-report', className: input }),
      h('input', { value: learn.goal, onChange: e => setLearn({ ...learn, goal: e.target.value }), placeholder: 'What should it let the assistant do?', className: input })),
    h('textarea', { rows: 4, value: learn.material, onChange: e => setLearn({ ...learn, material: e.target.value }),
      placeholder: 'Paste notes, a how-to, steps that worked… The assistant writes a reusable skill from it. (In chat you can also say "save what we just did as a skill".)',
      className: input + ' resize-y' }),
    h('div', { className: 'flex justify-end' },
      h('button', { onClick: learnSkill, disabled: !learn.name.trim() || !(learn.goal.trim() || learn.material.trim()) || !!busy, className: btnPrimary },
        busy === 'learn' ? 'Learning… (the model writes it)' : '🧠 Learn skill')));

  const trash = (data && data.trash) || [];
  const viewer = open ? h('div', { className: 'space-y-2' },
    h('div', { className: 'flex items-center gap-2' },
      h('div', { className: 'flex-1 text-sm font-semibold' }, open.skill, open.builtin ? ' (built-in)' : ''),
      open.builtin ? null : edit
        ? h('button', { onClick: saveEdit, disabled: !!busy, className: btnPrimary }, 'Save')
        : h('button', { onClick: () => setEdit({ description: open.description || '', instructions: open.instructions || '' }), className: btn }, 'Edit'),
      h('button', { onClick: () => { setOpen(null); setEdit(null); }, className: btn }, 'Close')),
    edit ? h('input', { value: edit.description, onChange: e => setEdit({ ...edit, description: e.target.value }), className: input })
      : h('div', { className: 'text-xs text-slate-400' }, open.description),
    edit ? h('textarea', { rows: 16, value: edit.instructions, onChange: e => setEdit({ ...edit, instructions: e.target.value }), className: input + ' font-mono text-xs' })
      : h('pre', { className: 'max-h-96 overflow-auto whitespace-pre-wrap rounded-xl border border-slate-800 bg-slate-950 p-3 text-xs' }, open.instructions),
    (open.files || []).length > 1 ? h('div', { className: 'text-[11px] text-slate-500' }, `Files: ${open.files.join(', ')}`) : null) : null;

  return h('div', { className: 'grid md:grid-cols-12 gap-3 mb-3' },
    h('div', { className: 'md:col-span-5 space-y-3' },
      card(`Skills (${skills.length})`, list),
      trash.length ? card('Skill trash', h('div', { className: 'space-y-1' }, trash.map(t => h('div', { key: t.trash_name, className: 'flex items-center gap-2 text-xs' },
        h('span', { className: 'flex-1 text-slate-400' }, t.trash_name),
        h('button', { onClick: () => restore(t.trash_name), disabled: !!busy || installedNames.has(t.name), className: btn }, 'Restore'))))) : null),
    h('div', { className: 'md:col-span-7 space-y-3' },
      viewer ? card(null, viewer) : null,
      card('Get skills', finder),
      card('Learn a new skill', learner)));
}
