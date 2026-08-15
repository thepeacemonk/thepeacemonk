#!/usr/bin/env python3
"""Build every SVG asset used by the profile README.

Everything is generated from this one file so the look stays consistent:

  assets/terminal-{light,dark}.svg   animated typing terminal (hero)
  assets/header-*-{light,dark}.svg   section headings
  assets/badges/*-{light,dark}.svg   link badges

Poppins is embedded as a base64 WOFF2 *subset* inside each SVG. GitHub renders
README images through camo, which blocks external font requests, so a font only
shows up if it travels inside the file. Subsetting keeps each SVG small.

Usage:  python3 tools/build_assets.py
Deps:   pip install fonttools brotli
"""

from __future__ import annotations

import base64
import io
import os
from dataclasses import dataclass, field

from fontTools.ttLib import TTFont
from fontTools.subset import Subsetter, Options

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(ROOT, "assets", "fonts")

# --------------------------------------------------------------------------
# palette - flat colours only, no gradients anywhere
# --------------------------------------------------------------------------

LIGHT = {
    "page": "#eff1f5",
    "chrome": "#e6e9ef",
    "body": "#ffffff",
    "border": "#ccd0da",
    "text": "#4c4f69",
    "dim": "#6c6f85",
    "green": "#40a02b",
    "blue": "#1e66f5",
    "mauve": "#8839ef",
    "peach": "#fe640b",
    "teal": "#179299",
    "red": "#d20f39",
    "yellow": "#df8e1d",
    "badge_fg": "#ffffff",
}

DARK = {
    "page": "#1e1e2e",
    "chrome": "#181825",
    "body": "#1e1e2e",
    "border": "#313244",
    "text": "#cdd6f4",
    "dim": "#a6adc8",
    "green": "#a6e3a1",
    "blue": "#89b4fa",
    "mauve": "#cba6f7",
    "peach": "#fab387",
    "teal": "#94e2d5",
    "red": "#f38ba8",
    "yellow": "#f9e2af",
    "badge_fg": "#11111b",
}

THEMES = {"light": LIGHT, "dark": DARK}

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
        [("Pre-medical student, Anki add-on developer & AI enthusiast", "mauve")],
    ),
    Line(
        "cat skills.txt",
        [("Python  ·  PyQt  ·  Anki Add-ons  ·  Web Apps  ·  AI", "teal")],
    ),
    Line(
        "cat status.txt",
        [("Brazil  ·  shipping add-ons  ·  new web-app in the oven", "peach")],
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
    for k, colour in enumerate((c["red"], c["yellow"], c["green"])):
        dots += f'<circle cx="{28 + k * 20}" cy="{CHROME_H / 2:.0f}" r="6" fill="{colour}"/>'
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
        f'<rect x="1" y="1" width="{W - 2}" height="{height - 2}" rx="14" '
        f'fill="{c["body"]}" stroke="{c["border"]}" stroke-width="1.5"/>'
        f'<path d="M1 15a14 14 0 0 1 14-14h{W - 30}a14 14 0 0 1 14 14v{CHROME_H - 15}H1z" '
        f'fill="{c["chrome"]}"/>'
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
    ("addons", "Anki add-ons", "green"),
    ("projects", "Other projects", "blue"),
    ("soon", "In the oven", "peach"),
    ("snake", "The snake eats my commits", "teal"),
    ("connect", "Come say hi", "red"),
]


def header_svg(theme: str, label: str, colour: str) -> str:
    c = THEMES[theme]
    size = 21.0
    w = text_width(label, size, 600)
    bar_w = 5.0
    gap = 12.0
    width = int(bar_w + gap + w + 4)
    height = 40
    face = font_face(600, label)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{esc(label)}">'
        f"<style>{face}"
        f"text{{font-family:'Poppins',sans-serif;font-size:{size}px;font-weight:600;"
        f"fill:{c['text']}}}</style>"
        f'<rect x="0" y="8" width="{bar_w}" height="{height - 16}" rx="2.5" '
        f'fill="{c[colour]}"/>'
        f'<text x="{bar_w + gap}" y="{height / 2 + size * 0.36:.1f}">{esc(label)}</text>'
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
    """Flat pill badge - solid fill, no gradient."""
    c = THEMES[theme]
    size = 14.0
    pad = 14.0
    icon_size = 16.0
    gap = 8.0
    w = text_width(label, size, 600)
    width = int(pad + icon_size + gap + w + pad)
    height = 34
    face = font_face(600, label)
    fill = c[colour]
    fg = c["badge_fg"]
    scale = icon_size / 24.0
    icon_y = (height - icon_size) / 2
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{esc(label)}">'
        f"<style>{face}"
        f"text{{font-family:'Poppins',sans-serif;font-size:{size}px;font-weight:600;fill:{fg}}}"
        f"</style>"
        f'<rect width="{width}" height="{height}" rx="8" fill="{fill}"/>'
        f'<g transform="translate({pad:.1f} {icon_y:.1f}) scale({scale:.4f})">'
        f'<path d="{ICONS[icon]}" fill="{fg}"/></g>'
        f'<text x="{pad + icon_size + gap:.1f}" y="{height / 2 + size * 0.35:.1f}">'
        f"{esc(label)}</text></svg>"
    )


BADGES = [
    ("discord", "Join my Discord", "discord", "mauve"),
    ("ankiweb", "My add-ons on AnkiWeb", "anki", "blue"),
    ("github", "All my repos", "github", "green"),
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


if __name__ == "__main__":
    main()
