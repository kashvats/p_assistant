/* Shared UI kit for the shell: icons (lucide-style, inline SVG), buttons, avatars, badges, drawers,
   and the human wording for what the agent is doing. Text from models or the web is always rendered
   as text, never HTML. */
const React = globalThis.React;
const h = React.createElement;

export const cx = (...p) => p.filter(Boolean).join(' ');

// lucide icon paths (MIT, lucide.dev), drawn with stroke="currentColor"
const ICONS = {
  sparkles: ['M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z', 'M20 3v4', 'M22 5h-4'],
  bot: ['M12 8V4H8', 'M2 14h2', 'M20 14h2', 'M15 13v2', 'M9 13v2', 'rect:4,8,16,12,2'],
  users: ['M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2', 'circle:9,7,4', 'M22 21v-2a4 4 0 0 0-3-3.87', 'M16 3.13a4 4 0 0 1 0 7.75'],
  message: ['M7.9 20A9 9 0 1 0 4 16.1L2 22Z'],
  plus: ['M5 12h14', 'M12 5v14'],
  send: ['M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z', 'm21.854 2.147-10.94 10.939'],
  stop: ['rect:6,6,12,12,2'],
  paperclip: ['m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48'],
  check: ['M20 6 9 17l-5-5'],
  x: ['M18 6 6 18', 'm6 6 12 12'],
  hand: ['M18 11V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2', 'M14 10V4a2 2 0 0 0-2-2a2 2 0 0 0-2 2v2', 'M10 10.5V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2v8', 'M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15'],
  bell: ['M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9', 'M10.3 21a1.94 1.94 0 0 0 3.4 0'],
  activity: ['M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2'],
  zap: ['M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z'],
  settings: ['M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z', 'circle:12,12,3'],
  wrench: ['M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z'],
  shield: ['M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z'],
  cpu: ['rect:4,4,16,16,2', 'rect:9,9,6,6,1', 'M15 2v2', 'M15 20v2', 'M2 15h2', 'M2 9h2', 'M20 15h2', 'M20 9h2', 'M9 2v2', 'M9 20v2'],
  calendar: ['M8 2v4', 'M16 2v4', 'rect:3,4,18,18,2', 'M3 10h18'],
  briefcase: ['M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16', 'rect:2,6,20,14,2'],
  book: ['M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H19a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6.5a1 1 0 0 1 0-5H20'],
  search: ['circle:11,11,8', 'm21 21-4.3-4.3'],
  trash: ['M3 6h18', 'M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6', 'M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2'],
  edit: ['M12 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7', 'M18.375 2.625a1 1 0 0 1 3 3l-9.013 9.014a2 2 0 0 1-.853.505l-2.873.84a.5.5 0 0 1-.62-.62l.84-2.873a2 2 0 0 1 .506-.852z'],
  chevronDown: ['m6 9 6 6 6-6'],
  chevronRight: ['m9 18 6-6-6-6'],
  power: ['M12 2v10', 'M18.4 6.6a9 9 0 1 1-12.77.04'],
  globe: ['circle:12,12,10', 'M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20', 'M2 12h20'],
  file: ['M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z', 'M14 2v4a2 2 0 0 0 2 2h4'],
  code: ['m16 18 6-6-6-6', 'm8 6-6 6 6 6'],
  terminal: ['m4 17 6-6-6-6', 'M12 19h8'],
  brain: ['M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z', 'M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z', 'M12 5v13'],
  folder: ['M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z'],
  menu: ['M4 12h16', 'M4 6h16', 'M4 18h16'],
  panelRight: ['rect:3,3,18,18,2', 'M15 3v18'],
  clock: ['circle:12,12,10', 'M12 6v6l4 2'],
  table: ['M12 3v18', 'rect:3,3,18,18,2', 'M3 9h18', 'M3 15h18'],
  target: ['circle:12,12,10', 'circle:12,12,6', 'circle:12,12,2'],
  heart: ['M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z'],
  trendingUp: ['M22 7 13.5 15.5 8.5 10.5 2 17', 'M16 7h6v6'],
  newspaper: ['M15 18h-5', 'M18 14h-8', 'M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-4 0v-9a2 2 0 0 1 2-2h2', 'rect:10,6,8,4,1'],
  graduation: ['M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z', 'M22 10v6', 'M6 12.5V16a6 3 0 0 0 12 0v-3.5'],
  stethoscope: ['M11 2v2', 'M5 2v2', 'M5 3H4a2 2 0 0 0-2 2v4a6 6 0 0 0 12 0V5a2 2 0 0 0-2-2h-1', 'M8 15a6 6 0 0 0 12 0v-3', 'circle:20,10,2'],
  baby: ['M9 12h.01', 'M15 12h.01', 'M10 16c.5.3 1.2.5 2 .5s1.5-.2 2-.5', 'M19 6.3a9 9 0 0 1 1.8 3.9 2 2 0 0 1 0 3.6 9 9 0 0 1-17.6 0 2 2 0 0 1 0-3.6A9 9 0 0 1 12 3c2 0 3.5 1.1 3.5 2.5s-.9 2.5-2 2.5c-.8 0-1.5-.4-1.5-1'],
  server: ['rect:2,2,20,8,2', 'rect:2,14,20,8,2', 'M6 6h.01', 'M6 18h.01'],
  cloud: ['M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z'],
  layers: ['M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83z', 'm22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65', 'm22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65'],
  download: ['M12 15V3', 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4', 'm7 10 5 5 5-5'],
  refresh: ['M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8', 'M21 3v5h-5', 'M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16', 'M8 16H3v5'],
  rocket: ['M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z', 'm12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z', 'M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0', 'M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5'],
};
const ALIASES = {'file-text': 'file', 'message-square': 'message', 'messages-square': 'message', 'pen': 'edit', 'pencil': 'edit',
  'graduation-cap': 'graduation', 'trending-up': 'trendingUp', 'user': 'users', 'heart-pulse': 'heart', 'shield-check': 'shield',
  'line-chart': 'trendingUp', 'chart-line': 'trendingUp', 'bar-chart': 'trendingUp', 'newspaper': 'newspaper', 'box': 'layers',
  'workflow': 'layers', 'network': 'layers', 'brain-circuit': 'brain', 'lightbulb': 'sparkles', 'wand': 'sparkles', 'star': 'sparkles'};

export function Icon({ name, size = 16, className = '', strokeWidth = 1.8 }) {
  const parts = ICONS[name] || ICONS[ALIASES[name]] || ICONS.bot;
  return h('svg', { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth,
    strokeLinecap: 'round', strokeLinejoin: 'round', className: cx('shrink-0', className), 'aria-hidden': 'true' },
    parts.map((d, i) => {
      if (d.startsWith('circle:')) { const [x, y, r] = d.slice(7).split(','); return h('circle', { key: i, cx: x, cy: y, r }); }
      if (d.startsWith('rect:')) { const [x, y, w, hh, r] = d.slice(5).split(','); return h('rect', { key: i, x, y, width: w, height: hh, rx: r }); }
      return h('path', { key: i, d });
    }));
}

export function Spinner({ size = 14, className = '' }) {
  return h('span', { className: cx('inline-block animate-spin rounded-full border-2 border-current border-t-transparent', className),
    style: { width: size, height: size } });
}

export function Avatar({ agent, size = 32, team = false }) {
  const color = (agent && agent.color) || '#6366f1';
  return h('span', { className: 'inline-flex shrink-0 items-center justify-center rounded-xl text-white shadow-sm',
    style: { width: size, height: size, background: `linear-gradient(135deg, ${color}, ${color}bb)` } },
    h(Icon, { name: (agent && agent.icon) || (team ? 'users' : 'bot'), size: Math.round(size * 0.52), strokeWidth: 2 }));
}

const BTN = {
  primary: 'bg-indigo-500 hover:bg-indigo-400 text-white border border-indigo-400/60 shadow-sm shadow-indigo-900/40',
  default: 'bg-zinc-800/80 hover:bg-zinc-700/80 text-zinc-100 border border-zinc-700',
  ghost: 'hover:bg-zinc-800/80 text-zinc-300 hover:text-white border border-transparent',
  danger: 'bg-rose-500/15 hover:bg-rose-500/25 text-rose-200 border border-rose-500/40',
  success: 'bg-emerald-500 hover:bg-emerald-400 text-white border border-emerald-400/60',
};
export function Button({ variant = 'default', size = 'md', icon, children, className = '', ...rest }) {
  const sz = size === 'sm' ? 'px-2.5 py-1 text-xs gap-1.5 rounded-lg' : size === 'icon' ? 'p-2 rounded-lg' : 'px-3.5 py-2 text-sm gap-2 rounded-xl';
  return h('button', { type: 'button', ...rest, className: cx('inline-flex items-center justify-center font-medium transition disabled:opacity-40 disabled:pointer-events-none', sz, BTN[variant], className) },
    icon ? h(Icon, { name: icon, size: size === 'sm' ? 13 : 16 }) : null, children);
}

export function Badge({ tone = 'zinc', children, className = '' }) {
  const tones = { zinc: 'bg-zinc-800 text-zinc-300 border-zinc-700', indigo: 'bg-indigo-500/15 text-indigo-200 border-indigo-500/30',
    green: 'bg-emerald-500/15 text-emerald-200 border-emerald-500/30', red: 'bg-rose-500/15 text-rose-200 border-rose-500/30',
    amber: 'bg-amber-500/15 text-amber-200 border-amber-500/40', sky: 'bg-sky-500/15 text-sky-200 border-sky-500/30' };
  return h('span', { className: cx('inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium', tones[tone] || tones.zinc, className) }, children);
}

export function Card({ title, actions, children, className = '', pad = true }) {
  return h('section', { className: cx('rounded-2xl border border-zinc-800 bg-zinc-900/60', pad && 'p-4', className) },
    title || actions ? h('div', { className: 'mb-3 flex items-center gap-2' },
      title ? h('h3', { className: 'flex-1 text-sm font-semibold text-zinc-100' }, title) : h('div', { className: 'flex-1' }), actions) : null,
    children);
}

export function Empty({ icon = 'sparkles', title, text, action }) {
  return h('div', { className: 'flex flex-col items-center justify-center gap-2 px-6 py-12 text-center' },
    h('span', { className: 'rounded-2xl bg-zinc-800/80 p-3 text-zinc-400' }, h(Icon, { name: icon, size: 22 })),
    title ? h('div', { className: 'text-sm font-semibold text-zinc-200' }, title) : null,
    text ? h('div', { className: 'max-w-sm text-sm text-zinc-500' }, text) : null, action || null);
}

export function Drawer({ open, title, onClose, children, footer, width = 'max-w-xl' }) {
  if (!open) return null;
  return h('div', { className: 'fixed inset-0 z-40 flex justify-end' },
    h('div', { className: 'absolute inset-0 bg-black/50 backdrop-blur-[1px]', onClick: onClose }),
    h('div', { className: cx('relative flex h-full w-full flex-col border-l border-zinc-800 bg-zinc-950 shadow-2xl', width) },
      h('div', { className: 'flex items-center gap-2 border-b border-zinc-800 px-5 py-4' },
        h('div', { className: 'flex-1 text-base font-semibold' }, title),
        h(Button, { variant: 'ghost', size: 'icon', icon: 'x', onClick: onClose, 'aria-label': 'Close' })),
      h('div', { className: 'flex-1 overflow-y-auto px-5 py-4' }, children),
      footer ? h('div', { className: 'flex justify-end gap-2 border-t border-zinc-800 px-5 py-3' }, footer) : null));
}

export const input = 'w-full rounded-xl border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/20';

export function Field({ label, hint, children }) {
  return h('label', { className: 'block space-y-1.5' },
    h('span', { className: 'text-xs font-medium text-zinc-300' }, label),
    children, hint ? h('span', { className: 'block text-[11px] text-zinc-500' }, hint) : null);
}

export const json = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

// ---- what the agent is doing, in plain words ------------------------------------------------

const TOOL_WORDS = [
  [/^web_search|search_web|^web_research/, 'Searching the web', 'globe'],
  [/web_fetch|web_extract|browse|scrape|crawl|article/, 'Reading a web page', 'globe'],
  [/^browser_/, 'Using the browser', 'globe'],
  [/read_file|read_attachment|^list_files|find_files|list_directory|file_info/, 'Reading files', 'file'],
  [/write_file|edit_file|create_file|move_file|copy_file|rename/, 'Changing files', 'edit'],
  [/delete|remove/, 'Removing something', 'trash'],
  [/run_command|shell|start_process|terminal/, 'Running a command', 'terminal'],
  [/^git_/, 'Working with git', 'code'],
  [/^skill_read/, 'Loading a skill', 'book'],
  [/^skill_learn/, 'Learning a new skill', 'brain'],
  [/^skill_/, 'Managing skills', 'book'],
  [/team_ask/, 'Handing work to a team member', 'users'],
  [/delegate_agent/, 'Asking a specialist', 'users'],
  [/agent_|team_create|agents_and_teams/, 'Managing agents', 'bot'],
  [/analyze_image|vision|screenshot|look/, 'Looking at an image', 'search'],
  [/calendar|todo|reminder|schedule/, 'Updating your schedule', 'calendar'],
  [/goal/, 'Working on a goal', 'target'],
  [/memory|remember|recall/, 'Using memory', 'brain'],
  [/discover_tools|tool_catalog|search_tools/, 'Finding the right tool', 'wrench'],
  [/career|job/, 'Working on job applications', 'briefcase'],
  [/download/, 'Downloading', 'download'],
  [/show_file/, 'Showing a file', 'file'],
];
export function describeTool(name) {
  const n = String(name || '');
  for (const [re, words, icon] of TOOL_WORDS) if (re.test(n)) return { words, icon };
  return { words: n.replace(/_/g, ' ').replace(/^./, c => c.toUpperCase()), icon: 'wrench' };
}

// The most useful argument of a tool call ("query", "path", "url", ...) for one line of detail.
export function argSummary(args) {
  if (!args) return '';
  let obj = args;
  if (typeof args === 'string') { try { obj = JSON.parse(args); } catch (_) { return args.slice(0, 140); } }
  if (!obj || typeof obj !== 'object') return String(obj).slice(0, 140);
  for (const k of ['query', 'q', 'url', 'path', 'name', 'command', 'task', 'member', 'source', 'goal', 'title', 'question', 'file']) {
    if (obj[k]) return `${k === 'member' ? `${obj.member}: ` : ''}${String(k === 'member' ? (obj.task || '') : obj[k])}`.slice(0, 160);
  }
  const first = Object.values(obj).find(v => typeof v === 'string' && v);
  return first ? first.slice(0, 140) : '';
}

export function timeAgo(t) {
  const ms = Date.now() - (typeof t === 'number' ? (t < 1e12 ? t * 1000 : t) : Date.parse(t));
  if (!isFinite(ms)) return '';
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}
