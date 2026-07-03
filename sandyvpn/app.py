"""SandyVPN — simple GUI for OpenVPN 3 session-start."""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from sandyvpn.errors import CredentialsCorruptedError, OpenVpn3Error
from sandyvpn.glow import TopBanner
from sandyvpn.icon import APP_WM_CLASS, configure_app_window
from sandyvpn.import_dialog import ConfigImportDialog
from sandyvpn.mascot import GingerCatMascot
from sandyvpn.session_service import VpnSessionService
from sandyvpn.storage import CredentialStore
from sandyvpn.theme import ScrolledText, apply_theme, style_text_widget
from sandyvpn.threading_ui import run_in_thread

STATUS_POLL_MS = 10_000
UPTIME_TICK_MS = 1_000
PASSWORD_PLACEHOLDER = "•" * 20


def _format_duration(seconds: int) -> str:
    hours, rem = divmod(max(0, seconds), 3600)
    minutes, secs = divmod(rem, 60)
    if hours >= 24:
        days, hours = divmod(hours, 24)
        return f"{days}d {hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class SandyVPNApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("sandyOVPN")
        self.root.minsize(520, 480)
        self._store = CredentialStore()
        self._sessions = VpnSessionService()
        self._busy = False
        self._connected = False
        self._active_config = ""
        self._status_timer_id: str | None = None
        self._uptime_timer_id: str | None = None
        self._connected_since: datetime | None = None

        apply_theme(root)
        self._build_ui()
        self._set_busy(False)
        self._load_saved_credentials()
        self._check_existing_session()

    def _build_ui(self) -> None:
        self.frame = ttk.Frame(self.root, padding=12)
        self.frame.pack(fill=tk.BOTH, expand=True)

        self.top_banner = TopBanner(self.frame)
        self.top_banner.grid(row=0, column=0, sticky=tk.EW, pady=(0, 12))

        self.mascot = GingerCatMascot()
        self.mascot.set_mood(False)
        self.top_banner.set_mascot(self.mascot)

        self.setup_frame = ttk.Frame(self.frame)
        self.setup_frame.grid(row=1, column=0, sticky=tk.NSEW)

        field_pad = (0, 8)
        ttk.Label(self.setup_frame, text="Config name").grid(row=0, column=0, sticky=tk.W, padx=(0, 8), pady=(0, 4))
        ttk.Label(self.setup_frame, text="VPN username").grid(row=0, column=1, sticky=tk.W, padx=(0, 8), pady=(0, 4))
        ttk.Label(self.setup_frame, text="VPN password").grid(row=0, column=2, sticky=tk.W, pady=(0, 4))

        self.config_var = tk.StringVar()
        self.config_var.trace_add("write", self._on_config_var_changed)
        self.config_entry = ttk.Entry(self.setup_frame, textvariable=self.config_var, width=18)
        self.config_entry.grid(row=1, column=0, sticky=tk.EW, padx=(0, 8), pady=field_pad)

        self.username_var = tk.StringVar()
        self.username_var.trace_add("write", self._on_setup_field_changed)
        self.username_entry = ttk.Entry(self.setup_frame, textvariable=self.username_var, width=18)
        self.username_entry.grid(row=1, column=1, sticky=tk.EW, padx=(0, 8), pady=field_pad)

        self.password_var = tk.StringVar()
        self.password_var.trace_add("write", self._on_setup_field_changed)
        self.password_entry = ttk.Entry(self.setup_frame, textvariable=self.password_var, show="•", width=18)
        self.password_entry.grid(row=1, column=2, sticky=tk.EW, pady=field_pad)
        self.password_entry.bind("<FocusIn>", self._on_password_focus_in)
        self.password_entry.bind("<Key>", self._on_password_key, add="+")

        setup_btn_row = ttk.Frame(self.setup_frame)
        setup_btn_row.grid(row=2, column=0, columnspan=3, sticky=tk.EW, pady=(0, 12))

        connect_col = ttk.Frame(setup_btn_row)
        connect_col.pack(side=tk.LEFT, anchor=tk.N)

        self.connect_btn = ttk.Button(
            connect_col, text="Connect", style="Accent.TButton", command=self._on_connect
        )
        self.connect_btn.pack(anchor=tk.W)

        self.connect_hint_var = tk.StringVar()
        self.connect_hint = ttk.Label(
            connect_col, textvariable=self.connect_hint_var, style="Hint.TLabel", wraplength=220
        )
        self.connect_hint.pack(anchor=tk.W, pady=(1, 0))

        right_btn_row = ttk.Frame(setup_btn_row)
        right_btn_row.pack(side=tk.RIGHT)
        self.right_btn_row = right_btn_row

        self.import_btn = ttk.Button(
            right_btn_row,
            text="Import ovpn file",
            style="Import.TButton",
            command=self._on_import_config,
        )
        self.import_btn.pack(side=tk.RIGHT, padx=(12, 0))

        self.clear_btn = ttk.Button(right_btn_row, text="Clear saved config", command=self._on_clear)
        self.clear_btn.pack(side=tk.RIGHT, padx=(8, 0))

        self.save_btn = ttk.Button(right_btn_row, text="Save credentials", command=self._on_save)
        self.save_btn.pack(side=tk.RIGHT, padx=(8, 0))

        self.status_frame = ttk.LabelFrame(self.frame, text="VPN status", padding=8)
        self.status_frame.grid(row=2, column=0, sticky=tk.NSEW, pady=(0, 12))
        self.status_frame.grid_remove()

        self.status_summary_var = tk.StringVar(value="Not connected")
        ttk.Label(self.status_frame, textvariable=self.status_summary_var).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 8)
        )

        self.status_text = ScrolledText(self.status_frame, height=8, state=tk.DISABLED, wrap=tk.WORD)
        self.status_text.grid(row=1, column=0, sticky=tk.NSEW, pady=(0, 8))
        style_text_widget(self.status_text)

        status_btn_row = ttk.Frame(self.status_frame)
        status_btn_row.grid(row=2, column=0, sticky=tk.W)

        self.disconnect_btn = ttk.Button(status_btn_row, text="Disconnect", command=self._on_disconnect)
        self.disconnect_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.reconnect_btn = ttk.Button(
            status_btn_row, text="Reconnect", style="Accent.TButton", command=self._on_reconnect
        )
        self.reconnect_btn.pack(side=tk.LEFT)

        ttk.Label(self.frame, text="Log").grid(row=3, column=0, sticky=tk.W, pady=(0, 4))
        self.output = ScrolledText(self.frame, height=8, state=tk.DISABLED, wrap=tk.WORD)
        self.output.grid(row=4, column=0, sticky=tk.NSEW)
        style_text_widget(self.output)

        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(4, weight=1)
        for col in range(3):
            self.setup_frame.columnconfigure(col, weight=1)
        self.status_frame.columnconfigure(0, weight=1)
        self.status_frame.rowconfigure(1, weight=1)
        self._update_credential_buttons()

    def _connect_allowed(self) -> bool:
        return self._store.credentials_exist() and self._store.has_stored_password()

    def _connect_disabled_reason(self) -> str | None:
        if self._connected:
            return None
        if self._busy:
            return "Please wait…"
        if self._connect_allowed():
            return None
        if not self.config_var.get().strip():
            return "Enter a config name, then save credentials to connect."
        if not self.username_var.get().strip():
            return "Enter a username, then save credentials to connect."
        if not self._get_typed_password() and not self._store.has_stored_password():
            return "Enter a password, then save credentials to connect."
        return "Save credentials to connect."

    def _update_connect_button(self) -> None:
        reason = self._connect_disabled_reason()
        if self._connected or self._busy or reason:
            self.connect_btn.config(state=tk.DISABLED)
            self.connect_hint_var.set(reason or "")
        else:
            self.connect_btn.config(state=tk.NORMAL)
            self.connect_hint_var.set("")

    def _password_is_placeholder(self) -> bool:
        return self.password_var.get() == PASSWORD_PLACEHOLDER

    def _show_password_placeholder(self) -> None:
        self.password_var.set(PASSWORD_PLACEHOLDER)

    def _clear_password_field(self) -> None:
        self.password_var.set("")

    def _purge_password_from_ui(self) -> None:
        if self._store.credentials_exist() and self._store.has_stored_password():
            self._show_password_placeholder()
        else:
            self._clear_password_field()

    def _get_typed_password(self) -> str | None:
        value = self.password_var.get()
        if not value or value == PASSWORD_PLACEHOLDER:
            return None
        return value

    def _on_password_focus_in(self, _event: tk.Event) -> None:
        if self._password_is_placeholder():
            self._clear_password_field()

    def _on_password_key(self, _event: tk.Event) -> None:
        if self._password_is_placeholder():
            self._clear_password_field()

    def _on_config_var_changed(self, *_args: object) -> None:
        self._update_import_button()
        self._update_connect_button()

    def _on_setup_field_changed(self, *_args: object) -> None:
        self._update_connect_button()

    def _update_credential_buttons(self) -> None:
        if self._store.credentials_exist():
            self.save_btn.pack_forget()
            self.clear_btn.pack(in_=self.right_btn_row, side=tk.RIGHT, padx=(8, 0))
        else:
            self.clear_btn.pack_forget()
            self.save_btn.pack(in_=self.right_btn_row, side=tk.RIGHT, padx=(8, 0))
        self._update_import_button()
        self._update_connect_button()

    def _update_import_button(self) -> None:
        show = not self._connected and not self.config_var.get().strip()
        if show:
            self.import_btn.pack(in_=self.right_btn_row, side=tk.RIGHT, padx=(12, 0))
        else:
            self.import_btn.pack_forget()

    def _show_validation_error(self, error: tuple[str, str]) -> None:
        title, message = error
        messagebox.showwarning(title, message)

    def _load_saved_credentials(self) -> None:
        load_error = self._store.load_error
        if load_error is not None:
            messagebox.showerror("Credentials error", load_error)
            return

        try:
            profile = self._store.load_profile()
        except CredentialsCorruptedError as exc:
            messagebox.showerror("Credentials error", str(exc))
            return

        if profile is None:
            return
        self.config_var.set(profile.config_name)
        self.username_var.set(profile.username)
        self._purge_password_from_ui()
        self._update_credential_buttons()
        if self._store.has_stored_password():
            self._append_output("Loaded saved profile. \n(Password stays encrypted at all times.)\n")
        else:
            self._append_output("Loaded saved profile.\n")

    def _resolve_connect_auth(self) -> tuple[str, str, str] | None:
        result = self._store.resolve_connect(
            self.config_var.get().strip(),
            self.username_var.get().strip(),
            self._get_typed_password(),
        )
        if isinstance(result, tuple):
            self._show_validation_error(result)
            return None
        if self._get_typed_password():
            self._purge_password_from_ui()
        return result.config_name, result.username, result.password

    def _resolve_save_auth(self):
        result = self._store.resolve_save(
            self.config_var.get().strip(),
            self.username_var.get().strip(),
            self._get_typed_password(),
        )
        if result is None:
            return None
        if isinstance(result, tuple):
            self._show_validation_error(result)
            return None
        return result

    def _check_existing_session(self) -> None:
        config_name = self.config_var.get().strip()
        if not config_name:
            return

        def work() -> None:
            if not self._sessions.is_active(config_name):
                return
            started_at = self._sessions.started_at(config_name)
            self.root.after(
                0,
                lambda c=config_name, s=started_at: self._enter_connected_state(c, started_at=s),
            )

        run_in_thread(self.root, work)

    def _on_import_config(self) -> None:
        if self._busy or self._connected:
            return

        def on_imported(config_name: str) -> None:
            self.config_var.set(config_name)
            self._append_output(
                f"Imported config '{config_name}'. Enter username and password, then save credentials.\n"
            )

        ConfigImportDialog(
            self.root,
            sessions=self._sessions,
            on_imported=on_imported,
            on_output=self._append_output,
        )

    def _on_save(self) -> None:
        creds = self._resolve_save_auth()
        if creds is None:
            return
        self._store.save(creds)
        self._purge_password_from_ui()
        self._update_credential_buttons()
        self._append_output("Credentials saved (password encrypted on disk).\n")

    def _on_clear(self) -> None:
        if not messagebox.askyesno("Clear credentials", "Remove saved credentials and clear the form?"):
            return
        self._store.clear()
        self.config_var.set("")
        self.username_var.set("")
        self._purge_password_from_ui()
        self._update_credential_buttons()
        self._append_output("Saved credentials cleared.\n")

    def _on_connect(self) -> None:
        if self._busy or not self._connect_allowed():
            return
        auth = self._resolve_connect_auth()
        if auth is None:
            return

        config_name, username, password = auth
        self._set_busy(True)
        self._append_output(f"\nStarting session for config '{config_name}'...\n")

        def work() -> None:
            def append_line(line: str) -> None:
                self.root.after(0, lambda: self._append_output(line))

            session_password = password
            try:
                code, _ = self._sessions.connect(
                    config_name,
                    username,
                    session_password,
                    on_output=append_line,
                )
                if code == 0:
                    self.root.after(
                        0,
                        lambda: self._enter_connected_state(config_name, "Session started.\n"),
                    )
                else:
                    self.root.after(
                        0,
                        lambda: self._append_output(f"\nSession start failed with code {code}.\n"),
                    )
            finally:
                session_password = ""

        run_in_thread(self.root, work, error_title="Connection error", on_finally=lambda: self._set_busy(False))

    def _on_disconnect(self) -> None:
        if self._busy or not self._connected:
            return
        if not messagebox.askyesno("Disconnect", f"Disconnect VPN session '{self._active_config}'?"):
            return

        active_config = self._active_config
        self._set_busy(True)
        self._append_output(f"\nDisconnecting '{active_config}'...\n")

        def work() -> None:
            code, output = self._sessions.disconnect(active_config)
            self.root.after(0, lambda: self._append_output(output))
            if code == 0:
                self.root.after(0, self._enter_disconnected_state)
                self.root.after(0, lambda: self._append_output("Disconnected.\n"))
            else:
                self.root.after(
                    0,
                    lambda: messagebox.showerror("Disconnect failed", output or f"Exit code {code}"),
                )

        run_in_thread(self.root, work, error_title="Disconnect error", on_finally=lambda: self._set_busy(False))

    def _on_reconnect(self) -> None:
        if self._busy or not self._connected:
            return

        active_config = self._active_config
        self._set_busy(True)
        self._append_output(f"\nReconnecting '{active_config}'...\n")

        def work() -> None:
            code, output = self._sessions.reconnect(active_config)
            self.root.after(0, lambda: self._append_output(output))
            if code == 0:
                self.root.after(
                    0,
                    lambda: self._append_output("Reconnect triggered successfully.\n"),
                )
                started_at = self._sessions.started_at(active_config)
                self.root.after(0, lambda s=started_at: self._reset_uptime(s))
                self.root.after(0, self._refresh_status)
            else:
                self.root.after(
                    0,
                    lambda: messagebox.showerror("Reconnect failed", output or f"Exit code {code}"),
                )

        run_in_thread(self.root, work, error_title="Reconnect error", on_finally=lambda: self._set_busy(False))

    def _set_connected_look(self, active: bool) -> None:
        self.top_banner.set_connected(active)

    def _enter_connected_state(
        self,
        config_name: str,
        message: str = "",
        started_at: datetime | None = None,
    ) -> None:
        self._connected = True
        self._active_config = config_name
        self._purge_password_from_ui()
        self.status_frame.grid()
        self._set_credentials_enabled(False)
        self.status_summary_var.set(f"Connected — {config_name}")
        self.mascot.set_mood(True)
        self._set_connected_look(True)
        self._reset_uptime(started_at)
        if message:
            self._append_output(message)
        self._refresh_status()
        self._schedule_status_poll()
        self._set_busy(False)
        self._update_import_button()

    def _enter_disconnected_state(self) -> None:
        self._connected = False
        self._active_config = ""
        self._cancel_status_poll()
        self._stop_uptime_counter()
        self.status_frame.grid_remove()
        self._set_credentials_enabled(True)
        self.status_summary_var.set("Not connected")
        self.top_banner.set_uptime_text("")
        self.mascot.set_mood(False)
        self._set_connected_look(False)
        self._set_status_text("")
        self._purge_password_from_ui()
        self._update_credential_buttons()
        self._set_busy(False)

    def _reset_uptime(self, started_at: datetime | None = None) -> None:
        self._cancel_uptime_timer()
        self._connected_since = started_at or datetime.now()
        self._update_uptime_display()
        self._uptime_timer_id = self.root.after(UPTIME_TICK_MS, self._tick_uptime)

    def _cancel_uptime_timer(self) -> None:
        if self._uptime_timer_id is not None:
            self.root.after_cancel(self._uptime_timer_id)
            self._uptime_timer_id = None

    def _stop_uptime_counter(self) -> None:
        self._cancel_uptime_timer()
        self._connected_since = None

    def _tick_uptime(self) -> None:
        if not self._connected or self._connected_since is None:
            return
        self._update_uptime_display()
        self._uptime_timer_id = self.root.after(UPTIME_TICK_MS, self._tick_uptime)

    def _update_uptime_display(self) -> None:
        if self._connected_since is None:
            self.top_banner.set_uptime_text("")
            return
        elapsed = int((datetime.now() - self._connected_since).total_seconds())
        self.top_banner.set_uptime_text(f"Connected for: {_format_duration(elapsed)}")

    def _set_credentials_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        self.config_entry.config(state=state)
        self.username_entry.config(state=state)
        self.password_entry.config(state=state)
        self.import_btn.config(state=state)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        if busy:
            self.disconnect_btn.config(state=tk.DISABLED)
            self.reconnect_btn.config(state=tk.DISABLED)
            self.import_btn.config(state=tk.DISABLED)
            self._update_connect_button()
            return

        if self._connected:
            self.disconnect_btn.config(state=tk.NORMAL)
            self.reconnect_btn.config(state=tk.NORMAL)
            self.import_btn.config(state=tk.DISABLED)
            self._update_connect_button()
        else:
            self._update_connect_button()
            self.disconnect_btn.config(state=tk.DISABLED)
            self.reconnect_btn.config(state=tk.DISABLED)
            self.import_btn.config(state=tk.NORMAL)

    def _schedule_status_poll(self) -> None:
        self._cancel_status_poll()
        self._status_timer_id = self.root.after(STATUS_POLL_MS, self._poll_status)

    def _cancel_status_poll(self) -> None:
        if self._status_timer_id is not None:
            self.root.after_cancel(self._status_timer_id)
            self._status_timer_id = None

    def _poll_status(self) -> None:
        if not self._connected:
            return
        self._refresh_status()
        self._schedule_status_poll()

    def _refresh_status(self) -> None:
        if not self._connected:
            return

        config_name = self._active_config

        def work() -> None:
            try:
                code, output = self._sessions.stats(config_name)
            except OpenVpn3Error as exc:
                self.root.after(
                    0,
                    lambda: self._set_status_text(f"Failed to fetch status: {exc}\n"),
                )
                return

            timestamp = datetime.now().strftime("%H:%M:%S")
            if code == 0:

                text = f"Updated: {timestamp}\n\n{output.strip()}\n\n[ ฅ^>⩊<^ ฅ Please wait 10 seconds for network to be connected ]"
                self.root.after(0, lambda: self._set_status_text(text))
                self.root.after(
                    0,
                    lambda: self.status_summary_var.set(f"Connected — {config_name} (updated {timestamp})"),
                )
            else:
                text = f"Updated {timestamp}\n\nSession no longer active.\n{output.strip()}\n"
                self.root.after(0, lambda: self._set_status_text(text))
                self.root.after(0, self._enter_disconnected_state)
                self.root.after(0, lambda: self._append_output("VPN session ended.\n"))

        run_in_thread(self.root, work)

    def _set_status_text(self, text: str) -> None:
        self.status_text.config(state=tk.NORMAL)
        self.status_text.delete("1.0", tk.END)
        self.status_text.insert(tk.END, text)
        self.status_text.config(state=tk.DISABLED)

    def _append_output(self, text: str) -> None:
        self.output.config(state=tk.NORMAL)
        self.output.insert(tk.END, text)
        self.output.see(tk.END)
        self.output.config(state=tk.DISABLED)


def main() -> None:
    try:
        from tkinterdnd2 import TkinterDnD

        root = TkinterDnD.Tk(className=APP_WM_CLASS)
    except ImportError:
        root = tk.Tk(className=APP_WM_CLASS)

    root.withdraw()
    configure_app_window(root)
    SandyVPNApp(root)
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()
