from __future__ import annotations

import base64
import json
import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from .security_utils import is_local_model_endpoint, redact_secrets


class DesktopError(RuntimeError):
    pass


@dataclass
class MonitorInfo:
    id: int
    left: int
    top: int
    width: int
    height: int
    primary: bool = False


@dataclass
class WindowInfo:
    title: str
    app: str = ""
    pid: int | None = None
    bounds: dict[str, int] | None = None
    active: bool = False


class DesktopController:
    """Accessibility-first desktop inspection and approval-gated control.

    Native semantic APIs are preferred. Pixel coordinates are a fallback and are
    never treated as stable semantic identifiers.
    """

    def __init__(self, workspace, approval, config: dict, provider=None, model_manager=None):
        self.workspace = workspace
        self.approval = approval
        self.config = config
        self.provider = provider
        self.model_manager = model_manager
        self.desktop_cfg = config.get("desktop", {})
        self.system = platform.system().lower()

    def _approve(self, action: str, reason: str, kind: str = "DESKTOP_WRITE") -> dict:
        return self.approval.request(action, reason, kind)

    def status(self) -> dict:
        return {
            "platform": self.system,
            "semantic_backend": self._semantic_backend(),
            "mouse_keyboard": self._module_available("pyautogui"),
            "screenshots": self._module_available("mss") and self._module_available("PIL"),
            "vision_enabled": bool(self.desktop_cfg.get("vision_enabled", False)),
            "vision_model": self.desktop_cfg.get("vision_model"),
            "multi_monitor": self._module_available("mss"),
            "accessibility_note": self._accessibility_note(),
        }

    @staticmethod
    def _module_available(name: str) -> bool:
        try:
            __import__(name)
            return True
        except Exception:
            return False

    def _semantic_backend(self) -> str:
        if self.system == "windows":
            return "windows-ui-automation" if shutil.which("powershell") or shutil.which("pwsh") else "window-list-only"
        if self.system == "darwin":
            return "macos-system-events" if shutil.which("osascript") else "window-list-only"
        if self.system == "linux":
            if self._module_available("pyatspi"):
                return "at-spi"
            if shutil.which("wmctrl"):
                return "wmctrl-window-list"
            return "unavailable"
        return "unavailable"

    def _accessibility_note(self) -> str:
        if self.system == "darwin":
            return "macOS requires Accessibility permission for System Events and input control."
        if self.system == "windows":
            return "Some elevated windows cannot be controlled from a non-elevated assistant process."
        if self.system == "linux":
            return "Full semantic trees require AT-SPI (pyatspi/system accessibility packages); Wayland may restrict input injection."
        return "Unsupported platform."

    def monitors(self) -> list[dict]:
        try:
            import mss
        except ImportError as exc:
            raise DesktopError('Multi-monitor support is optional. Install with: pip install -e ".[desktop]"') from exc
        with mss.mss() as sct:
            out = []
            for idx, mon in enumerate(sct.monitors[1:], start=1):
                out.append(asdict(MonitorInfo(idx, int(mon["left"]), int(mon["top"]), int(mon["width"]), int(mon["height"]), idx == 1)))
            return out

    def windows(self, include_titles: bool = False) -> dict:
        if include_titles:
            req = self._approve(
                "Read visible application window titles",
                "Window titles may contain customer names, document names, messages, or other sensitive information.",
                "SENSITIVE_READ",
            )
            if not req.get("allowed"):
                return {"ok": False, "approval_required": True, **req}

        if self.system == "windows":
            windows = self._windows_windows()
        elif self.system == "darwin":
            windows = self._mac_windows()
        elif self.system == "linux":
            windows = self._linux_windows()
        else:
            windows = []

        if not include_titles:
            windows = [
                {key: value for key, value in item.items() if key != "title"}
                for item in windows if isinstance(item, dict)
            ]
        return {"ok": True, "windows": windows, "titles_included": bool(include_titles)}

    def _run(self, args: list[str], timeout: float = 8) -> subprocess.CompletedProcess:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout, shell=False)

    def _windows_windows(self) -> list[dict]:
        exe = shutil.which("pwsh") or shutil.which("powershell")
        if not exe:
            return []
        script = r'''Get-Process | Where-Object {$_.MainWindowTitle} | ForEach-Object { [PSCustomObject]@{title=$_.MainWindowTitle;app=$_.ProcessName;pid=$_.Id} } | ConvertTo-Json -Compress'''
        p = self._run([exe, "-NoProfile", "-NonInteractive", "-Command", script])
        if p.returncode != 0 or not p.stdout.strip():
            return []
        try:
            data = json.loads(p.stdout)
            if isinstance(data, dict): data = [data]
            return [dict(x) for x in data if isinstance(x, dict)]
        except Exception:
            return []

    def _mac_windows(self) -> list[dict]:
        if not shutil.which("osascript"):
            return []
        script = '''tell application "System Events"\nset output to ""\nrepeat with p in (application processes whose background only is false)\nrepeat with w in windows of p\nset output to output & (name of p as text) & tab & (name of w as text) & linefeed\nend repeat\nend repeat\nreturn output\nend tell'''
        p = self._run(["osascript", "-e", script])
        out=[]
        for line in p.stdout.splitlines():
            if "\t" in line:
                app,title=line.split("\t",1); out.append({"app":app,"title":title})
        return out

    def _linux_windows(self) -> list[dict]:
        if shutil.which("wmctrl"):
            p = self._run(["wmctrl", "-lp"])
            out=[]
            for line in p.stdout.splitlines():
                parts=line.split(None,4)
                if len(parts)>=5:
                    try: pid=int(parts[2])
                    except Exception: pid=None
                    out.append({"title":parts[4],"pid":pid,"app":parts[3]})
            return out
        return []

    def accessibility_tree(self, max_nodes: int = 250) -> dict:
        max_nodes=max(10,min(int(max_nodes),1000))
        req=self._approve("Read current desktop accessibility tree", "Application UI text may contain sensitive information.", "SENSITIVE_READ")
        if not req.get("allowed"):
            return {"ok":False,"approval_required":True,**req}
        try:
            if self.system == "windows":
                nodes=self._windows_accessibility(max_nodes)
            elif self.system == "darwin":
                nodes=self._mac_accessibility(max_nodes)
            elif self.system == "linux":
                nodes=self._linux_accessibility(max_nodes)
            else:
                raise DesktopError("Unsupported platform")
            return {"ok":True,"backend":self._semantic_backend(),"nodes":nodes,"truncated":len(nodes)>=max_nodes}
        except Exception as exc:
            return {"ok":False,"backend":self._semantic_backend(),"error":redact_secrets(exc,1200),"fallback":"Use windows() or an approved screenshot/vision analysis."}

    def _windows_accessibility(self, max_nodes: int) -> list[dict]:
        exe = shutil.which("pwsh") or shutil.which("powershell")
        if not exe: raise DesktopError("PowerShell unavailable")
        # UIAutomation is part of Windows; this intentionally reads only the foreground subtree.
        script = rf'''
Add-Type -AssemblyName UIAutomationClient
$root=[System.Windows.Automation.AutomationElement]::FocusedElement
if ($null -eq $root) {{ exit 0 }}
$walker=[System.Windows.Automation.TreeWalker]::ControlViewWalker
$q=New-Object System.Collections.Queue
$q.Enqueue($root)
$out=@()
while ($q.Count -gt 0 -and $out.Count -lt {max_nodes}) {{
  $e=$q.Dequeue(); try {{ $r=$e.Current.BoundingRectangle; $out += [PSCustomObject]@{{name=$e.Current.Name;type=$e.Current.ControlType.ProgrammaticName;automation_id=$e.Current.AutomationId;enabled=$e.Current.IsEnabled;bounds=@{{left=[int]$r.Left;top=[int]$r.Top;width=[int]$r.Width;height=[int]$r.Height}}}} }} catch {{}}
  try {{ $c=$walker.GetFirstChild($e); while($null -ne $c) {{ $q.Enqueue($c); $c=$walker.GetNextSibling($c) }} }} catch {{}}
}}
$out | ConvertTo-Json -Compress -Depth 4
'''
        p=self._run([exe,"-NoProfile","-NonInteractive","-Command",script],timeout=12)
        if p.returncode!=0: raise DesktopError(p.stderr.strip() or "UI Automation failed")
        if not p.stdout.strip(): return []
        data=json.loads(p.stdout); return data if isinstance(data,list) else [data]

    def _mac_accessibility(self, max_nodes: int) -> list[dict]:
        if not shutil.which("osascript"): raise DesktopError("osascript unavailable")
        script=f'''tell application "System Events"\nset fp to first application process whose frontmost is true\nset out to {{}}\ntry\nset els to entire contents of front window of fp\nrepeat with e in els\nif (count of out) is greater than or equal to {max_nodes} then exit repeat\ntry\nset end of out to ((role of e as text) & tab & (description of e as text) & tab & (title of e as text))\nend try\nend repeat\nend try\nreturn out as text\nend tell'''
        p=self._run(["osascript","-e",script],timeout=12)
        if p.returncode!=0: raise DesktopError(p.stderr.strip() or "System Events accessibility failed")
        return [{"summary":x.strip()} for x in p.stdout.split(", ") if x.strip()][:max_nodes]

    def _linux_accessibility(self, max_nodes: int) -> list[dict]:
        try:
            import pyatspi
        except ImportError as exc:
            raise DesktopError("AT-SPI Python bindings are not installed. Install your distro's pyatspi package.") from exc
        desktop=pyatspi.Registry.getDesktop(0); nodes=[]
        def walk(obj, depth=0):
            if len(nodes)>=max_nodes: return
            try:
                states=obj.getState(); nodes.append({"name":str(obj.name or ""),"role":str(obj.getRoleName()),"depth":depth,"states":[str(s) for s in states.getStates()]})
                for child in obj: walk(child,depth+1)
            except Exception: return
        for app in desktop:
            try:
                if app.getState().contains(pyatspi.STATE_ACTIVE) or app.getState().contains(pyatspi.STATE_FOCUSED): walk(app)
            except Exception: continue
        return nodes

    def _pyautogui(self):
        try:
            import pyautogui
            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = float(self.desktop_cfg.get("input_pause_seconds", 0.08))
            return pyautogui
        except ImportError as exc:
            raise DesktopError('Mouse/keyboard control is optional. Install with: pip install -e ".[desktop]"') from exc

    def click(self, x: int, y: int, button: str = "left") -> dict:
        if button not in {"left","right","middle"}: return {"ok":False,"error":"Invalid mouse button"}
        req=self._approve(f"Desktop click at ({int(x)}, {int(y)}) using {button}", "Mouse input can activate controls in arbitrary applications.")
        if not req.get("allowed"): return {"ok":False,"approval_required":True,**req}
        self._pyautogui().click(int(x),int(y),button=button); return {"ok":True}

    def type_text(self, text: str, interval: float = 0.01) -> dict:
        if len(text)>10000: return {"ok":False,"error":"Text is too long for desktop typing."}
        req=self._approve(f"Type {len(text)} characters into the active application", "Keyboard input may submit data to an arbitrary application.")
        if not req.get("allowed"): return {"ok":False,"approval_required":True,**req}
        self._pyautogui().write(text,interval=max(0,min(float(interval),0.5))); return {"ok":True,"characters":len(text)}

    def hotkey(self, keys: list[str]) -> dict:
        keys=[str(x).lower() for x in keys][:6]
        if not keys: return {"ok":False,"error":"No keys supplied"}
        req=self._approve(f"Send desktop hotkey: {'+'.join(keys)}", "Keyboard shortcuts can close windows, submit forms, or trigger application actions.")
        if not req.get("allowed"): return {"ok":False,"approval_required":True,**req}
        self._pyautogui().hotkey(*keys); return {"ok":True,"keys":keys}

    def move_mouse(self, x: int, y: int, duration: float = 0.2) -> dict:
        req=self._approve(f"Move pointer to ({int(x)}, {int(y)})", "Pointer movement changes desktop state.", "DESKTOP_WRITE")
        if not req.get("allowed"): return {"ok":False,"approval_required":True,**req}
        self._pyautogui().moveTo(int(x),int(y),duration=max(0,min(float(duration),2.0))); return {"ok":True}

    def screenshot(self, destination: str = "artifacts/desktop-screenshot.png", monitor_id: int = 0) -> dict:
        target=self.workspace.resolve(destination)
        req=self._approve(f"Capture desktop screenshot -> {target}", "Desktop screenshots may contain passwords, messages or private documents.", "SENSITIVE_READ")
        if not req.get("allowed"): return {"ok":False,"approval_required":True,**req}
        try:
            import mss
            from PIL import Image
        except ImportError as exc:
            return {"ok":False,"error":str(DesktopError('Screenshot support is optional. Install with: pip install -e ".[desktop]"'))}
        with mss.mss() as sct:
            idx=int(monitor_id)
            if idx<0 or idx>=len(sct.monitors): return {"ok":False,"error":"Unknown monitor id"}
            mon=sct.monitors[idx]
            raw=sct.grab(mon); image=Image.frombytes("RGB",raw.size,raw.rgb)
            target.parent.mkdir(parents=True,exist_ok=True); image.save(target)
        return {"ok":True,"path":str(target),"monitor_id":idx,"width":raw.width,"height":raw.height}

    def analyze_screen(self, prompt: str = "Describe the visible UI and actionable controls.", monitor_id: int = 0) -> dict:
        if not bool(self.desktop_cfg.get("vision_enabled", False)):
            return {"ok":False,"error":"Desktop vision is disabled. Set desktop.vision_enabled=true explicitly."}
        model=str(self.desktop_cfg.get("vision_model") or "").strip()
        if not model: return {"ok":False,"error":"desktop.vision_model is not configured."}
        if self.provider is None or self.model_manager is None: return {"ok":False,"error":"Model provider unavailable."}
        allow_remote=bool(self.desktop_cfg.get("allow_remote_vision",False))
        if not is_local_model_endpoint(self.provider.base_url) and not allow_remote:
            return {"ok":False,"error":"Remote desktop vision is blocked because screenshots may contain sensitive data."}
        with tempfile.NamedTemporaryFile(prefix="living-assistant-screen-",suffix=".png",delete=False) as f:
            tmp=Path(f.name)
        try:
            # Avoid a second approval by doing the capture here under one sensitive-read request.
            req=self._approve(f"Analyze monitor {monitor_id} screenshot with local vision model {model}", "A screenshot of the desktop will be read by the configured vision model.", "SENSITIVE_READ")
            if not req.get("allowed"): return {"ok":False,"approval_required":True,**req}
            try:
                import mss
                from PIL import Image
            except ImportError as exc: raise DesktopError('Vision screenshots require the desktop optional dependencies.') from exc
            with mss.mss() as sct:
                idx=int(monitor_id)
                if idx<0 or idx>=len(sct.monitors): return {"ok":False,"error":"Unknown monitor id"}
                raw=sct.grab(sct.monitors[idx]); Image.frombytes("RGB",raw.size,raw.rgb).save(tmp)
            encoded=base64.b64encode(tmp.read_bytes()).decode("ascii")
            message={"role":"user","content":str(prompt)[:4000],"images":[encoded]}
            with self.model_manager.lease(model) as keep_alive:
                result=self.provider.chat(model,[message],keep_alive=keep_alive)
            content=((result.get("message") or {}).get("content") or "") if isinstance(result,dict) else ""
            return {"ok":True,"model":model,"analysis":str(content)[:20000],"monitor_id":int(monitor_id)}
        except Exception as exc:
            return {"ok":False,"error":redact_secrets(exc,1600)}
        finally:
            try: tmp.unlink(missing_ok=True)
            except Exception: pass
