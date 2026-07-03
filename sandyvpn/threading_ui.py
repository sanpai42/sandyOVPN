"""Helpers for running blocking work off the Tk main thread."""

from __future__ import annotations

import threading
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox

from sandyvpn.errors import OpenVpn3Error, OpenVpn3NotFoundError

_OPENVPN3_MISSING = (
    "openvpn3 not found",
    "Could not find the openvpn3 command. Is OpenVPN 3 installed?",
)


def run_in_thread(
    widget: tk.Misc,
    work: Callable[[], None],
    *,
    error_title: str = "Error",
    on_finally: Callable[[], None] | None = None,
    parent: tk.Misc | None = None,
) -> None:
    """Run blocking work on a daemon thread and marshal UI updates via ``widget.after``."""

    def wrapper() -> None:
        try:
            work()
        except OpenVpn3NotFoundError:
            widget.after(
                0,
                lambda: messagebox.showerror(_OPENVPN3_MISSING[0], _OPENVPN3_MISSING[1], parent=parent),
            )
        except OpenVpn3Error as exc:
            widget.after(
                0,
                lambda e=exc: messagebox.showerror(error_title, str(e), parent=parent),
            )
        except OSError as exc:
            widget.after(
                0,
                lambda e=exc: messagebox.showerror(error_title, str(e), parent=parent),
            )
        finally:
            if on_finally is not None:
                widget.after(0, on_finally)

    threading.Thread(target=wrapper, daemon=True).start()
