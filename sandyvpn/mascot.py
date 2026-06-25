"""Ginger cat mascot drawn on a tkinter canvas."""

from __future__ import annotations

import math
import random
import tkinter as tk
from datetime import datetime

# One pun is chosen at random each time the app launches.
CONNECTED_PUNS: tuple[str, ...] = (
    "Purrfect!",
    "Claw-some link!",
    "Meow's connected!",
    "Pawsitively on!",
    "Fur-real secure!",
    "Tail-ored tunnel!",
    "Whiskers synced!",
    "Cat-alyst online!",
    "Purr protocol on!",
    "Feline fine!",
    "No cat-astrophe!",
    "Tabby tunnel up!",
    "Paw-some ping!",
    "Meow-tunnel live!",
    "Fur-midable link!",
    "Purr-sistant VPN!",
    "Mew-nited nets!",
    "Orange you online?",
    "Ginger snap link!",
    "Nine lives, one VPN!",
    "Scratch that lag!",
    "Purr-imeter sealed!",
    "Cat-ch the signal!",
    "Litter-ally secure!",
    "Meow-mentum gained!",
    "Pounce on packets!",
    "Fur-st class tunnel!",
    "Hiss-terically fast!",
    "Claw-ver routing!",
    "Tunnel of treats!",
    "Lap-top secured!",
    "Kitty tunnel go!",
    "Sandypaws online!",
    "Paws and reflect!",
    "You've got cat-mail!",
)

CAT_WIDTH = 102
CAT_HEIGHT = 110


class GingerCatMascot:
    """Chibi ginger cat illustration drawn on the top banner canvas."""

    GINGER = "#e8892b"
    GINGER_DARK = "#c46f1a"
    GINGER_LIGHT = "#f8c878"
    BELLY = "#ffe8c8"
    EAR_INNER = "#ffb8b0"
    EYE = "#5c3d28"
    EYE_SHINE = "#ffffff"
    BLUSH = "#ff9aaa"
    NOSE = "#ff8fa8"
    WHISKER = "#e8d8c8"
    OUTLINE = "#9a6b3a"
    TAG = "mascot"

    def __init__(self) -> None:
        self._connected_pun = random.choice(CONNECTED_PUNS)
        self._connected = False

    def set_mood(self, connected: bool) -> None:
        self._connected = connected

    def draw(self, canvas: tk.Canvas, right_x: int, top_y: int) -> None:
        ox = right_x - CAT_WIDTH
        oy = top_y
        self._draw_cat(canvas, ox, oy, awake=self._connected)
        self._draw_speech(canvas, ox, oy)

    def _draw_spiral_tail(self, canvas: tk.Canvas, ox: int, oy: int, tag: str) -> None:
        """Thin spiral tail rooted low on the body; body is drawn on top of the root."""
        round_cap = {"capstyle": tk.ROUND, "joinstyle": tk.ROUND}
        ax = ox + 36
        ay = oy + 90
        tail: list[float] = [ax, ay]
        for i in range(1, 21):
            t = i / 20
            angle = math.radians(205 + t * 400)
            radius = 1.2 + t * 8.5
            x = ax + radius * math.cos(angle)
            y = ay + radius * math.sin(angle) * 0.42
            tail.extend([x, min(y, oy + 93.5)])

        for color, width in ((self.OUTLINE, 6), (self.GINGER_DARK, 4), (self.GINGER, 2)):
            canvas.create_line(
                *tail, fill=color, width=width, smooth=True, tags=tag, **round_cap,
            )

    def _draw_cat(self, canvas: tk.Canvas, ox: int, oy: int, *, awake: bool) -> None:
        tag = self.TAG

        self._draw_spiral_tail(canvas, ox, oy, tag)

        # Small sitting body tucked under the head.
        canvas.create_oval(
            ox + 34, oy + 68, ox + 68, oy + 92,
            fill=self.GINGER, outline=self.OUTLINE, width=2, tags=tag,
        )
        canvas.create_oval(
            ox + 42, oy + 74, ox + 60, oy + 88,
            fill=self.BELLY, outline="", tags=tag,
        )

        # Big round head (covers the top of the body).
        canvas.create_oval(
            ox + 22, oy + 22, ox + 80, oy + 76,
            fill=self.GINGER, outline=self.OUTLINE, width=2, tags=tag,
        )

        # Ears.
        for tip_x, base_l, base_r, base_y in ((34, 26, 40, 30), (62, 62, 76, 30)):
            canvas.create_polygon(
                ox + tip_x, oy + 16, ox + base_l, oy + base_y, ox + base_r, oy + base_y,
                fill=self.GINGER_DARK, outline=self.OUTLINE, width=1, tags=tag,
            )
            canvas.create_polygon(
                ox + tip_x, oy + 20, ox + base_l + 3, oy + base_y - 2, ox + base_r - 3, oy + base_y - 2,
                fill=self.EAR_INNER, outline="", tags=tag,
            )

        # Forehead tabby mark.
        canvas.create_line(
            ox + 44, oy + 30, ox + 51, oy + 38, ox + 58, oy + 30,
            fill=self.GINGER_DARK, width=2, smooth=True, tags=tag,
        )

        # Cheek blush.
        for bx in (28, 64):
            canvas.create_oval(
                ox + bx, oy + 52, ox + bx + 12, oy + 60,
                fill=self.BLUSH, outline="", tags=tag,
            )

        if awake:
            self._draw_awake_face(canvas, ox, oy, tag)
        else:
            self._draw_sleep_face(canvas, ox, oy, tag)

        # Two front paws at the bottom.
        for px in (38, 54):
            canvas.create_oval(
                ox + px, oy + 84, ox + px + 12, oy + 96,
                fill=self.GINGER_LIGHT, outline=self.OUTLINE, width=1, tags=tag,
            )

        # Whiskers.
        for y_off in (-2, 4, 10):
            canvas.create_line(
                ox + 26, oy + 54 + y_off, ox + 38, oy + 54 + y_off,
                fill=self.WHISKER, width=1, tags=tag,
            )
            canvas.create_line(
                ox + 76, oy + 54 + y_off, ox + 64, oy + 54 + y_off,
                fill=self.WHISKER, width=1, tags=tag,
            )

        if not awake:
            self._draw_sleep_zzzs(canvas, ox, oy)

    def _draw_awake_face(self, canvas: tk.Canvas, ox: int, oy: int, tag: str) -> None:
        for cx in (38, 64):
            canvas.create_oval(
                ox + cx - 8, oy + 42, ox + cx + 8, oy + 56,
                fill=self.EYE, outline=self.OUTLINE, width=1, tags=tag,
            )
            canvas.create_oval(
                ox + cx - 5, oy + 44, ox + cx + 1, oy + 50,
                fill=self.EYE_SHINE, outline="", tags=tag,
            )

        canvas.create_polygon(
            ox + 51, oy + 56, ox + 55, oy + 60, ox + 47, oy + 60,
            fill=self.NOSE, outline=self.OUTLINE, width=1, tags=tag,
        )
        canvas.create_arc(
            ox + 45, oy + 58, ox + 57, oy + 68,
            start=200, extent=140, style=tk.ARC,
            outline=self.OUTLINE, width=1, tags=tag,
        )

    def _draw_sleep_face(self, canvas: tk.Canvas, ox: int, oy: int, tag: str) -> None:
        for cx in (38, 64):
            canvas.create_arc(
                ox + cx - 7, oy + 46, ox + cx + 7, oy + 54,
                start=0, extent=180, style=tk.ARC,
                outline=self.OUTLINE, width=2, tags=tag,
            )

        canvas.create_oval(
            ox + 49, oy + 58, ox + 53, oy + 62,
            fill=self.NOSE, outline=self.OUTLINE, width=1, tags=tag,
        )
        canvas.create_arc(
            ox + 47, oy + 62, ox + 55, oy + 68,
            start=10, extent=160, style=tk.ARC,
            outline=self.OUTLINE, width=1, tags=tag,
        )

    def _draw_letter_z(
        self,
        canvas: tk.Canvas,
        x: int,
        y: int,
        size: int,
        color: str,
        *,
        width: int = 2,
    ) -> None:
        tag = self.TAG
        canvas.create_line(x, y, x + size, y, fill=color, width=width, tags=tag)
        canvas.create_line(x + size, y, x, y + size, fill=color, width=width, tags=tag)
        canvas.create_line(x, y + size, x + size, y + size, fill=color, width=width, tags=tag)

    def _draw_sleep_zzzs(self, canvas: tk.Canvas, ox: int, oy: int) -> None:
        """Small Z's drifting up over the forehead, clear of the speech bubble."""
        self._draw_letter_z(canvas, ox + 64, oy + 14, 3, "#7a8a9e", width=1)
        self._draw_letter_z(canvas, ox + 70, oy + 8, 4, "#95a5b8", width=1)
        self._draw_letter_z(canvas, ox + 76, oy + 2, 5, "#b0c0d4", width=1)

    def _draw_speech(self, canvas: tk.Canvas, ox: int, oy: int) -> None:
        if self._connected:
            message = self._connected_pun
            color = "#7fd67f"
        else:
            day = datetime.now().strftime("%A")
            message = "I love Fridays" if day == "Friday" else f"I hate {day}s"
            color = "#ffaa55"
        canvas.create_text(
            ox + 30,
            oy + 10,
            text=message,
            fill=color,
            font=("Segoe UI", 5, "italic"),
            width=96,
            anchor=tk.N,
            justify=tk.CENTER,
            tags=self.TAG,
        )
