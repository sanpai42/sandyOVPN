"""Window and launcher icon for SandyVPN."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
ICON_PNG = ASSETS_DIR / "icon.png"


def load_app_icon(root: tk.Misc) -> tk.PhotoImage | None:
    """Load the SandyVPN icon, preferring a user-provided ``assets/icon.png``."""
    if ICON_PNG.is_file():
        try:
            return tk.PhotoImage(file=str(ICON_PNG), master=root)
        except tk.TclError:
            pass
    return None


def apply_window_icon(root: tk.Tk) -> tk.PhotoImage | None:
    """Set the taskbar/window icon. Caller must keep the returned image alive."""
    icon = load_app_icon(root)
    if icon is not None:
        root.iconphoto(True, icon)
    return icon


def icon_path() -> Path | None:
    """Return the icon file path for desktop launchers, if it exists."""
    return ICON_PNG if ICON_PNG.is_file() else None
