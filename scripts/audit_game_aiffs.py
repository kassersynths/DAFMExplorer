"""Peak/RMS audit for game demo AIFFs + silent-patch heuristics."""
from __future__ import annotations

import aifc
import array
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "Ludo2026-DAFMExplorer-LaTeX" / "videos" / "presets"
JSON_PATH = ROOT / "artifacts" / "game_demo_exemplars.json"


def aiff_stats(path: Path) -> tuple[int, float]:
    with aifc.open(str(path), "r") as f:
        n = f.getnframes()
        data = f.readframes(n)
    arr = array.array("h")
    arr.frombytes(data)
    if sys_byteorder_little():
        arr.byteswap()
    if not arr:
        return 0, 0.0
    peak = max(abs(x) for x in arr)
    rms = (sum(x * x for x in arr) / len(arr)) ** 0.5
    return peak, rms


def sys_byteorder_little() -> bool:
    import sys

    return sys.byteorder == "little"


def carrier_tls(params: dict) -> list[int]:
    # rough: for any CON, lower TL on ops that can be carriers helps
    ops = params["operators"]
    return [ops[k]["tl"] for k in ("m1", "c1", "m2", "c2")]


def main() -> None:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    for ex in data["exemplars"]:
        p = PRESETS / ex["aiff"]
        if not p.exists():
            print(f"{ex['id']:6s} MISSING {ex['aiff']}")
            continue
        peak, rms = aiff_stats(p)
        tls = carrier_tls(ex["params"])
        flag = " SILENT?" if peak < 200 else (" quiet" if peak < 1500 else "")
        print(
            f"{ex['id']:6s} peak={peak:5d} rms={rms:7.1f} CON={ex['CON']} FL={ex['FL']} "
            f"B={ex['Brightness']:.3f} TL={tls}{flag}  {ex['Filename'][:50]}"
        )


if __name__ == "__main__":
    main()
