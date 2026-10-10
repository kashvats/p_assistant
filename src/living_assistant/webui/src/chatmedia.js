/* Files in chat, shared by the dashboard chat and the floating agent.

   - uploadFile(): send any supported file (image, video, audio, PDF, CSV/XLSX, document, text)
   - fileChip(): a compact attachment shown in a user message or the composer
   - mediaCard(): a file the assistant shows (downloads, show_file) rendered in the reply:
     images, video and audio play inline, PDFs in a viewer, tables as a scrollable grid,
     documents as text; everything else as a download link.
   Built with DOM APIs and textContent only: no HTML from files or the model is injected. */

export const FILE_MARKER = /\[file (file_[0-9a-f]{16})(?: ([^\]\n]{1,160}))?\]/g;
export const ACCEPT = 'image/*,video/*,audio/*,.pdf,.csv,.tsv,.xlsx,.xlsm,.xls,.docx,.pptx,.txt,.md,.json,.log,.xml,.yaml,.yml';
const ICONS = {image: '🖼', video: '🎬', audio: '🎵', pdf: '📕', table: '📊', document: '📄', text: '📝', other: '📎'};
const EXT_KIND = {};
[['image', 'png jpg jpeg gif webp bmp tif tiff'], ['video', 'mp4 webm mov mkv avi m4v'], ['audio', 'mp3 wav ogg m4a flac aac opus'],
 ['pdf', 'pdf'], ['table', 'csv tsv xlsx xlsm xls'], ['document', 'docx pptx'],
 ['text', 'txt md json log xml yaml yml py js ts html css ini toml sql']]
  .forEach(([kind, exts]) => exts.split(' ').forEach((e) => { EXT_KIND[e] = kind; }));

export function kindOf(name) {
  const ext = String(name || '').toLowerCase().split('.').pop();
  return EXT_KIND[ext] || 'other';
}

export function fileIcon(kind) { return ICONS[kind] || ICONS.other; }

export function fmtSize(bytes) {
  if (!Number.isFinite(bytes)) return '';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0, n = bytes;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i += 1; }
  return `${n.toFixed(n >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
}

export function contentUrl(ref, token, {download = false} = {}) {
  const q = new URLSearchParams({ref});
  if (token) q.set('token', token);
  if (download) q.set('download', 'true');
  return `/files/content?${q}`;
}

export async function uploadFile(file, token, name = '') {
  const res = await fetch(`/files/upload?name=${encodeURIComponent(name || file.name || 'file')}`, {
    method: 'POST', body: file,
    headers: Object.assign({'Content-Type': 'application/octet-stream'}, token ? {Authorization: `Bearer ${token}`} : {}),
  });
  if (!res.ok) {
    let detail = '';
    try { detail = (await res.json()).detail; } catch (_) { detail = await res.text().catch(() => ''); }
    throw new Error(detail || `Upload failed (HTTP ${res.status})`);
  }
  return res.json();
}

/** Split a message into its text and the files recorded in it ([file …] markers). */
export function extractFiles(text) {
  const files = [...String(text || '').matchAll(FILE_MARKER)].map((m) => ({ref: m[1], name: m[2] || m[1], kind: kindOf(m[2])}));
  return {text: String(text || '').replace(FILE_MARKER, '').trim(), files};
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function link(label, href, {download = false} = {}) {
  const a = el('a', 'chat-media-link', label);
  a.href = href;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  if (download) a.setAttribute('download', '');
  return a;
}

/** A small attachment chip; clicking opens the file. `onRemove` adds a ✕ (composer). */
export function fileChip(item, token, {onRemove = null} = {}) {
  const chip = el('span', 'chat-file-chip');
  chip.title = item.name;
  const open = el('a', 'chat-file-chip-name', `${fileIcon(item.kind)} ${item.name}`);
  open.href = contentUrl(item.ref || item.id, token);
  open.target = '_blank';
  open.rel = 'noopener noreferrer';
  chip.appendChild(open);
  if (item.bytes) chip.appendChild(el('span', 'chat-file-chip-size', fmtSize(item.bytes)));
  if (onRemove) {
    const remove = el('button', 'chat-file-chip-remove', '✕');
    remove.type = 'button';
    remove.title = 'Remove';
    remove.setAttribute('aria-label', `Remove ${item.name}`);
    remove.addEventListener('click', onRemove);
    chip.appendChild(remove);
  }
  return chip;
}

async function preview(ref, token) {
  const res = await fetch(`/files/preview?ref=${encodeURIComponent(ref)}&limit=100`, {
    headers: token ? {Authorization: `Bearer ${token}`} : {},
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function tableView(data) {
  const wrap = el('div', 'chat-media-table');
  const table = el('table');
  const head = el('tr');
  (data.columns || []).forEach((c) => head.appendChild(el('th', '', c)));
  table.appendChild(el('thead')).appendChild(head);
  const body = table.appendChild(el('tbody'));
  (data.rows || []).forEach((row) => {
    const tr = body.appendChild(el('tr'));
    row.forEach((v) => tr.appendChild(el('td', '', v == null ? '' : String(v))));
  });
  wrap.appendChild(table);
  const shown = (data.rows || []).length;
  if (data.total_rows > shown) wrap.appendChild(el('div', 'chat-media-note', `Showing ${shown} of ${data.total_rows} rows`));
  return wrap;
}

/** A file shown in a reply: {ref, name, kind, bytes?, caption?}. */
export function mediaCard(item, token) {
  const kind = item.kind && item.kind !== 'other' ? item.kind : kindOf(item.name);
  const card = el('figure', `chat-media chat-media-${kind}`);
  const url = contentUrl(item.ref, token);
  let body;
  if (kind === 'image') {
    body = el('img');
    body.src = url; body.alt = item.caption || item.name; body.loading = 'lazy';
    body.addEventListener('click', () => window.open(url, '_blank', 'noopener'));
  } else if (kind === 'video' || kind === 'audio') {
    body = el(kind);
    body.src = url; body.controls = true; body.preload = 'metadata';
  } else if (kind === 'pdf') {
    body = el('iframe');
    body.src = url; body.title = item.name; body.loading = 'lazy';
  } else if (kind === 'table' || kind === 'document' || kind === 'text') {
    body = el('div', 'chat-media-loading', 'Loading preview…');
    preview(item.ref, token).then((data) => {
      const view = kind === 'table' ? tableView(data) : el('pre', 'chat-media-text', String(data.text || '').slice(0, 20000));
      body.replaceWith(view);
    }).catch((e) => { body.textContent = `No preview (${e.message}).`; });
  }
  if (body) card.appendChild(body);
  const caption = el('figcaption', 'chat-media-caption');
  caption.appendChild(el('span', 'chat-media-name', `${fileIcon(kind)} ${item.caption || item.name}`));
  if (item.bytes) caption.appendChild(el('span', 'chat-media-size', fmtSize(item.bytes)));
  caption.appendChild(link('Open', url));
  caption.appendChild(link('Download', contentUrl(item.ref, token, {download: true}), {download: true}));
  card.appendChild(caption);
  return card;
}

/** Media cards for a list of items, de-duplicated by ref. */
export function mediaList(items, token) {
  const wrap = el('div', 'chat-media-list');
  const seen = new Set();
  (items || []).forEach((item) => {
    if (!item || !item.ref || seen.has(item.ref)) return;
    seen.add(item.ref);
    wrap.appendChild(mediaCard(item, token));
  });
  return wrap;
}
