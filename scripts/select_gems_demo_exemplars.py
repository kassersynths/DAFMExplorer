"""Pick GEMS vs non-GEMS listening exemplars (Nightmare Circus vs Thunder Force IV)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import pandas as pd

import select_game_demo_exemplars as m

CSV = ROOT / "data" / "processed" / "all_instruments_final.csv"
OUT = ROOT / "artifacts" / "gems_demo_exemplars.json"
GAME_DEMOS = ROOT / "artifacts" / "game_demo_exemplars.json"


def main() -> None:
    df = pd.read_csv(CSV)
    df["B"] = df.apply(m.brightness, axis=1)

    nc = df[df.Filename.str.startswith("Nightmare_Circus_-_", na=False)]
    aud = nc[nc.apply(m.is_audible, axis=1)]
    pool = aud[(aud.CON == 2) & (aud.FL == 0)]
    if len(pool) == 0:
        pool = aud[aud.FL == 0]
    if len(pool) == 0:
        pool = aud
    if len(pool) == 0:
        raise SystemExit("No audible Nightmare Circus presets")

    r = pool.sort_values("B", ascending=False).iloc[0]
    nc_ex = {
        "id": "NC",
        "label": "Nightmare Circus",
        "Name": str(r.Name),
        "Filename": str(r.Filename),
        "CON": int(r.CON),
        "FL": int(r.FL),
        "Brightness": round(float(r.B), 3),
        "aiff": f"game_nightmare_circus_con{int(r.CON)}_fl{int(r.FL)}.aiff",
        "params": m.row_to_params(r),
    }
    print(
        "NC",
        nc_ex["Filename"][:55],
        "CON",
        nc_ex["CON"],
        "FL",
        nc_ex["FL"],
        "B",
        nc_ex["Brightness"],
    )

    old = json.loads(GAME_DEMOS.read_text(encoding="utf-8"))
    tf4 = next(e for e in old["exemplars"] if e["id"] == "TF4")
    OUT.write_text(json.dumps({"exemplars": [nc_ex, tf4]}, indent=2), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
