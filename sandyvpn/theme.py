"""Dark theme with orange accents for SandyVPN."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# Palette
BG = "#14141a"
SURFACE = "#1f1f28"
SURFACE_ALT = "#2a2a36"
FG = "#ece8e4"
FG_MUTED = "#a8a4a0"
ORANGE = "#ff8c32"
ORANGE_BRIGHT = "#ffaa55"
ORANGE_DIM = "#c96a18"
BORDER = "#ff8c32"
ENTRY_BG = "#252530"
TEXT_BG = "#181820"
ACCENT_LINE = "#ff8c32"
GLOW_TINT = "#17241e"


def blend_hex(color_a: str, color_b: str, ratio: float) -> str:
    ratio = max(0.0, min(1.0, ratio))
    ar, ag, ab = int(color_a[1:3], 16), int(color_a[3:5], 16), int(color_a[5:7], 16)
    br, bg, bb = int(color_b[1:3], 16), int(color_b[3:5], 16), int(color_b[5:7], 16)
    return f"#{int(ar + (br - ar) * ratio):02x}{int(ag + (bg - ag) * ratio):02x}{int(ab + (bb - ab) * ratio):02x}"


def apply_theme(root: tk.Tk) -> ttk.Style:
    root.configure(bg=BG)

    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(".", background=BG, foreground=FG, bordercolor=BORDER, troughcolor=SURFACE_ALT)
    style.configure("TFrame", background=BG)
    style.configure("Surface.TFrame", background=SURFACE)
    style.configure("TLabel", background=BG, foreground=FG)
    style.configure("Muted.TLabel", background=BG, foreground=FG_MUTED)
    style.configure("Hint.TLabel", background=BG, foreground=FG_MUTED, font=("Segoe UI", 6))
    style.configure("Header.TLabel", background=BG, foreground=ORANGE_BRIGHT, font=("Segoe UI", 18, "bold"))
    style.configure("Uptime.TLabel", background=BG, foreground="#8fdf8f", font=("Segoe UI", 12, "bold"), anchor="center")
    style.configure("TLabelframe", background=BG, foreground=ORANGE, bordercolor=BORDER, relief="solid")
    style.configure("TLabelframe.Label", background=BG, foreground=ORANGE, font=("Segoe UI", 10, "bold"))
    style.configure(
        "TEntry",
        fieldbackground=ENTRY_BG,
        foreground=FG,
        insertcolor=ORANGE_BRIGHT,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", ORANGE_BRIGHT), ("!focus", BORDER)],
        lightcolor=[("focus", ORANGE_BRIGHT)],
        darkcolor=[("focus", ORANGE_BRIGHT)],
    )
    style.configure(
        "TButton",
        background=SURFACE_ALT,
        foreground=FG,
        bordercolor=BORDER,
        focusthickness=2,
        focuscolor=ORANGE,
        padding=(12, 6),
    )
    style.map(
        "TButton",
        background=[("active", ORANGE_DIM), ("pressed", ORANGE), ("disabled", SURFACE)],
        foreground=[("active", FG), ("pressed", BG), ("disabled", FG_MUTED)],
        bordercolor=[("active", ORANGE_BRIGHT), ("pressed", ORANGE_BRIGHT)],
    )
    style.configure(
        "Accent.TButton",
        background=ORANGE_DIM,
        foreground=BG,
        bordercolor=ORANGE_BRIGHT,
        font=("Segoe UI", 10, "bold"),
    )
    style.map(
        "Accent.TButton",
        background=[("active", ORANGE), ("pressed", ORANGE_BRIGHT), ("disabled", SURFACE)],
        foreground=[("active", BG), ("pressed", BG), ("disabled", FG_MUTED)],
    )
    style.configure(
        "TScrollbar",
        background=ORANGE_DIM,
        troughcolor=TEXT_BG,
        bordercolor=BORDER,
        lightcolor=ORANGE,
        darkcolor=ORANGE_DIM,
        arrowcolor=ORANGE_BRIGHT,
    )
    style.map(
        "TScrollbar",
        background=[("active", ORANGE), ("pressed", ORANGE_BRIGHT), ("disabled", SURFACE_ALT)],
        arrowcolor=[("active", ORANGE_BRIGHT), ("pressed", FG), ("disabled", FG_MUTED)],
    )

    return style


class ScrolledText(tk.Text):
    """Text area with a themed ttk scrollbar instead of the OS-native tk.Scrollbar."""

    def __init__(self, master: tk.Misc | None = None, **kwargs: object) -> None:
        self.frame = ttk.Frame(master)
        self._vbar = ttk.Scrollbar(self.frame, orient=tk.VERTICAL)

        tk.Text.__init__(self, self.frame, **kwargs)
        self.configure(yscrollcommand=self._vbar.set)
        self._vbar.configure(command=self.yview)

        self.grid(row=0, column=0, sticky=tk.NSEW)
        self._vbar.grid(row=0, column=1, sticky=tk.NS)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(0, weight=1)

        text_meths = vars(tk.Text).keys()
        methods = vars(tk.Pack).keys() | vars(tk.Grid).keys() | vars(tk.Place).keys()
        methods = methods.difference(text_meths)

        for name in methods:
            if name[0] != "_" and name not in ("config", "configure"):
                setattr(self, name, getattr(self.frame, name))

    def __str__(self) -> str:
        return str(self.frame)


def style_text_widget(widget: tk.Text) -> None:
    widget.configure(
        bg=TEXT_BG,
        fg=FG,
        insertbackground=ORANGE_BRIGHT,
        selectbackground=ORANGE_DIM,
        selectforeground=FG,
        relief=tk.FLAT,
        highlightthickness=1,
        highlightbackground=BORDER,
        highlightcolor=ORANGE_BRIGHT,
        font=("Consolas", 10),
    )
