"""Window and launcher icon for SandyVPN."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
ICON_PNG = ASSETS_DIR / "icon.png"

# Lowercase class name matches WM_CLASS on Linux and groups with the .desktop entry.
APP_WM_CLASS = "sandyovpn"


def load_app_icon(root: tk.Misc) -> tk.PhotoImage | None:
    """Load the SandyVPN icon, preferring a user-provided ``assets/icon.png``."""
    if ICON_PNG.is_file():
        try:
            return tk.PhotoImage(file=str(ICON_PNG), master=root)
        except tk.TclError:
            pass
    return None


def _icon_variants(root: tk.Tk, base: tk.PhotoImage) -> list[tk.PhotoImage]:
    """Return several icon sizes for the window manager / Ubuntu dock."""
    images = [base]
    width = base.width()
    for target in (64, 32, 16):
        if width > target:
            div = max(1, width // target)
            if width // div >= 12:
                images.append(base.subsample(div))
    return images


def apply_window_icon(root: tk.Tk) -> list[tk.PhotoImage]:
    """Set the taskbar/window icon. Icons are kept alive on ``root``."""
    icon = load_app_icon(root)
    if icon is None:
        return []

    images = _icon_variants(root, icon)
    root.iconphoto(True, *images)
    root.iconname("sandyOVPN")
    root._app_icon_images = images
    return images


def configure_app_window(root: tk.Tk) -> None:
    """Apply title and icon settings needed for GNOME/Ubuntu dock integration."""
    root.title("sandyOVPN")
    images = apply_window_icon(root)

    def _reapply(_event: tk.Event | None = None) -> None:
        if images:
            root.iconphoto(True, *images)

    root.bind("<Map>", _reapply, add="+")


def icon_path() -> Path | None:
    """Return the icon file path for desktop launchers, if it exists."""
    return ICON_PNG if ICON_PNG.is_file() else None
