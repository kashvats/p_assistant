#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, shutil, subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/'dist'; DIST.mkdir(exist_ok=True)
for p in DIST.glob('living_assistant-*.whl'): p.unlink()
cmd=[sys.executable,'-m','pip','wheel','.', '--no-deps','--no-build-isolation','-w',str(DIST)]
p=subprocess.run(cmd,cwd=ROOT)
if p.returncode: raise SystemExit(p.returncode)
wheels=sorted(DIST.glob('living_assistant-*.whl'))
if len(wheels)!=1: raise SystemExit('Expected one wheel')
def sha(path):
    h=hashlib.sha256();
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()
lines=[f'{sha(w)}  dist/{w.name}' for w in wheels]
(ROOT/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('\n'.join(lines))
