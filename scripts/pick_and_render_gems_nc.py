"""Pick an audible Nightmare Circus GEMS-signature preset and merge into gems JSON."""
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


def score(r: pd.Series) -> float:
    """Prefer CON2 FL0, moderate MULs, open C2 — avoids emu-silent extreme FM."""
    s = 0.0
    if int(r.CON) == 2:
        s += 5
    if int(r.FL) == 0:
        s += 5
    s += max(0, 40 - int(r.C2_TL)) / 10
    max_mul = max(int(r.M1_MUL), int(r.C1_MUL), int(r.M2_MUL), int(r.C2_MUL))
    s += max(0, 8 - max_mul)
    # Prefer not-insane modulator levels into the chain
    s += min(int(r.M2_TL), 40) / 20
    return s


def main() -> None:
    df = pd.read_csv(CSV)
    df["B"] = df.apply(m.brightness, axis=1)
    nc = df[df.Filename.str.startswith("Nightmare_Circus_-_", na=False)]
    aud = nc[nc.apply(m.is_audible, axis=1)].copy()
    # Keep GEMS grammar candidates first
    pool = aud[(aud.CON == 2) & (aud.FL == 0) & (aud.C2_TL < 48)]
    if len(pool) == 0:
        pool = aud[(aud.FL == 0) & (aud.C2_TL < 48)]
    if len(pool) == 0:
        pool = aud[aud.C2_TL < 40]
    pool = pool.copy()
    pool["score"] = pool.apply(score, axis=1)
    # Prefer moderate MULs for reliable render
    pool = pool[pool[["M1_MUL", "C1_MUL", "M2_MUL", "C2_MUL"]].max(axis=1) <= 6]
    if len(pool) == 0:
        pool = aud[(aud.CON == 2) & (aud.FL == 0)].copy()
        pool["score"] = pool.apply(score, axis=1)
    r = pool.sort_values(["score", "B"], ascending=[False, False]).iloc[0]
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
        nc_ex["Filename"],
        "CON",
        nc_ex["CON"],
        "FL",
        nc_ex["FL"],
        "C2_TL",
        int(r.C2_TL),
        "maxMUL",
        int(r[["M1_MUL", "C1_MUL", "M2_MUL", "C2_MUL"]].max()),
        "B",
        nc_ex["Brightness"],
        "score",
        round(float(r.score), 2),
    )
    old = json.loads(GAME_DEMOS.read_text(encoding="utf-8"))
    tf4 = next(e for e in old["exemplars"] if e["id"] == "TF4")
    OUT.write_text(json.dumps({"exemplars": [nc_ex, tf4]}, indent=2), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
