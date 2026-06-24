"""Dialog for importing OpenVPN .ovpn configuration profiles."""

from __future__ import annotations

import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from sandyvpn.theme import BG, BORDER, FG, FG_MUTED, ORANGE_BRIGHT, SURFACE_ALT
from sandyvpn.vpn import import_config

try:
    from tkinterdnd2 import DND_FILES

    _HAS_DND = True
except ImportError:
    _HAS_DND = False


class ConfigImportDialog:
    """Modal popup to import an .ovpn file via drag-and-drop or file picker."""

    def __init__(
        self,
        parent: tk.Tk,
        *,
        on_imported: Callable[[str], None] | None = None,
        on_output: Callable[[str], None] | None = None,
    ) -> None:
        self.parent = parent
        self.on_imported = on_imported
        self.on_output = on_output
        self._ovpn_path: Path | None = None
        self._busy = False

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Import OpenVPN config")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.resizable(False, False)
        self.dialog.configure(bg=BG)

        self._build_ui()
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.dialog.bind("<Escape>", lambda _event: self._on_cancel())

        self.dialog.update_idletasks()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        dialog_w = self.dialog.winfo_width()
        dialog_h = self.dialog.winfo_height()
        self.dialog.geometry(
            f"+{parent_x + (parent_w - dialog_w) // 2}+{parent_y + (parent_h - dialog_h) // 2}"
        )

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.dialog, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        drop_hint = (
            "Drop an .ovpn file here\nor click to browse"
            if _HAS_DND
            else "Click to choose an .ovpn file"
        )
        self.drop_zone = tk.Frame(
            frame,
            bg=SURFACE_ALT,
            highlightthickness=2,
            highlightbackground=BORDER,
            highlightcolor=ORANGE_BRIGHT,
            cursor="hand2",
        )
        self.drop_zone.pack(fill=tk.X, pady=(0, 12))
        self.drop_zone.bind("<Button-1>", self._on_browse)

        self.drop_label = tk.Label(
            self.drop_zone,
            text=drop_hint,
            bg=SURFACE_ALT,
            fg=FG_MUTED,
            font=("Segoe UI", 10),
            justify=tk.CENTER,
            padx=24,
            pady=28,
        )
        self.drop_label.pack(fill=tk.BOTH, expand=True)
        self.drop_label.bind("<Button-1>", self._on_browse)

        if _HAS_DND:
            for widget in (self.drop_zone, self.drop_label):
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self._on_drop)
                widget.dnd_bind("<<DragEnter>>", self._on_drag_enter)
                widget.dnd_bind("<<DragLeave>>", self._on_drag_leave)

        self.file_var = tk.StringVar(value="No file selected")
        ttk.Label(frame, textvariable=self.file_var, style="Muted.TLabel").pack(
            anchor=tk.W, pady=(0, 12)
        )

        ttk.Label(frame, text="Config name").pack(anchor=tk.W, pady=(0, 4))
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(frame, textvariable=self.name_var, width=40)
        self.name_entry.pack(fill=tk.X, pady=(0, 16))

        btn_row = ttk.Frame(frame)
        btn_row.pack(fill=tk.X)

        self.import_btn = ttk.Button(
            btn_row,
            text="Import",
            style="Accent.TButton",
            command=self._on_import,
            state=tk.DISABLED,
        )
        self.import_btn.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(btn_row, text="Cancel", command=self._on_cancel).pack(side=tk.LEFT)

    def _set_drop_highlight(self, active: bool) -> None:
        color = ORANGE_BRIGHT if active else BORDER
        self.drop_zone.configure(highlightbackground=color)

    def _on_drag_enter(self, _event: tk.Event) -> None:
        self._set_drop_highlight(True)

    def _on_drag_leave(self, _event: tk.Event) -> None:
        self._set_drop_highlight(False)

    def _on_drop(self, event: tk.Event) -> None:
        self._set_drop_highlight(False)
        paths = self.parent.tk.splitlist(event.data)
        if paths:
            self._select_file(Path(paths[0]))

    def _on_browse(self, _event: tk.Event | None = None) -> None:
        if self._busy:
            return
        path = filedialog.askopenfilename(
            parent=self.dialog,
            title="Select OpenVPN config",
            filetypes=[("OpenVPN config", "*.ovpn"), ("All files", "*.*")],
        )
        if path:
            self._select_file(Path(path))

    def _select_file(self, path: Path) -> None:
        if path.suffix.lower() != ".ovpn":
            messagebox.showwarning(
                "Invalid file",
                "Choose an OpenVPN configuration file (.ovpn).",
                parent=self.dialog,
            )
            return
        if not path.is_file():
            messagebox.showwarning("Invalid file", "That file does not exist.", parent=self.dialog)
            return

        self._ovpn_path = path
        self.file_var.set(path.name)
        self.drop_label.configure(text=path.name, fg=FG)
        self.import_btn.configure(state=tk.NORMAL if not self._busy else tk.DISABLED)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self.import_btn.configure(state=state if self._ovpn_path else tk.DISABLED)
        self.name_entry.configure(state=state)
        self.drop_zone.configure(cursor="" if busy else "hand2")

    def _on_import(self) -> None:
        if self._busy or self._ovpn_path is None:
            return

        config_name = self.name_var.get().strip()
        if not config_name:
            messagebox.showwarning("Missing name", "Enter a name for this configuration.", parent=self.dialog)
            return

        ovpn_path = self._ovpn_path
        self._set_busy(True)
        if self.on_output is not None:
            self.on_output(f"\nImporting '{ovpn_path.name}' as '{config_name}'...\n")

        def run() -> None:
            try:
                code, output = import_config(
                    ovpn_path,
                    config_name,
                    on_output=self.on_output,
                )
                if code == 0:
                    self.dialog.after(
                        0,
                        lambda: self._finish_success(config_name, output),
                    )
                else:
                    self.dialog.after(
                        0,
                        lambda: self._finish_failure(output or f"Import failed with code {code}."),
                    )
            except FileNotFoundError:
                self.dialog.after(
                    0,
                    lambda: messagebox.showerror(
                        "openvpn3 not found",
                        "Could not find the openvpn3 command. Is OpenVPN 3 installed?",
                        parent=self.dialog,
                    ),
                )
                self.dialog.after(0, lambda: self._set_busy(False))
            except Exception as exc:  # noqa: BLE001
                self.dialog.after(
                    0,
                    lambda: messagebox.showerror("Import error", str(exc), parent=self.dialog),
                )
                self.dialog.after(0, lambda: self._set_busy(False))

        threading.Thread(target=run, daemon=True).start()

    def _finish_success(self, config_name: str, output: str) -> None:
        if output and self.on_output is not None:
            self.on_output(output)
        if self.on_output is not None:
            self.on_output(f"Configuration '{config_name}' imported.\n")
        if self.on_imported is not None:
            self.on_imported(config_name)
        self.dialog.grab_release()
        self.dialog.destroy()

    def _finish_failure(self, message: str) -> None:
        if self.on_output is not None:
            self.on_output(f"\n{message}\n")
        messagebox.showerror("Import failed", message, parent=self.dialog)
        self._set_busy(False)

    def _on_cancel(self) -> None:
        if self._busy:
            return
        self.dialog.grab_release()
        self.dialog.destroy()
