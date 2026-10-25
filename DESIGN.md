---
name: peace profile README
description: A quiet, neutral component gallery for Anki add-ons and small experiments.
colors:
  ink-light: "#191919"
  muted-light: "#626262"
  stage-light: "#f1f1f1"
  paper-light: "#ffffff"
  line-light: "#dedede"
  ink-dark: "#ededed"
  muted-dark: "#a8a8a8"
  stage-dark: "#1c2026"
  paper-dark: "#292e35"
  line-dark: "#41464d"
typography:
  display:
    fontFamily: "Poppins, sans-serif"
    fontSize: "54px"
    fontWeight: 500
    letterSpacing: "-1.6px"
  display-compact:
    fontFamily: "Poppins, sans-serif"
    fontSize: "46px"
    fontWeight: 500
    letterSpacing: "-1.6px"
  subtitle:
    fontFamily: "Poppins, sans-serif"
    fontSize: "17px"
    fontWeight: 400
  subtitle-compact:
    fontFamily: "Poppins, sans-serif"
    fontSize: "13.5px"
    fontWeight: 400
  title:
    fontFamily: "Poppins, sans-serif"
    fontSize: "14px"
    fontWeight: 500
  description:
    fontFamily: "Poppins, sans-serif"
    fontSize: "11.5px"
    fontWeight: 400
    lineHeight: "15px"
  status:
    fontFamily: "Poppins, sans-serif"
    fontSize: "9px"
    fontWeight: 500
rounded:
  preview-stage: "20px"
  status: "10.5px"
  raster-logo: "8px"
spacing:
  description-lines: "15px"
  label-inset: "4px"
components:
  preview-stage-light:
    backgroundColor: "{colors.stage-light}"
    rounded: "{rounded.preview-stage}"
    width: "260px"
    height: "136px"
  preview-stage-dark:
    backgroundColor: "{colors.stage-dark}"
    rounded: "{rounded.preview-stage}"
    width: "260px"
    height: "136px"
  gallery-card:
    width: "260px"
    height: "218px"
  status-light:
    backgroundColor: "{colors.paper-light}"
    textColor: "{colors.muted-light}"
    typography: "{typography.status}"
    rounded: "{rounded.status}"
    height: "21px"
  status-dark:
    backgroundColor: "{colors.paper-dark}"
    textColor: "{colors.muted-dark}"
    typography: "{typography.status}"
    rounded: "{rounded.status}"
    height: "21px"
---

# Design System: peace profile README

## Overview

**Creative North Star: "Quiet Component Gallery"**

The profile translates the user-selected modern, minimal Bencho reference into GitHub-supported Markdown and SVG artwork. Neutral preview stages give each project room to show its own identity; names and descriptions sit beneath on the transparent page ground. The result is calm, compact, and easy to scan.

The visual system belongs to the profile README and its generated assets. GitHub supplies the surrounding page typography and native link behavior. All 18 projects remain visible across the three existing sections.

**Key Characteristics:**
- Neutral preview stages with original colored logos.
- Poppins inside generated artwork; native GitHub typography outside it.
- Flat surfaces, generous stage corners, and transparent text grounds.
- Explicit light, dark, and compact introduction assets.
- A simple wordmark and subtitle, without decorative dots.

## Colors

The gallery palette is neutral, with distinct light and dark assignments from `PROFILE` in `tools/build_assets.py`.

### Neutral

- **Ink:** wordmark and project names; use the matching `ink-light` or `ink-dark` token.
- **Muted:** subtitles, descriptions, outward-link marks, and secondary details in static previews.
- **Stage:** the soft gray rectangle behind a logo or project illustration.
- **Paper:** small status pills and the illustrated surfaces inside preview stages; this is not a page background token.
- **Line:** restrained separators inside the stacked application-window illustration.

**The Original Color Rule.** Preserve supplied logo colors and proportions. Color within a logo or the Highlightr illustration does not become a gallery-wide accent.

Contribution activity is excluded from the profile README.

## Typography

**Artwork Font:** Poppins, with a sans-serif fallback. The generator embeds per-asset WOFF2 subsets for regular (400) and medium (500), so README images carry their own font.

**Body Font:** GitHub's native Markdown typography. The profile does not impose a custom body font, heading scale, or link style on GitHub.

### Hierarchy

- **Display / Display compact:** the lowercase `peace` wordmark, with medium weight and compact tracking.
- **Subtitle / Subtitle compact:** the single-line introduction below the wordmark.
- **Title:** medium project names beneath each stage.
- **Description:** regular project summaries, wrapped with actual Poppins font metrics within a 248px measure and up to three lines.
- **Status:** medium `paid` labels in small pills.

The frontmatter owns exact type values. SVG text uses explicit baselines rather than a general CSS line-height system; description lines use the documented 15px rhythm.

## Layout

The README presents the introduction, native Markdown biography and links, then the existing Anki add-ons, Other projects, and In the oven sections. Their centered galleries contain 12, three, and three entries respectively. All 18 remain visible; gallery wrapping is handled by GitHub's HTML layout rather than a custom CSS grid.

Each gallery image has a fixed 260 × 218 artwork canvas. Its stage occupies the top 260 × 136; the name baseline is at y=163 and descriptions begin at y=183 with a 4px left inset. The stage does not extend behind the text. Published entries show a small outward-link mark beside the name; development entries have neither that mark nor an invented destination.

The desktop introduction canvas is 808 × 164. At viewport widths up to 500px, the README selects a dedicated 360 × 140 compact source, independently combined with the dark-theme source. Compact layouts adjust wordmark and subtitle typography rather than scaling the desktop composition alone. Gallery assets retain their own dimensions and wrap naturally.

## Elevation & Depth

The gallery uses no shadows or outer card borders. Tonal contrast between the preview stage and its internal artwork creates depth; labels remain on transparent ground. The Stacked Library illustration uses overlapping paper surfaces with graduated opacity, as a depiction of that project rather than a general card elevation rule.

## Shapes

Preview stages use the large, soft corner radius established by the chosen reference. Status pills have fully rounded ends. Preserve original SVG logo geometry; the existing raster logo has its own clipping radius. Static project illustrations use their source-defined shapes without establishing a universal radius scale for future controls.

## Components

### Introduction

A lowercase wordmark and subtitle form the introduction. Keep it free of decorative dots and animation, with descriptive accessible text.

### Gallery card

A neutral stage previews a project above its name and concise description. Supplied logos are centered and constrained to a maximum 104px width and 76px height, preserving aspect ratio and original colors. Entries without logos use the generator's static SVG illustrations. The outward-link mark is informational artwork, not a separate button.

Published cards are wrapped in native README anchors. GitHub owns their pointer, hover, focus, and keyboard behavior; do not invent custom CSS states that cannot ship in a README. Each image has an accessible name and description, and README image alt text preserves the full project description even when artwork wraps or truncates it.

### Status pill

Only `paid` renders as a pill inside the top-right preview stage. Their width follows measured text plus 18px; the shape and text use the matching theme's paper and muted tokens. In-development status stays in the project description. Language and star metadata in generator records are not visible chip variants.

### Profile links and section headings

AnkiWeb, Discord, and GitHub remain native Markdown links. Section headings and biography use GitHub's own rendering and theme. No custom buttons, inputs, or navigation controls belong to this implemented system.


## Do's and Don'ts

### Do:
- **Do** keep all 18 projects visible in their existing sections.
- **Do** preserve original logo colors, aspect ratios, and project destinations.
- **Do** pair each gray preview stage with labels on transparent page ground.
- **Do** generate matching light and dark assets from `PROFILE` and use the compact introduction sources at the existing breakpoint.
- **Do** embed Poppins subsets in artwork and let GitHub render native text and links.
- **Do** keep the introduction free of decorative dots and the README free of contribution activity.
- **Do** depict “New apps” with three overlapping application windows.

### Don't:
- **Don't** extend the stage into a filled outer card behind the labels.
- **Don't** recolor logos to enforce monochrome styling or stretch them to fill the stage.
- **Don't** add simulated interactive controls, custom JavaScript, or page CSS to the README.
- **Don't** invent hover treatments, button variants, or unpublished project links.
- **Don't** restore the Onigiri beta label, dotted header motif, or contribution calendar.
