#!/usr/bin/env python3
"""Windows MVP runner for the d2lut in-game overlay.

This is a pragmatic runner that wires the existing OverlayApp to:
- screen capture via ``mss`` (full primary monitor)
- a fixed tooltip rectangle (provided via CLI)
- a tiny topmost Tk window (or console output) for displaying current FG estimate

It is intentionally minimal and avoids memory reading / game injection.
"""

from __future__ import annotations

import argparse
import io
import queue
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image


def _parse_tooltip(s: str) -> tuple[int, int, int, int]:
    parts = [p.strip() for p in s.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("tooltip must be 'x,y,w,h'")
    try:
        x, y, w, h = (int(p) for p in parts)
    except ValueError as e:
        raise argparse.ArgumentTypeError("tooltip coordinates must be integers") from e
    if w <= 0 or h <= 0:
        raise argparse.ArgumentTypeError("tooltip width/height must be > 0")
    return x, y, w, h


@dataclass
class OverlayDisplayState:
    """Data rendered in the lightweight topmost overlay window."""
    title: str
    price_line: str
    meta_line: str
    inline_line: str
    color: str
    x: int
    y: int
    visible: bool = True
    refresh_status: str = ""  # LIVE/STALE/REFRESHING/ERROR badge


class MSSScreenCapture:
    """Full-screen screenshot provider using mss."""

    def __init__(self, monitor_index: int = 1):
        try:
            import mss  # type: ignore
        except ImportError as e:
            raise ImportError(
                "mss is required for Windows screen capture. Install with: pip install mss"
            ) from e

        self._mss_mod = mss
        self._sct = mss.mss()
        self.monitor_index = monitor_index
        self._lock = threading.Lock()

    def capture_png_bytes(self) -> bytes:
        with self._lock:
            monitor = self._sct.monitors[self.monitor_index]
            shot = self._sct.grab(monitor)
            img = Image.frombytes("RGB", shot.size, shot.rgb)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()


class TkTopmostOverlay:
    """Minimal topmost text window for displaying current price info."""

    def __init__(self, alpha: float = 0.88, font_size: int = 12):
        try:
            import tkinter as tk
        except ImportError as e:
            raise ImportError("tkinter is required for GUI overlay mode") from e

        self.tk = tk
        self.root = tk.Tk()
        self.root.title("d2lut-overlay")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-alpha", alpha)
        except Exception:
            pass

        self.root.configure(bg="#111111")
        self.title_var = tk.StringVar(value="d2lut")
        self.price_var = tk.StringVar(value="waiting...")
        self.meta_var = tk.StringVar(value="")
        self.inline_var = tk.StringVar(value="d2lut - waiting...")

        self.frame = tk.Frame(self.root, bg="#111111", bd=1, relief="solid", highlightthickness=0)
        self.frame.pack(fill="both", expand=True)
        self.inline_lbl = tk.Label(
            self.frame, textvariable=self.inline_var, fg="#a7f3d0", bg="#111111",
            font=("Consolas", font_size + 1, "bold"), anchor="w", padx=8, pady=6
        )
        self.title_lbl = tk.Label(
            self.frame, textvariable=self.title_var, fg="#e5e7eb", bg="#111111",
            font=("Consolas", max(10, font_size), "bold"), anchor="w", padx=8, pady=2
        )
        self.title_lbl.pack(fill="x")
        self.price_lbl = tk.Label(
            self.frame, textvariable=self.price_var, fg="#a7f3d0", bg="#111111",
            font=("Consolas", font_size + 2, "bold"), anchor="w", padx=8
        )
        self.price_lbl.pack(fill="x")
        self.meta_lbl = tk.Label(
            self.frame, textvariable=self.meta_var, fg="#cbd5e1", bg="#111111",
            font=("Consolas", max(9, font_size - 1)), anchor="w", padx=8, pady=2
        )
        self.meta_lbl.pack(fill="x")

        self.inline_lbl.pack_forget()
        self.root.geometry("340x82+20+20")
        self._visible = True
        self._compact = False

    def set_compact(self, compact: bool) -> None:
        self._compact = compact
        if compact:
            self.title_lbl.pack_forget()
            self.price_lbl.pack_forget()
            self.meta_lbl.pack_forget()
            self.inline_lbl.pack(fill="x")
            self.root.geometry("420x34+20+20")
        else:
            self.inline_lbl.pack_forget()
            self.title_lbl.pack(fill="x")
            self.price_lbl.pack(fill="x")
            self.meta_lbl.pack(fill="x")
            self.root.geometry("340x82+20+20")

    def update_state(self, state: OverlayDisplayState) -> None:
        if not state.visible:
            self.hide()
            return
        self.title_var.set(state.title)
        self.price_var.set(state.price_line)
        self.meta_var.set(state.meta_line)
        self.inline_var.set(state.inline_line)
        self.price_lbl.configure(fg=state.color)
        self.inline_lbl.configure(fg=state.color)
        if self._compact:
            self.root.geometry(f"420x34+{state.x}+{state.y}")
        else:
            self.root.geometry(f"340x82+{state.x}+{state.y}")
        if not self._visible:
            self.root.deiconify()
            self._visible = True

    def hide(self) -> None:
        self.root.withdraw()
        self._visible = False

    def loop(self, poll_cb, interval_ms: int = 100) -> None:
        def _tick():
            try:
                poll_cb()
            finally:
                self.root.after(interval_ms, _tick)
        self.root.after(interval_ms, _tick)
        self.root.mainloop()


def _color_for_bucket(bucket: str | None) -> str:
    return {
        "high": "#fca5a5",
        "medium": "#fde68a",
        "low": "#86efac",
        "no_data": "#93c5fd",
    }.get(bucket or "no_data", "#93c5fd")


class HotkeyController:
    """Optional global hotkeys via `keyboard` package (Windows)."""

    def __init__(self, toggle_cb, quit_cb, toggle_hotkey: str, quit_hotkey: str):
        self._toggle_cb = toggle_cb
        self._quit_cb = quit_cb
        self._toggle_hotkey = toggle_hotkey
        self._quit_hotkey = quit_hotkey
        self._keyboard = None
        self._registered = False

    def start(self) -> bool:
        try:
            import keyboard  # type: ignore
        except Exception:
            return False
        self._keyboard = keyboard
        keyboard.add_hotkey(self._toggle_hotkey, self._toggle_cb, suppress=False)
        keyboard.add_hotkey(self._quit_hotkey, self._quit_cb, suppress=False)
        self._registered = True
        return True

    def stop(self) -> None:
        if self._keyboard and self._registered:
            try:
                self._keyboard.clear_all_hotkeys()
            except Exception:
                pass
        self._registered = False


def main() -> int:
    parser = argparse.ArgumentParser(description="Run d2lut Windows overlay MVP (fixed tooltip rectangle)")
    parser.add_argument("--db", default="data/cache/d2lut.db", help="Path to d2lut SQLite database")
    parser.add_argument("--tooltip", required=True, type=_parse_tooltip, help="Tooltip rect as x,y,w,h (screen coords)")
    parser.add_argument("--config", default=None, help="Optional overlay JSON config path")
    parser.add_argument("--ocr-engine", choices=["easyocr", "pytesseract"], default=None, help="Override OCR engine")
    parser.add_argument("--monitor", type=int, default=1, help="mss monitor index (usually 1 for primary)")
    parser.add_argument("--console-only", action="store_true", help="Print price updates to console instead of Tk overlay window")
    parser.add_argument("--demo-image", default=None, help="Use a static image file instead of live screen capture")
    parser.add_argument("--font-size", type=int, default=12, help="Overlay font size (Tk mode)")
    parser.add_argument("--poll-ms", type=int, default=250, help="UI poll interval for render queue")
    parser.add_argument("--compact", action="store_true", help="Compact inline mode: 'Item - 5fg'")
    parser.add_argument(
        "--no-approx-prefix",
        action="store_true",
        help="Do not prefix estimated prices with '~' (compact mode becomes 'Item - 5fg')",
    )
    parser.add_argument(
        "--no-data-text",
        default="no data",
        help="Text to show when no price exists in compact mode (default: 'no data')",
    )
    parser.add_argument("--hide-no-data", action="store_true", help="Hide overlay when no price data is found")
    parser.add_argument("--label-x-offset", type=int, default=8, help="Horizontal offset from tooltip rectangle")
    parser.add_argument("--label-y-offset", type=int, default=0, help="Vertical offset from tooltip rectangle")
    parser.add_argument("--hotkey-toggle", default="f8", help="Global hotkey to pause/resume overlay (requires keyboard package)")
    parser.add_argument("--hotkey-quit", default="f10", help="Global hotkey to quit runner (requires keyboard package)")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: database not found: {db_path}", file=sys.stderr)
        return 2

    # Import late so script can print dependency guidance cleanly.
    try:
        from d2lut.overlay.config import load_config
        from d2lut.overlay.overlay_app import OverlayApp
        from d2lut.overlay.ocr_parser import TooltipCoords
        from d2lut.overlay.label_ux import format_compact_label
    except Exception as e:
        print(f"ERROR: failed to import d2lut overlay modules: {e}", file=sys.stderr)
        return 2

    # Load and optionally tweak config
    config = load_config(args.config)
    if args.ocr_engine:
        config.ocr.engine = args.ocr_engine
    # Faster MVP polling than default 1000ms
    config.overlay.update_interval_ms = min(config.overlay.update_interval_ms, 250)

    x, y, w, h = args.tooltip
    tooltip_coords = TooltipCoords(x=x, y=y, width=w, height=h)

    # Screenshot source
    if args.demo_image:
        img_path = Path(args.demo_image)
        if not img_path.exists():
            print(f"ERROR: demo image not found: {img_path}", file=sys.stderr)
            return 2
        img_bytes = img_path.read_bytes()

        def screenshot_cb() -> bytes:
            return img_bytes
    else:
        try:
            capture = MSSScreenCapture(monitor_index=args.monitor)
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            print("Install runtime deps on Windows: pip install mss pillow", file=sys.stderr)
            return 2

        screenshot_cb = capture.capture_png_bytes

    render_q: queue.Queue[OverlayDisplayState | None] = queue.Queue(maxsize=8)
    stop_event = threading.Event()
    paused_event = threading.Event()

    with OverlayApp(db_path=db_path, config=config) as app:
        app.set_screenshot_callback(screenshot_cb)

        def render_cb(_overlay_render: Any) -> None:
            details = app.get_hover_details()
            if details is None:
                return
            approx = "" if args.no_approx_prefix else "~"
            label_x = max(10, x + w + args.label_x_offset)
            label_y = max(10, y + args.label_y_offset)
            refresh_badge = app.state.refresh_status.value
            if details.has_data and details.median_price is not None:
                conf = details.confidence or "unknown"
                samples = details.sample_count or 0
                lo_hi = (
                    f"{details.price_range[0]:.0f}-{details.price_range[1]:.0f} fg"
                    if details.price_range else "n/a"
                )
                label = format_compact_label(
                    details.item_name,
                    details.median_price,
                    details.confidence,
                    stale=(refresh_badge == "STALE"),
                    approx_prefix=not args.no_approx_prefix,
                    no_data_text=args.no_data_text,
                )
                state = OverlayDisplayState(
                    title=details.item_name or "Unknown item",
                    price_line=f"{approx}{details.median_price:.0f} fg",
                    meta_line=f"{lo_hi} | {conf} | n={samples}",
                    inline_line=label.text,
                    color=_color_for_bucket(details.color),
                    x=label_x,
                    y=label_y,
                    refresh_status=refresh_badge,
                )
            else:
                item_name = details.item_name or "Unknown item"
                label = format_compact_label(
                    item_name,
                    None,
                    no_data_text=args.no_data_text,
                )
                state = OverlayDisplayState(
                    title=item_name,
                    price_line="No price data",
                    meta_line="Check manually / extend parser",
                    inline_line=label.text,
                    color=_color_for_bucket("no_data"),
                    x=label_x,
                    y=label_y,
                    visible=not args.hide_no_data,
                    refresh_status=refresh_badge,
                )
            try:
                render_q.put_nowait(state)
            except queue.Full:
                try:
                    render_q.get_nowait()
                except queue.Empty:
                    pass
                try:
                    render_q.put_nowait(state)
                except queue.Full:
                    pass

        app.set_render_callback(render_cb)
        app.start()
        app.on_hover_start(tooltip_coords)

        def _toggle_pause():
            if paused_event.is_set():
                paused_event.clear()
                app.resume()
                print("[d2lut] overlay resumed")
            else:
                paused_event.set()
                app.pause()
                print("[d2lut] overlay paused")

        def _quit():
            print("[d2lut] quit requested")
            stop_event.set()

        hotkeys = HotkeyController(
            toggle_cb=_toggle_pause,
            quit_cb=_quit,
            toggle_hotkey=args.hotkey_toggle,
            quit_hotkey=args.hotkey_quit,
        )
        hotkeys_enabled = hotkeys.start()
        if hotkeys_enabled:
            print(f"[d2lut] hotkeys: toggle={args.hotkey_toggle}, quit={args.hotkey_quit}")
        else:
            print("[d2lut] hotkeys unavailable (install `keyboard` for global hotkeys)")

        if args.console_only:
            print("d2lut Windows overlay MVP (console mode)")
            print(f"tooltip={x},{y},{w},{h} db={db_path}")
            print("Press Ctrl+C to stop")
            last: OverlayDisplayState | None = None
            try:
                while not stop_event.is_set():
                    try:
                        state = render_q.get(timeout=1.0)
                    except queue.Empty:
                        continue
                    if state and (last is None or state != last):
                        badge = f" [{state.refresh_status}]" if state.refresh_status else ""
                        if args.compact:
                            print(f"[{time.strftime('%H:%M:%S')}]{badge} {state.inline_line}")
                        else:
                            print(f"[{time.strftime('%H:%M:%S')}]{badge} {state.title} | {state.price_line} | {state.meta_line}")
                        last = state
            except KeyboardInterrupt:
                pass
        else:
            try:
                ui = TkTopmostOverlay(font_size=args.font_size)
            except Exception as e:
                print(f"ERROR: {e}", file=sys.stderr)
                print("Retry with --console-only (or install a Python build with tkinter)", file=sys.stderr)
                return 2

            ui.set_compact(args.compact)
            # Initial placeholder state
            ui.update_state(
                OverlayDisplayState(
                    title="d2lut overlay",
                    price_line="Watching tooltip...",
                    meta_line="Move tooltip into configured rectangle",
                    inline_line="d2lut - watching tooltip...",
                    color="#93c5fd",
                    x=max(10, x + w + 8),
                    y=max(10, y),
                )
            )

            def poll_queue() -> None:
                drained = False
                latest = None
                while True:
                    try:
                        latest = render_q.get_nowait()
                        drained = True
                    except queue.Empty:
                        break
                if drained and latest is not None:
                    ui.update_state(latest)

            try:
                def poll_queue_and_stop() -> None:
                    if stop_event.is_set():
                        try:
                            ui.root.destroy()
                        except Exception:
                            pass
                        return
                    poll_queue()
                ui.loop(poll_queue_and_stop, interval_ms=max(50, args.poll_ms))
            except KeyboardInterrupt:
                pass

        app.on_hover_end()
        app.stop()
        hotkeys.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
