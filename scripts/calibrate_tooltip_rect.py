#!/usr/bin/env python3
"""Interactive tooltip rectangle calibrator (Windows-friendly).

Usage:
  python scripts/calibrate_tooltip_rect.py

Click-drag over a visible D2R tooltip. The script prints:
  x,y,width,height

This is intended to feed ``scripts/run_overlay_windows_mvp.py --tooltip ...``.
"""

from __future__ import annotations

import io
import sys
from dataclasses import dataclass

from PIL import Image


@dataclass
class Rect:
    x: int
    y: int
    w: int
    h: int

    def normalize(self) -> "Rect":
        x2 = self.x + self.w
        y2 = self.y + self.h
        x1, x2 = sorted((self.x, x2))
        y1, y2 = sorted((self.y, y2))
        return Rect(x1, y1, x2 - x1, y2 - y1)

    def as_cli(self) -> str:
        r = self.normalize()
        return f"{r.x},{r.y},{r.w},{r.h}"


def _capture_screen_image():
    try:
        import mss  # type: ignore
    except ImportError as e:
        raise ImportError("mss is required. Install with: pip install mss") from e

    with mss.mss() as sct:
        mon = sct.monitors[1]
        shot = sct.grab(mon)
        return Image.frombytes("RGB", shot.size, shot.rgb)


def main() -> int:
    try:
        import tkinter as tk
    except ImportError as e:
        print("ERROR: tkinter is required for calibration UI", file=sys.stderr)
        return 2

    try:
        screen_img = _capture_screen_image()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    # Delay import to keep non-UI errors cleaner.
    from PIL import ImageTk

    width, height = screen_img.size
    root = tk.Tk()
    root.title("d2lut tooltip calibration")
    root.attributes("-topmost", True)
    root.attributes("-fullscreen", True)
    root.configure(bg="black")
    root.bind("<Escape>", lambda e: root.destroy())

    photo = ImageTk.PhotoImage(screen_img)
    canvas = tk.Canvas(root, width=width, height=height, highlightthickness=0, cursor="crosshair")
    canvas.pack(fill="both", expand=True)
    canvas.create_image(0, 0, anchor="nw", image=photo)

    overlay_text = canvas.create_text(
        20, 20, anchor="nw",
        text="Drag over D2R tooltip. Enter = print/exit, Esc = cancel",
        fill="#ffffff", font=("Consolas", 16, "bold")
    )
    rect_id = None
    start = {"x": 0, "y": 0}
    current = {"x": 0, "y": 0}
    selected: Rect | None = None

    def _refresh_text():
        nonlocal selected
        if selected:
            cli = selected.as_cli()
            canvas.itemconfig(overlay_text, text=f"Selected: {cli}  |  Enter=print, Esc=cancel")

    def on_press(event):
        nonlocal rect_id
        start["x"], start["y"] = event.x, event.y
        current["x"], current["y"] = event.x, event.y
        if rect_id is not None:
            canvas.delete(rect_id)
        rect_id = canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="#22c55e", width=2, dash=(4, 2)
        )

    def on_drag(event):
        nonlocal selected
        current["x"], current["y"] = event.x, event.y
        if rect_id is not None:
            canvas.coords(rect_id, start["x"], start["y"], current["x"], current["y"])
        selected = Rect(start["x"], start["y"], current["x"] - start["x"], current["y"] - start["y"]).normalize()
        _refresh_text()

    def on_release(event):
        nonlocal selected
        current["x"], current["y"] = event.x, event.y
        selected = Rect(start["x"], start["y"], current["x"] - start["x"], current["y"] - start["y"]).normalize()
        _refresh_text()

    def on_enter(_event):
        if selected is None or selected.w <= 2 or selected.h <= 2:
            print("No valid selection", file=sys.stderr)
            root.destroy()
            return
        cli = selected.as_cli()
        print(cli)
        root.clipboard_clear()
        root.clipboard_append(cli)
        root.update()
        root.destroy()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    root.bind("<Return>", on_enter)

    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

