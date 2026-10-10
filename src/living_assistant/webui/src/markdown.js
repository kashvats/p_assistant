/* Markdown for model and web text: headings, lists, quotes, code (Prism-highlighted) and safe links.
   Text is rendered as text, never HTML. */
const React = globalThis.React;
const Prism = globalThis.Prism;
const h = React.createElement;

function safeText(value) { return value == null ? '' : String(value); }

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
export function Markdown({text}) {
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
