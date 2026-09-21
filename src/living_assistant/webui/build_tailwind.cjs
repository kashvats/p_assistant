const fs = require('fs');
const path = require('path');

function loadTailwind() {
  try { return require('tailwindcss'); } catch (_) {}
  return require('/opt/nvm/versions/node/v22.16.0/lib/node_modules/tailwindcss/dist/lib.js');
}

function copyTree(source, destination) {
  fs.rmSync(destination, {recursive: true, force: true});
  fs.mkdirSync(destination, {recursive: true});
  for (const name of fs.readdirSync(source)) {
    const src = path.join(source, name);
    const dst = path.join(destination, name);
    const stat = fs.statSync(src);
    if (stat.isDirectory()) copyTree(src, dst);
    else fs.copyFileSync(src, dst);
  }
}

(async () => {
  const root = __dirname;
  const {compile} = loadTailwind();
  let tailwindRoot;
  try { tailwindRoot = path.dirname(require.resolve('tailwindcss/package.json')); }
  catch (_) { tailwindRoot = '/opt/nvm/versions/node/v22.16.0/lib/node_modules/tailwindcss'; }
  const baseCss = fs.readFileSync(path.join(tailwindRoot, 'index.css'), 'utf8');
  const customCss = fs.readFileSync(path.join(root, 'src', 'styles.css'), 'utf8')
    .replace('@import "tailwindcss";', '');
  const source = `${baseCss}
${customCss}`;
  const manual = fs.readFileSync(path.join(root, 'tailwind.candidates.txt'), 'utf8');
  const app = fs.readFileSync(path.join(root, 'src', 'main.js'), 'utf8');
  const strings = [...app.matchAll(/(['"])(.*?)\1/gs)].map((match) => match[2]).join(' ');
  const candidates = `${manual} ${strings}`.split(/\s+/).map(x => x.trim()).filter(Boolean);
  const result = await compile(source);
  const css = result.build([...new Set(candidates)]) + `\n\n/* App-specific production-safe primitives */\n.markdown-body p{margin:.35rem 0 .7rem}.markdown-body h1,.markdown-body h2,.markdown-body h3{font-weight:700;margin:.9rem 0 .4rem}.markdown-body ul,.markdown-body ol{padding-left:1.4rem;margin:.45rem 0}.markdown-body ul{list-style:disc}.markdown-body ol{list-style:decimal}.markdown-body blockquote{border-left:3px solid #475569;padding-left:.75rem;color:#cbd5e1}.markdown-body a{color:#8ba8ff;text-decoration:underline}.markdown-body pre{margin:.65rem 0}.markdown-body code:not(pre code){background:#0f172a;border:1px solid #1e293b;border-radius:.35rem;padding:.08rem .3rem;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}\n`;
  const dist = path.join(root, 'dist');
  fs.mkdirSync(dist, {recursive: true});
  fs.writeFileSync(path.join(dist, 'app.css'), css, 'utf8');

  const publicRoot = path.join(root, 'public');
  fs.mkdirSync(path.join(publicRoot, 'dist'), {recursive: true});
  fs.writeFileSync(path.join(publicRoot, 'dist', 'app.css'), css, 'utf8');
  copyTree(path.join(root, 'vendor'), path.join(publicRoot, 'vendor'));
})();
