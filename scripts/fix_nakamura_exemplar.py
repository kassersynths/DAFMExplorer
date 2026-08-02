"""Prefer a musical Sonic zone (Star Light / Green Hill) for Nakamura demos."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import pandas as pd

import select_game_demo_exemplars as m

PREFERRED = [
    "Star_Light_Zone",
    "Green_Hill_Zone",
    "Spring_Yard_Zone",
    "Marble_Zone",
    "Scrap_Brain_Zone",
]

df = pd.read_csv(ROOT / "data" / "processed" / "all_instruments_final.csv", low_memory=False)
df["B"] = df.apply(m.brightness, axis=1)
s = df[df.Filename.str.startswith("Sonic_the_Hedgehog_-_", na=False)]
s = s[
    ~s.Filename.str.contains(
        r"Drowning|Game_Over|Continue|Extra_Life|Staff|Level_Clear|Sega_Logo|Labyrinth",
        case=False,
        na=False,
        regex=True,
    )
]
s = s[s.apply(m.is_audible, axis=1)]
s = s[(s.CON == 4) & (s.FL == 7)]
s = s[s[["M1_MUL", "C1_MUL", "M2_MUL", "C2_MUL"]].max(axis=1) <= 8]

row = None
for zone in PREFERRED:
    z = s[s.Filename.str.contains(zone, case=False, na=False)]
    if len(z):
        row = z.assign(d=(z.B - 0.58).abs()).sort_values("d").iloc[0]
        break
if row is None:
    row = s.assign(d=(s.B - 0.58).abs()).sort_values("d").iloc[0]

print(row.Filename, int(row.CON), int(row.FL), round(float(row.B), 3))

path = ROOT / "artifacts" / "composer_demo_exemplars.json"
data = json.loads(path.read_text(encoding="utf-8"))
for e in data["exemplars"]:
    if e["id"] == "MN":
        e.update(
            {
                "Name": str(row.Name),
                "Filename": str(row.Filename),
                "CON": int(row.CON),
                "FL": int(row.FL),
                "Brightness": round(float(row.B), 3),
                "aiff": (
                    f"composer_nakamura_con{int(row.CON)}_fl{int(row.FL)}"
                    f"_b{str(round(float(row.B), 3)).replace('.', 'p')}.aiff"
                ),
                "params": m.row_to_params(row),
            }
        )
        print("updated", e["aiff"])
path.write_text(json.dumps(data, indent=2), encoding="utf-8")
