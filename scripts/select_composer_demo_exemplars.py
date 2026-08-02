"""Pick audible presets for composer-signature slides (game proxies)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import pandas as pd

import select_game_demo_exemplars as m

CSV = ROOT / "data" / "processed" / "all_instruments_final.csv"
OUT = ROOT / "artifacts" / "composer_demo_exemplars.json"


def pick(
    df: pd.DataFrame,
    *,
    cue: str,
    label: str,
    prefix: str,
    prefer_con: int | None = None,
    prefer_fl: int | None = None,
    brightness_mode: str = "median",
) -> dict:
    s = df[df.Filename.str.startswith(prefix, na=False)].copy()
    # Prefer musical beds over short jingles / system cues when possible
    s = s[
        ~s.Filename.str.contains(
            r"Drowning|Game_Over|Continue|Extra_Life|Staff_Roll|Level_Clear|Sega_Logo",
            case=False,
            na=False,
            regex=True,
        )
    ]
    s = s[s.apply(m.is_audible, axis=1)]
    if prefer_con is not None:
        s2 = s[s.CON == prefer_con]
        if len(s2):
            s = s2
    if prefer_fl is not None:
        s2 = s[s.FL == prefer_fl]
        if len(s2):
            s = s2
    # Avoid extreme MULs that rendered silent in the emu
    s = s[s[["M1_MUL", "C1_MUL", "M2_MUL", "C2_MUL"]].max(axis=1) <= 8]
    if len(s) == 0:
        raise RuntimeError(f"No audible preset for {label} ({prefix})")

    if brightness_mode == "max":
        s = s.sort_values("B", ascending=False)
    elif brightness_mode == "min":
        s = s.sort_values("B", ascending=True)
    else:
        med = float(s.B.median())
        s = s.assign(d=(s.B - med).abs()).sort_values("d")

    r = s.iloc[0]
    aiff = (
        f"composer_{m.slug(label)}_con{int(r.CON)}_fl{int(r.FL)}"
        f"_b{str(round(float(r.B), 3)).replace('.', 'p')}.aiff"
    )
    ex = {
        "id": cue,
        "label": label,
        "Name": str(r.Name),
        "Filename": str(r.Filename),
        "CON": int(r.CON),
        "FL": int(r.FL),
        "Brightness": round(float(r.B), 3),
        "aiff": aiff,
        "params": m.row_to_params(r),
    }
    print(
        f"{cue:6s} {label:22s} CON={ex['CON']} FL={ex['FL']} B={ex['Brightness']:.3f}  "
        f"{ex['Filename'][:55]}"
    )
    return ex


def main() -> None:
    df = pd.read_csv(CSV)
    df["B"] = df.apply(m.brightness, axis=1)

    picks = [
        pick(
            df,
            cue="YK",
            label="Koshiro",
            prefix="Streets_of_Rage_-_",
            prefer_con=4,
            prefer_fl=7,
            brightness_mode="max",
        ),
        pick(
            df,
            cue="MN",
            label="Nakamura",
            prefix="Sonic_the_Hedgehog_-_",
            prefer_con=4,
            prefer_fl=7,
            brightness_mode="median",
        ),
        pick(
            df,
            cue="HK",
            label="Kawaguchi",
            prefix="Golden_Axe_-_",
            prefer_fl=7,
            brightness_mode="median",
        ),
        pick(
            df,
            cue="NH",
            label="Hanzawa",
            prefix="Gunstar_Heroes_-_",
            prefer_con=5,
            prefer_fl=7,
            brightness_mode="median",
        ),
        pick(
            df,
            cue="NK",
            label="Kodaka",
            prefix="Super_Fantasy_Zone_-_",
            prefer_con=2,
            prefer_fl=7,
            brightness_mode="median",
        ),
        # Uematsu: no clean solo MD pack in this dump for safe attribution.
        # Contrast listen uses Koshiro (Alg.4 workhorse) vs Kodaka (Alg.2 exception).
    ]

    OUT.write_text(json.dumps({"note_midi": 60, "exemplars": picks}, indent=2), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
