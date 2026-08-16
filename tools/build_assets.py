#!/usr/bin/env python3
"""Build every SVG asset used by the profile README.

Everything is generated from this one file so the look stays consistent:

  assets/terminal-{light,dark}.svg   animated typing terminal (hero)
  assets/header-*-{light,dark}.svg   section headings
  assets/badges/*-{light,dark}.svg   link badges
  assets/cards/*-{light,dark}.svg    add-on / project grid tiles

Grid tiles inline the matching logo from assets/logos untouched - the logos own
their colours, everything else follows the GitHub brand palette below.

Poppins is embedded as a base64 WOFF2 *subset* inside each SVG. GitHub renders
README images through camo, which blocks external font requests, so a font only
shows up if it travels inside the file. Subsetting keeps each SVG small.

Usage:  python3 tools/build_assets.py
Deps:   pip install fonttools brotli
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser

from fontTools.ttLib import TTFont
from fontTools.subset import Subsetter, Options

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(ROOT, "assets", "fonts")

# --------------------------------------------------------------------------
# palette - neutral greys only, flat, no gradients anywhere
# --------------------------------------------------------------------------

# Straight from the GitHub UI neutrals (Primer). No hues: the only colour on
# the page comes from the add-on logos, which keep their own palette.
# The old accent keys (green/blue/mauve/...) still exist so callers keep
# working, but they all resolve to a grey step now.

LIGHT = {
    "page": "#ffffff",
    "chrome": "#f6f8fa",
    "body": "#ffffff",
    "border": "#d1d9e0",
    "text": "#1f2328",
    "dim": "#59636e",
    "soft": "#818b98",
    "card": "#ffffff",
    "card_border": "#d1d9e0",
    "card_border_op": "1",
    "badge_bg": "#f6f8fa",
    "badge_fg": "#1f2328",
}

DARK = {
    "page": "#0d1117",
    "chrome": "#161b22",
    "body": "#0d1117",
    "border": "#30363d",
    "text": "#e6edf3",
    "dim": "#9198a1",
    "soft": "#6e7681",
    "card": "#161b22",
    "card_border": "#30363d",
    "card_border_op": "1",
    "badge_bg": "#161b22",
    "badge_fg": "#e6edf3",
}

# legacy accent names -> grey steps, so nothing on the page shouts
for _pal in (LIGHT, DARK):
    _pal.update(
        green=_pal["text"],
        blue=_pal["dim"],
        mauve=_pal["text"],
        peach=_pal["dim"],
        teal=_pal["dim"],
        red=_pal["soft"],
        yellow=_pal["soft"],
    )

THEMES = {"light": LIGHT, "dark": DARK}

HEATMAP_LEVELS = {
    "light": ("#ebedf0", "#c6d1dc", "#9aa7b4", "#64748b", "#334155"),
    "dark": ("#161b22", "#29313a", "#3d4955", "#5d6b7a", "#8c9bab"),
}

# --------------------------------------------------------------------------
# shape language - rectangles with a small radius, never pills
# --------------------------------------------------------------------------

R_SM = 6.0     # chips
R_MD = 8.0     # badges, headers, logo plates
R_LG = 10.0    # cards
R_XL = 12.0    # hero terminal

# --------------------------------------------------------------------------
# font plumbing
# --------------------------------------------------------------------------

_FONT_CACHE: dict[int, TTFont] = {}


def _font(weight: int) -> TTFont:
    if weight not in _FONT_CACHE:
        path = os.path.join(FONT_DIR, f"poppins-{weight}.woff2")
        _FONT_CACHE[weight] = TTFont(path)
    return _FONT_CACHE[weight]


def text_width(s: str, size: float, weight: int = 400) -> float:
    """Advance width of `s` in px, from the real font metrics."""
    font = _font(weight)
    upem = font["head"].unitsPerEm
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]
    glyphs = font.getGlyphOrder()
    total = 0
    for ch in s:
        name = cmap.get(ord(ch))
        if name is None or name not in glyphs:
            name = cmap.get(ord("?"))
        total += hmtx[name][0]
    return total * size / upem


def font_face(weight: int, chars: str) -> str:
    """@font-face rule with a base64 WOFF2 subset covering `chars`."""
    path = os.path.join(FONT_DIR, f"poppins-{weight}.woff2")
    font = TTFont(path)
    opts = Options()
    opts.layout_features = ["kern", "liga", "calt"]
    opts.desubroutinize = True
    opts.notdef_outline = False
    sub = Subsetter(options=opts)
    sub.populate(text="".join(sorted(set(chars))) + " ")
    sub.subset(font)
    font.flavor = "woff2"
    buf = io.BytesIO()
    font.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return (
        "@font-face{font-family:'Poppins';font-style:normal;"
        f"font-weight:{weight};src:url(data:font/woff2;base64,{b64}) format('woff2');}}"
    )


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --------------------------------------------------------------------------
# GitHub contribution heatmap
# --------------------------------------------------------------------------

GITHUB_USERNAME = "thepeacemonk"


class ContributionParser(HTMLParser):
    """Read GitHub's public contribution-calendar cells without an API token."""

    def __init__(self) -> None:
        super().__init__()
        self.days: list[tuple[date, int, int]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "td":
            return
        data = dict(attrs)
        if not {"data-date", "data-level", "data-ix"} <= data.keys():
            return
        try:
            self.days.append(
                (date.fromisoformat(data["data-date"]), int(data["data-level"]), int(data["data-ix"]))
            )
        except (TypeError, ValueError):
            pass


def fetch_contributions(username: str = GITHUB_USERNAME) -> list[tuple[date, int, int]]:
    request = urllib.request.Request(
        f"https://github.com/users/{username}/contributions",
        headers={"User-Agent": "thepeacemonk-profile-heatmap"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        page = response.read().decode("utf-8")
    parser = ContributionParser()
    parser.feed(page)
    if len(parser.days) < 350:
        raise RuntimeError("GitHub did not return a complete contribution calendar")
    return parser.days


def heatmap_svg(theme: str, days: list[tuple[date, int, int]]) -> str:
    """A compact, calendar-aligned contribution grid."""
    c = THEMES[theme]
    levels = HEATMAP_LEVELS[theme]
    width, height = 760, 170
    left, top = 0, 52
    cell, gap = 10, 4
    first_by_month: dict[tuple[int, int], int] = {}
    cells: list[str] = []

    for day, level, week in days:
        x = left + week * (cell + gap)
        y = top + ((day.weekday() + 1) % 7) * (cell + gap)
        key = (day.year, day.month)
        first_by_month.setdefault(key, x)
        cells.append(
            f'<rect class="cell l{level}" x="{x}" y="{y}" width="{cell}" height="{cell}" '
            f'rx="2" aria-label="{day.isoformat()}: contribution level {level}"/>'
        )

    labels: list[str] = []
    last_x = -999
    for key, x in first_by_month.items():
        if x - last_x < 44:
            continue
        labels.append(f'<text x="{x}" y="34">{date(key[0], key[1], 1):%b}</text>')
        last_x = x

    style = (
        f"text{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;fill:{c['text']}}}"
        f".title{{font-size:16px;font-weight:600}}.month{{font-size:11px;fill:{c['dim']}}}"
        + "".join(f".l{i}{{fill:{colour}}}" for i, colour in enumerate(levels))
    )
    legend = "".join(
        f'<rect x="{left + 34 + i * 14}" y="151" width="10" height="10" rx="2" fill="{colour}"/>'
        for i, colour in enumerate(levels)
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="GitHub contribution heatmap">'
        f"<style>{style}</style>"
        f'<text class="title" x="{left}" y="18">Contribution activity</text>'
        f'<g class="month">{"".join(labels)}</g><g>{"".join(cells)}</g>'
        f'<text class="month" x="{left}" y="160">Less</text>{legend}'
        f'<text class="month" x="{left + 108}" y="160">More</text></svg>'
    )


def wrap(text: str, size: float, weight: int, max_w: float, max_lines: int = 2) -> list[str]:
    """Greedy word wrap using real font metrics; last line gets an ellipsis."""
    lines: list[str] = []
    cur = ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if not cur or text_width(trial, size, weight) <= max_w:
            cur = trial
            continue
        lines.append(cur)
        cur = word
        if len(lines) == max_lines:
            break
    if len(lines) < max_lines and cur:
        lines.append(cur)
    if len(lines) == max_lines and cur and cur not in lines[-1]:
        tail = lines[-1]
        while tail and text_width(tail + "...", size, weight) > max_w:
            tail = tail[:-1]
        lines[-1] = tail.rstrip() + "..."
    return lines


# --------------------------------------------------------------------------
# hero terminal
# --------------------------------------------------------------------------


@dataclass
class Line:
    command: str
    out: list[tuple[str, str]] = field(default_factory=list)  # (text, colour key)


PROMPT_USER = "peace"
PROMPT_HOST = "anki"

LINES = [
    Line(
        "whoami",
        [("Pre medical student, Anki add on developer & AI enthusiast", "mauve")],
    ),
    Line(
        "cat skills.txt",
        [("Python  ·  PyQt  ·  Anki Add ons  ·  Web apps  ·  AI", "teal")],
    ),
    Line(
        "cat status.txt",
        [("Brazil  ·  shipping add ons  ·  new web app in the oven", "peach")],
    ),
]

FS = 15.5           # font size
LH = 30.0           # line height
PAD_X = 26.0
CHROME_H = 44.0
TOP_PAD = 20.0
W = 760

CHAR_T = 0.055      # seconds per typed character
AFTER_CMD = 0.45    # pause between command and its output
AFTER_OUT = 0.30    # pause between output and next prompt
HOLD = 4.0          # hold the finished screen before looping
BLINK = 0.5         # cursor blink half-period


def terminal_svg(theme: str) -> str:
    c = THEMES[theme]
    prompt = f"{PROMPT_USER}@{PROMPT_HOST}:~$ "
    prompt_w = text_width(prompt, FS, 500)

    # ---- timeline -------------------------------------------------------
    # The loop starts on the *finished* screen and holds it, then clears and
    # types everything again. Two reasons: t=0 is what a renderer that ignores
    # SMIL inside <img> will show, and the card reads better when the first
    # thing you see is the content rather than an empty window.
    t_clear = HOLD
    t = t_clear + 0.35
    schedule = []  # (t_prompt, t_type_start, t_type_end, t_out)
    for ln in LINES:
        t_prompt = t
        t_type = t + 0.18
        t_end = t_type + len(ln.command) * CHAR_T
        t_out = t_end + AFTER_CMD
        schedule.append((t_prompt, t_type, t_end, t_out))
        t = t_out + AFTER_OUT
    t_final_prompt = t
    total = t_final_prompt + 0.9

    def kt(x: float) -> str:
        return f"{max(0.0, min(1.0, x / total)):.6f}"

    def appear(t_show: float) -> str:
        """Visible during the hold, wiped at t_clear, back at t_show."""
        return (
            f'<animate attributeName="opacity" dur="{total:.2f}s" repeatCount="indefinite" '
            f'calcMode="discrete" keyTimes="0;{kt(t_clear)};{kt(t_show)};1" '
            f'values="1;0;1;1"/>'
        )

    parts: list[str] = []
    y = CHROME_H + TOP_PAD + FS
    used_chars = set(prompt)
    cursor_h = FS * 1.15
    cursor_w = text_width("m", FS, 400) * 0.62

    for i, (ln, (t_prompt, t_type, t_end, t_out)) in enumerate(zip(LINES, schedule)):
        used_chars |= set(ln.command)
        for txt, _ in ln.out:
            used_chars |= set(txt)

        # prompt --------------------------------------------------------
        # NOTE: every element's *static* attributes describe the finished
        # screen, and the animation only overrides them while it runs. Some
        # renderers ignore SMIL inside <img>; there the card still reads as a
        # complete terminal instead of an empty box.
        parts.append(
            f'<g opacity="1">{appear(t_prompt)}'
            f'<text x="{PAD_X:.1f}" y="{y:.1f}" class="p">'
            f'<tspan class="u">{PROMPT_USER}</tspan>'
            f'<tspan class="at">@</tspan>'
            f'<tspan class="h">{PROMPT_HOST}</tspan>'
            f'<tspan class="at">:</tspan>'
            f'<tspan class="pa">~</tspan>'
            f'<tspan class="at">$</tspan></text></g>'
        )

        # typed command, revealed with a clip that grows one char at a time
        steps = len(ln.command)
        full_w = f"{text_width(ln.command, FS, 400):.2f}"
        keytimes = ["0", kt(t_clear), kt(t_type)]
        values = [full_w, "0", "0"]
        for k in range(1, steps + 1):
            keytimes.append(kt(t_type + k * CHAR_T))
            values.append(f"{text_width(ln.command[:k], FS, 400):.2f}")
        keytimes.append("1")
        values.append(full_w)
        cid = f"clip{i}"
        cmd_x = PAD_X + prompt_w
        parts.append(
            f'<clipPath id="{cid}"><rect x="{cmd_x:.1f}" y="{y - FS:.1f}" '
            f'width="{values[-1]}" height="{LH:.1f}">'
            f'<animate attributeName="width" dur="{total:.2f}s" repeatCount="indefinite" '
            f'calcMode="discrete" keyTimes="{";".join(keytimes)}" values="{";".join(values)}"/>'
            f"</rect></clipPath>"
        )
        parts.append(
            f'<g clip-path="url(#{cid})"><text x="{cmd_x:.1f}" y="{y:.1f}" class="c">'
            f"{esc(ln.command)}</text></g>"
        )

        # caret that walks along while the line is being typed
        ckeys = ["0", kt(t_type)]
        cvals = [f"{cmd_x:.1f}", f"{cmd_x:.1f}"]
        for k in range(1, steps + 1):
            ckeys.append(kt(t_type + k * CHAR_T))
            cvals.append(f"{cmd_x + text_width(ln.command[:k], FS, 400):.2f}")
        ckeys.append("1")
        cvals.append(cvals[-1])
        parts.append(
            f'<rect y="{y - FS + 2:.1f}" width="{cursor_w:.1f}" height="{cursor_h:.1f}" '
            f'rx="1.5" class="cur" opacity="0">'
            f'<animate attributeName="x" dur="{total:.2f}s" repeatCount="indefinite" '
            f'calcMode="discrete" keyTimes="{";".join(ckeys)}" values="{";".join(cvals)}"/>'
            f'<animate attributeName="opacity" dur="{total:.2f}s" repeatCount="indefinite" '
            f'calcMode="discrete" keyTimes="0;{kt(t_type)};{kt(t_end + 0.12)};1" '
            f'values="0;1;0;0"/></rect>'
        )

        # output --------------------------------------------------------
        y += LH
        segs = []
        for txt, colour in ln.out:
            segs.append(f'<tspan class="{colour}">{esc(txt)}</tspan>')
        parts.append(
            f'<g opacity="1">{appear(t_out)}'
            f'<text x="{PAD_X:.1f}" y="{y:.1f}" class="o">{"".join(segs)}</text></g>'
        )
        y += LH

    # trailing prompt with a blinking caret --------------------------------
    parts.append(
        f'<g opacity="1">{appear(t_final_prompt)}'
        f'<text x="{PAD_X:.1f}" y="{y:.1f}" class="p">'
        f'<tspan class="u">{PROMPT_USER}</tspan><tspan class="at">@</tspan>'
        f'<tspan class="h">{PROMPT_HOST}</tspan><tspan class="at">:</tspan>'
        f'<tspan class="pa">~</tspan><tspan class="at">$</tspan></text></g>'
    )
    blink_k, blink_v = ["0"], ["1"]
    on = False
    tb = BLINK
    while tb < t_clear:  # blinks through the hold
        blink_k.append(kt(tb))
        blink_v.append("1" if on else "0")
        on = not on
        tb += BLINK
    blink_k.append(kt(t_clear))  # gone while the screen retypes
    blink_v.append("0")
    blink_k.append(kt(t_final_prompt))
    blink_v.append("1")
    on = False
    tb = t_final_prompt + BLINK
    while tb < total:
        blink_k.append(kt(tb))
        blink_v.append("1" if on else "0")
        on = not on
        tb += BLINK
    blink_k.append("1")
    blink_v.append("1")
    parts.append(
        f'<rect x="{PAD_X + prompt_w:.1f}" y="{y - FS + 2:.1f}" width="{cursor_w:.1f}" '
        f'height="{cursor_h:.1f}" rx="1.5" class="cur" opacity="1">'
        f'<animate attributeName="opacity" dur="{total:.2f}s" repeatCount="indefinite" '
        f'calcMode="discrete" keyTimes="{";".join(blink_k)}" values="{";".join(blink_v)}"/></rect>'
    )

    height = int(y + TOP_PAD + 6)
    faces = font_face(400, "".join(used_chars)) + font_face(500, "".join(used_chars))
    style = (
        f"{faces}"
        "text{font-family:'Poppins',sans-serif;font-size:%.1fpx;dominant-baseline:auto}" % FS
        + f".p{{font-weight:500}}.c{{fill:{c['text']};font-weight:400}}"
        f".o{{font-weight:400}}"
        f".u{{fill:{c['green']}}}.h{{fill:{c['blue']}}}.at{{fill:{c['dim']}}}"
        f".pa{{fill:{c['yellow']}}}"
        f".mauve{{fill:{c['mauve']}}}.teal{{fill:{c['teal']}}}.peach{{fill:{c['peach']}}}"
        f".cur{{fill:{c['blue']}}}"
    )

    dots = ""
    for k in range(3):
        dots += (
            f'<circle cx="{28 + k * 20}" cy="{CHROME_H / 2:.0f}" r="5.5" fill="none" '
            f'stroke="{c["border"]}" stroke-width="1.5"/>'
        )
    title = f"{PROMPT_USER}@{PROMPT_HOST}: ~"
    title_face = font_face(500, title)
    title_w = text_width(title, 13, 500)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" '
        f'viewBox="0 0 {W} {height}" role="img" '
        f'aria-label="Terminal: whoami, cat skills.txt, cat status.txt">'
        f"<style>{style}{title_face}"
        f".t{{font-family:'Poppins',sans-serif;font-size:13px;font-weight:500;fill:{c['dim']}}}"
        f"</style>"
        f'<rect x="1" y="1" width="{W - 2}" height="{height - 2}" rx="{R_XL:.0f}" '
        f'fill="{c["body"]}" stroke="{c["border"]}" stroke-width="1.5"/>'
        f'<path d="M1 {R_XL + 1:.0f}a{R_XL:.0f} {R_XL:.0f} 0 0 1 {R_XL:.0f}-{R_XL:.0f}'
        f'h{W - 2 * R_XL - 2:.0f}a{R_XL:.0f} {R_XL:.0f} 0 0 1 {R_XL:.0f} {R_XL:.0f}'
        f'v{CHROME_H - R_XL - 1:.0f}H1z" fill="{c["chrome"]}"/>'
        f'<line x1="1" y1="{CHROME_H}" x2="{W - 1}" y2="{CHROME_H}" '
        f'stroke="{c["border"]}" stroke-width="1.5"/>'
        f"{dots}"
        f'<text x="{(W - title_w) / 2:.1f}" y="{CHROME_H / 2 + 4.5:.1f}" class="t">'
        f"{esc(title)}</text>"
        f"{''.join(parts)}"
        f"</svg>"
    )


# --------------------------------------------------------------------------
# section headers
# --------------------------------------------------------------------------

HEADERS = [
    ("about", "About me", "mauve"),
    ("addons", "Anki add ons", "green"),
    ("projects", "Other projects", "blue"),
    ("soon", "In the oven", "peach"),
    ("connect", "Get in touch", "red"),
]


def header_svg(theme: str, label: str, colour: str) -> str:
    """Neutral, rounded rectangular section label."""
    c = THEMES[theme]
    size = 19.0
    pad = 18.0
    w = text_width(label, size, 600)
    width = int(pad + w + pad)
    height = 38
    face = font_face(600, label)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{esc(label)}">'
        f"<style>{face}"
        f"text{{font-family:'Poppins',sans-serif;font-size:{size}px;font-weight:600;"
        f"fill:{c['text']}}}</style>"
        f'<rect x="0.75" y="0.75" width="{width - 1.5:.1f}" height="{height - 1.5:.1f}" '
        f'rx="{R_MD:.0f}" fill="{c["chrome"]}" stroke="{c["border"]}" stroke-width="1.5"/>'
        f'<text x="{pad:.1f}" y="{height / 2 + size * 0.35:.1f}">'
        f"{esc(label)}</text>"
        f"</svg>"
    )


# --------------------------------------------------------------------------
# badges
# --------------------------------------------------------------------------

# single-colour icon paths from simple-icons (24x24 viewBox), MIT/CC0.
ICONS = {
    "discord": "M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.198.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189Z",
    # stack of flashcards - drawn here, Anki has no simple-icons entry
    "anki": "M8.6 1.6h11.2a2.6 2.6 0 0 1 2.6 2.6v11.2a2.6 2.6 0 0 1-2.6 2.6H8.6A2.6 2.6 0 0 1 6 15.4V4.2a2.6 2.6 0 0 1 2.6-2.6Zm0 2a.6.6 0 0 0-.6.6v11.2c0 .33.27.6.6.6h11.2c.33 0 .6-.27.6-.6V4.2a.6.6 0 0 0-.6-.6H8.6Zm2 2.6h7.2v2h-7.2v-2Zm0 3.6h7.2v2h-7.2v-2ZM4 6.4v13a.6.6 0 0 0 .6.6h12.2v2H4.6A2.6 2.6 0 0 1 2 19.4v-13h2Z",
    "github": "M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12",
}


def badge_svg(theme: str, label: str, icon: str, colour: str) -> str:
    """Neutral, rounded rectangular link badge."""
    c = THEMES[theme]
    size = 14.0
    pad = 18.0
    icon_size = 16.0
    gap = 8.0
    w = text_width(label, size, 600)
    width = int(pad + icon_size + gap + w + pad)
    height = 34
    face = font_face(600, label)
    fg = c["text"]
    scale = icon_size / 24.0
    icon_y = (height - icon_size) / 2
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{esc(label)}">'
        f"<style>{face}"
        f"text{{font-family:'Poppins',sans-serif;font-size:{size}px;font-weight:600;fill:{fg}}}"
        f"</style>"
        f'<rect x="0.75" y="0.75" width="{width - 1.5:.1f}" height="{height - 1.5:.1f}" '
        f'rx="{R_SM:.0f}" fill="{c["badge_bg"]}" stroke="{c["border"]}" stroke-width="1.5"/>'
        f'<g transform="translate({pad:.1f} {icon_y:.1f}) scale({scale:.4f})">'
        f'<path d="{ICONS[icon]}" fill="{fg}"/></g>'
        f'<text x="{pad + icon_size + gap:.1f}" y="{height / 2 + size * 0.35:.1f}">'
        f"{esc(label)}</text></svg>"
    )


BADGES = [
    ("discord", "Join my Discord", "discord", "mauve"),
    ("ankiweb", "My add ons on AnkiWeb", "anki", "blue"),
    ("github", "All my repos", "github", "green"),
]


# --------------------------------------------------------------------------
# project cards - the light/dark grid
# --------------------------------------------------------------------------

LOGO_DIR = os.path.join(ROOT, "assets", "logos")

CARD_W = 300.0
CARD_PAD = 22.0
LOGO_W = 124.0
LOGO_BOTTOM = 104.0  # every logo sits on the same baseline, whatever its aspect

def logo_markup(filename: str, w: float, bottom: float, x: float) -> str:
    """Inline a logo file into a card. Logo colours are never touched."""
    import re

    path = os.path.join(LOGO_DIR, filename)

    if filename.lower().endswith((".jpg", ".jpeg", ".png")):
        with open(path, "rb") as fh:
            raw = fh.read()
        mime = "image/png" if filename.lower().endswith(".png") else "image/jpeg"
        b64 = base64.b64encode(raw).decode()
        # PNG dimensions are stored in the fixed IHDR header. JPEG remains on
        # the legacy logo canvas because it has no alpha and is no longer used
        # by current cards.
        if mime == "image/png" and raw.startswith(b"\x89PNG\r\n\x1a\n"):
            vb_w = float(int.from_bytes(raw[16:20], "big"))
            vb_h = float(int.from_bytes(raw[20:24], "big"))
        else:
            vb_w, vb_h = 203.0, 111.0
        h = w * vb_h / vb_w
        cid = f"clip-{os.path.splitext(filename)[0]}"
        return (
            f'<clipPath id="{cid}"><rect x="{x:.1f}" y="{bottom - h:.1f}" '
            f'width="{w:.1f}" height="{h:.1f}" rx="{R_MD:.0f}"/></clipPath>'
            f'<image x="{x:.1f}" y="{bottom - h:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'clip-path="url(#{cid})" href="data:{mime};base64,{b64}"/>'
        )

    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    open_tag = re.search(r"<svg[^>]*>", src).group(0)
    vb = re.search(r'viewBox="([\d.\s-]+)"', open_tag).group(1).split()
    vb_w, vb_h = float(vb[2]), float(vb[3])
    inner = src[src.index(open_tag) + len(open_tag): src.rindex("</svg>")]
    h = w * vb_h / vb_w
    # some logos use xlink:href internally; the nested <svg> needs the prefix bound
    return (
        f'<svg x="{x:.1f}" y="{bottom - h:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'viewBox="0 0 {vb_w:g} {vb_h:g}" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink">{inner}</svg>'
    )


def placeholder_markup(theme: str, w: float, bottom: float, x: float) -> str:
    c = THEMES[theme]
    h = w * 111.0 / 203.0
    return (
        f'<rect x="{x:.1f}" y="{bottom - h:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'rx="{R_MD:.0f}" fill="{c["chrome"]}" stroke="{c["border"]}" stroke-width="1.5"/>'
    )


@dataclass
class Card:
    slug: str
    name: str
    desc: str
    logo: str | None = None          # file in assets/logos, or None
    tag: str | None = None           # small chip next to the name
    tag_colour: str = "peach"
    repo: str | None = None           # GitHub repository name for star refreshes
    stars: int | None = None


def card_svg(theme: str, card: Card) -> str:
    """Rounded surface: logo, name, wrapped description, optional tag."""
    c = THEMES[theme]
    name_size, desc_size, tag_size = 17.0, 12.5, 10.5
    inner_w = CARD_W - CARD_PAD * 2

    has_media = card.logo is not None or card.slug in NEEDS_PLACEHOLDER
    top = LOGO_BOTTOM + 30 if has_media else CARD_PAD + name_size
    desc_lines = wrap(card.desc, desc_size, 400, inner_w, 2)
    height = top + 10 + 2 * 18 + CARD_PAD - 6  # always two description lines tall

    name_w = text_width(card.name, name_size, 600)
    display_tag = f"★ {card.stars}" if card.stars is not None else card.tag
    chars = card.name + card.desc + (display_tag or "")
    faces = font_face(600, chars) + font_face(400, chars)

    media = ""
    if card.logo:
        # Keep the original logo directly on the card. No white logo plates.
        media = logo_markup(card.logo, LOGO_W, LOGO_BOTTOM, CARD_PAD)
    elif card.slug in NEEDS_PLACEHOLDER:
        media = placeholder_markup(theme, LOGO_W, LOGO_BOTTOM, CARD_PAD)

    chip = ""
    if display_tag:
        tw = text_width(display_tag, tag_size, 600)
        cw, ch = tw + 18, 19.0
        cx = CARD_PAD + name_w + 9
        chip = (
            f'<rect x="{cx:.1f}" y="{top - name_size + 1.5:.1f}" width="{cw:.1f}" '
            f'height="{ch:.1f}" rx="{R_SM:.0f}" fill="{c["chrome"]}" '
            f'stroke="{c["border"]}" stroke-width="1"/>'
            f'<text x="{cx + 9:.1f}" y="{top - name_size + 1.5 + ch / 2 + tag_size * 0.35:.1f}" '
            f'class="chip">{esc(display_tag)}</text>'
        )

    desc = "".join(
        f'<text x="{CARD_PAD:.1f}" y="{top + 22 + i * 18:.1f}" class="d">{esc(line)}</text>'
        for i, line in enumerate(desc_lines)
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CARD_W:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {CARD_W:.0f} {height:.0f}" role="img" '
        f'aria-label="{esc(card.name)} - {esc(card.desc)}">'
        f"<style>{faces}"
        f"text{{font-family:'Poppins',sans-serif}}"
        f".n{{font-size:{name_size}px;font-weight:600;fill:{c['text']}}}"
        f".d{{font-size:{desc_size}px;font-weight:400;fill:{c['dim']}}}"
        f".chip{{font-size:{tag_size}px;font-weight:600;fill:{c['dim']}}}"
        f"</style>"
        f'<rect x="0.75" y="0.75" width="{CARD_W - 1.5:.1f}" height="{height - 1.5:.1f}" '
        f'rx="{R_LG:.0f}" fill="{c["card"]}" stroke="{c["card_border"]}" '
        f'stroke-opacity="{c["card_border_op"]}" stroke-width="1.5"/>'
        f"{media}"
        f'<text x="{CARD_PAD:.1f}" y="{top:.1f}" class="n">{esc(card.name)}</text>'
        f"{chip}{desc}"
        f"</svg>"
    )


NEEDS_PLACEHOLDER = {"webapp"}

ADDONS = [
    Card("onigiri", "Onigiri", "A modern, customizable replacement for the "
         "standard Anki interface", "onigiri.svg", "beta", "mauve"),
    Card("focumon", "Focumon", "Focumon inside Anki, made with Milton Ren", "focumon.svg"),
    Card("lofitown", "lofi.town", "Play lofi.town without ever leaving your reviews",
         "lofitown.svg"),
    Card("league", "League", "Climb the league table while you study", "league.svg",
         "paid", "yellow"),
    Card("senchado", "Senchado", "A tea timer for your study breaks", "senchado.svg"),
    Card("paper", "Paper", "Multiple cheat sheets, one shortcut away", "paper.svg"),
    Card("sticky", "Sticky", "Quick notes pinned to the main menu", "sticky.svg"),
    Card("power", "Power", "Your battery level, right on the main menu", "power.svg"),
    Card("hours", "Hours", "The current time, right on the main menu", "hours.svg"),
    Card("global", "Global", "Temperature and forecast via Open-Meteo", "global.svg"),
    Card("berry", "Berry", "See which Bluetooth devices are connected", "berry.svg"),
    Card("fixcaps", "First Letter Caps fix", "Temporary fix for the macOS caps lock bug",
         "fixcaps-transparent.png"),
]

SOON = [
    Card("astra", "Astra", "Anki add on, in development", "astra.svg"),
    Card("8bitdo", "8BitDo Micro", "Anki add on, in development", "8bitdo.svg"),
    Card("webapp", "A new web app", "In development, details soon"),
]

PROJECTS = [
    Card("stacked-library", "Stacked Library", "Spicetify extension that groups artists, "
         "albums and playlists in Spotify", None, "JavaScript", "yellow", "Stacked-Library", 0),
    Card("little-cats", "Little Cats Explain", "AI Studio experiment recreating "
         "“Explain Things with Lots of Tiny Cats”", None, "TypeScript", "blue", "Little-Cats-Explain", 1),
    Card("highlightr", "Highlightr Enhanced", "Fork of the Obsidian highlighting menu, "
         "with colour-coded highlighting", None, "TypeScript", "blue", "Highlightr-Enhanced", 1),
]


# --------------------------------------------------------------------------

def write(path: str, content: str) -> None:
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(content)
    print(f"{path}  {len(content) / 1024:.1f} KB")


def main() -> None:
    for theme in THEMES:
        write(f"assets/terminal-{theme}.svg", terminal_svg(theme))
        for slug, label, colour in HEADERS:
            write(f"assets/header-{slug}-{theme}.svg", header_svg(theme, label, colour))
        for slug, label, icon, colour in BADGES:
            write(f"assets/badges/{slug}-{theme}.svg", badge_svg(theme, label, icon, colour))
        for card in ADDONS + SOON + PROJECTS:
            write(f"assets/cards/{card.slug}-{theme}.svg", card_svg(theme, card))


def build_heatmap() -> None:
    days = fetch_contributions()
    for theme in THEMES:
        write(f"assets/heatmap-{theme}.svg", heatmap_svg(theme, days))


def fetch_project_stars() -> None:
    """Update the project cards from GitHub's public repository metadata."""
    for card in PROJECTS:
        if not card.repo:
            continue
        request = urllib.request.Request(
            f"https://api.github.com/repos/{GITHUB_USERNAME}/{card.repo}",
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "thepeacemonk-profile-stars",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            card.stars = int(json.load(response)["stargazers_count"])


def build_project_cards(refresh_stars: bool = False) -> None:
    if refresh_stars:
        fetch_project_stars()
    for theme in THEMES:
        for card in PROJECTS:
            write(f"assets/cards/{card.slug}-{theme}.svg", card_svg(theme, card))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--heatmap", action="store_true", help="refresh contribution heatmap assets")
    parser.add_argument("--dynamic", action="store_true", help="refresh heatmap and project star counts")
    args = parser.parse_args()
    if args.dynamic:
        build_heatmap()
        build_project_cards(refresh_stars=True)
    elif args.heatmap:
        build_heatmap()
    else:
        main()
