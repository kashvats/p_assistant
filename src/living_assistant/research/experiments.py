"""Reproducible experiments for software and computational research.

An experiment runs a command (through the shell tool's normal approval and safety
path) several times and records everything needed to reproduce and judge it:
input command and parameters, code version (git commit + dirty flag), dataset
(path + SHA-256), environment (Python, platform, CPU), per-run metrics, logs and
timing. The program reports metrics by printing one JSON object as its last line,
e.g. {"compression_ratio": 2.91, "compress_mb_s": 412, "lossless": true}.

Runs are also stored as ``experiment_result`` events, so the pattern engine sees
experiment outcomes like any other observation.
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

import numpy as np

from .events import add_events
from .store import KnowledgeStore

RunCommand = Callable[..., dict]  # the shell tool's run_command(command, cwd, timeout_seconds)


def _sha256(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _git_version(cwd: Path) -> dict:
    def git(*args):
        try:
            out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10)
            return out.stdout.strip() if out.returncode == 0 else None
        except (OSError, subprocess.SubprocessError):
            return None

    commit = git("rev-parse", "HEAD")
    return {"commit": commit, "dirty": bool(git("status", "--porcelain")) if commit else None}


def _metrics(stdout: str) -> dict:
    for line in reversed([l.strip() for l in str(stdout or "").splitlines() if l.strip()]):
        if line.startswith("{"):
            try:
                data = json.loads(line)
            except ValueError:
                return {}
            out = {}
            for k, v in data.items():
                if isinstance(v, bool):
                    out[str(k)] = 1.0 if v else 0.0
                elif isinstance(v, (int, float)):
                    out[str(k)] = float(v)
            return out
    return {}


class ExperimentRunner:
    def __init__(self, store: KnowledgeStore, run_command: RunCommand, resolve_path: Callable[[str], Path]):
        self.store = store
        self.run_command = run_command
        self.resolve_path = resolve_path

    def run(self, project_id: str, name: str, command: str, *, cwd: str = ".", variant: str = "", params: dict | None = None,
            dataset: str = "", repeats: int = 3, timeout_seconds: int = 600, hypothesis_id: str | None = None,
            baselines: list[str] | None = None) -> dict:
        folder = self.resolve_path(cwd or ".")
        data_path = self.resolve_path(dataset) if dataset else None
        environment = {"python": sys.version.split()[0], "platform": platform.platform(), "machine": platform.machine(),
                       "processor": platform.processor()}
        runs = []
        for i in range(max(1, min(int(repeats), 20))):
            started = time.perf_counter()
            result = self.run_command(command, cwd=str(folder), timeout_seconds=timeout_seconds)
            elapsed = round(time.perf_counter() - started, 3)
            if result.get("approval_required") or result.get("blocked"):
                return {"ok": False, "stage": "run", **result}
            stdout = str(result.get("stdout") or "")
            runs.append({
                "run": i + 1, "ok": bool(result.get("ok")) and not result.get("timeout"),
                "returncode": result.get("returncode"), "seconds": elapsed,
                "metrics": _metrics(stdout), "log_tail": (stdout[-1500:] + "\n" + str(result.get("stderr") or "")[-800:]).strip(),
            })
        summary = {}
        names = sorted({m for r in runs if r["ok"] for m in r["metrics"]})
        reproducible = bool(runs) and all(r["ok"] for r in runs) and bool(names)
        for m in names:
            values = np.array([r["metrics"][m] for r in runs if r["ok"] and m in r["metrics"]], dtype=float)
            mean, std = float(values.mean()), float(values.std())
            cv = std / abs(mean) if mean else (0.0 if std == 0 else float("inf"))
            summary[m] = {"mean": mean, "std": std, "min": float(values.min()), "max": float(values.max()), "n": int(values.size),
                          "cv": round(cv, 4)}
            # Speed metrics vary run to run; quality metrics (ratio, lossless) should not.
            reproducible = reproducible and (cv <= 0.1 or any(t in m.lower() for t in ("speed", "time", "_s", "ms", "mb_s", "throughput")))
        data = {
            "command": command, "cwd": str(folder), "variant": variant or name, "params": params or {},
            "dataset": str(data_path) if data_path else None, "dataset_label": dataset or None,
            "dataset_sha256": _sha256(data_path) if data_path and data_path.is_file() else None,
            "code_version": _git_version(folder), "environment": environment, "runs": runs, "metrics": summary,
            "reproducible": reproducible, "baselines": baselines or [],
        }
        links = [("tests", hypothesis_id)] if hypothesis_id else []
        x = self.store.add(project_id, "experiment", name, kind=f"{variant or name}|{dataset}", status="DONE" if reproducible else "UNSTABLE",
                           level="OBSERVED", data=data, links=links, body=f"{name} {command} {variant} {dataset} {list(summary)}")
        if hypothesis_id:
            self.store.link(hypothesis_id, "tested_in", x["id"])
        events = add_events(self.store, project_id, [
            {"event_type": "experiment_result", "stream": "experiments", "entities": [variant or name, dataset or "no_dataset"],
             "numeric_features": r["metrics"], "attributes": {"experiment": x["id"], "run": r["run"], "ok": r["ok"]}}
            for r in runs], source="experiment")
        for e in events:
            self.store.link(x["id"], "produced", e["id"])
        return {"ok": True, "experiment": x["id"], "reproducible": reproducible, "metrics": summary,
                "runs_ok": sum(1 for r in runs if r["ok"]), "runs": len(runs)}
