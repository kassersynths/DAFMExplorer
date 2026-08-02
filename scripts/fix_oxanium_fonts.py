"""Download official Oxanium statics and instantiate from variable if needed."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Ludo2026-DAFMExplorer-LaTeX" / "assets" / "fonts"
VAR_CANDIDATES = [
    OUT / "Oxanium-Variable.ttf",
    ROOT / "web-scrollytelling" / "public" / "assets" / "fonts" / "Oxanium-Variable.ttf",
    ROOT / "web-scrollytelling" / "public" / "fonts" / "Oxanium-Variable.ttf",
]

RELEASE_ZIP = "https://github.com/sevmeyer/oxanium/releases/download/2.000/oxanium-2.000.zip"
GF_VAR = "https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/oxanium/Oxanium%5Bwght%5D.ttf"


def fetch(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "DAFMExplorer-font-fix/1.0"})
    with urlopen(req, timeout=60) as r:
        return r.read()


def set_names(font: TTFont, family: str, subfamily: str, ps: str) -> None:
    name = font["name"]
    for platformID, platEncID, langID in ((3, 1, 0x409), (1, 0, 0)):
        name.setName(family, 1, platformID, platEncID, langID)
        name.setName(subfamily, 2, platformID, platEncID, langID)
        name.setName(f"{family} {subfamily}", 4, platformID, platEncID, langID)
        name.setName(ps, 6, platformID, platEncID, langID)
        name.setName(family, 16, platformID, platEncID, langID)
        name.setName(subfamily, 17, platformID, platEncID, langID)


def save_static(var_path: Path, weight: int, out_name: str, subfamily: str) -> Path:
    var = TTFont(var_path)
    static = instantiateVariableFont(var, {"wght": weight}, inplace=False)
    static["OS/2"].usWeightClass = weight
    set_names(static, "Oxanium", subfamily, f"Oxanium-{subfamily}")
    out = OUT / out_name
    static.save(out)
    check = TTFont(out)
    print(
        "wrote",
        out.name,
        "size",
        out.stat().st_size,
        "ps",
        check["name"].getDebugName(6),
        "weight",
        check["OS/2"].usWeightClass,
        "glyphs",
        len(check.getGlyphOrder()),
    )
    return out


def try_release_zip() -> bool:
    try:
        data = fetch(RELEASE_ZIP)
    except Exception as e:
        print("release zip failed:", e)
        return False
    zf = zipfile.ZipFile(io.BytesIO(data))
    names = zf.namelist()
    print("zip entries", [n for n in names if n.lower().endswith((".ttf", ".otf"))][:20])
    mapping = {
        "Oxanium-Regular.ttf": None,
        "Oxanium-Bold.ttf": None,
    }
    for n in names:
        base = Path(n).name
        if base in mapping:
            mapping[base] = n
    if not all(mapping.values()):
        # try fonts/static paths
        for n in names:
            base = Path(n).name
            if base in mapping and mapping[base] is None:
                mapping[base] = n
    if not all(mapping.values()):
        print("zip missing statics", mapping)
        return False
    OUT.mkdir(parents=True, exist_ok=True)
    for out_name, src in mapping.items():
        raw = zf.read(src)
        dest = OUT / out_name
        dest.write_bytes(raw)
        f = TTFont(dest)
        set_names(
            f,
            "Oxanium",
            "Regular" if "Regular" in out_name else "Bold",
            "Oxanium-Regular" if "Regular" in out_name else "Oxanium-Bold",
        )
        f["OS/2"].usWeightClass = 400 if "Regular" in out_name else 700
        f.save(dest)
        print("from zip", out_name, dest.stat().st_size, f["name"].getDebugName(6))
    return True


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if try_release_zip():
        return

    var_path = next((p for p in VAR_CANDIDATES if p.exists() and p.stat().st_size > 50000), None)
    if var_path is None:
        print("downloading variable from jsDelivr…")
        var_path = OUT / "Oxanium-Variable.ttf"
        var_path.write_bytes(fetch(GF_VAR))
        print("saved", var_path, var_path.stat().st_size)

    save_static(var_path, 400, "Oxanium-Regular.ttf", "Regular")
    save_static(var_path, 700, "Oxanium-Bold.ttf", "Bold")


if __name__ == "__main__":
    main()
