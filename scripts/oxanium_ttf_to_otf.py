"""Convert Oxanium TTF statics to CFF-flavoured OTF for Acrobat-friendly PDF embedding.

Decomposes composite glyphs (e.g. ``%``) so outlines are not dropped.
"""
from __future__ import annotations

from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.qu2cuPen import Qu2CuPen
from fontTools.pens.recordingPen import DecomposingRecordingPen, replayRecording
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "Ludo2026-DAFMExplorer-LaTeX" / "assets" / "fonts"

JOBS = [
    ("Oxanium-Regular.ttf", "Oxanium-Regular.otf", "Regular", 400),
    ("Oxanium-Bold.ttf", "Oxanium-Bold.otf", "Bold", 700),
]


def convert(ttf_name: str, otf_name: str, style: str, weight: int) -> None:
    src = FONT_DIR / ttf_name
    dst = FONT_DIR / otf_name
    tt = TTFont(src)
    glyph_order = tt.getGlyphOrder()
    metrics = {gn: tt["hmtx"][gn] for gn in glyph_order}
    gs = tt.getGlyphSet()
    charstrings = {}
    empty = []
    for gn in glyph_order:
        adv = metrics[gn][0]
        rec = DecomposingRecordingPen(gs)
        gs[gn].draw(rec)
        t2pen = T2CharStringPen(adv, None)
        if rec.value:
            try:
                replayRecording(rec.value, Qu2CuPen(t2pen, max_err=1.0, all_cubic=True))
            except Exception:
                t2pen = T2CharStringPen(adv, None)
                replayRecording(rec.value, t2pen)
        else:
            empty.append(gn)
        charstrings[gn] = t2pen.getCharString()

    fb = FontBuilder(tt["head"].unitsPerEm, isTTF=False)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(tt.getBestCmap() or {})
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=tt["hhea"].ascent, descent=tt["hhea"].descent)
    fb.setupNameTable(
        {
            "familyName": "Oxanium",
            "styleName": style,
            "psName": f"Oxanium-{style}",
            "fullName": f"Oxanium {style}",
        }
    )
    fb.setupOS2(
        sTypoAscender=tt["OS/2"].sTypoAscender,
        sTypoDescender=tt["OS/2"].sTypoDescender,
        usWeightClass=weight,
    )
    fb.setupPost()
    fb.setupCFF(
        f"Oxanium-{style}",
        {},
        charstrings,
        {},
    )
    fb.save(dst)

    check = TTFont(dst)
    cmap = check.getBestCmap() or {}
    from fontTools.pens.recordingPen import RecordingPen

    pct_ops = 0
    if 0x25 in cmap:
        pen = RecordingPen()
        check.getGlyphSet()[cmap[0x25]].draw(pen)
        pct_ops = len(pen.value)
    print(
        "wrote",
        dst.name,
        "size",
        dst.stat().st_size,
        "empty_src",
        empty,
        "%_ops",
        pct_ops,
    )


def main() -> None:
    for job in JOBS:
        convert(*job)


if __name__ == "__main__":
    main()
