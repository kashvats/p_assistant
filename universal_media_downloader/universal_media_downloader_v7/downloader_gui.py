import io
import json
import math
import os
import platform
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    import yt_dlp
    from yt_dlp.utils import DownloadError
except ImportError:
    raise SystemExit("yt-dlp is not installed. Start this app using run.bat or run.sh.")

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

try:
    from plyer import notification
except ImportError:
    notification = None

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    TkBase = TkinterDnD.Tk
except Exception:
    DND_FILES = None
    TkBase = tk.Tk


APP_NAME = "Universal Media Downloader"
SYSTEM = platform.system().lower()
APP_DIR = Path(__file__).resolve().parent
DEFAULT_DIR = Path.home() / "Downloads" / "MediaDownloader"
HISTORY_FILE = APP_DIR / "history.json"
SETTINGS_FILE = APP_DIR / "settings.json"
QUEUE_FILE = APP_DIR / "queue.json"

BEST_QUALITY_LABEL = "Best available"
AUDIO_ONLY_LABEL = "Audio only"
DEFAULT_AUDIO_LABEL = "Original / Default"
MULTI_AUDIO_LABEL = "Multiple languages…"
NO_SUBTITLES_LABEL = "None"
MULTI_SUBTITLES_LABEL = "Multiple subtitles…"

COMPRESSION_PRESETS = {
    "Small reduction": {"crf": "24", "preset": "medium", "audio_bitrate": "160k"},
    "Balanced": {"crf": "27", "preset": "medium", "audio_bitrate": "128k"},
    "Maximum": {"crf": "30", "preset": "slow", "audio_bitrate": "96k"},
}

SPEED_LIMITS = {
    "Unlimited": None,
    "1 MB/s": 1 * 1024 * 1024,
    "2 MB/s": 2 * 1024 * 1024,
    "5 MB/s": 5 * 1024 * 1024,
    "10 MB/s": 10 * 1024 * 1024,
}

CODEC_PATTERNS = {
    "Recommended": None,
    "Smaller file": "av01",
    "Best compatibility": "avc1",
    "VP9": "vp9",
    "H.265 / HEVC": "hev",
}

FILENAME_PRESETS = {
    "Simple title": "%(title)s [%(id)s].%(ext)s",
    "Title + channel": "%(title)s - %(channel|uploader)s [%(id)s].%(ext)s",
    "Playlist number + title": "%(playlist_index&{} - |)s%(title)s [%(id)s].%(ext)s",
    "Title + quality": "%(title)s [%(resolution)s] [%(id)s].%(ext)s",
}

QUICK_PRESETS = {
    "Best Quality": {"quality": BEST_QUALITY_LABEL, "compress": False},
    "1080p Recommended": {"quality": "1080p", "compress": False},
    "720p Small Size": {"quality": "720p", "compress": True, "compression_level": "Balanced"},
    "MP3 Audio": {"quality": AUDIO_ONLY_LABEL, "compress": False},
    "Best + All Audio": {"quality": BEST_QUALITY_LABEL, "compress": False, "select_all_audio": True},
}

DARK_BG = "#1f1f1f"
DARK_FG = "#f0f0f0"
DARK_FIELD = "#2a2a2a"


class DownloaderApp(TkBase):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("980x820")
        self.minsize(860, 700)

        self.events = queue.Queue()
        self.worker = None
        self.analysis_worker = None
        self.queue_worker = None
        self.analysis_timer = None
        self.clipboard_timer = None
        self.last_analyzed_url = ""
        self.last_clipboard = ""
        self.last_downloaded_path = None

        self.pause_requested = threading.Event()
        self.cancel_requested = threading.Event()

        self.audio_options = []
        self.subtitle_options = []
        self.quality_map = {BEST_QUALITY_LABEL: None}
        self.analysis_formats = []
        self.analysis_duration = None
        self.analysis_info = {}
        self.thumbnail_photo = None

        self.history = self._load_json(HISTORY_FILE, [])
        self.settings = self._load_json(SETTINGS_FILE, {})
        self.queue_jobs = self._load_json(QUEUE_FILE, [])
        self.site_preferences = self.settings.get("site_preferences", {})

        self.url_var = tk.StringVar()
        self.folder_var = tk.StringVar(value=self.settings.get("folder", str(DEFAULT_DIR)))
        self.quality_var = tk.StringVar(value=BEST_QUALITY_LABEL)
        self.audio_var = tk.StringVar(value=DEFAULT_AUDIO_LABEL)
        self.subtitle_var = tk.StringVar(value=NO_SUBTITLES_LABEL)

        self.codec_var = tk.StringVar(value=self.settings.get("codec", "Recommended"))
        self.container_var = tk.StringVar(value=self.settings.get("container", "Auto"))
        self.playlist_var = tk.BooleanVar(value=self.settings.get("playlist", True))

        self.compress_var = tk.BooleanVar(value=self.settings.get("compress", False))
        self.compression_level_var = tk.StringVar(value=self.settings.get("compression_level", "Balanced"))
        self.delete_original_var = tk.BooleanVar(value=self.settings.get("delete_original", True))

        self.embed_subtitles_var = tk.BooleanVar(value=self.settings.get("embed_subtitles", True))
        self.include_auto_subs_var = tk.BooleanVar(value=self.settings.get("include_auto_subs", True))
        self.split_chapters_var = tk.BooleanVar(value=self.settings.get("split_chapters", False))

        self.playlist_start_var = tk.StringVar()
        self.playlist_end_var = tk.StringVar()
        self.playlist_items_var = tk.StringVar()
        self.skip_shorts_var = tk.BooleanVar(value=self.settings.get("skip_shorts", False))
        self.skip_live_var = tk.BooleanVar(value=self.settings.get("skip_live", True))

        self.speed_var = tk.StringVar(value=self.settings.get("speed", "Unlimited"))
        self.cookies_var = tk.StringVar(value=self.settings.get("cookies", "None"))
        self.filename_var = tk.StringVar(value=self.settings.get("filename", "Playlist number + title"))

        self.status_var = tk.StringVar(value="Paste a link to begin")
        self.progress_var = tk.DoubleVar(value=0)
        self.media_title_var = tk.StringVar(value="No video analyzed yet")
        self.media_meta_var = tk.StringVar(value="")
        self.estimate_var = tk.StringVar(value="")
        self.version_var = tk.StringVar(value=f"yt-dlp {getattr(yt_dlp.version, '__version__', 'installed')}")
        self.advanced_visible = tk.BooleanVar(value=self.settings.get("advanced_visible", False))

        self.clipboard_watch_var = tk.BooleanVar(value=self.settings.get("clipboard_watch", True))
        self.notify_var = tk.BooleanVar(value=self.settings.get("notify", True))
        self.queue_finish_action_var = tk.StringVar(value=self.settings.get("queue_finish_action", "Do nothing"))
        self.theme_var = tk.StringVar(value=self.settings.get("theme", "System"))
        self.preferred_audio_var = tk.StringVar(value=self.settings.get("preferred_audio", ""))
        self.fallback_audio_var = tk.StringVar(value=self.settings.get("fallback_audio", ""))
        self.remember_site_var = tk.BooleanVar(value=self.settings.get("remember_site", True))
        self.target_size_var = tk.StringVar(value=self.settings.get("target_size_mb", ""))
        self.auto_open_var = tk.BooleanVar(value=self.settings.get("auto_open", False))

        self._build_ui()
        self._apply_theme()
        self._dependency_status()
        self._refresh_history()
        self._refresh_queue()
        self._apply_advanced_visibility()

        if DND_FILES is not None:
            try:
                self.url_entry.drop_target_register(DND_FILES)
                self.url_entry.dnd_bind("<<Drop>>", self._handle_drop)
            except Exception:
                pass

        self.after(100, self._process_events)
        self.after(1200, self._watch_clipboard)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- UI ----------
    def _build_ui(self):
        header = ttk.Frame(self)
        header.pack(fill="x", padx=18, pady=(16, 8))
        ttk.Label(header, text="Universal Media Downloader", font=("Segoe UI", 19, "bold")).pack(side="left")
        ttk.Label(header, textvariable=self.version_var).pack(side="right")

        tabs = ttk.Notebook(self)
        tabs.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        self.download_tab = ttk.Frame(tabs)
        self.queue_tab = ttk.Frame(tabs)
        self.history_tab = ttk.Frame(tabs)
        self.settings_tab = ttk.Frame(tabs)

        tabs.add(self.download_tab, text="Download")
        tabs.add(self.queue_tab, text="Queue")
        tabs.add(self.history_tab, text="History")
        tabs.add(self.settings_tab, text="Settings")

        self._build_download_tab()
        self._build_queue_tab()
        self._build_history_tab()
        self._build_settings_tab()

        ttk.Label(
            self,
            text="Use only for media you own, have permission to download, or the site allows you to save.",
            anchor="center"
        ).pack(fill="x", padx=18, pady=(0, 8))

    def _build_download_tab(self):
        outer = ttk.Frame(self.download_tab)
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, highlightthickness=0)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        body = ttk.Frame(canvas)

        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)

        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        pad = {"padx": 12, "pady": 6}

        ttk.Label(body, text="Paste video or playlist link", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", **pad
        )

        self.url_entry = ttk.Entry(body, textvariable=self.url_var, font=("Segoe UI", 11))
        self.url_entry.grid(row=1, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 8))
        self.url_entry.bind("<KeyRelease>", self._schedule_auto_analysis)

        ttk.Button(body, text="Analyze now", command=self._start_analysis).grid(
            row=1, column=3, sticky="ew", padx=12, pady=(0, 8)
        )

        # Quick presets
        quick = ttk.LabelFrame(body, text="Quick Download")
        quick.grid(row=2, column=0, columnspan=4, sticky="ew", padx=12, pady=6)
        for i, name in enumerate(QUICK_PRESETS):
            ttk.Button(quick, text=name, command=lambda n=name: self._apply_quick_preset(n)).grid(
                row=0, column=i, padx=5, pady=6, sticky="ew"
            )
            quick.columnconfigure(i, weight=1)

        # Preview
        preview = ttk.LabelFrame(body, text="Video")
        preview.grid(row=3, column=0, columnspan=4, sticky="ew", padx=12, pady=8)

        self.thumbnail_label = ttk.Label(preview, text="Thumbnail", anchor="center", width=28)
        self.thumbnail_label.pack(side="left", padx=10, pady=10)

        preview_text = ttk.Frame(preview)
        preview_text.pack(side="left", fill="both", expand=True, padx=8, pady=10)

        ttk.Label(preview_text, textvariable=self.media_title_var, font=("Segoe UI", 12, "bold"),
                  wraplength=660).pack(anchor="w")
        ttk.Label(preview_text, textvariable=self.media_meta_var, wraplength=660).pack(anchor="w", pady=(5, 0))
        ttk.Label(preview_text, textvariable=self.estimate_var, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(6, 0))

        # Simple controls
        ttk.Label(body, text="Quality").grid(row=4, column=0, sticky="w", **pad)
        ttk.Label(body, text="Audio").grid(row=4, column=1, sticky="w", **pad)
        ttk.Label(body, text="Subtitles").grid(row=4, column=2, sticky="w", **pad)

        self.quality_combo = ttk.Combobox(body, textvariable=self.quality_var, state="readonly",
                                          values=[BEST_QUALITY_LABEL, AUDIO_ONLY_LABEL])
        self.quality_combo.grid(row=5, column=0, sticky="ew", **pad)
        self.quality_combo.bind("<<ComboboxSelected>>", lambda e: self._update_estimate())

        self.audio_combo = ttk.Combobox(body, textvariable=self.audio_var, state="readonly",
                                        values=[DEFAULT_AUDIO_LABEL])
        self.audio_combo.grid(row=5, column=1, sticky="ew", **pad)
        self.audio_combo.bind("<<ComboboxSelected>>", self._audio_choice_changed)

        self.subtitle_combo = ttk.Combobox(body, textvariable=self.subtitle_var, state="readonly",
                                           values=[NO_SUBTITLES_LABEL])
        self.subtitle_combo.grid(row=5, column=2, sticky="ew", **pad)
        self.subtitle_combo.bind("<<ComboboxSelected>>", self._subtitle_choice_changed)

        ttk.Checkbutton(body, text="Playlist", variable=self.playlist_var).grid(
            row=5, column=3, sticky="w", **pad
        )

        # Multi selectors
        self.multi_audio_frame = ttk.LabelFrame(body, text="Choose multiple audio languages")
        self.audio_listbox = tk.Listbox(self.multi_audio_frame, selectmode=tk.MULTIPLE, exportselection=False, height=6)
        self.audio_listbox.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        a_scroll = ttk.Scrollbar(self.multi_audio_frame, orient="vertical", command=self.audio_listbox.yview)
        self.audio_listbox.configure(yscrollcommand=a_scroll.set)
        a_scroll.pack(side="left", fill="y", pady=8)
        a_btns = ttk.Frame(self.multi_audio_frame)
        a_btns.pack(side="left", padx=8, pady=8)
        ttk.Button(a_btns, text="Select all", command=self._select_all_audio).pack(fill="x", pady=2)
        ttk.Button(a_btns, text="Done", command=self._finish_multi_audio).pack(fill="x", pady=2)
        ttk.Button(a_btns, text="Clear", command=self._clear_audio_selection).pack(fill="x", pady=2)

        self.multi_subtitle_frame = ttk.LabelFrame(body, text="Choose multiple subtitles")
        self.subtitle_listbox = tk.Listbox(self.multi_subtitle_frame, selectmode=tk.MULTIPLE, exportselection=False, height=6)
        self.subtitle_listbox.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        s_scroll = ttk.Scrollbar(self.multi_subtitle_frame, orient="vertical", command=self.subtitle_listbox.yview)
        self.subtitle_listbox.configure(yscrollcommand=s_scroll.set)
        s_scroll.pack(side="left", fill="y", pady=8)
        s_btns = ttk.Frame(self.multi_subtitle_frame)
        s_btns.pack(side="left", padx=8, pady=8)
        ttk.Button(s_btns, text="Select all", command=self._select_all_subtitles).pack(fill="x", pady=2)
        ttk.Button(s_btns, text="Done", command=self._finish_multi_subtitles).pack(fill="x", pady=2)
        ttk.Button(s_btns, text="Clear", command=self._clear_subtitle_selection).pack(fill="x", pady=2)

        ttk.Label(body, text="Save to").grid(row=8, column=0, sticky="w", **pad)
        ttk.Entry(body, textvariable=self.folder_var).grid(row=9, column=0, columnspan=3, sticky="ew", **pad)
        ttk.Button(body, text="Browse…", command=self._browse_folder).grid(row=9, column=3, sticky="ew", **pad)

        self.advanced_btn = ttk.Button(body, text="Advanced Options ▼", command=self._toggle_advanced)
        self.advanced_btn.grid(row=10, column=0, columnspan=4, sticky="w", padx=12, pady=(8, 4))

        self.advanced_frame = ttk.LabelFrame(body, text="Advanced Options")
        self.advanced_frame.grid(row=11, column=0, columnspan=4, sticky="ew", padx=12, pady=(0, 8))
        self._build_advanced_options()

        action = ttk.Frame(body)
        action.grid(row=12, column=0, columnspan=4, sticky="ew", padx=12, pady=8)

        self.download_btn = ttk.Button(action, text="Download", command=self._start_download)
        self.download_btn.pack(side="left", ipadx=16, ipady=4)

        ttk.Button(action, text="Add to Queue", command=self._add_to_queue).pack(side="left", padx=8)
        ttk.Button(action, text="Open Folder", command=self._open_folder).pack(side="left", padx=8)
        ttk.Button(action, text="Open File", command=self._open_last_file).pack(side="left", padx=8)
        ttk.Button(action, text="Copy File Path", command=self._copy_last_path).pack(side="left", padx=8)

        ttk.Button(action, text="Pause", command=self._pause_download).pack(side="right", padx=4)
        ttk.Button(action, text="Cancel", command=self._cancel_download).pack(side="right", padx=4)

        ttk.Progressbar(body, variable=self.progress_var, maximum=100).grid(
            row=13, column=0, columnspan=4, sticky="ew", padx=12, pady=(8, 3)
        )
        ttk.Label(body, textvariable=self.status_var).grid(
            row=14, column=0, columnspan=4, sticky="w", padx=12, pady=(2, 7)
        )

        log_box = ttk.LabelFrame(body, text="Activity")
        log_box.grid(row=15, column=0, columnspan=4, sticky="nsew", padx=12, pady=8)
        self.log = tk.Text(log_box, height=8, wrap="word")
        l_scroll = ttk.Scrollbar(log_box, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=l_scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        l_scroll.pack(side="right", fill="y")

        for c in range(4):
            body.columnconfigure(c, weight=1)

    def _build_advanced_options(self):
        f = self.advanced_frame

        ttk.Label(f, text="Video compatibility").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 3))
        ttk.Label(f, text="Container").grid(row=0, column=1, sticky="w", padx=8, pady=(8, 3))
        ttk.Label(f, text="Speed limit").grid(row=0, column=2, sticky="w", padx=8, pady=(8, 3))
        ttk.Label(f, text="Browser login").grid(row=0, column=3, sticky="w", padx=8, pady=(8, 3))

        ttk.Combobox(f, textvariable=self.codec_var, state="readonly", values=list(CODEC_PATTERNS)).grid(
            row=1, column=0, sticky="ew", padx=8, pady=(0, 7)
        )
        ttk.Combobox(f, textvariable=self.container_var, state="readonly", values=["Auto", "MP4", "MKV", "WebM"]).grid(
            row=1, column=1, sticky="ew", padx=8, pady=(0, 7)
        )
        ttk.Combobox(f, textvariable=self.speed_var, state="readonly", values=list(SPEED_LIMITS)).grid(
            row=1, column=2, sticky="ew", padx=8, pady=(0, 7)
        )
        ttk.Combobox(f, textvariable=self.cookies_var, state="readonly", values=["None", "Chrome", "Edge", "Firefox"]).grid(
            row=1, column=3, sticky="ew", padx=8, pady=(0, 7)
        )

        range_frame = ttk.Frame(f)
        range_frame.grid(row=2, column=0, columnspan=2, sticky="w", padx=8, pady=6)
        ttk.Label(range_frame, text="Playlist:").pack(side="left")
        ttk.Label(range_frame, text="Start").pack(side="left", padx=(8, 0))
        ttk.Entry(range_frame, textvariable=self.playlist_start_var, width=6).pack(side="left", padx=(4, 8))
        ttk.Label(range_frame, text="End").pack(side="left")
        ttk.Entry(range_frame, textvariable=self.playlist_end_var, width=6).pack(side="left", padx=(4, 8))
        ttk.Label(range_frame, text="Items").pack(side="left")
        ttk.Entry(range_frame, textvariable=self.playlist_items_var, width=15).pack(side="left", padx=(4, 0))

        ttk.Checkbutton(f, text="Skip Shorts", variable=self.skip_shorts_var).grid(row=2, column=2, sticky="w", padx=8)
        ttk.Checkbutton(f, text="Skip livestreams", variable=self.skip_live_var).grid(row=2, column=3, sticky="w", padx=8)

        ttk.Separator(f, orient="horizontal").grid(row=3, column=0, columnspan=4, sticky="ew", padx=8, pady=6)

        ttk.Label(f, text="Reduce file size").grid(row=4, column=0, sticky="w", padx=8, pady=(4, 3))
        self.compression_display_var = tk.StringVar(
            value=self.compression_level_var.get() if self.compress_var.get() else "Off"
        )
        comp = ttk.Combobox(f, textvariable=self.compression_display_var, state="readonly",
                            values=["Off", "Small reduction", "Balanced", "Maximum"])
        comp.grid(row=5, column=0, sticky="ew", padx=8, pady=(0, 7))
        comp.bind("<<ComboboxSelected>>", self._compression_display_changed)

        ttk.Label(f, text="Target size MB (optional)").grid(row=4, column=1, sticky="w", padx=8, pady=(4, 3))
        ttk.Entry(f, textvariable=self.target_size_var).grid(row=5, column=1, sticky="ew", padx=8, pady=(0, 7))

        ttk.Checkbutton(f, text="Embed subtitles", variable=self.embed_subtitles_var).grid(row=5, column=2, sticky="w", padx=8)
        ttk.Checkbutton(f, text="Include auto subtitles", variable=self.include_auto_subs_var).grid(row=5, column=3, sticky="w", padx=8)

        ttk.Label(f, text="Filename style").grid(row=6, column=0, sticky="w", padx=8, pady=(4, 3))
        ttk.Combobox(f, textvariable=self.filename_var, state="readonly", values=list(FILENAME_PRESETS)).grid(
            row=7, column=0, sticky="ew", padx=8, pady=(0, 8)
        )
        ttk.Checkbutton(f, text="Split by chapters", variable=self.split_chapters_var).grid(row=7, column=1, sticky="w", padx=8)
        ttk.Checkbutton(f, text="Delete larger original", variable=self.delete_original_var).grid(row=7, column=2, sticky="w", padx=8)
        ttk.Button(f, text="Update yt-dlp", command=self._update_ytdlp).grid(row=7, column=3, sticky="e", padx=8)

        for c in range(4):
            f.columnconfigure(c, weight=1)

    def _build_queue_tab(self):
        frame = ttk.Frame(self.queue_tab)
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        ttk.Label(frame, text="Download Queue", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Queue is saved automatically and restored next time.").pack(anchor="w", pady=(2, 8))

        self.queue_listbox = tk.Listbox(frame, height=18)
        self.queue_listbox.pack(fill="both", expand=True, pady=8)

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Start Queue", command=self._start_queue).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Remove Selected", command=self._remove_queue_item).pack(side="left", padx=6)
        ttk.Button(buttons, text="Clear Queue", command=self._clear_queue).pack(side="left", padx=6)
        ttk.Button(buttons, text="Import URLs from .txt", command=self._import_url_file).pack(side="left", padx=6)

        ttk.Label(buttons, text="When queue finishes:").pack(side="right", padx=(10, 4))
        ttk.Combobox(
            buttons, textvariable=self.queue_finish_action_var, state="readonly",
            values=["Do nothing", "Sleep", "Shut down"], width=12
        ).pack(side="right")

    def _build_history_tab(self):
        frame = ttk.Frame(self.history_tab)
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        top = ttk.Frame(frame)
        top.pack(fill="x")
        ttk.Label(top, text="History", font=("Segoe UI", 15, "bold")).pack(side="left")
        ttk.Button(top, text="Retry Failed", command=self._retry_failed).pack(side="right", padx=6)
        ttk.Button(top, text="Clear History", command=self._clear_history).pack(side="right")

        self.history_tree = ttk.Treeview(
            frame,
            columns=("status", "title", "quality", "audio", "date"),
            show="headings",
            height=18
        )

        for key, label, width in [
            ("status", "Status", 90),
            ("title", "Title / URL", 400),
            ("quality", "Quality", 100),
            ("audio", "Audio", 190),
            ("date", "Date", 150),
        ]:
            self.history_tree.heading(key, text=label)
            self.history_tree.column(key, width=width, anchor="w")

        self.history_tree.pack(fill="both", expand=True, pady=10)

    def _build_settings_tab(self):
        frame = ttk.Frame(self.settings_tab)
        frame.pack(fill="both", expand=True, padx=18, pady=18)

        ttk.Label(frame, text="Preferences", font=("Segoe UI", 15, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")

        ttk.Checkbutton(frame, text="Detect copied links from clipboard", variable=self.clipboard_watch_var).grid(
            row=1, column=0, sticky="w", pady=7
        )
        ttk.Checkbutton(frame, text="Show desktop notification when finished", variable=self.notify_var).grid(
            row=2, column=0, sticky="w", pady=7
        )
        ttk.Checkbutton(frame, text="Open downloaded file automatically", variable=self.auto_open_var).grid(
            row=3, column=0, sticky="w", pady=7
        )
        ttk.Checkbutton(frame, text="Remember quality/audio choices per site", variable=self.remember_site_var).grid(
            row=4, column=0, sticky="w", pady=7
        )

        ttk.Label(frame, text="Theme").grid(row=5, column=0, sticky="w", pady=(12, 3))
        theme = ttk.Combobox(frame, textvariable=self.theme_var, state="readonly", values=["System", "Light", "Dark"])
        theme.grid(row=6, column=0, sticky="ew", pady=(0, 8))
        theme.bind("<<ComboboxSelected>>", lambda e: self._apply_theme())

        ttk.Label(frame, text="Preferred audio language (e.g. hi, en, te)").grid(row=7, column=0, sticky="w", pady=(12, 3))
        ttk.Entry(frame, textvariable=self.preferred_audio_var).grid(row=8, column=0, sticky="ew", pady=(0, 8))

        ttk.Label(frame, text="Fallback audio language").grid(row=9, column=0, sticky="w", pady=(12, 3))
        ttk.Entry(frame, textvariable=self.fallback_audio_var).grid(row=10, column=0, sticky="ew", pady=(0, 8))

        ttk.Button(frame, text="Check Dependencies", command=self._dependency_status).grid(row=11, column=0, sticky="w", pady=(18, 5))
        ttk.Button(frame, text="Update yt-dlp", command=self._update_ytdlp).grid(row=12, column=0, sticky="w", pady=5)

        ttk.Label(
            frame,
            text="Drag-and-drop: drag a .txt file containing URLs onto the URL box, or import it from Queue.",
            wraplength=650
        ).grid(row=13, column=0, sticky="w", pady=(18, 5))

        frame.columnconfigure(0, weight=1)

    # ---------- Convenience ----------
    def _apply_quick_preset(self, name):
        preset = QUICK_PRESETS[name]
        requested_quality = preset["quality"]

        if requested_quality in self.quality_map:
            self.quality_var.set(requested_quality)
        elif requested_quality in {"1080p", "720p"}:
            # fall back to nearest lower detected quality
            target = int(requested_quality[:-1])
            heights = sorted(
                [v for v in self.quality_map.values() if isinstance(v, int)],
                reverse=True
            )
            chosen = next((h for h in heights if h <= target), None)
            if chosen:
                self.quality_var.set(f"{chosen}p")

        self.compress_var.set(preset.get("compress", False))
        if preset.get("compression_level"):
            self.compression_level_var.set(preset["compression_level"])
            self.compression_display_var.set(preset["compression_level"])
        else:
            self.compression_display_var.set("Off")

        if preset.get("select_all_audio"):
            self._select_all_audio()
            if self.audio_listbox.size():
                self.audio_var.set(f"{self.audio_listbox.size()} languages selected")

        self._update_estimate()

    def _watch_clipboard(self):
        try:
            if self.clipboard_watch_var.get():
                text = self.clipboard_get().strip()
                if (
                    text != self.last_clipboard
                    and re.match(r"^https?://", text)
                    and len(text) < 3000
                ):
                    self.last_clipboard = text
                    if not self.url_var.get().strip():
                        if messagebox.askyesno("Link detected", "A media link was copied. Paste and analyze it?"):
                            self.url_var.set(text)
                            self._start_analysis()
        except Exception:
            pass
        self.after(1400, self._watch_clipboard)

    def _handle_drop(self, event):
        data = event.data.strip()
        # tkinterdnd wraps paths with spaces in braces
        path = data.strip("{}")
        p = Path(path)
        if p.exists() and p.suffix.lower() == ".txt":
            urls = self._urls_from_text_file(p)
            if urls:
                self.url_var.set(urls[0])
                for url in urls[1:]:
                    self.queue_jobs.append(self._minimal_job(url))
                self._save_queue()
                self._refresh_queue()
                self._start_analysis()

    def _import_url_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not file_path:
            return
        urls = self._urls_from_text_file(Path(file_path))
        if not urls:
            messagebox.showinfo("Import URLs", "No HTTP/HTTPS URLs were found.")
            return
        for url in urls:
            self.queue_jobs.append(self._minimal_job(url))
        self._save_queue()
        self._refresh_queue()

    @staticmethod
    def _urls_from_text_file(path):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []
        return re.findall(r"https?://[^\s]+", text)

    def _minimal_job(self, url):
        return {
            "url": url,
            "folder": self.folder_var.get(),
            "quality_label": BEST_QUALITY_LABEL,
            "quality_value": None,
            "codec": "Recommended",
            "container": "Auto",
            "audio": [],
            "subtitles": [],
            "embed_subtitles": True,
            "include_auto_subs": True,
            "playlist": True,
            "playlist_start": "",
            "playlist_end": "",
            "playlist_items": "",
            "skip_shorts": False,
            "skip_live": True,
            "speed": "Unlimited",
            "cookies": "None",
            "filename": "Playlist number + title",
            "split_chapters": False,
            "compress": False,
            "compression_level": "Balanced",
            "delete_original": True,
            "target_size_mb": "",
            "title": url,
        }

    def _open_last_file(self):
        if not self.last_downloaded_path or not Path(self.last_downloaded_path).exists():
            messagebox.showinfo("Open File", "No completed downloaded file is available yet.")
            return
        self._open_path(self.last_downloaded_path)

    def _copy_last_path(self):
        if not self.last_downloaded_path:
            messagebox.showinfo("Copy Path", "No downloaded file path is available yet.")
            return
        self.clipboard_clear()
        self.clipboard_append(str(self.last_downloaded_path))
        self.status_var.set("Downloaded file path copied")

    def _open_path(self, path):
        try:
            if SYSTEM == "windows":
                os.startfile(str(path))
            elif SYSTEM == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror("Open File", str(exc))

    def _notify(self, title, message):
        if not self.notify_var.get():
            return
        try:
            if notification:
                notification.notify(title=title, message=message, app_name=APP_NAME, timeout=5)
        except Exception:
            pass

    # ---------- Simple UI behavior ----------
    def _toggle_advanced(self):
        self.advanced_visible.set(not self.advanced_visible.get())
        self._apply_advanced_visibility()

    def _apply_advanced_visibility(self):
        if self.advanced_visible.get():
            self.advanced_frame.grid()
            self.advanced_btn.configure(text="Advanced Options ▲")
        else:
            self.advanced_frame.grid_remove()
            self.advanced_btn.configure(text="Advanced Options ▼")

    def _schedule_auto_analysis(self, _event=None):
        if self.analysis_timer:
            self.after_cancel(self.analysis_timer)
        self.analysis_timer = self.after(900, self._auto_analyze_if_url)

    def _auto_analyze_if_url(self):
        url = self.url_var.get().strip()
        if url and url != self.last_analyzed_url and re.match(r"^https?://", url):
            self._start_analysis()

    def _audio_choice_changed(self, _event=None):
        if self.audio_var.get() == MULTI_AUDIO_LABEL:
            self.multi_audio_frame.grid(row=6, column=0, columnspan=4, sticky="ew", padx=12, pady=(0, 8))
        else:
            self.multi_audio_frame.grid_remove()
        self._update_estimate()

    def _subtitle_choice_changed(self, _event=None):
        if self.subtitle_var.get() == MULTI_SUBTITLES_LABEL:
            self.multi_subtitle_frame.grid(row=7, column=0, columnspan=4, sticky="ew", padx=12, pady=(0, 8))
        else:
            self.multi_subtitle_frame.grid_remove()

    def _finish_multi_audio(self):
        selected = self.audio_listbox.curselection()
        if not selected:
            self.audio_var.set(DEFAULT_AUDIO_LABEL)
        elif len(selected) == 1:
            self.audio_var.set(self.audio_options[selected[0]][0])
        else:
            self.audio_var.set(f"{len(selected)} languages selected")
        self.multi_audio_frame.grid_remove()
        self._update_estimate()

    def _finish_multi_subtitles(self):
        selected = self.subtitle_listbox.curselection()
        if not selected:
            self.subtitle_var.set(NO_SUBTITLES_LABEL)
        elif len(selected) == 1:
            self.subtitle_var.set(self.subtitle_options[selected[0]][0])
        else:
            self.subtitle_var.set(f"{len(selected)} subtitles selected")
        self.multi_subtitle_frame.grid_remove()

    def _compression_display_changed(self, _event=None):
        value = self.compression_display_var.get()
        if value == "Off":
            self.compress_var.set(False)
        else:
            self.compress_var.set(True)
            self.compression_level_var.set(value)

    def _select_all_audio(self):
        if self.audio_listbox.size():
            self.audio_listbox.selection_set(0, tk.END)

    def _clear_audio_selection(self):
        self.audio_listbox.selection_clear(0, tk.END)

    def _select_all_subtitles(self):
        if self.subtitle_listbox.size():
            self.subtitle_listbox.selection_set(0, tk.END)

    def _clear_subtitle_selection(self):
        self.subtitle_listbox.selection_clear(0, tk.END)

    def _selected_audio_tracks(self):
        multi = [self.audio_options[i] for i in self.audio_listbox.curselection() if i < len(self.audio_options)]
        if multi:
            return multi

        selected_label = self.audio_var.get()
        if selected_label in {DEFAULT_AUDIO_LABEL, MULTI_AUDIO_LABEL} or selected_label.endswith("languages selected"):
            return []

        for item in self.audio_options:
            if item[0] == selected_label:
                return [item]
        return []

    def _selected_subtitles(self):
        multi = [self.subtitle_options[i] for i in self.subtitle_listbox.curselection() if i < len(self.subtitle_options)]
        if multi:
            return multi

        selected_label = self.subtitle_var.get()
        if selected_label in {NO_SUBTITLES_LABEL, MULTI_SUBTITLES_LABEL} or selected_label.endswith("subtitles selected"):
            return []

        for item in self.subtitle_options:
            if item[0] == selected_label:
                return [item]
        return []

    # ---------- Analysis ----------
    def _start_analysis(self):
        url = self.url_var.get().strip()
        if not url:
            return
        if self.analysis_worker and self.analysis_worker.is_alive():
            return

        self.last_analyzed_url = url
        self.status_var.set("Analyzing link…")
        self.media_title_var.set("Analyzing…")
        self.media_meta_var.set("")
        self.estimate_var.set("")
        self.thumbnail_label.configure(image="", text="Thumbnail")
        self.thumbnail_photo = None

        self.audio_options = []
        self.subtitle_options = []
        self.audio_listbox.delete(0, tk.END)
        self.subtitle_listbox.delete(0, tk.END)

        self.analysis_worker = threading.Thread(target=self._analysis_worker, args=(url,), daemon=True)
        self.analysis_worker.start()

    @staticmethod
    def _first_playable_entry(info):
        if not isinstance(info, dict):
            return info
        entries = info.get("entries")
        if not entries:
            return info
        for entry in entries:
            if entry:
                return entry
        return info

    @staticmethod
    def _language_display_name(fmt):
        lang = (fmt.get("language") or "").strip()
        note = (fmt.get("format_note") or "").strip()
        name = (fmt.get("name") or "").strip()

        if not lang:
            return None

        descriptive = None
        for candidate in (note, name):
            if candidate and candidate.lower() not in {"default", "audio only", "medium", "low", "high", "audio"}:
                descriptive = candidate
                break

        return f"{descriptive} [{lang}]" if descriptive else lang

    def _analysis_worker(self, url):
        try:
            opts = {"quiet": True, "skip_download": True, "extract_flat": False, "noplaylist": False}
            cookies = self.cookies_var.get()
            if cookies != "None":
                opts["cookiesfrombrowser"] = (cookies.lower(),)

            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)

            media = self._first_playable_entry(info)
            if not media:
                raise RuntimeError("No playable media was found.")

            formats = media.get("formats") or []

            detected_languages = {}
            for fmt in formats:
                if fmt.get("acodec") in (None, "none"):
                    continue
                lang = (fmt.get("language") or "").strip()
                if not lang:
                    continue
                display = self._language_display_name(fmt) or lang
                if lang not in detected_languages or len(display) > len(detected_languages[lang]):
                    detected_languages[lang] = display

            language_options = [
                (label, lang)
                for lang, label in sorted(detected_languages.items(), key=lambda item: item[1].lower())
            ]

            subtitle_map = {}
            for lang in (media.get("subtitles") or {}):
                subtitle_map[lang] = (f"{lang}", lang, False)
            for lang in (media.get("automatic_captions") or {}):
                if lang not in subtitle_map:
                    subtitle_map[lang] = (f"{lang} (auto)", lang, True)
            subtitle_options = sorted(subtitle_map.values(), key=lambda x: x[0].lower())

            heights = set()
            codecs = set()

            for fmt in formats:
                vcodec = fmt.get("vcodec")
                if not vcodec or vcodec == "none":
                    continue
                h = fmt.get("height")
                if isinstance(h, int) and h > 0:
                    heights.add(h)

                if vcodec.startswith("av01"):
                    codecs.add("AV1")
                elif vcodec.startswith(("vp9", "vp0")):
                    codecs.add("VP9")
                elif vcodec.startswith("avc1"):
                    codecs.add("H.264 / AVC")
                elif vcodec.startswith(("hev", "hvc1")):
                    codecs.add("H.265 / HEVC")

            quality_options = [(BEST_QUALITY_LABEL, None)]
            quality_options.extend((f"{h}p", h) for h in sorted(heights, reverse=True))
            quality_options.append((AUDIO_ONLY_LABEL, "audio"))

            title = media.get("title") or info.get("title") or "Unknown title"
            playlist_title = info.get("title") if info.get("_type") == "playlist" else None
            shown_title = f"{playlist_title} — first item: {title}" if playlist_title and playlist_title != title else title

            self.events.put(("analysis_done", {
                "title": shown_title,
                "channel": media.get("channel") or media.get("uploader") or "Unknown channel",
                "duration": media.get("duration"),
                "thumbnail": media.get("thumbnail"),
                "native_resolution": (
                    f"{media.get('width')}x{media.get('height')}"
                    if media.get("width") and media.get("height") else ""
                ),
                "languages": language_options,
                "subtitles": subtitle_options,
                "qualities": quality_options,
                "codecs": sorted(codecs),
                "formats": formats,
            }))

        except Exception as exc:
            self.events.put(("analysis_error", str(exc)))

    def _load_thumbnail(self, url):
        if not url or Image is None or ImageTk is None:
            return

        def worker():
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = r.read()
                image = Image.open(io.BytesIO(data)).convert("RGB")
                image.thumbnail((220, 125))
                self.events.put(("thumbnail", image))
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _apply_preferred_language(self):
        pref = self.preferred_audio_var.get().strip().lower()
        fallback = self.fallback_audio_var.get().strip().lower()

        for code in [pref, fallback]:
            if not code:
                continue
            for label, lang in self.audio_options:
                if lang.lower() == code or label.lower().startswith(code):
                    self.audio_var.set(label)
                    return

    def _site_key(self, url):
        m = re.match(r"https?://([^/]+)", url)
        return m.group(1).lower() if m else ""

    def _apply_site_preferences(self):
        if not self.remember_site_var.get():
            return
        key = self._site_key(self.url_var.get().strip())
        pref = self.site_preferences.get(key)
        if not pref:
            return
        if pref.get("quality") in self.quality_map:
            self.quality_var.set(pref["quality"])
        audio = pref.get("audio")
        if audio and audio in [label for label, _ in self.audio_options]:
            self.audio_var.set(audio)

    # ---------- Estimate / disk ----------
    def _update_estimate(self):
        if not self.analysis_formats:
            self.estimate_var.set("")
            return

        q = self.quality_map.get(self.quality_var.get())

        if q == "audio":
            candidates = [
                f for f in self.analysis_formats
                if f.get("acodec") not in (None, "none") and f.get("vcodec") == "none"
            ]
            size = max((f.get("filesize") or f.get("filesize_approx") or 0 for f in candidates), default=0)
        else:
            codec_pattern = CODEC_PATTERNS.get(self.codec_var.get())
            video = []
            for f in self.analysis_formats:
                if f.get("vcodec") in (None, "none"):
                    continue
                if q is not None and f.get("height") != q:
                    continue
                if codec_pattern and not str(f.get("vcodec", "")).startswith(codec_pattern):
                    continue
                video.append(f)

            video_size = max((f.get("filesize") or f.get("filesize_approx") or 0 for f in video), default=0)

            selected = self._selected_audio_tracks()
            if selected:
                audio_size = 0
                for _label, code in selected:
                    choices = [
                        f for f in self.analysis_formats
                        if f.get("acodec") not in (None, "none")
                        and f.get("vcodec") == "none"
                        and (f.get("language") or "") == code
                    ]
                    audio_size += max((f.get("filesize") or f.get("filesize_approx") or 0 for f in choices), default=0)
            else:
                choices = [
                    f for f in self.analysis_formats
                    if f.get("acodec") not in (None, "none") and f.get("vcodec") == "none"
                ]
                audio_size = max((f.get("filesize") or f.get("filesize_approx") or 0 for f in choices), default=0)

            size = video_size + audio_size

        if size:
            self.estimate_var.set(f"Estimated download: ~{self._human_bytes(size)}")
        else:
            self.estimate_var.set("Estimated size unavailable")

    def _estimated_bytes(self):
        text = self.estimate_var.get()
        m = re.search(r"~([\d.]+)\s*(KB|MB|GB|TB)", text)
        if not m:
            return None
        value = float(m.group(1))
        unit = m.group(2)
        mult = {"KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}[unit]
        return int(value * mult)

    @staticmethod
    def _human_bytes(n):
        value = float(n)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if value < 1024 or unit == "TB":
                return f"{value:.1f} {unit}"
            value /= 1024

    def _check_disk_space(self, folder):
        try:
            folder = Path(folder).expanduser()
            folder.mkdir(parents=True, exist_ok=True)
            free = shutil.disk_usage(folder).free
            estimated = self._estimated_bytes()
            if estimated and free < estimated * 1.1:
                return False, f"Estimated need: {self._human_bytes(estimated)}\nFree space: {self._human_bytes(free)}"
        except Exception:
            pass
        return True, ""

    # ---------- Jobs ----------
    def _collect_job(self):
        url = self.url_var.get().strip()
        if not url:
            raise ValueError("Paste a URL first.")

        job = {
            "url": url,
            "folder": self.folder_var.get(),
            "quality_label": self.quality_var.get(),
            "quality_value": self.quality_map.get(self.quality_var.get()),
            "codec": self.codec_var.get(),
            "container": self.container_var.get(),
            "audio": self._selected_audio_tracks(),
            "subtitles": self._selected_subtitles(),
            "embed_subtitles": self.embed_subtitles_var.get(),
            "include_auto_subs": self.include_auto_subs_var.get(),
            "playlist": self.playlist_var.get(),
            "playlist_start": self.playlist_start_var.get().strip(),
            "playlist_end": self.playlist_end_var.get().strip(),
            "playlist_items": self.playlist_items_var.get().strip(),
            "skip_shorts": self.skip_shorts_var.get(),
            "skip_live": self.skip_live_var.get(),
            "speed": self.speed_var.get(),
            "cookies": self.cookies_var.get(),
            "filename": self.filename_var.get(),
            "split_chapters": self.split_chapters_var.get(),
            "compress": self.compress_var.get(),
            "compression_level": self.compression_level_var.get(),
            "delete_original": self.delete_original_var.get(),
            "target_size_mb": self.target_size_var.get().strip(),
            "title": (
                self.media_title_var.get()
                if self.media_title_var.get() not in {"No video analyzed yet", "Analyzing…"} else url
            ),
        }

        if self.remember_site_var.get():
            key = self._site_key(url)
            self.site_preferences[key] = {
                "quality": self.quality_var.get(),
                "audio": self.audio_var.get(),
            }

        return job

    # ---------- Download ----------
    def _start_download(self):
        try:
            job = self._collect_job()
        except ValueError as exc:
            messagebox.showwarning("Missing information", str(exc))
            return

        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Download running", "A download is already in progress.")
            return

        ok, info = self._check_disk_space(job["folder"])
        if not ok and not messagebox.askyesno("Low disk space", info + "\n\nContinue anyway?"):
            return

        dup = self._find_duplicate(job)
        if dup:
            choice = messagebox.askyesnocancel(
                "Already downloaded",
                f"This item appears in your history as completed.\n\n{dup}\n\nYes = download again\nNo = open folder\nCancel = stop"
            )
            if choice is None:
                return
            if choice is False:
                self._open_folder()
                return

        self.pause_requested.clear()
        self.cancel_requested.clear()
        self.progress_var.set(0)
        self.download_btn.config(state="disabled")

        self.worker = threading.Thread(target=self._run_job, args=(job, False), daemon=True)
        self.worker.start()

    def _find_duplicate(self, job):
        title = job.get("title")
        for entry in reversed(self.history):
            if entry.get("status") == "Completed" and entry.get("title") == title:
                return entry.get("date", "")
        return None

    def _add_to_queue(self):
        try:
            job = self._collect_job()
        except ValueError as exc:
            messagebox.showwarning("Missing information", str(exc))
            return
        self.queue_jobs.append(job)
        self._save_queue()
        self._refresh_queue()
        self.status_var.set("Added to queue")

    def _start_queue(self):
        if self.queue_worker and self.queue_worker.is_alive():
            return
        if not self.queue_jobs:
            messagebox.showinfo("Queue", "The queue is empty.")
            return

        self.pause_requested.clear()
        self.cancel_requested.clear()
        self.queue_worker = threading.Thread(target=self._queue_worker_loop, daemon=True)
        self.queue_worker.start()

    def _queue_worker_loop(self):
        while self.queue_jobs:
            if self.cancel_requested.is_set() or self.pause_requested.is_set():
                break

            job = self.queue_jobs[0]
            ok = self._run_job(job, True)

            if ok and self.queue_jobs:
                self.queue_jobs.pop(0)
                self._save_queue()
                self.events.put(("refresh_queue", None))
            else:
                break

        self.events.put(("queue_done", None))

    def _remove_queue_item(self):
        sel = self.queue_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self.queue_jobs):
            self.queue_jobs.pop(idx)
        self._save_queue()
        self._refresh_queue()

    def _clear_queue(self):
        self.queue_jobs.clear()
        self._save_queue()
        self._refresh_queue()

    def _refresh_queue(self):
        if not hasattr(self, "queue_listbox"):
            return
        self.queue_listbox.delete(0, tk.END)
        for i, job in enumerate(self.queue_jobs, 1):
            audio = ", ".join(label for label, _ in job.get("audio", [])) or "default"
            self.queue_listbox.insert(
                tk.END,
                f"{i}. {job.get('title', job['url'])} | {job.get('quality_label', BEST_QUALITY_LABEL)} | {audio}"
            )

    def _save_queue(self):
        self._save_json(QUEUE_FILE, self.queue_jobs)

    def _pause_download(self):
        if (self.worker and self.worker.is_alive()) or (self.queue_worker and self.queue_worker.is_alive()):
            self.pause_requested.set()
            self.status_var.set("Pausing… partial download will be kept")

    def _cancel_download(self):
        if (self.worker and self.worker.is_alive()) or (self.queue_worker and self.queue_worker.is_alive()):
            self.cancel_requested.set()
            self.status_var.set("Cancelling…")

    def _progress_hook(self, data):
        if self.cancel_requested.is_set():
            raise DownloadError("Cancelled by user")
        if self.pause_requested.is_set():
            raise DownloadError("Paused by user")

        status = data.get("status")

        if status == "downloading":
            raw = data.get("_percent_str", "").replace("%", "").strip()
            try:
                self.events.put(("progress", float(raw)))
            except ValueError:
                pass
            speed = data.get("_speed_str", "").strip()
            eta = data.get("_eta_str", "").strip()
            filename = Path(data.get("filename", "")).name
            text = f"Downloading {filename}"
            if speed:
                text += f" | {speed}"
            if eta:
                text += f" | ETA {eta}"
            self.events.put(("status", text))

        elif status == "finished":
            self.events.put(("progress", 100))
            self.events.put(("status", "Download finished. Processing…"))
            self.events.put(("log", f"Downloaded: {Path(data.get('filename', '')).name}"))

    def _postprocessor_hook(self, data):
        if data.get("status") == "finished":
            self.events.put(("log", f"Finished: {data.get('postprocessor', 'post-processing')}"))

    def _match_filter(self, job):
        def f(info, *, incomplete):
            if job["skip_live"] and (info.get("is_live") or info.get("live_status") in {"is_live", "is_upcoming"}):
                return "Skipping livestream"
            if job["skip_shorts"]:
                url = (info.get("webpage_url") or info.get("original_url") or "").lower()
                if "/shorts/" in url:
                    return "Skipping Short"
            return None
        return f

    def _video_selector(self, height, codec_name):
        if height is None:
            base = "bv*"
        else:
            base = f"(bv*[height={height}]/bv*[height<={height}])"

        pattern = CODEC_PATTERNS.get(codec_name)
        if not pattern:
            return base

        if height is None:
            return f"(bv*[vcodec^={pattern}]/bv*)"

        return f"(bv*[height={height}][vcodec^={pattern}]/bv*[height<={height}][vcodec^={pattern}]/{base})"

    def _video_format_selector(self, height, codec_name, selected_audio):
        video = self._video_selector(height, codec_name)
        if not selected_audio:
            return f"{video}+ba/b"
        parts = [f"ba[language={code}]" for _label, code in selected_audio]
        if len(parts) == 1:
            return f"{video}+{parts[0]}/{video}+ba/b"
        return f"{video}+{'+'.join(parts)}/{video}+ba/b"

    @staticmethod
    def _audio_selector(code):
        return f"ba[language={code}]/ba/b" if code else "ba/b"

    def _resolve_container(self, job):
        if len(job["audio"]) > 1:
            return "mkv"
        if len(job["subtitles"]) > 1 and job["embed_subtitles"]:
            return "mkv"
        c = job["container"].lower()
        return "mp4" if c == "auto" else c

    def _build_outtmpl(self, job):
        filename = FILENAME_PRESETS.get(job["filename"], list(FILENAME_PRESETS.values())[0])
        return str(Path(job["folder"]).expanduser() / "%(playlist|Singles)s" / filename)

    def _base_options(self, job):
        opts = {
            "noplaylist": not job["playlist"],
            "ignoreerrors": False,
            "continuedl": True,
            "overwrites": False,
            "windowsfilenames": SYSTEM == "windows",
            "retries": 10,
            "fragment_retries": 10,
            "skip_unavailable_fragments": True,
            "outtmpl": self._build_outtmpl(job),
            "progress_hooks": [self._progress_hook],
            "postprocessor_hooks": [self._postprocessor_hook],
            "quiet": True,
            "no_warnings": False,
            "ratelimit": SPEED_LIMITS.get(job["speed"]),
            "match_filter": self._match_filter(job),
            "split_chapters": job["split_chapters"],
            "download_archive": str(Path(job["folder"]).expanduser() / "downloaded.txt"),
        }

        if job["playlist_start"].isdigit():
            opts["playliststart"] = int(job["playlist_start"])
        if job["playlist_end"].isdigit():
            opts["playlistend"] = int(job["playlist_end"])
        if job["playlist_items"]:
            opts["playlist_items"] = job["playlist_items"]
        if job["cookies"] != "None":
            opts["cookiesfrombrowser"] = (job["cookies"].lower(),)

        selected_subs = job["subtitles"]
        if selected_subs:
            langs = [lang for _label, lang, _auto in selected_subs]
            opts["subtitleslangs"] = langs
            opts["writesubtitles"] = any(not auto for _label, _lang, auto in selected_subs)
            opts["writeautomaticsub"] = job["include_auto_subs"] and any(auto for _label, _lang, auto in selected_subs)
            opts["embedsubtitles"] = job["embed_subtitles"]

        return opts

    def _download_audio_only_multiple(self, job):
        for label, code in job["audio"]:
            self.events.put(("log", f"Downloading audio language: {label}"))
            opts = self._base_options(job)
            opts.pop("download_archive", None)

            safe_lang = "".join(c if c.isalnum() or c in "-_" else "_" for c in code)
            opts["format"] = self._audio_selector(code)
            opts["outtmpl"] = str(
                Path(job["folder"]).expanduser()
                / "%(playlist|Singles)s"
                / f"%(playlist_index&{{}} - |)s%(title)s [%(id)s] [{safe_lang}].%(ext)s"
            )
            opts["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"},
                {"key": "FFmpegMetadata", "add_metadata": True},
            ]

            with yt_dlp.YoutubeDL(opts) as ydl:
                if ydl.download([job["url"]]) != 0:
                    raise RuntimeError(f"Download failed for {label}")

    def _run_job(self, job, from_queue):
        folder = Path(job["folder"]).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        is_audio_only = job["quality_value"] == "audio"

        try:
            audio_names = ", ".join(label for label, _code in job["audio"]) or "Original / Default"
            self.events.put(("log", f"URL: {job['url']}"))
            self.events.put(("log", f"Quality: {job['quality_label']}"))
            self.events.put(("log", f"Audio: {audio_names}"))
            self.events.put(("log", ""))

            if is_audio_only and len(job["audio"]) > 1:
                self._download_audio_only_multiple(job)
                new_files = []
            else:
                opts = self._base_options(job)

                if is_audio_only:
                    code = job["audio"][0][1] if job["audio"] else None
                    opts["format"] = self._audio_selector(code)
                    opts["postprocessors"] = [
                        {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"},
                        {"key": "FFmpegMetadata", "add_metadata": True},
                    ]
                else:
                    container = self._resolve_container(job)
                    multi_audio = len(job["audio"]) > 1
                    opts.update({
                        "format": self._video_format_selector(job["quality_value"], job["codec"], job["audio"]),
                        "allow_multiple_audio_streams": multi_audio,
                        "merge_output_format": container,
                        "postprocessors": [{"key": "FFmpegMetadata", "add_metadata": True}],
                    })

                before = self._snapshot_media_files(folder)
                with yt_dlp.YoutubeDL(opts) as ydl:
                    result = ydl.download([job["url"]])
                if result != 0:
                    raise RuntimeError(f"yt-dlp returned status code {result}")

                after = self._snapshot_media_files(folder)
                new_files = sorted(after - before, key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)

                # Optional target size overrides regular compression for the newest video.
                target_mb = job.get("target_size_mb", "").strip()
                if target_mb and not is_audio_only and new_files:
                    try:
                        target = float(target_mb)
                        if target > 0:
                            self._compress_to_target_size(new_files[0], target, job["delete_original"])
                    except ValueError:
                        self.events.put(("log", "Target size ignored: enter a numeric MB value."))
                elif job["compress"] and not is_audio_only:
                    for target in new_files:
                        if target.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"} and "_compressed" not in target.stem:
                            self._compress_file(target, job["compression_level"], job["delete_original"])

                for target in new_files[:8]:
                    if target.exists() and target.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov", ".mp3"}:
                        self._verify_file(target)

            if new_files:
                self.last_downloaded_path = new_files[0]

            self._record_history(job, "Completed")
            self.events.put(("status", "Complete ✓"))
            self.events.put(("log", "Download completed successfully."))
            self._notify("Download complete", job["title"])

            if self.auto_open_var.get() and self.last_downloaded_path and Path(self.last_downloaded_path).exists():
                self.events.put(("open_path", str(self.last_downloaded_path)))

            if not from_queue:
                self.events.put(("done", "Download completed."))

            return True

        except Exception as exc:
            text = str(exc)

            if self.pause_requested.is_set():
                self._record_history(job, "Paused")
                self.events.put(("status", "Paused — press Download again to resume"))
                self.events.put(("log", "Paused. Partial files were kept."))

            elif self.cancel_requested.is_set():
                self._record_history(job, "Cancelled")
                self.events.put(("status", "Cancelled"))
                self.events.put(("log", "Cancelled by user."))

            else:
                self._record_history(job, "Failed")
                self.events.put(("error", text))

            return False

        finally:
            if not from_queue:
                self.events.put(("download_idle", None))

    def _snapshot_media_files(self, folder):
        exts = {".mp4", ".mkv", ".webm", ".mov", ".mp3", ".m4a", ".opus"}
        return {p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in exts}

    # ---------- Compression ----------
    def _compress_file(self, input_path, level, delete_original):
        if not shutil.which("ffmpeg"):
            self.events.put(("log", "Compression skipped: FFmpeg not found."))
            return

        preset = COMPRESSION_PRESETS.get(level, COMPRESSION_PRESETS["Balanced"])
        input_path = Path(input_path)
        out_ext = ".mkv" if input_path.suffix.lower() == ".mkv" else ".mp4"
        output_path = input_path.with_name(f"{input_path.stem}_compressed{out_ext}")

        cmd = [
            "ffmpeg", "-y", "-i", str(input_path),
            "-map", "0:v:0", "-map", "0:a?", "-map", "0:s?", "-map_metadata", "0",
            "-c:v", "libx265", "-crf", preset["crf"], "-preset", preset["preset"],
            "-c:a", "aac", "-b:a", preset["audio_bitrate"], "-c:s", "copy",
        ]

        if out_ext == ".mp4":
            cmd += ["-movflags", "+faststart"]
        cmd.append(str(output_path))

        self.events.put(("status", f"Compressing: {input_path.name}"))
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            self.events.put(("log", f"Compression failed for {input_path.name}; original kept."))
            return

        self._finish_compression(input_path, output_path, delete_original)

    def _compress_to_target_size(self, input_path, target_mb, delete_original):
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.events.put(("log", "Target-size compression needs FFmpeg and ffprobe."))
            return

        input_path = Path(input_path)
        try:
            probe = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(input_path)],
                capture_output=True, text=True, timeout=20
            )
            duration = float(probe.stdout.strip())
            if duration <= 0:
                raise ValueError

            # Reserve 128 kbps for audio and ~3% mux overhead.
            total_bits = target_mb * 1024 * 1024 * 8 * 0.97
            total_bitrate = total_bits / duration
            audio_bitrate = 128_000
            video_bitrate = max(250_000, int(total_bitrate - audio_bitrate))

            out_ext = ".mkv" if input_path.suffix.lower() == ".mkv" else ".mp4"
            output_path = input_path.with_name(f"{input_path.stem}_target_{int(target_mb)}MB{out_ext}")

            cmd = [
                "ffmpeg", "-y", "-i", str(input_path),
                "-map", "0:v:0", "-map", "0:a?", "-map", "0:s?",
                "-c:v", "libx265", "-b:v", str(video_bitrate), "-maxrate", str(int(video_bitrate*1.25)),
                "-bufsize", str(int(video_bitrate*2)),
                "-c:a", "aac", "-b:a", "128k", "-c:s", "copy",
            ]
            if out_ext == ".mp4":
                cmd += ["-movflags", "+faststart"]
            cmd.append(str(output_path))

            self.events.put(("status", f"Compressing toward {target_mb:.0f} MB…"))
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)

            if result.returncode != 0:
                self.events.put(("log", "Target-size compression failed; original kept."))
                return

            self._finish_compression(input_path, output_path, delete_original)

        except Exception:
            self.events.put(("log", "Could not calculate target-size compression."))

    def _finish_compression(self, input_path, output_path, delete_original):
        if not output_path.exists():
            return
        original_size = input_path.stat().st_size
        compressed_size = output_path.stat().st_size

        self.events.put(("log", f"Compressed {self._human_bytes(original_size)} → {self._human_bytes(compressed_size)}"))

        if compressed_size >= original_size:
            output_path.unlink(missing_ok=True)
            self.events.put(("log", "Compressed copy was not smaller, so it was removed."))
        else:
            self.last_downloaded_path = output_path
            if delete_original:
                input_path.unlink(missing_ok=True)
                self.events.put(("log", "Original larger file deleted."))

    def _verify_file(self, path):
        if not shutil.which("ffprobe"):
            return
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", "-show_format", str(path)],
                capture_output=True, text=True, timeout=20
            )
            if result.returncode != 0:
                return

            data = json.loads(result.stdout)
            streams = data.get("streams", [])
            videos = [s for s in streams if s.get("codec_type") == "video"]
            audios = [s for s in streams if s.get("codec_type") == "audio"]
            subs = [s for s in streams if s.get("codec_type") == "subtitle"]

            details = []
            if videos:
                v = videos[0]
                details.append(f"{v.get('width', '?')}x{v.get('height', '?')} {v.get('codec_name', '?')}")
            details.append(f"{len(audios)} audio track(s)")
            if subs:
                details.append(f"{len(subs)} subtitle track(s)")

            self.events.put(("log", f"Verified {path.name}: " + ", ".join(details)))
        except Exception:
            pass

    # ---------- Queue finish ----------
    def _queue_finished_action(self):
        action = self.queue_finish_action_var.get()
        if action == "Do nothing":
            return

        self._notify("Queue complete", f"Queue finished. Action: {action}")

        try:
            if SYSTEM == "windows":
                if action == "Shut down":
                    subprocess.Popen(["shutdown", "/s", "/t", "30"])
                elif action == "Sleep":
                    subprocess.Popen([
                        "rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"
                    ])
            elif SYSTEM == "linux":
                if action == "Shut down":
                    subprocess.Popen(["systemctl", "poweroff"])
                elif action == "Sleep":
                    subprocess.Popen(["systemctl", "suspend"])
        except Exception:
            self.events.put(("log", f"Could not perform queue finish action: {action}"))

    # ---------- Retry ----------
    def _retry_failed(self):
        failed = [e for e in self.history if e.get("status") == "Failed" and e.get("url")]
        if not failed:
            messagebox.showinfo("Retry Failed", "No retryable failed items were found.")
            return
        for entry in failed:
            self.queue_jobs.append(self._minimal_job(entry["url"]))
        self._save_queue()
        self._refresh_queue()
        messagebox.showinfo("Retry Failed", f"Added {len(failed)} failed item(s) back to the queue.")

    # ---------- History/settings ----------
    def _record_history(self, job, status):
        self.history.append({
            "status": status,
            "title": job.get("title") or job["url"],
            "url": job["url"],
            "quality": job["quality_label"],
            "audio": ", ".join(label for label, _code in job["audio"]) or "default",
            "date": time.strftime("%Y-%m-%d %H:%M"),
        })
        self._save_json(HISTORY_FILE, self.history[-500:])
        self.events.put(("refresh_history", None))

    def _refresh_history(self):
        if not hasattr(self, "history_tree"):
            return
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        for entry in reversed(self.history[-200:]):
            self.history_tree.insert("", "end", values=(
                entry.get("status", ""),
                entry.get("title", ""),
                entry.get("quality", ""),
                entry.get("audio", ""),
                entry.get("date", ""),
            ))

    def _clear_history(self):
        self.history = []
        self._save_json(HISTORY_FILE, [])
        self._refresh_history()

    def _save_settings(self):
        data = {
            "folder": self.folder_var.get(),
            "codec": self.codec_var.get(),
            "container": self.container_var.get(),
            "playlist": self.playlist_var.get(),
            "compress": self.compress_var.get(),
            "compression_level": self.compression_level_var.get(),
            "delete_original": self.delete_original_var.get(),
            "embed_subtitles": self.embed_subtitles_var.get(),
            "include_auto_subs": self.include_auto_subs_var.get(),
            "split_chapters": self.split_chapters_var.get(),
            "skip_shorts": self.skip_shorts_var.get(),
            "skip_live": self.skip_live_var.get(),
            "speed": self.speed_var.get(),
            "cookies": self.cookies_var.get(),
            "filename": self.filename_var.get(),
            "advanced_visible": self.advanced_visible.get(),
            "clipboard_watch": self.clipboard_watch_var.get(),
            "notify": self.notify_var.get(),
            "queue_finish_action": self.queue_finish_action_var.get(),
            "theme": self.theme_var.get(),
            "preferred_audio": self.preferred_audio_var.get(),
            "fallback_audio": self.fallback_audio_var.get(),
            "remember_site": self.remember_site_var.get(),
            "target_size_mb": self.target_size_var.get(),
            "auto_open": self.auto_open_var.get(),
            "site_preferences": self.site_preferences,
        }
        self._save_json(SETTINGS_FILE, data)

    @staticmethod
    def _load_json(path, default):
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return default

    @staticmethod
    def _save_json(path, data):
        try:
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ---------- Theme ----------
    def _apply_theme(self):
        theme = self.theme_var.get()
        style = ttk.Style(self)

        if theme == "Dark":
            try:
                style.theme_use("clam")
            except Exception:
                pass
            self.configure(bg=DARK_BG)
            style.configure(".", background=DARK_BG, foreground=DARK_FG, fieldbackground=DARK_FIELD)
            style.configure("TEntry", fieldbackground=DARK_FIELD, foreground=DARK_FG)
            style.configure("TCombobox", fieldbackground=DARK_FIELD, foreground=DARK_FG)
            style.map("TCombobox", fieldbackground=[("readonly", DARK_FIELD)])
        elif theme == "Light":
            try:
                style.theme_use("clam")
            except Exception:
                pass
            self.configure(bg="#f4f4f4")
            style.configure(".", background="#f4f4f4", foreground="#111111", fieldbackground="#ffffff")
            style.configure("TEntry", fieldbackground="#ffffff", foreground="#111111")
            style.configure("TCombobox", fieldbackground="#ffffff", foreground="#111111")
        else:
            try:
                if SYSTEM == "windows":
                    style.theme_use("vista")
                else:
                    style.theme_use("default")
            except Exception:
                pass

    # ---------- Update/dependencies ----------
    def _update_ytdlp(self):
        def worker():
            self.events.put(("status", "Updating yt-dlp…"))
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-U", "yt-dlp[default]"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                self.events.put(("status", "yt-dlp updated. Restart the app to use the new version."))
                self.events.put(("log", result.stdout[-1200:]))
            else:
                self.events.put(("error", result.stderr[-1600:] or "yt-dlp update failed"))
        threading.Thread(target=worker, daemon=True).start()

    def _dependency_status(self):
        self._append_log(f"Operating system: {platform.system()}")
        self._append_log(f"Python: {sys.executable}")
        self._append_log(f"yt-dlp: {getattr(yt_dlp.version, '__version__', 'installed')}")
        self._append_log("FFmpeg: found ✓" if shutil.which("ffmpeg") else "FFmpeg: NOT FOUND")
        self._append_log("ffprobe: found ✓" if shutil.which("ffprobe") else "ffprobe: NOT FOUND")
        self._append_log("Deno: found ✓" if shutil.which("deno") else "Deno: not found (optional)")
        self._append_log("Drag/drop: available ✓" if DND_FILES is not None else "Drag/drop: unavailable (tkinterdnd2 missing)")
        self._append_log("Desktop notifications: available ✓" if notification else "Desktop notifications: unavailable (plyer missing)")
        self._append_log("")

    # ---------- Generic ----------
    def _append_log(self, message):
        if hasattr(self, "log"):
            self.log.insert("end", str(message) + "\n")
            self.log.see("end")

    def _browse_folder(self):
        selected = filedialog.askdirectory(initialdir=self.folder_var.get())
        if selected:
            self.folder_var.set(selected)

    def _open_folder(self):
        folder = Path(self.folder_var.get()).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        self._open_path(folder)

    def _on_close(self):
        self._save_settings()
        self._save_queue()
        self.destroy()

    # ---------- Events ----------
    def _process_events(self):
        try:
            while True:
                event, value = self.events.get_nowait()

                if event == "progress":
                    self.progress_var.set(value)
                elif event == "status":
                    self.status_var.set(value)
                elif event == "log":
                    self._append_log(value)
                elif event == "open_path":
                    self._open_path(value)

                elif event == "thumbnail":
                    if ImageTk is not None:
                        self.thumbnail_photo = ImageTk.PhotoImage(value)
                        self.thumbnail_label.configure(image=self.thumbnail_photo, text="")

                elif event == "analysis_done":
                    self.status_var.set("Ready to download")
                    self.analysis_formats = value["formats"]
                    self.analysis_duration = value["duration"]
                    self.analysis_info = value

                    self.media_title_var.set(value["title"])

                    duration = value["duration"]
                    if duration:
                        mins, secs = divmod(int(duration), 60)
                        duration_text = f"{mins}:{secs:02d}"
                    else:
                        duration_text = "unknown"

                    meta = f"{value['channel']}   •   {duration_text}"
                    if value["native_resolution"]:
                        meta += f"   •   {value['native_resolution']}"
                    self.media_meta_var.set(meta)

                    self.audio_options = value["languages"]
                    self.audio_listbox.delete(0, tk.END)
                    for label, _code in self.audio_options:
                        self.audio_listbox.insert(tk.END, label)

                    audio_values = [DEFAULT_AUDIO_LABEL] + [label for label, _code in self.audio_options]
                    if len(self.audio_options) > 1:
                        audio_values.append(MULTI_AUDIO_LABEL)
                    self.audio_combo["values"] = audio_values
                    self.audio_var.set(DEFAULT_AUDIO_LABEL)

                    self.subtitle_options = value["subtitles"]
                    self.subtitle_listbox.delete(0, tk.END)
                    for label, _lang, _auto in self.subtitle_options:
                        self.subtitle_listbox.insert(tk.END, label)

                    subtitle_values = [NO_SUBTITLES_LABEL] + [label for label, _lang, _auto in self.subtitle_options]
                    if len(self.subtitle_options) > 1:
                        subtitle_values.append(MULTI_SUBTITLES_LABEL)
                    self.subtitle_combo["values"] = subtitle_values
                    self.subtitle_var.set(NO_SUBTITLES_LABEL)

                    self.quality_map = {label: code for label, code in value["qualities"]}
                    labels = list(self.quality_map)
                    self.quality_combo["values"] = labels
                    self.quality_var.set(labels[0])

                    self._apply_site_preferences()
                    if self.audio_var.get() == DEFAULT_AUDIO_LABEL:
                        self._apply_preferred_language()

                    self._append_log(f"Analyzed: {value['title']}")
                    self._append_log("")
                    self._update_estimate()
                    self._load_thumbnail(value["thumbnail"])

                elif event == "analysis_error":
                    self.status_var.set("Could not analyze this link")
                    self.media_title_var.set("Analysis failed")
                    self._append_log("ANALYZE ERROR: " + value)
                    messagebox.showerror("Analysis failed", value)

                elif event == "done":
                    messagebox.showinfo("Finished", value)

                elif event == "error":
                    self.status_var.set("Failed")
                    self._append_log("ERROR: " + value)
                    messagebox.showerror("Download failed", value)

                elif event == "download_idle":
                    self.download_btn.config(state="normal")

                elif event == "refresh_queue":
                    self._refresh_queue()

                elif event == "queue_done":
                    self._refresh_queue()
                    if self.pause_requested.is_set():
                        self.status_var.set("Queue paused")
                    elif self.cancel_requested.is_set():
                        self.status_var.set("Queue cancelled")
                    else:
                        self.status_var.set("Queue complete")
                        self._queue_finished_action()

                elif event == "refresh_history":
                    self._refresh_history()

        except queue.Empty:
            pass

        self.after(100, self._process_events)


if __name__ == "__main__":
    DEFAULT_DIR.mkdir(parents=True, exist_ok=True)
    app = DownloaderApp()
    app.mainloop()
