from __future__ import annotations
from pathlib import Path
from .base import Tool
from ..workspace import Workspace

def build_filesystem_tools(workspace: Workspace) -> list[Tool]:
    def list_files(path: str = "."):
        return workspace.list(path)

    def read_file(path: str):
        return {"path": str(workspace.resolve(path)), "content": workspace.read_text(path)}

    def write_file(path: str, content: str):
        return {"path": workspace.write_text(path, content), "bytes": len(content.encode("utf-8"))}

    def search_files(query: str, path: str = ".", limit: int = 50):
        root = workspace.resolve(path)
        out = []
        q = query.lower()
        for p in root.rglob("*"):
            if len(out) >= min(limit, 200):
                break
            if p.is_file():
                if q in p.name.lower():
                    out.append({"path": str(p), "match": "filename"})
                    continue
                if p.stat().st_size <= 2_000_000:
                    try:
                        txt = p.read_text(encoding="utf-8", errors="ignore")
                        if q in txt.lower():
                            out.append({"path": str(p), "match": "content"})
                    except Exception:
                        pass
        return out

    return [
        Tool("list_files", "List files/directories inside an approved workspace.",
             {"type":"object","properties":{"path":{"type":"string","default":"."}}}, list_files),
        Tool("read_file", "Read a UTF-8 text file inside an approved workspace.",
             {"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}, read_file),
        Tool("write_file", "Write text inside an approved workspace. Parent folders are created.",
             {"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}, write_file),
        Tool("search_files", "Search filenames/text inside an approved workspace.",
             {"type":"object","properties":{"query":{"type":"string"},"path":{"type":"string","default":"."},"limit":{"type":"integer","default":50}},"required":["query"]}, search_files),
    ]
