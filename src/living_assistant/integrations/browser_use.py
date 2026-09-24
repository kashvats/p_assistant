from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib
from pathlib import Path
import sys
import threading
import time
import tomllib
from typing import Any, Callable, Coroutine, TypeVar

from living_assistant.security.security_utils import redact_secrets


_T = TypeVar("_T")


class BrowserUseAdapter:
    """Production boundary around the pinned Browser Use repository.

    The adapter intentionally keeps Browser Use lazy and isolated from the
    assistant core.  It preserves the existing public contract (``available``
    and synchronous ``run`` returning plain dictionaries) while adding:

    - verification that imports come from the configured pinned checkout;
    - bounded, serialized execution for local-resource safety;
    - the intended max-step limit on ``Agent.run`` (Browser Use 0.13.x takes
      max_steps on ``run``, not the Agent constructor);
    - structured task outcome/history metadata;
    - download capture before Browser Use tears its session down;
    - on-disk verification and SHA-256 for downloaded files;
    - safe operation when invoked from a thread that already owns an asyncio
      event loop;
    - redacted, bounded error messages.

    Third-party Browser Use objects never escape this class.
    """

    _import_lock = threading.RLock()

    def __init__(
        self,
        repository_path: str | Path,
        ollama_url: str,
        model: str,
        *,
        max_steps: int = 8,
        max_failures: int = 2,
        use_vision: bool = False,
        use_thinking: bool = False,
        use_judge: bool = False,
    ):
        # Preserve the original three positional arguments used by runtime.py.
        self.repository_path = Path(repository_path).expanduser().resolve()
        self.ollama_url = str(ollama_url or "").strip()
        self.model = str(model or "").strip()

        # Preserve the intended settings from the previous adapter.
        self.max_steps = max(1, min(int(max_steps), 500))
        self.max_failures = max(1, min(int(max_failures), 50))
        self.use_vision = bool(use_vision)
        self.use_thinking = bool(use_thinking)
        self.use_judge = bool(use_judge)

        # Browser Use launches an Ollama-backed agent directly, bypassing the
        # main ModelManager lease.  Serialize this adapter so two autonomous
        # browser agents do not compete for a small local GPU at once.
        self._run_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Repository / imports
    # ------------------------------------------------------------------

    def _repository_version(self) -> str | None:
        pyproject = self.repository_path / "pyproject.toml"
        try:
            with pyproject.open("rb") as handle:
                payload = tomllib.load(handle)
            value = payload.get("project", {}).get("version")
            return str(value) if value else None
        except Exception:
            return None

    def _imports(self):
        """Load Browser Use from the configured checkout and nowhere else."""

        package_init = self.repository_path / "browser_use" / "__init__.py"
        if not package_init.is_file():
            raise RuntimeError(
                "Browser Use repository is missing or invalid at "
                f"{self.repository_path}. Expected browser_use/__init__.py."
            )

        repo = str(self.repository_path)

        with self._import_lock:
            # Put the pinned checkout first.  Merely appending it can silently
            # import a globally installed, different Browser Use version.
            if repo in sys.path:
                sys.path.remove(repo)
            sys.path.insert(0, repo)

            try:
                browser_use = importlib.import_module("browser_use")
                Agent = getattr(browser_use, "Agent")

                # 0.13.10 exposes ChatOllama at the package root.  Retain the
                # old import path as a compatibility fallback for nearby pinned
                # revisions without changing the core contract.
                try:
                    ChatOllama = getattr(browser_use, "ChatOllama")
                except (AttributeError, ImportError):
                    from browser_use.llm import ChatOllama  # type: ignore
            except (ImportError, AttributeError) as exc:
                raise RuntimeError(
                    "Browser Use is enabled but its pinned checkout or optional "
                    "dependencies are incomplete. Install it with: "
                    'pip install -e "external-components/browser-use"'
                ) from exc

            module_file = getattr(browser_use, "__file__", None)
            if not module_file:
                raise RuntimeError("Browser Use imported without a module file path.")

            origin = Path(module_file).resolve()
            try:
                origin.relative_to(self.repository_path)
            except ValueError as exc:
                raise RuntimeError(
                    "A different Browser Use installation is already loaded from "
                    f"{origin}. Expected the pinned checkout at "
                    f"{self.repository_path}. Restart the assistant after fixing "
                    "the Python environment."
                ) from exc

        return Agent, ChatOllama

    def available(self) -> bool:
        """Return whether the pinned integration can be imported."""

        try:
            self._imports()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Safe primitive conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _bounded_text(value: Any, limit: int) -> str:
        try:
            return str(value or "")[: max(0, int(limit))]
        except Exception:
            return ""

    @staticmethod
    def _safe_error(value: Any, limit: int = 2000) -> str:
        try:
            return str(redact_secrets(value, limit))[:limit]
        except Exception:
            return str(value or "")[:limit]

    @staticmethod
    def _safe_call(obj: Any, name: str, default: Any = None) -> Any:
        fn = getattr(obj, name, None)
        if not callable(fn):
            return default
        try:
            return fn()
        except Exception:
            return default

    # ------------------------------------------------------------------
    # Download capture / verification
    # ------------------------------------------------------------------

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _path_is_within(path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except (OSError, ValueError):
            return False

    def _verify_download(self, raw_path: str, root: Path | None) -> dict[str, Any]:
        path = Path(str(raw_path)).expanduser()
        if not path.is_absolute() and root is not None:
            path = root / path
        resolved = path.resolve()

        result: dict[str, Any] = {
            "path": str(resolved),
            "exists": resolved.exists(),
            "is_file": resolved.is_file(),
        }

        if root is not None:
            inside = self._path_is_within(resolved, root)
            result["inside_download_directory"] = inside
            if not inside:
                # Do not read/hash an unexpected path emitted by a third-party
                # integration.  Report it for diagnostics only.
                result["verified"] = False
                result["verification_error"] = (
                    "Browser Use reported a download outside its configured "
                    "download directory."
                )
                return result

        if not resolved.exists() or not resolved.is_file():
            result["verified"] = False
            return result

        try:
            size = resolved.stat().st_size
            result["bytes"] = size
            result["sha256"] = self._sha256(resolved)
            result["verified"] = size > 0
        except OSError as exc:
            result["verified"] = False
            result["verification_error"] = self._safe_error(exc, 1000)

        return result

    def _capture_download_state(self, agent: Any, state: dict[str, Any]) -> None:
        """Capture download paths before Browser Use clears session state.

        Browser Use 0.13.10 clears ``BrowserSession.downloaded_files`` during
        Agent cleanup.  Both the done callback and the step-end callback run
        before cleanup, so we snapshot the public property there.
        """

        session = getattr(agent, "browser_session", None)
        if session is None:
            return

        profile = getattr(session, "browser_profile", None)
        downloads_path = getattr(profile, "downloads_path", None)
        if downloads_path:
            try:
                state["downloads_directory"] = str(Path(downloads_path).expanduser().resolve())
            except Exception:
                state["downloads_directory"] = str(downloads_path)

        try:
            raw_paths = list(getattr(session, "downloaded_files", []) or [])
        except Exception:
            raw_paths = []

        seen: set[str] = state.setdefault("download_paths", set())
        for raw_path in raw_paths:
            if raw_path:
                seen.add(str(raw_path))

    def _download_results(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        root_value = state.get("downloads_directory")
        root = Path(root_value).expanduser().resolve() if root_value else None
        paths = sorted(state.get("download_paths", set()))
        return [self._verify_download(path, root) for path in paths]

    # ------------------------------------------------------------------
    # Browser Use history conversion
    # ------------------------------------------------------------------

    def _history_result(self, history: Any, capture: dict[str, Any]) -> dict[str, Any]:
        answer = self._bounded_text(self._safe_call(history, "final_result", ""), 20000)
        done = bool(self._safe_call(history, "is_done", False))
        successful = self._safe_call(history, "is_successful", None)

        raw_urls = self._safe_call(history, "urls", []) or []
        visited_urls: list[str] = []
        seen_urls: set[str] = set()
        for raw_url in raw_urls:
            if not raw_url:
                continue
            url = self._safe_error(raw_url, 4000)
            if url and url not in seen_urls:
                seen_urls.add(url)
                visited_urls.append(url)
            if len(visited_urls) >= 100:
                break

        raw_errors = self._safe_call(history, "errors", []) or []
        errors = [self._safe_error(item, 2000) for item in raw_errors if item]
        errors = errors[:50]

        raw_actions = self._safe_call(history, "action_names", []) or []
        actions = [self._bounded_text(item, 200) for item in raw_actions if item][:100]

        steps = self._safe_call(history, "number_of_steps", None)
        duration = self._safe_call(history, "total_duration_seconds", None)

        downloads = self._download_results(capture)
        verified_downloads = [item for item in downloads if item.get("verified") is True]

        # Browser Use 0.13.10's done action carries an explicit success value.
        # A completed adapter call is not the same as successful task execution.
        # Preserve the old result keys while making `ok` operationally honest.
        ok = bool(done and successful is True)

        return {
            "ok": ok,
            "task_successful": successful,
            "done": done,
            "answer": answer,
            "visited_urls": visited_urls,
            "final_url": visited_urls[-1] if visited_urls else None,
            "actions": actions,
            "errors": errors,
            "steps": steps,
            "duration_seconds": duration,
            "downloads_directory": capture.get("downloads_directory"),
            "downloads": downloads,
            "verified_download_count": len(verified_downloads),
        }

    # ------------------------------------------------------------------
    # Async execution / sync bridge
    # ------------------------------------------------------------------

    async def _execute(self, task: str, timeout_seconds: float) -> dict[str, Any]:
        Agent, ChatOllama = self._imports()
        capture: dict[str, Any] = {"download_paths": set()}
        holder: dict[str, Any] = {}

        def on_done(_history: Any) -> None:
            agent = holder.get("agent")
            if agent is not None:
                self._capture_download_state(agent, capture)

        async def on_step_end(agent: Any) -> None:
            self._capture_download_state(agent, capture)

        llm = ChatOllama(model=self.model, host=self.ollama_url)

        # These values exactly preserve the previous adapter's intended model
        # behaviour.  max_steps belongs on agent.run() in Browser Use 0.13.10;
        # passing it to Agent(...) was accepted only via **kwargs and ignored.
        agent = Agent(
            task=task,
            llm=llm,
            use_vision=self.use_vision,
            max_failures=self.max_failures,
            use_thinking=self.use_thinking,
            use_judge=self.use_judge,
            register_done_callback=on_done,
            # Embedded integrations should not install process-wide signal
            # handlers; the Living Assistant owns process lifecycle/timeout.
            enable_signal_handler=False,
        )
        holder["agent"] = agent

        # Capture Browser Use's generated download directory even before the
        # first step.  Its profile creates a unique directory by default.
        self._capture_download_state(agent, capture)

        try:
            history = await asyncio.wait_for(
                agent.run(max_steps=self.max_steps, on_step_end=on_step_end),
                timeout=max(1.0, float(timeout_seconds)),
            )
        except asyncio.TimeoutError:
            # Previous completed steps may already have downloaded files; those
            # were captured by on_step_end before Browser Use cleanup ran.
            downloads = self._download_results(capture)
            return {
                "ok": False,
                "timeout": True,
                "task_successful": False,
                "done": False,
                "answer": "",
                "error": "Browser Use task timed out.",
                "downloads_directory": capture.get("downloads_directory"),
                "downloads": downloads,
                "verified_download_count": sum(1 for item in downloads if item.get("verified") is True),
            }

        result = self._history_result(history, capture)
        if not result["ok"]:
            if result.get("done") and result.get("task_successful") is False:
                result["error"] = "Browser Use completed the task but reported failure."
            elif not result.get("done"):
                result["error"] = "Browser Use stopped without a verified done result."
            else:
                result["error"] = "Browser Use did not verify successful completion."
        return result

    @staticmethod
    def _run_coroutine_factory(factory: Callable[[], Coroutine[Any, Any, _T]]) -> _T:
        """Run async Browser Use code from a synchronous tool handler.

        ``asyncio.run`` is correct in the normal synchronous tool path.  If a
        caller already owns an event loop in this thread, use one isolated
        worker thread rather than failing with "asyncio.run() cannot be called
        from a running event loop".
        """

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(factory())

        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="browser-use") as executor:
            return executor.submit(lambda: asyncio.run(factory())).result()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, task: str, *, timeout_seconds: float = 120) -> dict[str, Any]:
        """Run one bounded Browser Use task and return only JSON-like data."""

        task = str(task or "").strip()
        timeout = max(1.0, float(timeout_seconds))

        if not task:
            return {"ok": False, "error": "Browser Use task must not be empty."}
        if not self.model:
            return {"ok": False, "error": "Browser Use model is not configured."}
        if not self.ollama_url:
            return {"ok": False, "error": "Browser Use Ollama URL is not configured."}

        started = time.monotonic()
        acquired = self._run_lock.acquire(timeout=timeout)
        if not acquired:
            return {
                "ok": False,
                "timeout": True,
                "busy": True,
                "error": "Browser Use is busy with another task and the wait timed out.",
            }

        try:
            remaining = max(1.0, timeout - (time.monotonic() - started))
            try:
                result = self._run_coroutine_factory(lambda: self._execute(task, remaining))
            except Exception as exc:
                return {"ok": False, "error": self._safe_error(exc, 2000)}

            # Preserve all legacy keys relied on by the current tool boundary.
            result.setdefault("task", task)
            result.setdefault("answer", "")
            result.setdefault("model", self.model)
            result.setdefault("browser_use_version", self._repository_version())
            return result
        finally:
            self._run_lock.release()
