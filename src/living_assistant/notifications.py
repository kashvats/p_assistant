from __future__ import annotations
import platform, shutil, subprocess

class Notifier:
    def send(self, title: str, message: str) -> dict:
        title = str(title)[:120]
        message = str(message)[:500]
        system = platform.system()
        try:
            if system == "Darwin" and shutil.which("osascript"):
                safe_t = title.replace('"', '\\"')
                safe_m = message.replace('"', '\\"')
                subprocess.run(["osascript", "-e", f'display notification "{safe_m}" with title "{safe_t}"'], timeout=5)
                return {"ok": True, "backend": "osascript"}
            if system == "Linux" and shutil.which("notify-send"):
                subprocess.run(["notify-send", title, message], timeout=5)
                return {"ok": True, "backend": "notify-send"}
            if system == "Windows" and shutil.which("powershell"):
                script = (
                    "Add-Type -AssemblyName System.Windows.Forms; "
                    "$n=New-Object System.Windows.Forms.NotifyIcon; "
                    "$n.Icon=[System.Drawing.SystemIcons]::Information; "
                    "$n.BalloonTipTitle=$env:LA_TITLE; $n.BalloonTipText=$env:LA_MSG; "
                    "$n.Visible=$true; $n.ShowBalloonTip(5000); Start-Sleep -Seconds 1; $n.Dispose()"
                )
                env = __import__("os").environ.copy(); env["LA_TITLE"] = title; env["LA_MSG"] = message
                subprocess.run(["powershell", "-NoProfile", "-Command", script], timeout=8, env=env)
                return {"ok": True, "backend": "powershell"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        print(f"[{title}] {message}")
        return {"ok": True, "backend": "console"}
