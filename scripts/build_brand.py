#!/usr/bin/env python3
"""Madalean brand assets: one master, every derived file generated (never edit the outputs by hand).

    scripts/build_brand.py --trace shells/branding/madalean-logo-source.png   re-trace the master wordmark
    scripts/build_brand.py                                                     regenerate every derived file

The master is shells/branding/madalean-wordmark.svg: three absolute paths traced with potrace from the
user-supplied logo (navy script "Madal_an", orange ∃ standing for the "e", orange swoosh). Everything else —
dark and mono wordmarks, the app icon (orange ∃ + swoosh on a navy rounded square), the monochrome mark, the
maskable / Android adaptive layers and every PNG / ICO size — is derived from it here.

Needs: rsvg-convert, ImageMagick (`magick`), and potrace for --trace. Colours and usage: docs/BRAND.md.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "shells" / "branding"
WEB = ROOT / "web" / "public" / "brand"
ANDROID_RES = ROOT / "shells" / "android" / "android" / "app" / "src" / "main" / "res"
TAURI_ICONS = ROOT / "shells" / "desktop" / "src-tauri" / "icons"
DESKTOP_UI = ROOT / "shells" / "desktop" / "ui"
DOCS_BRAND = ROOT / "docs" / "brand"

NAVY = "#002B5C"
ORANGE = "#FE7B01"
WHITE = "#FFFFFF"

# Crop of the source raster kept around the traced logo (source px): x0, y0, width, height.
CROP = (240, 132, 1726, 508)

# --------------------------------------------------------------------------------------------- path geometry

_TOK = re.compile(r"[MmLlCcZz]|-?\d*\.?\d+(?:[eE][-+]?\d+)?")
_ARGS = {"M": 2, "L": 2, "C": 6, "Z": 0}


def parse_path(d: str) -> list[tuple[str, list[float]]]:
    """Parse M/L/C/Z (absolute or relative, implicit repeats) into absolute segments."""
    out: list[tuple[str, list[float]]] = []
    toks = _TOK.findall(d)
    i, cmd = 0, ""
    cx = cy = sx = sy = 0.0
    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t
            i += 1
            if cmd in "Zz":
                out.append(("Z", []))
                cx, cy = sx, sy
            continue
        up = cmd.upper()
        n = _ARGS[up]
        vals = [float(v) for v in toks[i:i + n]]
        i += n
        rel = cmd.islower()
        pts = []
        for k in range(0, n, 2):
            x, y = vals[k], vals[k + 1]
            pts += [x + cx, y + cy] if rel else [x, y]
        if up == "M":
            out.append(("M", pts))
            cx, cy = sx, sy = pts
            cmd = "l" if rel else "L"                 # implicit lineto after moveto
        else:
            out.append((up, pts))
            cx, cy = pts[-2], pts[-1]
    return out


def transform(segs, sx: float, sy: float, tx: float, ty: float):
    """Affine x' = sx·x + tx, y' = sy·y + ty (no rotation)."""
    return [(c, [v * (sx if k % 2 == 0 else sy) + (tx if k % 2 == 0 else ty) for k, v in enumerate(p)])
            for c, p in segs]


def fmt(segs, nd: int = 1) -> str:
    def n(v: float) -> str:
        s = f"{v:.{nd}f}".rstrip("0").rstrip(".")
        return "0" if s in ("-0", "") else s
    return " ".join(c + " ".join(n(v) for v in p) for c, p in segs)


def bbox(segs) -> tuple[float, float, float, float]:
    xs = [v for _, p in segs for v in p[0::2]]
    ys = [v for _, p in segs for v in p[1::2]]
    return min(xs), min(ys), max(xs), max(ys)


# --------------------------------------------------------------------------------------------- tracing

def run(*cmd: str) -> None:
    subprocess.run(cmd, check=True)


def trace(src: Path) -> None:
    """Separate navy and orange by colour, trace each with potrace, write the master wordmark."""
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        # Masks: black where the colour is. A light blur + 50 % threshold puts the edge mid-antialiasing.
        masks = {
            "script": "(r<0.5 && b>r+0.04)?0:1",
            "orange": "(r>0.6 && r-b>0.3)?0:1",
        }
        for name, fx in masks.items():
            run("magick", str(src), "-fx", fx, "-colorspace", "gray", "-blur", "0x1.5", "-threshold", "50%",
                str(t / f"{name}.bmp"))
        # The ∃ sits above the swoosh: split the orange layer on a horizontal line between them.
        run("magick", str(t / "orange.bmp"), "-fill", "white", "-draw", "rectangle 0,485 4000,4000",
            str(t / "exists.bmp"))
        run("magick", str(t / "orange.bmp"), "-fill", "white", "-draw", "rectangle 0,0 4000,484",
            str(t / "swoosh.bmp"))
        h = int(subprocess.run(["magick", "identify", "-format", "%h", str(src)], check=True,
                               capture_output=True, text=True).stdout)
        paths = {}
        for name in ("script", "exists", "swoosh"):
            svg = t / f"{name}.svg"
            run("potrace", str(t / f"{name}.bmp"), "-s", "--flat", "-t", "30", "-a", "1.1", "-O", "0.5",
                "-o", str(svg))
            d = " ".join(re.findall(r'<path d="([^"]+)"', svg.read_text(), re.S))
            # potrace writes in 1/10 px with y up: map back to source px, then to the crop origin.
            paths[name] = transform(parse_path(" ".join(d.split())), 0.1, -0.1, -CROP[0], h - CROP[1])
    write_master(paths)


def write_master(p: dict) -> None:
    w, h = CROP[2], CROP[3]
    (BRAND / "madalean-wordmark.svg").write_text(f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <title>Madalean</title>
  <!-- MASTER wordmark, traced with potrace from madalean-logo-source.png (scripts/build_brand.py, trace mode).
       Layers by id: script (navy {NAVY}), exists (the orange ∃ standing for the "e", {ORANGE}),
       swoosh ({ORANGE}). Every other brand file is generated from this one by scripts/build_brand.py. -->
  <path id="script" fill="{NAVY}" d="{fmt(p['script'])}"/>
  <path id="exists" fill="{ORANGE}" d="{fmt(p['exists'])}"/>
  <path id="swoosh" fill="{ORANGE}" d="{fmt(p['swoosh'])}"/>
</svg>
""")


def read_master() -> dict:
    text = (BRAND / "madalean-wordmark.svg").read_text()
    return {i: parse_path(d) for i, d in re.findall(r'<path id="(\w+)" fill="[^"]+" d="([^"]+)"', text)}


# --------------------------------------------------------------------------------------------- the icon mark

# Icon canvas 1024 × 1024. The ∃ is the traced glyph, scaled up; the swoosh is redrawn (the logo's own swoosh is a
# 14:1 hairline that vanishes below 64 px) as a crescent with the same rise: low pointed left tip, higher right tip.
MARK = {
    # (∃ height, ∃ top, swoosh crescent) on the 1024 canvas
    "normal": (520, 150, "M170 846 C380 724 680 690 856 752 C680 740 390 806 170 846 Z"),
    # ≤ 32 px: bigger glyph, heavier swoosh, so both survive at 16 px
    "small": (600, 96, "M150 866 C390 750 660 712 874 728 C660 800 400 846 150 866 Z"),
}


def mark_paths(m: dict, scale: float = 1.0, cx: float = 512, cy: float = 512, size: float = 1024,
               variant: str = "normal"):
    """∃ + swoosh in a size×size canvas (default the 1024 icon), optionally scaled about the canvas centre."""
    eh, top, swoosh = MARK[variant]
    x0, y0, x1, y1 = bbox(m["exists"])
    s = eh / (y1 - y0)
    ex = transform(m["exists"], s, s, 512 - s * (x0 + x1) / 2, top - s * y0)
    sw = parse_path(swoosh)
    k = scale * size / 1024
    out = []
    for segs in (ex, sw):
        out.append(transform(segs, k, k, cx * size / 1024 - 512 * k, cy * size / 1024 - 512 * k))
    return out


def icon_svg(m: dict, *, maskable: bool = False, round_: bool = False, small: bool = False) -> str:
    if maskable:      # full-bleed square, content inside the 80 % safe circle
        bg = f'<rect width="1024" height="1024" fill="{NAVY}"/>'
        ex, sw = mark_paths(m, scale=0.8)
    elif round_:
        bg = f'<circle cx="512" cy="512" r="512" fill="{NAVY}"/>'
        ex, sw = mark_paths(m, scale=0.86)
    else:
        bg = f'<rect width="1024" height="1024" rx="224" fill="{NAVY}"/>'
        ex, sw = mark_paths(m, variant="small" if small else "normal")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">
  <title>Madalean</title>
  <!-- Generated by scripts/build_brand.py: orange ∃ (from the wordmark) and swoosh on navy. Do not edit. -->
  {bg}
  <path fill="{ORANGE}" d="{fmt(ex)}"/>
  <path fill="{ORANGE}" d="{fmt(sw)}"/>
</svg>
"""


def mark_mono_svg(m: dict) -> str:
    ex, sw = mark_paths(m)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">
  <title>Madalean</title>
  <!-- Generated by scripts/build_brand.py: the ∃ + swoosh mark in one colour (currentColor). Do not edit. -->
  <path fill="currentColor" d="{fmt(ex)} {fmt(sw)}"/>
</svg>
"""


def wordmark_variant(m: dict, script: str, accent: str, note: str) -> str:
    w, h = CROP[2], CROP[3]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <title>Madalean</title>
  <!-- Generated by scripts/build_brand.py from madalean-wordmark.svg: {note}. Do not edit. -->
  <path fill="{script}" d="{fmt(m['script'])}"/>
  <path fill="{accent}" d="{fmt(m['exists'])}"/>
  <path fill="{accent}" d="{fmt(m['swoosh'])}"/>
</svg>
"""


def android_vector(m: dict, colour: str, note: str) -> str:
    # 108 dp adaptive layer; the visible safe zone is the central 66 dp circle (radius 33). The farthest points
    # of the mark (swoosh tips) are ~480 units from the 1024 canvas centre: scale 0.068 keeps them within 33 dp.
    ex, sw = mark_paths(m, scale=1.0, size=1024)
    k = 0.068
    ex, sw = (transform(s, k, k, 54 - 512 * k, 54 - 500 * k) for s in (ex, sw))
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!-- Madalean mark (orange ∃ + swoosh), generated by scripts/build_brand.py from shells/branding: {note}.
     108 dp adaptive-icon layer, content inside the 66 dp safe zone. Do not edit by hand. -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp" android:height="108dp"
    android:viewportWidth="108" android:viewportHeight="108">
  <path android:fillColor="{colour}" android:pathData="{fmt(ex, 2)}"/>
  <path android:fillColor="{colour}" android:pathData="{fmt(sw, 2)}"/>
</vector>
"""


# --------------------------------------------------------------------------------------------- rasters

def png(svg: Path, out: Path, w: int, h: int | None = None, bg: str | None = None) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["rsvg-convert", "-w", str(w), "-h", str(h or w), str(svg), "-o", str(out)]
    if bg:
        cmd[1:1] = ["-b", bg]
    run(*cmd)
    run("magick", str(out), "-strip", "-define", "png:exclude-chunks=date,time", str(out))


def build() -> None:
    m = read_master()
    for k in ("script", "exists", "swoosh"):
        if k not in m:
            sys.exit(f"master wordmark lacks the {k!r} layer")
    files = {
        BRAND / "madalean-wordmark-dark.svg": wordmark_variant(m, WHITE, ORANGE, "for dark backgrounds, white script"),
        BRAND / "madalean-wordmark-mono.svg": wordmark_variant(m, "currentColor", "currentColor", "one colour"),
        BRAND / "madalean-icon.svg": icon_svg(m),
        BRAND / "madalean-icon-small.svg": icon_svg(m, small=True),
        BRAND / "madalean-icon-maskable.svg": icon_svg(m, maskable=True),
        BRAND / "madalean-icon-round.svg": icon_svg(m, round_=True),
        BRAND / "madalean-mark-mono.svg": mark_mono_svg(m),
    }
    for p, t in files.items():
        p.write_text(t)

    icon, small = BRAND / "madalean-icon.svg", BRAND / "madalean-icon-small.svg"
    maskable, round_ = BRAND / "madalean-icon-maskable.svg", BRAND / "madalean-icon-round.svg"
    pngd = BRAND / "png"
    for old in pngd.glob("*.png"):
        old.unlink()
    for s in (16, 24, 32, 48, 64, 128, 256, 512, 1024):
        png(small if s <= 32 else icon, pngd / f"madalean-icon-{s}.png", s)
    png(maskable, pngd / "madalean-icon-maskable-512.png", 512)
    with tempfile.TemporaryDirectory() as tmp:
        mono_navy = Path(tmp) / "mono.svg"
        mono_navy.write_text(files[BRAND / "madalean-mark-mono.svg"].replace("currentColor", NAVY))
        png(mono_navy, pngd / "madalean-mark-mono-1024.png", 1024)
    png(BRAND / "madalean-wordmark.svg", pngd / "madalean-wordmark-1300.png", 1300, round(1300 * CROP[3] / CROP[2]))
    png(BRAND / "madalean-wordmark-dark.svg", pngd / "madalean-wordmark-dark-1300.png", 1300,
        round(1300 * CROP[3] / CROP[2]))

    # Web UI (served under /brand/).
    WEB.mkdir(parents=True, exist_ok=True)
    shutil.copy2(icon, WEB / "icon.svg")
    shutil.copy2(BRAND / "madalean-mark-mono.svg", WEB / "mark-mono.svg")
    shutil.copy2(BRAND / "madalean-wordmark.svg", WEB / "wordmark.svg")
    shutil.copy2(BRAND / "madalean-wordmark-dark.svg", WEB / "wordmark-dark.svg")
    png(small, WEB / "icon-32.png", 32)
    png(icon, WEB / "icon-192.png", 192)
    png(icon, WEB / "icon-256.png", 256)
    png(icon, WEB / "icon-512.png", 512)
    png(maskable, WEB / "icon-maskable-512.png", 512)
    png(maskable, WEB / "apple-touch-icon.png", 180)          # iOS rounds the corners itself: full bleed
    with tempfile.TemporaryDirectory() as tmp:
        parts = []
        for s in (16, 32, 48):
            p = Path(tmp) / f"{s}.png"
            png(small if s <= 32 else icon, p, s)
            parts.append(str(p))
        run("magick", *parts, str(WEB / "favicon.ico"))

    # Docs (README header) and the project site.
    DOCS_BRAND.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BRAND / "madalean-wordmark.svg", DOCS_BRAND / "madalean-wordmark.svg")
    shutil.copy2(BRAND / "madalean-wordmark-dark.svg", DOCS_BRAND / "madalean-wordmark-dark.svg")

    # Android: adaptive layers (vector), legacy launcher PNGs for API < 26.
    (ANDROID_RES / "drawable" / "ic_launcher_foreground.xml").write_text(
        android_vector(m, ORANGE, "foreground layer, also the splash icon"))
    (ANDROID_RES / "drawable" / "ic_launcher_monochrome.xml").write_text(
        android_vector(m, "#FFFFFFFF", "monochrome (themed icon) layer, only alpha is used"))
    for dens, s in {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}.items():
        png(icon, ANDROID_RES / f"mipmap-{dens}" / "ic_launcher.png", s)
        png(round_, ANDROID_RES / f"mipmap-{dens}" / "ic_launcher_round.png", s)

    # Tauri / AppImage (the list in tauri.conf.json "icon") and the desktop shell's connection screen.
    shutil.copy2(icon, DESKTOP_UI / "icon.svg")
    png(small, TAURI_ICONS / "32x32.png", 32)
    png(icon, TAURI_ICONS / "128x128.png", 128)
    png(icon, TAURI_ICONS / "128x128@2x.png", 256)
    png(icon, TAURI_ICONS / "icon.png", 512)
    print("brand assets regenerated")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trace", type=Path, help="re-trace the master wordmark from this raster first")
    a = ap.parse_args()
    if a.trace:
        trace(a.trace)
    build()


if __name__ == "__main__":
    main()
