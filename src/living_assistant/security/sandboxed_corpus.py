"""Read-only access to a third-party text corpus kept inside a container volume.

Security reference material (malware write-ups, YARA rules, exploit notes) trips
host antivirus heuristics when stored on the Windows filesystem. Keeping it in a
Docker/Podman volume means it lives only inside the sandbox VM; the assistant reads
individual files through short-lived, network-less, capability-free containers and
the content only ever reaches process memory, never the host disk.
"""
from __future__ import annotations

import re
import subprocess

from living_assistant.security.sandbox import ContainerRuntime

_SAFE_REL = re.compile(r"^[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*$")
_SEP = "\x1e__LA_SECTION__\x1e"


class CorpusUnavailable(RuntimeError):
    pass


class SandboxedCorpus:
    READY_MARKER = ".la-ready"

    def __init__(
        self,
        runtime: ContainerRuntime,
        volume: str,
        repository: str,
        revision: str,
        image: str = "alpine/git:latest",
        timeout: float = 30.0,
    ) -> None:
        self.runtime = runtime
        self.volume = volume
        self.repository = repository
        self.revision = revision
        self.image = image
        self.timeout = timeout

    # -- container plumbing -------------------------------------------------

    def _argv(self, script: str, args: list[str], *, network: bool, writable: bool, memory_mb: int = 256) -> list[str]:
        if not self.runtime.binary:
            raise CorpusUnavailable("Docker/Podman is not installed.")
        mount = f"type=volume,src={self.volume},dst=/corpus" + ("" if writable else ",readonly")
        return [
            self.runtime.binary, "run", "--rm", "--pull", "never",
            "--network", "bridge" if network else "none",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--read-only", "--tmpfs", "/tmp:rw,nosuid,noexec,size=64m",
            "--memory", f"{memory_mb}m", "--pids-limit", "64",
            "--mount", mount,
            "--entrypoint", "sh",
            self.image, "-c", script, "sh", *args,
        ]

    def _run(self, script: str, *args: str, network: bool = False, writable: bool = False, timeout: float | None = None) -> str:
        argv = self._argv(script, list(args), network=network, writable=writable)
        try:
            proc = subprocess.run(argv, capture_output=True, timeout=timeout or self.timeout)
        except subprocess.TimeoutExpired as exc:
            raise CorpusUnavailable("Sandbox read timed out.") from exc
        except OSError as exc:
            raise CorpusUnavailable(f"Container runtime failed to start: {exc}") from exc
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", "replace").strip()[:600]
            if "daemon" in err.lower() or "pipe" in err.lower() or "cannot connect" in err.lower():
                raise CorpusUnavailable("The container engine is not running (start Docker Desktop).")
            if "no such image" in err.lower() or "unable to find image" in err.lower():
                raise CorpusUnavailable(f"Sandbox image {self.image} is not present; run the security skills sync first.")
            raise CorpusUnavailable(err or f"Sandbox command failed with exit code {proc.returncode}.")
        return proc.stdout.decode("utf-8", "replace")

    @staticmethod
    def _check_rel(rel: str) -> str:
        rel = str(rel).strip().strip("/")
        if not _SAFE_REL.match(rel) or ".." in rel.split("/"):
            raise ValueError(f"Invalid corpus path: {rel!r}")
        return rel

    # -- public API -----------------------------------------------------------

    def status(self) -> dict:
        engine = self.runtime.status()
        if not engine.get("available"):
            return {"ready": False, "engine": engine, "reason": "Container engine unavailable (start Docker Desktop)."}
        try:
            out = self._run(f'test -f "/corpus/{self.READY_MARKER}" && cat "/corpus/{self.READY_MARKER}"', timeout=15)
        except CorpusUnavailable as exc:
            return {"ready": False, "engine": engine, "reason": str(exc)}
        return {"ready": True, "engine": engine, "revision": out.strip(), "volume": self.volume}

    def ready(self) -> bool:
        return bool(self.status().get("ready"))

    def read_text(self, rel: str, max_bytes: int = 4_000_000) -> str | None:
        rel = self._check_rel(rel)
        try:
            return self._run('f="/corpus/repo/$1"; [ -f "$f" ] || exit 3; head -c "$2" "$f"', rel, str(int(max_bytes)))
        except CorpusUnavailable as exc:
            if "exit code 3" in str(exc):
                return None
            raise

    def bundle(self, directory: str, main_file: str, listings: tuple[str, ...]) -> dict | None:
        """Read one file plus the names in sibling folders in a single container run."""
        directory = self._check_rel(directory)
        main_file = self._check_rel(main_file)
        for name in listings:
            self._check_rel(name)
        script = (
            'd="/corpus/repo/$1"; [ -f "$d/$2" ] || exit 3; cat "$d/$2"; shift 2; '
            f'for sub in "$@"; do printf "{_SEP}%s\\n" "$sub"; [ -d "$d/$sub" ] && ls -1 "$d/$sub"; done'
        )
        try:
            out = self._run(script, directory, main_file, *listings)
        except CorpusUnavailable as exc:
            if "exit code 3" in str(exc):
                return None
            raise
        parts = out.split(_SEP)
        result = {"content": parts[0], "listings": {}}
        for chunk in parts[1:]:
            name, _, rest = chunk.partition("\n")
            result["listings"][name] = [line for line in rest.splitlines() if line.strip()]
        return result

    def sync(self) -> dict:
        """Explicit, user-approved download of the pinned revision into the volume."""
        if not self.runtime.binary:
            return {"ok": False, "error": "Docker/Podman is not installed."}
        pull = subprocess.run([self.runtime.binary, "pull", self.image], capture_output=True, timeout=600)
        if pull.returncode != 0:
            return {"ok": False, "error": pull.stderr.decode("utf-8", "replace").strip()[:600] or "Image pull failed."}
        script = (
            'set -e; rm -rf /corpus/repo "/corpus/$3"; '
            'git clone --quiet --no-checkout "$1" /corpus/repo; '
            'git -C /corpus/repo -c advice.detachedHead=false checkout --quiet "$2"; '
            'rm -rf /corpus/repo/.git; printf "%s" "$2" > "/corpus/$3"'
        )
        argv = self._argv(script, [self.repository, self.revision, self.READY_MARKER], network=True, writable=True, memory_mb=512)
        # git needs a writable HOME inside the read-only root.
        argv[argv.index("--entrypoint"):argv.index("--entrypoint")] = ["-e", "HOME=/tmp"]
        proc = subprocess.run(argv, capture_output=True, timeout=900)
        if proc.returncode != 0:
            return {"ok": False, "error": proc.stderr.decode("utf-8", "replace").strip()[:800] or "Sync failed."}
        return {"ok": True, "volume": self.volume, "revision": self.revision}
