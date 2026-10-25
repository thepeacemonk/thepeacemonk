#!/usr/bin/env python3
"""Build the themed SVG gallery used by the profile README.

Everything is generated from this one file so the look stays consistent:

  assets/profile/intro-{light,dark}.svg   wordmark and subtitle
  assets/cards/*-{light,dark}.svg    add-on / project grid tiles

Grid tiles inline the matching logo from assets/logos untouched - the logos own
their colours, everything else follows the GitHub brand palette below.

Poppins is embedded as a base64 WOFF2 subset inside each SVG. GitHub renders
README images through camo, which blocks external font requests, so a font only
shows up if it travels inside the file. Subsetting keeps each SVG small.

Usage:  python3 tools/build_assets.py
Deps:   pip install fonttools brotli
"""

from __future__ import annotations

import base64
import io
import os
import re
import urllib.request
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser

from fontTools.ttLib import TTFont
from fontTools.subset import Subsetter, Options

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(ROOT, "assets", "fonts")

THEMES = {"light": {"text": "#1f2328", "dim": "#59636e"}, "dark": {"text": "#e6edf3", "dim": "#9198a1"}}
R_MD = 8.0  # Clipping of the existing raster logo.

HEATMAP_LEVELS = {
    "light": ("#ebedf0", "#c6d1dc", "#9aa7b4", "#64748b", "#334155"),
    "dark": ("#161b22", "#29313a", "#3d4955", "#5d6b7a", "#8c9bab"),
}

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


LOGO_DIR = os.path.join(ROOT, "assets", "logos")

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


# Bencho-inspired neutral component gallery. Logos retain their own colours.
PROFILE = {
    "light": {"ink": "#191919", "muted": "#626262", "stage": "#f1f1f1", "paper": "#ffffff", "line": "#dedede"},
    "dark": {"ink": "#ededed", "muted": "#a8a8a8", "stage": "#1c2026", "paper": "#292e35", "line": "#41464d"},
}


def intro_svg(theme: str, compact: bool = False) -> str:
    """A quiet wordmark and subtitle, with dedicated compact typography."""
    c = PROFILE[theme]
    width, height = (360, 140) if compact else (808, 164)
    words = "peaceAnki add-ons & small experiments."
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        'role="img" aria-label="peace — Anki add-ons and small experiments">'
        f'<style>{font_face(500, words)}{font_face(400, words)}'
        f'text{{font-family:Poppins,sans-serif;fill:{c["ink"]}}}'
        '</style>'
        f'<text x="2" y="{75 if compact else 85}" font-size="{46 if compact else 54}" font-weight="500" letter-spacing="-1.6">peace</text>'
        f'<text x="4" y="{108 if compact else 119}" font-size="{13.5 if compact else 17}" fill="{c["muted"]}" style="fill:{c["muted"]}">'
        'Anki add-ons &amp; small experiments.</text>'
        '</svg>'
    )


def project_element(slug: str, c: dict) -> str:
    """Static UI fragments illustrate the supplied project's purpose."""
    ink, muted, paper, line = (c[k] for k in ("ink", "muted", "paper", "line"))
    if slug == "stacked-library":
        rows = []
        for i, (width, opacity) in enumerate(((146, .35), (158, .6), (170, 1))):
            x, y = (260 - width) / 2, 27 + i * 19
            rows.append(f'<rect x="{x}" y="{y}" width="{width}" height="43" rx="12" fill="{paper}" opacity="{opacity}"/>')
        rows.append(f'<circle cx="65" cy="86" r="11" fill="{ink}"/><circle cx="65" cy="86" r="3" fill="{paper}"/>')
        rows.append(f'<path d="M86 81h80m-80 10h52" stroke="{muted}" stroke-width="3" stroke-linecap="round"/>')
        return "".join(rows)
    if slug == "little-cats":
        return (f'<rect x="43" y="34" width="174" height="68" rx="20" fill="{paper}"/>'
                f'<path d="m65 102-5 9 24-9" fill="{paper}"/>'
                f'<text x="130" y="63" text-anchor="middle" font-size="12" fill="{ink}">explain simply.</text>'
                f'<circle cx="120" cy="83" r="2.3" fill="{muted}"/><circle cx="130" cy="83" r="2.3" fill="{muted}"/>'
                f'<circle cx="140" cy="83" r="2.3" fill="{muted}"/>')
    if slug == "highlightr":
        return (f'<rect x="46" y="27" width="168" height="84" rx="14" fill="{paper}"/>'
                f'<rect x="62" y="45" width="106" height="18" rx="4" fill="#e9cc73"/>'
                '<text x="68" y="58" font-size="10" fill="#28241a">keep this thought.</text>'
                f'<path d="M64 78h130m-130 14h88" stroke="{muted}" stroke-width="3" stroke-linecap="round"/>')
    # Three overlapping application windows, each with a distinct UI fragment.
    return (
        f'<g transform="rotate(-8 103 64)">'
        f'<rect x="47" y="25" width="112" height="78" rx="11" fill="{paper}" stroke="{line}"/>'
        f'<path d="M47 44h112" stroke="{line}"/>'
        f'<path d="M61 36h30" stroke="{muted}" stroke-width="2" stroke-linecap="round"/>'
        f'<path d="M63 82V69m12 13V58m12 24V64" stroke="{muted}" stroke-width="6" stroke-linecap="round"/>'
        '</g>'
        f'<g transform="rotate(-1 132 67)">'
        f'<rect x="76" y="28" width="112" height="78" rx="11" fill="{paper}" stroke="{line}"/>'
        f'<path d="M76 47h112" stroke="{line}"/>'
        f'<path d="M90 39h31m-31 23h62m-62 13h44m-44 13h52" stroke="{muted}" stroke-width="2" stroke-linecap="round"/>'
        '</g>'
        f'<g transform="rotate(7 160 74)">'
        f'<rect x="104" y="35" width="112" height="78" rx="11" fill="{paper}" stroke="{line}"/>'
        f'<path d="M104 54h112m-87 0v59" stroke="{line}"/>'
        f'<path d="M117 46h29" stroke="{muted}" stroke-width="2" stroke-linecap="round"/>'
        f'<rect x="140" y="65" width="22" height="19" rx="4" fill="{muted}" opacity=".28"/>'
        f'<rect x="171" y="65" width="31" height="5" rx="2.5" fill="{muted}" opacity=".65"/>'
        f'<path d="M171 79h24m-55 17h62" stroke="{muted}" stroke-width="2" stroke-linecap="round"/>'
        '</g>'
    )


def card_svg(theme: str, card: Card) -> str:
    """A soft preview stage with its title and description on the page ground."""
    c = PROFILE[theme]
    width, height = 260, 218
    size = 11.5
    lines = wrap(card.desc, size, 400, 248, 3)
    words = card.name + card.desc + (card.tag or "") + "explain simply.keep this thought."
    faces = font_face(400, words) + font_face(500, words)
    if card.logo:
        # Constrain both dimensions without ever stretching the original artwork.
        if card.logo.endswith(".svg"):
            src = open(os.path.join(LOGO_DIR, card.logo), encoding="utf-8").read()
            view = re.search(r'viewBox="([\d.\s-]+)"', src).group(1).split()
            ratio = float(view[2]) / float(view[3])
        else:
            with open(os.path.join(LOGO_DIR, card.logo), "rb") as fh:
                raw = fh.read(24)
            ratio = int.from_bytes(raw[16:20], "big") / int.from_bytes(raw[20:24], "big")
        w = min(104, 76 * ratio)
        h = w / ratio
        media = logo_markup(card.logo, w, (136 + h) / 2, (width - w) / 2)
    else:
        media = project_element(card.slug, c)
    tag = ""
    if card.tag == "paid":
        tw = text_width(card.tag, 9, 500)
        tag = (f'<rect x="{244 - tw - 18:.1f}" y="12" width="{tw + 18:.1f}" height="21" rx="10.5" fill="{c["paper"]}"/>'
               f'<text x="{244 - tw - 9:.1f}" y="26" font-size="9" fill="{c["muted"]}" font-weight="500">{card.tag}</text>')
    desc = "".join(f'<text x="4" y="{183 + i * 15}" font-size="{size}" fill="{c["muted"]}">{esc(line)}</text>' for i, line in enumerate(lines))
    # Only published entries have an outward-link mark. Development items have none.
    arrow = "" if card in SOON else (f'<path d="M240 154h8v8m0-8-9 9" fill="none" stroke="{c["muted"]}" '
                                     'stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            f'role="img" aria-label="{esc(card.name)} — {esc(card.desc)}">'
            f'<style>{faces}text{{font-family:Poppins,sans-serif}}</style>'
            f'<rect width="260" height="136" rx="20" fill="{c["stage"]}"/>{media}{tag}'
            f'<text x="4" y="163" font-size="14" font-weight="500" fill="{c["ink"]}">{esc(card.name)}</text>'
            f'{arrow}{desc}</svg>')


ADDONS = [
    Card("onigiri", "Onigiri", "A modern, customizable replacement for the "
         "standard Anki interface", "onigiri.svg"),
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
    Card("webapp", "New apps", "In development, details soon"),
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
        write(f"assets/profile/intro-{theme}.svg", intro_svg(theme))
        write(f"assets/profile/intro-compact-{theme}.svg", intro_svg(theme, compact=True))
        for card in ADDONS + SOON + PROJECTS:
            write(f"assets/cards/{card.slug}-{theme}.svg", card_svg(theme, card))


def build_heatmap() -> None:
    days = fetch_contributions()
    for theme in THEMES:
        write(f"assets/heatmap-{theme}.svg", heatmap_svg(theme, days))


def build_project_cards() -> None:
    for theme in THEMES:
        for card in PROJECTS:
            write(f"assets/cards/{card.slug}-{theme}.svg", card_svg(theme, card))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--heatmap", action="store_true", help="refresh contribution heatmap assets")
    parser.add_argument("--dynamic", action="store_true", help="refresh contribution heatmap and project cards")
    args = parser.parse_args()
    if args.dynamic:
        build_heatmap()
        build_project_cards()
    elif args.heatmap:
        build_heatmap()
    else:
        main()
