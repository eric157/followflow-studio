from __future__ import annotations

import queue
import sys
import threading
import traceback
import tkinter as tk
from typing import Any
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tkinter import BooleanVar, StringVar, filedialog, messagebox

import customtkinter as ctk

from followflow.common import (
    APP_NAME,
    DEFAULT_BROWSER_PROFILE_DIR,
    DEFAULT_FOLLOWING_PATH,
    DEFAULT_NON_MUTUALS_PATH,
    DEFAULT_PROCESSED_DIR,
    DEFAULT_REVIEW_LOG_PATH,
    DEFAULT_REVIEW_STATE_PATH,
)
from followflow.compare import run_compare
from followflow.export_parser import run_extract
from followflow.review import run_review
from followflow.scrape import run_scrape

APP_BG = "#0a0e17"
PANEL_BG = "#0f1629"
PANEL_ALT = "#151d33"
CARD_BG = "#ffffff"
CARD_SUB = "#f4f6fb"
BORDER = "#c8d1e0"
TEXT = "#0b1220"
MUTED = "#5c6b82"
ACCENT = "#f97316"
ACCENT_HOVER = "#fb923c"
TEAL = "#14b8a6"
TEAL_HOVER = "#2dd4bf"
BUTTON_DARK = "#1e3a5f"
BUTTON_DARK_HOVER = "#274e7d"
CONSOLE_BG = "#070b12"
CONSOLE_FG = "#e2e8f0"
HEADER_ACCENT = "#f97316"
SIDEBAR_MUTED = "#94a3b8"
SIDEBAR_WIDTH = 252


class QueueWriter:
    def __init__(self, sink: queue.Queue[tuple[str, str]]) -> None:
        self._sink = sink

    def write(self, text: str) -> int:
        if text:
            self._sink.put(("log", text))
        return len(text)

    def flush(self) -> None:
        return


class FollowFlowLauncher(ctk.CTk):
    def __init__(self) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        super().__init__()
        self.title(f"{APP_NAME} Studio")
        self.minsize(1024, 640)
        self.configure(fg_color=APP_BG)

        self._queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self._worker: threading.Thread | None = None
        self._controls: list[Any] = []

        self._font_display = ctk.CTkFont(family="Segoe UI", size=26, weight="bold")
        self._font_title = ctk.CTkFont(family="Segoe UI", size=18, weight="bold")
        self._font_section = ctk.CTkFont(family="Segoe UI", size=14, weight="bold")
        self._font_body = ctk.CTkFont(family="Segoe UI", size=13)
        self._font_hint = ctk.CTkFont(family="Segoe UI", size=12)
        self._font_small = ctk.CTkFont(family="Segoe UI", size=11)
        self._font_mono = ctk.CTkFont(family="Consolas", size=12)

        self.source_var = StringVar(value="scrape")
        self.scrape_username_var = StringVar()
        self.zip_path_var = StringVar()
        self.output_dir_var = StringVar(value=str(DEFAULT_PROCESSED_DIR))
        self.browser_var = StringVar()
        self.profile_dir_var = StringVar(value=str(DEFAULT_BROWSER_PROFILE_DIR))
        self.review_input_var = StringVar(value=str(DEFAULT_NON_MUTUALS_PATH))
        self.following_var = StringVar(value=str(DEFAULT_FOLLOWING_PATH))
        self.state_var = StringVar(value=str(DEFAULT_REVIEW_STATE_PATH))
        self.log_var = StringVar(value=str(DEFAULT_REVIEW_LOG_PATH))
        self.start_at_var = StringVar()
        self.reset_var = BooleanVar(value=False)
        self.status_var = StringVar(value="Ready")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_ui()
        self._sync_review_paths()
        self._set_source_mode()
        self.after(120, self._drain_queue)

        self.geometry("1680x960")
        self.after(80, self._maximize_window)

    def _maximize_window(self) -> None:
        if sys.platform == "win32":
            try:
                self.state("zoomed")
            except tk.TclError:
                self.geometry("1680x960")
        elif sys.platform == "darwin":
            try:
                self.attributes("-zoomed", True)
            except tk.TclError:
                self.geometry("1680x960")
        else:
            self.attributes("-zoomed", True)

    def _build_ui(self) -> None:
        self._header().grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        content.grid_columnconfigure(0, weight=0, minsize=SIDEBAR_WIDTH)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)

        self._sidebar(content).grid(row=0, column=0, sticky="nsew", padx=(0, 14))

        main = ctk.CTkFrame(content, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=0)
        main.grid_columnconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(
            main,
            fg_color="transparent",
            scrollbar_button_color=PANEL_ALT,
            scrollbar_button_hover_color=ACCENT,
        )
        scroll.grid(row=0, column=0, sticky="nsew")
        self._workspace(scroll)

        self._console(main).grid(row=1, column=0, sticky="nsew", pady=(14, 0))

    def _header(self) -> ctk.CTkFrame:
        outer = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkFrame(outer, fg_color=HEADER_ACCENT, height=3, corner_radius=0).pack(fill="x")
        frame = ctk.CTkFrame(outer, fg_color=PANEL_BG, corner_radius=12, border_width=1, border_color="#1e293b")
        frame.pack(fill="x")
        frame.grid_columnconfigure(1, weight=1)

        mark = tk.Canvas(frame, width=76, height=76, bg=PANEL_BG, highlightthickness=0)
        mark.grid(row=0, column=0, padx=20, pady=20)
        mark.create_oval(8, 8, 68, 68, fill="#fff7ed", outline="")
        mark.create_arc(16, 20, 60, 64, start=205, extent=140, style="arc", outline=ACCENT, width=5)
        mark.create_oval(22, 24, 39, 41, fill=TEAL, outline="")
        mark.create_oval(37, 24, 54, 41, fill=ACCENT, outline="")

        text = ctk.CTkFrame(frame, fg_color="transparent")
        text.grid(row=0, column=1, sticky="ew", pady=20)
        ctk.CTkLabel(text, text=f"{APP_NAME} Studio", text_color="#f8fafc", font=self._font_display).pack(anchor="w")
        ctk.CTkLabel(
            text,
            text="Prepare lists, compare followers, and review profiles — with a browser session that waits for Instagram login.",
            text_color=SIDEBAR_MUTED,
            font=self._font_hint,
            wraplength=880,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        status = ctk.CTkLabel(
            frame,
            textvariable=self.status_var,
            text_color="#e0f2fe",
            font=self._font_small,
            fg_color="#1e293b",
            corner_radius=10,
            padx=18,
            pady=12,
        )
        status.grid(row=0, column=2, padx=20, pady=20, sticky="e")
        return outer

    def _sidebar(self, parent: ctk.CTkFrame) -> ctk.CTkScrollableFrame:
        rail = ctk.CTkScrollableFrame(
            parent,
            width=SIDEBAR_WIDTH,
            fg_color=PANEL_ALT,
            corner_radius=12,
            border_width=1,
            border_color="#1e293b",
            scrollbar_button_color="#334155",
            scrollbar_button_hover_color=ACCENT,
        )
        self._side_title(rail, "Mode")
        self.mode_scrape = self._side_button(rail, "Browser Scrape", lambda: self._set_source("scrape"), BUTTON_DARK, BUTTON_DARK_HOVER)
        self.mode_zip = self._side_button(rail, "Export ZIP", lambda: self._set_source("zip"), BUTTON_DARK, BUTTON_DARK_HOVER)
        ctk.CTkFrame(rail, fg_color="#334155", height=1).pack(fill="x", pady=(14, 14))
        self._side_title(rail, "Workflow", pady=(0, 10))
        self._side_button(rail, "Prepare Data", self._start_prepare, ACCENT, ACCENT_HOVER)
        self._side_button(rail, "Prepare + Review", self._start_end_to_end, TEAL, TEAL_HOVER)
        self._side_button(rail, "Start Review", self._start_review, BUTTON_DARK, BUTTON_DARK_HOVER)
        self._side_button(rail, "Open Data Folder", self._open_output_dir, BUTTON_DARK, BUTTON_DARK_HOVER)
        self._side_button(rail, "Open Runtime Folder", self._open_runtime_dir, BUTTON_DARK, BUTTON_DARK_HOVER)
        self._side_title(rail, "Notes", pady=(18, 10))
        for note in [
            "This rail scrolls if your window is short.",
            "The main area is wide for paths and typing — scroll there for all fields.",
            "If Instagram needs login, finish it in the opened browser; tasks resume automatically.",
        ]:
            note_card = ctk.CTkFrame(rail, fg_color="#1a2332", corner_radius=8, border_width=1, border_color="#334155")
            note_card.pack(fill="x", pady=(0, 10))
            ctk.CTkLabel(
                note_card,
                text=note,
                text_color="#cbd5e1",
                font=self._font_small,
                wraplength=SIDEBAR_WIDTH - 36,
                justify="left",
            ).pack(anchor="w", padx=12, pady=12)
        return rail

    def _workspace(self, parent: ctk.CTkScrollableFrame) -> None:
        access = self._card(parent, "Browser Session", "Managed browser profile — FollowFlow waits while you sign in to Instagram if needed.")
        access.pack(fill="x", pady=(0, 12))
        self._access_body(access.body)  # type: ignore[attr-defined]

        prepare = self._card(parent, "Prepare Data", "Choose the data source and where generated JSON files should be written.")
        prepare.pack(fill="x", pady=(0, 12))
        self._prepare_body(prepare.body)  # type: ignore[attr-defined]

        review = self._card(parent, "Review Settings", "Paths for review input, state, logs, and optional start index.")
        review.pack(fill="x")
        self._review_body(review.body)  # type: ignore[attr-defined]

    def _console(self, parent: ctk.CTkFrame) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent, fg_color=PANEL_BG, corner_radius=12, border_width=1, border_color="#1e293b")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(frame, text="Session console", text_color="#f8fafc", font=self._font_title).grid(row=0, column=0, sticky="w", padx=18, pady=(16, 4))
        ctk.CTkLabel(
            frame,
            text="Live output from prepare, compare, login, and review tasks.",
            text_color=SIDEBAR_MUTED,
            font=self._font_hint,
        ).grid(row=1, column=0, sticky="w", padx=18, pady=(0, 8))

        self.console = ctk.CTkTextbox(
            frame,
            height=220,
            fg_color=CONSOLE_BG,
            text_color=CONSOLE_FG,
            font=self._font_mono,
            corner_radius=10,
            border_width=1,
            border_color="#334155",
            wrap="word",
            activate_scrollbars=True,
        )
        self.console.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 18))
        self.console.insert("1.0", "FollowFlow Studio is ready.\n")
        self.console.configure(state="disabled")
        return frame

    def _card(self, parent: ctk.CTkScrollableFrame, title: str, subtitle: str) -> ctk.CTkFrame:
        shell = ctk.CTkFrame(parent, fg_color="transparent")
        card = ctk.CTkFrame(shell, fg_color=CARD_BG, corner_radius=14, border_width=1, border_color=BORDER)
        card.pack(fill="x", padx=2, pady=2)
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=22, pady=(20, 12))
        ctk.CTkLabel(head, text=title, text_color=TEXT, font=self._font_title).pack(anchor="w")
        ctk.CTkLabel(
            head,
            text=subtitle,
            text_color=MUTED,
            font=self._font_hint,
            justify="left",
            wraplength=1200,
        ).pack(anchor="w", pady=(6, 0))
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=22, pady=(0, 22))
        shell.body = body  # type: ignore[attr-defined]
        return shell

    def _access_body(self, body: ctk.CTkFrame) -> None:
        info = ctk.CTkFrame(body, fg_color=CARD_SUB, corner_radius=10, border_width=1, border_color=BORDER)
        info.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(info, text="Login happens in the browser", text_color=TEXT, font=self._font_section).pack(anchor="w", padx=16, pady=(14, 6))
        ctk.CTkLabel(
            info,
            text=(
                "When you start scraping or review, FollowFlow opens Instagram in the managed browser profile. "
                "If you are logged out, sign in there manually, complete any prompts, and the task continues automatically."
            ),
            text_color=MUTED,
            font=self._font_small,
            justify="left",
            wraplength=1100,
        ).pack(anchor="w", padx=16, pady=(0, 14))
        self._field(
            body,
            "Browser executable",
            self.browser_var,
            "Optional. Leave blank to auto-detect Brave, Chrome, or Edge.",
            button_text="Browse",
            button_command=lambda: self._choose_file(self.browser_var, [("Executable", "*.exe"), ("All files", "*.*")]),
        )
        self._field(
            body,
            "Browser profile directory",
            self.profile_dir_var,
            "Persistent browser profile used for login state, scraping, and review.",
            button_text="Browse",
            button_command=lambda: self._choose_directory(self.profile_dir_var),
        )

    def _prepare_body(self, body: ctk.CTkFrame) -> None:
        panel = ctk.CTkFrame(body, fg_color=CARD_SUB, corner_radius=10, border_width=1, border_color=BORDER)
        panel.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(panel, text="Data Source", text_color=TEXT, font=self._font_section).pack(anchor="w", padx=16, pady=(14, 8))
        chips = ctk.CTkFrame(panel, fg_color="transparent")
        chips.pack(anchor="w", padx=16, pady=(0, 14))
        self.prepare_scrape = self._chip(chips, "Browser scrape", lambda: self._set_source("scrape"))
        self.prepare_scrape.pack(side="left", padx=(0, 8))
        self.prepare_zip = self._chip(chips, "Export ZIP", lambda: self._set_source("zip"))
        self.prepare_zip.pack(side="left")
        self.scrape_username_entry, _ = self._field(
            body,
            "Instagram account username",
            self.scrape_username_var,
            "Target account to scrape. Leave blank to detect the logged-in account automatically.",
        )
        self.zip_entry, _ = self._field(
            body,
            "Export ZIP path",
            self.zip_path_var,
            "Pick the Instagram export archive if you want to skip browser scraping.",
            button_text="Browse",
            button_command=lambda: self._choose_file(self.zip_path_var, [("ZIP files", "*.zip")]),
        )
        self._field(
            body,
            "Output directory",
            self.output_dir_var,
            "Followers, following, and non-mutual JSON files are written here.",
            button_text="Browse",
            button_command=lambda: self._choose_directory(self.output_dir_var, sync_paths=True),
        )

    def _review_body(self, body: ctk.CTkFrame) -> None:
        self._field(
            body,
            "Review input",
            self.review_input_var,
            "JSON or text file containing usernames or profile URLs.",
            button_text="Browse",
            button_command=lambda: self._choose_file(self.review_input_var, [("JSON files", "*.json"), ("Text files", "*.txt"), ("All files", "*.*")]),
        )
        self._field(
            body,
            "Following file",
            self.following_var,
            "Updated after the session when profiles are marked as unfollowed.",
            button_text="Browse",
            button_command=lambda: self._choose_file(self.following_var, [("JSON files", "*.json"), ("All files", "*.*")]),
        )
        self._field(
            body,
            "Review state file",
            self.state_var,
            "Resume position for the next review launch.",
            button_text="Browse",
            button_command=lambda: self._choose_file(self.state_var, [("JSON files", "*.json"), ("All files", "*.*")]),
        )
        self._field(
            body,
            "Review log file",
            self.log_var,
            "JSONL log storing the outcome of each reviewed profile.",
            button_text="Browse",
            button_command=lambda: self._choose_file(self.log_var, [("Log files", "*.jsonl"), ("All files", "*.*")]),
        )
        self._field(body, "Start at index", self.start_at_var, "Optional zero-based override if you want to jump to a specific row.")
        opts = ctk.CTkFrame(body, fg_color=CARD_SUB, corner_radius=10, border_width=1, border_color=BORDER)
        opts.pack(fill="x")
        ctk.CTkLabel(opts, text="Review Options", text_color=TEXT, font=self._font_section).pack(anchor="w", padx=16, pady=(14, 8))
        reset = ctk.CTkCheckBox(
            opts,
            text="Reset saved review state and start from index 0",
            variable=self.reset_var,
            text_color=TEXT,
            font=self._font_body,
            fg_color=TEAL,
            hover_color=TEAL_HOVER,
        )
        reset.pack(anchor="w", padx=16, pady=(0, 14))
        self._controls.append(reset)

    def _side_title(self, parent: ctk.CTkScrollableFrame, text: str, *, pady: tuple[int, int] = (0, 10)) -> None:
        ctk.CTkLabel(parent, text=text, text_color="#eff6ff", font=self._font_section).pack(anchor="w", pady=pady)

    def _side_button(self, parent: ctk.CTkScrollableFrame, text: str, command, fg: str, hover: str) -> ctk.CTkButton:
        button = ctk.CTkButton(
            parent,
            text=text,
            command=command,
            fg_color=fg,
            hover_color=hover,
            text_color="#ffffff",
            font=self._font_body,
            height=40,
            corner_radius=10,
        )
        button.pack(fill="x", pady=(0, 10))
        self._controls.append(button)
        return button

    def _chip(self, parent: ctk.CTkFrame, text: str, command) -> ctk.CTkButton:
        button = ctk.CTkButton(
            parent,
            text=text,
            command=command,
            fg_color=CARD_BG,
            hover_color="#e2e8f0",
            text_color=TEXT,
            border_width=1,
            border_color=BORDER,
            font=self._font_body,
            height=36,
            corner_radius=10,
        )
        self._controls.append(button)
        return button

    def _field(
        self,
        parent: ctk.CTkFrame,
        label: str,
        variable: StringVar,
        hint: str,
        *,
        show: str | None = None,
        button_text: str | None = None,
        button_command=None,
    ) -> tuple[ctk.CTkEntry, ctk.CTkButton | None]:
        wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        wrapper.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(wrapper, text=label, text_color=TEXT, font=self._font_section).pack(anchor="w")
        ctk.CTkLabel(wrapper, text=hint, text_color=MUTED, font=self._font_small, justify="left", wraplength=1100).pack(anchor="w", pady=(4, 8))
        row = ctk.CTkFrame(wrapper, fg_color="transparent")
        row.pack(fill="x")
        entry = ctk.CTkEntry(
            row,
            textvariable=variable,
            show=show or "",
            height=44,
            font=self._font_body,
            corner_radius=10,
            border_width=1,
            border_color=BORDER,
            fg_color="#ffffff",
            text_color=TEXT,
        )
        entry.pack(side="left", fill="x", expand=True)
        self._controls.append(entry)
        button = None
        if button_text and button_command:
            button = ctk.CTkButton(
                row,
                text=button_text,
                command=button_command,
                width=100,
                height=44,
                fg_color="#e2e8f0",
                hover_color="#cbd5e1",
                text_color=TEXT,
                font=self._font_body,
                corner_radius=10,
            )
            button.pack(side="left", padx=(10, 0))
            self._controls.append(button)
        return entry, button

    def _set_source(self, mode: str) -> None:
        self.source_var.set(mode)
        self._set_source_mode()

    def _set_source_mode(self) -> None:
        scrape = self.source_var.get() == "scrape"
        self.status_var.set("Browser scrape mode selected" if scrape else "Export ZIP mode selected")
        self.scrape_username_entry.configure(state="normal" if scrape else "disabled")
        self.zip_entry.configure(state="normal" if not scrape else "disabled")
        self._paint_toggle(self.mode_scrape, scrape, dark=True)
        self._paint_toggle(self.mode_zip, not scrape, dark=True)
        self._paint_toggle(self.prepare_scrape, scrape, dark=False)
        self._paint_toggle(self.prepare_zip, not scrape, dark=False)

    def _paint_toggle(self, button: ctk.CTkButton, active: bool, *, dark: bool) -> None:
        if dark:
            if active:
                button.configure(fg_color=TEAL, hover_color=TEAL_HOVER)
            else:
                button.configure(fg_color=BUTTON_DARK, hover_color=BUTTON_DARK_HOVER)
            return
        if active:
            button.configure(fg_color=TEXT, hover_color=TEXT, text_color="#ffffff", border_width=0)
        else:
            button.configure(fg_color=CARD_BG, hover_color="#e2e8f0", text_color=TEXT, border_width=1, border_color=BORDER)

    def _choose_file(self, variable: StringVar, filetypes: list[tuple[str, str]]) -> None:
        filename = filedialog.askopenfilename(filetypes=filetypes)
        if filename:
            variable.set(filename)

    def _choose_directory(self, variable: StringVar, *, sync_paths: bool = False) -> None:
        directory = filedialog.askdirectory()
        if directory:
            variable.set(directory)
            if sync_paths:
                self._sync_review_paths()

    def _sync_review_paths(self) -> None:
        output_dir = Path(self.output_dir_var.get() or DEFAULT_PROCESSED_DIR).expanduser()
        self.review_input_var.set(str(output_dir / DEFAULT_NON_MUTUALS_PATH.name))
        self.following_var.set(str(output_dir / DEFAULT_FOLLOWING_PATH.name))

    def _append_console(self, text: str) -> None:
        self.console.configure(state="normal")
        self.console.insert("end", text)
        self.console.see("end")
        self.console.configure(state="disabled")

    def _drain_queue(self) -> None:
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "log":
                    self._append_console(payload)
                elif kind == "done":
                    self.status_var.set(payload)
                    self._set_busy(False)
                    messagebox.showinfo(f"{APP_NAME} Studio", payload)
                elif kind == "error":
                    self.status_var.set("A task stopped with an error")
                    self._set_busy(False)
                    messagebox.showerror(f"{APP_NAME} Studio", payload)
                elif kind == "status":
                    self.status_var.set(payload)
        except queue.Empty:
            pass
        self.after(120, self._drain_queue)

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for control in self._controls:
            try:
                control.configure(state=state)
            except (tk.TclError, TypeError, ValueError):
                continue

    def _run_task(self, label: str, callback) -> None:
        if self._worker is not None and self._worker.is_alive():
            messagebox.showinfo(f"{APP_NAME} Studio", "A task is already running. Let it finish first.")
            return
        self._set_busy(True)
        self._queue.put(("status", label))

        def worker() -> None:
            writer = QueueWriter(self._queue)
            try:
                with redirect_stdout(writer), redirect_stderr(writer):
                    callback()
            except SystemExit as exc:
                self._queue.put(("error", str(exc) or "The task exited early."))
            except Exception as exc:
                self._queue.put(("log", traceback.format_exc()))
                self._queue.put(("error", str(exc)))
            else:
                self._queue.put(("done", f"{label} finished successfully."))

        self._worker = threading.Thread(target=worker, daemon=True)
        self._worker.start()

    def _browser_path(self) -> Path | None:
        raw = self.browser_var.get().strip()
        return Path(raw).expanduser() if raw else None

    def _prepare_callback(self) -> None:
        source = self.source_var.get()
        output_dir = Path(self.output_dir_var.get()).expanduser()
        profile_dir = Path(self.profile_dir_var.get()).expanduser()
        browser = self._browser_path()
        if source == "scrape":
            scrape_username = self.scrape_username_var.get().strip() or None
            followers_path, following_path = run_scrape(
                username=scrape_username,
                output_dir=output_dir,
                profile_dir=profile_dir,
                browser_executable=browser,
                allow_terminal_input=False,
            )
        else:
            zip_path = self.zip_path_var.get().strip()
            followers_path, following_path = run_extract(
                zip_path=Path(zip_path).expanduser() if zip_path else None,
                output_dir=output_dir,
            )
        run_compare(
            followers_path=followers_path,
            following_path=following_path,
            output_path=output_dir / DEFAULT_NON_MUTUALS_PATH.name,
        )

    def _review_callback(self) -> None:
        start_at_value = self.start_at_var.get().strip()
        run_review(
            input_path=Path(self.review_input_var.get()).expanduser(),
            following_path=Path(self.following_var.get()).expanduser(),
            state_path=Path(self.state_var.get()).expanduser(),
            log_path=Path(self.log_var.get()).expanduser(),
            profile_dir=Path(self.profile_dir_var.get()).expanduser(),
            browser_executable=self._browser_path(),
            start_at=int(start_at_value) if start_at_value else None,
            reset=self.reset_var.get(),
            use_ui=True,
            allow_terminal_input=False,
        )

    def _prepare_and_review_callback(self) -> None:
        self._prepare_callback()
        self._review_callback()

    def _start_prepare(self) -> None:
        self._sync_review_paths()
        self._run_task("Preparing data", self._prepare_callback)

    def _start_review(self) -> None:
        self._run_task("Starting review", self._review_callback)

    def _start_end_to_end(self) -> None:
        self._sync_review_paths()
        self._run_task("Running full workflow", self._prepare_and_review_callback)

    def _open_output_dir(self) -> None:
        output_dir = Path(self.output_dir_var.get()).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            import os

            os.startfile(str(output_dir))  # type: ignore[attr-defined]
        except Exception:
            messagebox.showinfo(f"{APP_NAME} Studio", f"Open this folder manually:\n{output_dir}")

    def _open_runtime_dir(self) -> None:
        runtime_dir = Path(self.state_var.get()).expanduser().parent
        runtime_dir.mkdir(parents=True, exist_ok=True)
        try:
            import os

            os.startfile(str(runtime_dir))  # type: ignore[attr-defined]
        except Exception:
            messagebox.showinfo(f"{APP_NAME} Studio", f"Open this folder manually:\n{runtime_dir}")


def main() -> int:
    app = FollowFlowLauncher()
    app.mainloop()
    return 0
