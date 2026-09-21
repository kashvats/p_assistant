from __future__ import annotations

import ctypes
import json
# import os
import threading
import time
import tkinter as tk
# from tkinter import font as tkfont
# from urllib.parse import urljoin
import urllib.request
import urllib.error

try:
    from .api_auth import ensure_api_token
    from .config import data_dir
except ImportError:
    from living_assistant.api_auth import ensure_api_token
#     from living_assistant.config import data_dir


def _get_active_window_title() -> str:
    """Return the title of the current foreground window on Windows."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            return buff.value
    except Exception:
        pass
    return "Desktop"


class FloatingOverlay:
    """A modern, always-on-top floating HUD and companion widget for Windows."""

    def __init__(self, base_url: str = "http://127.0.0.1:8787"):
        self.base_url = base_url.rstrip("/")
        self.token, _, _ = ensure_api_token()
        self.session_id = f"overlay_{int(time.time())}"
        
        self.root = tk.Tk()
        self.root.title("Living Assistant")
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True) # Remove standard windows titlebar for modern borderless look
        self.root.attributes("-alpha", 0.95) # Slight glass transparency
        
        # Color Theme (Consistent with Living Assistant WebUI)
        self.BG_MAIN = "#0d131d"
        self.root.wm_attributes("-transparentcolor", self.BG_MAIN) # Make main background invisible so cards float
        self.BG_CARD = "#141c2a"
        self.BG_INPUT = "#0a0e16"
        self.BORDER = "#223048"
        self.ACCENT = "#7c9cff"
        self.TEXT_MAIN = "#edf2ff"
        self.TEXT_MUTED = "#8c9bb4"
        self.COLOR_GREEN = "#55d68b"
        self.COLOR_WARN = "#f3bd5d"

        self.root.configure(bg=self.BORDER)

        # Positioning defaults (Top-right corner, always visible)
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.hud_w = 420
        self.hud_h = 580
        self.eye_w = 200
        self.eye_h = 135

        self.pos_x = max(20, screen_w - self.hud_w - 40)
        self.pos_y = 60

        self.is_expanded = False  # Start as floating Eye
        self.is_scanning = False
        self.scan_pos = 70
        self.scan_dir = 1
        self._drag_start_x = 0
        self._drag_start_y = 0

        self._build_ui()
        self._set_expanded(False)
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

        # Context and inquiry polling
        self.active_inquiry_id = None
        self.current_window = _get_active_window_title()
        self._poll_context()
        self._poll_inquiries()
        self._draw_eye()

    def _build_ui(self):
        import customtkinter as ctk
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Make the inner container transparent so we see only rounded cards
        self.container = ctk.CTkFrame(self.root, fg_color="transparent")
        self.container.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # -------------------------------------------------------------
        # 1. EYE HEADER (Active in both Eye-Only and Expanded states)
        # -------------------------------------------------------------
        self.header = ctk.CTkFrame(self.container, fg_color=self.BG_CARD, corner_radius=15, cursor="fleur")
        self.header.pack(fill=tk.X, side=tk.TOP)

        self.control_bar = ctk.CTkFrame(self.header, fg_color="transparent", height=30)
        self.control_bar.pack(fill=tk.X, side=tk.TOP, padx=10, pady=(6, 0))

        self.lbl_dot = ctk.CTkLabel(self.control_bar, text="●", text_color=self.COLOR_GREEN, font=ctk.CTkFont(size=10))
        self.lbl_dot.pack(side=tk.LEFT, padx=(4, 2))

        self.lbl_title = ctk.CTkLabel(self.control_bar, text="LIVING ASSISTANT", text_color=self.TEXT_MUTED, font=ctk.CTkFont(size=10, weight="bold"))
        self.lbl_title.pack(side=tk.LEFT, padx=4)
        self.lbl_title.bind("<Button-1>", self._start_drag)
        self.lbl_title.bind("<B1-Motion>", self._on_drag)

        self.btn_close = ctk.CTkLabel(self.control_bar, text="✕", text_color=self.TEXT_MUTED, font=ctk.CTkFont(size=14), cursor="hand2")
        self.btn_close.pack(side=tk.RIGHT, padx=(4, 8))
        self.btn_close.bind("<Button-1>", lambda e: self.root.destroy())

        self.btn_toggle = ctk.CTkLabel(self.control_bar, text="💬", text_color=self.TEXT_MUTED, font=ctk.CTkFont(size=14), cursor="hand2")
        self.btn_toggle.pack(side=tk.RIGHT, padx=8)
        self.btn_toggle.bind("<Button-1>", lambda e: self._toggle_expand())

        # Eye Canvas (Interactive Cybernetic Eye - Must stay tk.Canvas for polygon drawing)
        self.eye_canvas = tk.Canvas(self.header, width=150, height=72, bg=self.BG_CARD, highlightthickness=0, cursor="hand2")
        self.eye_canvas.pack(pady=(2, 4))
        self.eye_canvas.bind("<Button-1>", lambda e: self._ask_active_screen())
        self.eye_canvas.bind("<B1-Motion>", self._on_drag)

        self.lbl_eye_status = ctk.CTkLabel(self.header, text="👁 Click Eye to Read Screen", text_color=self.ACCENT, font=ctk.CTkFont(size=11), cursor="hand2")
        self.lbl_eye_status.pack(pady=(0, 10))
        self.lbl_eye_status.bind("<Button-1>", lambda e: self._ask_active_screen())

        self.header.bind("<Button-1>", self._start_drag)
        self.header.bind("<B1-Motion>", self._on_drag)

        # -------------------------------------------------------------
        # 2. EXPANDED CONTENT BODY (Drawer)
        # -------------------------------------------------------------
        self.body_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.body_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        # Active Context / Screen bar
        self.context_bar = ctk.CTkFrame(self.body_frame, fg_color=self.BG_CARD, corner_radius=10, height=40)
        self.context_bar.pack(fill=tk.X, pady=(0, 8))
        self.context_bar.pack_propagate(False)

        self.lbl_context = ctk.CTkLabel(self.context_bar, text="🖥 Active: Detecting...", text_color=self.TEXT_MUTED, font=ctk.CTkFont(size=11))
        self.lbl_context.pack(side=tk.LEFT, padx=12)

        self.btn_ask_screen = ctk.CTkButton(
            self.context_bar, text="👁 Screen", command=self._ask_active_screen, 
            fg_color="#22324f", text_color=self.ACCENT, font=ctk.CTkFont(size=11, weight="bold"),
            width=70, height=26, corner_radius=6, cursor="hand2"
        )
        self.btn_ask_screen.pack(side=tk.RIGHT, padx=10)

        # Proactive Question Card
        self.inquiry_card = ctk.CTkFrame(self.body_frame, fg_color="#1c2538", border_color=self.COLOR_WARN, border_width=1, corner_radius=10)
        self.lbl_inquiry = ctk.CTkLabel(self.inquiry_card, text="Question?", text_color=self.COLOR_WARN, font=ctk.CTkFont(size=12, weight="bold"), wraplength=340, justify="left")
        self.lbl_inquiry.pack(fill=tk.X, padx=12, pady=(10, 4))

        self.inquiry_btn_box = ctk.CTkFrame(self.inquiry_card, fg_color="transparent")
        self.inquiry_btn_box.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.btn_inq_yes = ctk.CTkButton(self.inquiry_btn_box, text="Yes", command=lambda: self._answer_inquiry(True), fg_color="#1b3d2c", text_color=self.COLOR_GREEN, font=ctk.CTkFont(size=11, weight="bold"), width=60, height=28, corner_radius=6, cursor="hand2")
        self.btn_inq_yes.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_inq_no = ctk.CTkButton(self.inquiry_btn_box, text="No", command=lambda: self._answer_inquiry(False), fg_color="#3d1b22", text_color="#ff7575", font=ctk.CTkFont(size=11, weight="bold"), width=60, height=28, corner_radius=6, cursor="hand2")
        self.btn_inq_no.pack(side=tk.LEFT, padx=6)

        self.btn_inq_dismiss = ctk.CTkButton(self.inquiry_btn_box, text="Dismiss", command=self._dismiss_inquiry, fg_color="#223048", text_color=self.TEXT_MUTED, font=ctk.CTkFont(size=11), width=60, height=28, corner_radius=6, cursor="hand2")
        self.btn_inq_dismiss.pack(side=tk.RIGHT)

        # Message Display Stream (We use a CTkTextbox for modern look but keep tk.Text tags)
        self.chat_display = ctk.CTkTextbox(self.body_frame, fg_color=self.BG_CARD, text_color=self.TEXT_MAIN, font=ctk.CTkFont(size=12), corner_radius=12, wrap="word", border_width=0)
        self.chat_display.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        self.chat_display.tag_config("user", foreground=self.ACCENT)
        self.chat_display.tag_config("assistant", foreground=self.TEXT_MAIN)
        self.chat_display.tag_config("system", foreground=self.TEXT_MUTED)

        self._append_message("System", "Living Assistant floating companion active. Ask anything or click 👁 Screen.", "system")

        # Input Composer Frame
        self.composer_frame = ctk.CTkFrame(self.body_frame, fg_color="transparent")
        self.composer_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.input_text = ctk.CTkTextbox(self.composer_frame, height=45, fg_color=self.BG_INPUT, text_color=self.TEXT_MAIN, border_color=self.BORDER, border_width=1, corner_radius=12, font=ctk.CTkFont(size=12), wrap="word")
        self.input_text.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.input_text.bind("<Return>", self._on_enter_press)

        self.btn_send = ctk.CTkButton(self.composer_frame, text="➤", command=self._send_message, fg_color=self.ACCENT, text_color="#0b111b", font=ctk.CTkFont(size=16, weight="bold"), width=45, height=45, corner_radius=12, cursor="hand2")
        self.btn_send.pack(side=tk.RIGHT)

    # -------------------------------------------------------------
    # Eye Rendering & Cybernetic Animations
    # -------------------------------------------------------------
    def _draw_eye(self):
        self.eye_canvas.delete("all")
        w, h = 150, 72
        cx, cy = 75, 36

        # Eye contour (smooth cybernetic almond)
        eye_pts = [12, cy, cx, 8, w - 12, cy, cx, h - 8]
        outline_col = "#f59e0b" if self.is_scanning else ("#55d68b" if self.active_inquiry_id else "#38bdf8")
        sclera_col = "#1f1e14" if self.is_scanning else "#0d1424"
        self.eye_canvas.create_polygon(eye_pts, smooth=True, fill=sclera_col, outline=outline_col, width=2)

        # Iris radius & dilated pupil when seeing screen
        iris_r = 20
        pupil_r = 10 if not self.is_scanning else 13
        iris_outer = "#d97706" if self.is_scanning else "#0284c7"
        iris_inner = "#fbbf24" if self.is_scanning else "#38bdf8"

        self.eye_canvas.create_oval(cx - iris_r, cy - iris_r, cx + iris_r, cy + iris_r, fill=iris_outer, outline=iris_inner, width=2)
        self.eye_canvas.create_oval(cx - (iris_r - 5), cy - (iris_r - 5), cx + (iris_r - 5), cy + (iris_r - 5), fill=iris_inner, outline="")
        self.eye_canvas.create_oval(cx - pupil_r, cy - pupil_r, cx + pupil_r, cy + pupil_r, fill="#05080e", outline="")
        self.eye_canvas.create_oval(cx - 5, cy - 6, cx - 1, cy - 2, fill="#ffffff", outline="")

        # Scanning beam if seeing screen
        if self.is_scanning:
            scan_x = self.scan_pos
            self.eye_canvas.create_line(scan_x, 10, scan_x, h - 10, fill="#fef08a", width=2)
            self.eye_canvas.create_oval(scan_x - 3, cy - 3, scan_x + 3, cy + 3, fill="#ffffff", outline="")

    def _animate_eye(self):
        if self.is_scanning:
            self.scan_pos += self.scan_dir * 5
            if self.scan_pos >= 130:
                self.scan_dir = -1
            elif self.scan_pos <= 20:
                self.scan_dir = 1
            self._draw_eye()
            self.root.after(35, self._animate_eye)
        else:
            self.scan_pos = 75
            self._draw_eye()

    # -------------------------------------------------------------
    # Drag & Window Mode Helpers
    # -------------------------------------------------------------
    def _start_drag(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_drag(self, event):
        dx = event.x - self._drag_start_x
        dy = event.y - self._drag_start_y
        self.pos_x += dx
        self.pos_y += dy
        self.root.geometry(f"+{self.pos_x}+{self.pos_y}")

    def _set_expanded(self, expanded: bool):
        self.is_expanded = expanded
        if expanded:
            self.body_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(6, 10))
            self.btn_toggle.configure(text="🗕")
            self.root.geometry(f"{self.hud_w}x{self.hud_h}+{self.pos_x}+{self.pos_y}")
        else:
            self.body_frame.pack_forget()
            self.btn_toggle.configure(text="💬")
            self.root.geometry(f"{self.eye_w}x{self.eye_h}+{self.pos_x}+{self.pos_y}")

    def _toggle_expand(self):
        self._set_expanded(not self.is_expanded)

    # -------------------------------------------------------------
    # Context & Active Window Monitoring
    # -------------------------------------------------------------
    def _poll_context(self):
        title = _get_active_window_title()
        if title and title != self.current_window and title != "Living Assistant":
            self.current_window = title
            short_title = title if len(title) <= 24 else title[:22] + "..."
            self.lbl_context.configure(text=f"🖥 Active: {short_title}")
            if not self.is_scanning:
                self.lbl_eye_status.configure(text=f"👁 Watching: {short_title}")
        self.root.after(1500, self._poll_context)

    # -------------------------------------------------------------
    # Messaging & API Dispatch
    # -------------------------------------------------------------
    def _append_message(self, sender: str, text: str, tag: str = "assistant"):
        self.chat_display.configure(state=tk.NORMAL)
        if sender:
            self.chat_display.insert(tk.END, f"{sender}: ", tag)
        self.chat_display.insert(tk.END, f"{text}\n\n", tag)
        self.chat_display.see(tk.END)
        self.chat_display.configure(state=tk.DISABLED)

    def _on_enter_press(self, event):
        if not event.state & 0x0001:  # Not Shift+Enter
            self._send_message()
            return "break"

    def _send_message(self):
        msg = self.input_text.get("1.0", tk.END).strip()
        if not msg:
            return
        self.input_text.delete("1.0", tk.END)
        self._append_message("You", msg, "user")
        self.lbl_dot.configure(text_color=self.COLOR_WARN)
        threading.Thread(target=self._query_backend, args=(msg,), daemon=True).start()

    def _ask_active_screen(self):
        if self.is_scanning:
            return
        self.is_scanning = True
        self.scan_pos = 75
        self.scan_dir = 1
        self.lbl_eye_status.configure(text="👁 Seeing Screen...", text_color=self.COLOR_WARN)
        self.lbl_dot.configure(text_color=self.COLOR_WARN)
        self._animate_eye()

        target = self.current_window
        self._append_message("You", f"[Analyzing Screen Visuals (Focus: {target})]", "user")
        threading.Thread(target=self._analyze_screen_backend, args=(target,), daemon=True).start()

    def _analyze_screen_backend(self, target_window: str):
        url = f"{self.base_url}/desktop/analyze-screen"
        prompt = (
            f"Active foreground application: '{target_window}'. "
            "Analyze the screenshot of the display. Describe what application or code is visible, "
            "identify any visible errors, warnings, or status messages, and suggest actionable recommendations."
        )
        payload = json.dumps({"prompt": prompt, "monitor_id": 0}).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self.root.after(0, self._on_screen_analyzed, data)
        except Exception as e:
            self.root.after(0, self._on_screen_analysis_error, str(e))

    def _on_screen_analyzed(self, data: dict):
        self.is_scanning = False
        self._animate_eye()
        self.lbl_eye_status.configure(text=f"👁 Watching: {self.current_window[:20]}", text_color=self.ACCENT)
        self.lbl_dot.configure(text_color=self.COLOR_GREEN)
        if data.get("ok"):
            analysis = data.get("analysis", "No analysis text returned.")
            model_name = data.get("model", "Vision")
            self._append_message("Assistant", f"👁 [{model_name} Screen Analysis]:\n{analysis}", "assistant")
            if not self.is_expanded:
                self._set_expanded(True)
        else:
            err = data.get("error", "Unknown vision error")
            self._append_message("System", f"Screen analysis failed: {err}", "system")

    def _on_screen_analysis_error(self, error: str):
        self.is_scanning = False
        self._animate_eye()
        self.lbl_eye_status.configure(text="👁 Read Screen Failed", text_color="#ff5555")
        self.lbl_dot.configure(text_color="#ff5555")
        self._append_message("System", f"Vision request failed: {error}", "system")
        if not self.is_expanded:
            self._set_expanded(True)

    def show_inquiry(self, question: str, inquiry_id: str | None = None):
        """Displays a proactive question card to learn from user actions."""
        self.active_inquiry_id = inquiry_id
        self.lbl_inquiry.configure(text=question)
        self.inquiry_card.pack(fill=tk.X, pady=(0, 8), before=self.chat_display)
        if not self.is_expanded:
            self._set_expanded(True)

    def _dismiss_inquiry(self):
        self.inquiry_card.pack_forget()
        self.active_inquiry_id = None

    def _answer_inquiry(self, fixed: bool):
        inq_id = self.active_inquiry_id
        self._dismiss_inquiry()
        msg = "Yes, that fixed it." if fixed else "No, still broken."
        self._append_message("You", msg, "user")
        if inq_id:
            threading.Thread(target=self._resolve_inquiry_backend, args=(inq_id, fixed), daemon=True).start()

    def _resolve_inquiry_backend(self, inquiry_id: str, fixed: bool):
        url = f"{self.base_url}/inquiries/{inquiry_id}/resolve"
        payload = json.dumps({"fixed": fixed, "feedback": "User clicked confirmation"}).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if fixed:
                    lesson = (data.get("learned_lesson") or {}).get("lesson", "Lesson learned.")
                    self.root.after(0, self._append_message, "Experience Engine", f"✦ Verified recovery lesson saved with 95% confidence:\n{lesson}", "system")
                else:
                    self.root.after(0, self._append_message, "Experience Engine", "✦ Noted: Issue remains unresolved.", "system")
        except Exception as e:
            self.root.after(0, self._append_message, "System", f"Could not record lesson: {e}", "system")

    def _poll_inquiries(self):
        def _fetch():
            try:
                url = f"{self.base_url}/inquiries/pending"
                headers = {"Authorization": f"Bearer {self.token}"}
                req = urllib.request.Request(url, headers=headers, method="GET")
                with urllib.request.urlopen(req, timeout=3) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    inquiries = data.get("inquiries", [])
                    if inquiries:
                        first = inquiries[0]
                        if self.active_inquiry_id != first["id"]:
                            self.root.after(0, self.show_inquiry, first["question"], first["id"])
            except Exception:
                pass
            finally:
                try:
                    self.root.after(3000, self._poll_inquiries)
                except Exception:
                    pass

        threading.Thread(target=_fetch, daemon=True).start()

    def _query_backend(self, message: str, context: str = ""):
        url = f"{self.base_url}/ask"
        payload = json.dumps({"message": message, "context": context, "session_id": self.session_id}).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                ans = data.get("answer", "No answer received.")
                self.root.after(0, self._on_query_success, ans)
        except Exception as e:
            self.root.after(0, self._on_query_error, str(e))

    def _on_query_success(self, answer: str):
        self.lbl_dot.configure(text_color=self.COLOR_GREEN)
        self._append_message("Assistant", answer, "assistant")

    def _on_query_error(self, error: str):
        self.lbl_dot.configure(fg="#ff5555")
        self._append_message("System", f"Communication error: {error}", "system")

    def run(self):
        self.root.mainloop()


def start_overlay(base_url: str = "http://127.0.0.1:8787"):
    """Launch the floating overlay application."""
    overlay = FloatingOverlay(base_url=base_url)
    overlay.run()


if __name__ == "__main__":
    start_overlay()
