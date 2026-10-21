"""Colourful terminal rendering with plain ANSI escapes - no third-party packages."""

from __future__ import annotations

import os
import re
import sys
from datetime import date

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
ITALIC = "\x1b[3m"
STRIKE = "\x1b[9m"

RED = "\x1b[31m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
BLUE = "\x1b[34m"
MAGENTA = "\x1b[35m"
CYAN = "\x1b[36m"
GREY = "\x1b[90m"

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
WIDTH = 66

_PRIORITY_STYLE = {
    "HIGH": (RED, "H"),
    "MEDIUM": (YELLOW, "M"),
    "LOW": (GREY, "L"),
}


def supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return sys.stdout.isatty()


USE_COLOR = supports_color()


def _force_utf8() -> None:
    """Python writes redirected output in the ANSI codepage, which cannot encode box glyphs."""
    try:
        if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError):
        pass


_force_utf8()

# Consoles that still cannot take UTF-8 get an ASCII frame instead of a crash.
try:
    "╭╮╰╯─│✔○█░".encode(sys.stdout.encoding)
    BOX = {"tl": "╭", "tr": "╮", "bl": "╰", "br": "╯", "h": "─", "v": "│"}
    ICON_DONE, ICON_OPEN, FULL, EMPTY = "✔", "○", "█", "░"
    ELLIPSIS = "…"
except (UnicodeEncodeError, TypeError):
    BOX = {"tl": "+", "tr": "+", "bl": "+", "br": "+", "h": "-", "v": "|"}
    ICON_DONE, ICON_OPEN, FULL, EMPTY = "x", "*", "#", "."
    ELLIPSIS = "~"


def paint(text: str, *codes: str) -> str:
    if not USE_COLOR or not codes:
        return text
    return "".join(codes) + text + RESET


def visible_len(text: str) -> int:
    return len(_ANSI_RE.sub("", text))


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - visible_len(text))


def clip(text: str, width: int) -> str:
    """Keep rows inside the frame, so the right border stays aligned."""
    return text if len(text) <= width else text[: width - 1] + ELLIPSIS


def due_label(due: date, today: date) -> tuple[str, str]:
    days = (due - today).days
    if days < 0:
        return f"OVERDUE {-days}d", RED
    if days == 0:
        return "DUE TODAY", YELLOW
    if days == 1:
        return "DUE TOMORROW", YELLOW
    return f"due in {days}d", GREY


def progress_bar(done: int, total: int, width: int = 26) -> str:
    if total == 0:
        return paint(EMPTY * width + " no tasks yet", GREY)
    filled = round(width * done / total)
    ratio = done / total
    colour = GREEN if ratio == 1 else CYAN if ratio >= 0.5 else YELLOW
    return (
        paint(FULL * filled + EMPTY * (width - filled), colour)
        + paint(f" {int(ratio * 100)}%", BOLD, colour)
    )


def panel(title: str, lines: list[str]) -> str:
    inner = WIDTH - 2
    edge = paint(BOX["v"], BLUE)
    top = paint(BOX["tl"] + (" " + title + " ").ljust(inner, BOX["h"]) + BOX["tr"], BLUE)
    rows = [edge + _pad(line, inner) + edge for line in lines]
    bottom = paint(BOX["bl"] + BOX["h"] * inner + BOX["br"], BLUE)
    return "\n".join([top] + rows + [bottom])


def banner(total: int, done: int, filter_label: str = "", today: date | None = None) -> list[str]:
    date_text = paint(f"  {today.isoformat()}  ·  ", GREY) if today else ""
    lines = [
        "  "
        + date_text
        + paint(f"{total} total", BOLD)
        + paint(f"  ·  {total - done} open", CYAN)
        + paint(f"  ·  {done} done", GREEN),
        "  " + progress_bar(done, total),
    ]
    if filter_label:
        lines.append(paint(f"  showing: {filter_label}", MAGENTA, ITALIC))
    return lines


def task_row(index: int, task, today: date) -> list[str]:
    """Render one task as one or two frame lines (notes get their own line)."""
    number = paint(f"{index:>3}", GREY)
    if task.completed:
        return [f"  {number}  {paint(ICON_DONE, GREEN, BOLD)}  {paint(clip(task.description, 52), STRIKE, GREY)}"]

    icon = paint(ICON_OPEN, CYAN, BOLD)
    colour, letter = _PRIORITY_STYLE.get(task.priority.name, (GREY, "?"))
    priority = paint(f"[{letter}]", colour)
    if task.due:
        label, due_colour = due_label(task.due, today)
        due_cell = paint(label.ljust(13), due_colour)
    else:
        due_cell = ""
    lines = [
        f"  {number}  {icon}  {_pad(paint(clip(task.description, 32), BOLD), 32)}"
        f"  {priority}  {due_cell}"
    ]
    if task.notes:
        lines.append("        " + paint(clip(task.notes, 54), ITALIC, GREY))
    return lines


def message(text: str, flavour: str = "ok") -> str:
    colours = {"ok": GREEN, "warn": YELLOW, "error": RED, "info": CYAN}
    icons = {"ok": " +", "warn": " !", "error": " x", "info": " >"}
    return paint(clip(f"{icons[flavour]} {text}", WIDTH - 4), colours[flavour])


MENU_ITEMS = [
    ("1", "list"),
    ("2", "add"),
    ("3", "done / undone"),
    ("4", "edit"),
    ("5", "remove"),
    ("6", "filter"),
    ("7", "search"),
    ("8", "clear done"),
    ("9", "stats"),
    ("0", "quit"),
]


def menu() -> str:
    cells = [f" {key}  {label}" for key, label in MENU_ITEMS]
    cells += [""] * (-len(cells) % 3)
    column_width = max(len(cell) for cell in cells) + 2
    lines = []
    for row_index in range(0, len(cells), 3):
        parts = []
        for cell in cells[row_index : row_index + 3]:
            padded = cell.ljust(column_width)
            if not cell.strip():
                parts.append(padded)
            else:
                parts.append(
                    paint(padded[:4], BOLD, YELLOW) + paint(padded[4:], GREY)
                )
        lines.append("  " + "".join(parts).rstrip())
    return "\n".join(lines)


def legend() -> str:
    return (
        "  "
        + paint(f"{ICON_OPEN} open", CYAN)
        + paint("   " + ICON_DONE + " done", GREEN)
        + paint("   [H]", RED)
        + paint("[M]", YELLOW)
        + paint("[L]", GREY)
        + paint(" priority", GREY)
    )
