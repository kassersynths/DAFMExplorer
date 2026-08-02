"""Pick game-fingerprint / brightness demo presets and write JSON for AIFF render."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "processed" / "all_instruments_final.csv"
OUT = ROOT / "artifacts" / "game_demo_exemplars.json"

OPS = ["M1", "C1", "M2", "C2"]

# Must match scripts/con_conditioned_eda.py ROLE_BY_CON carriers
CARRIERS_BY_CON: dict[int, list[str]] = {
    0: ["C2"],
    1: ["C2"],
    2: ["C2"],
    3: ["C2"],
    4: ["C1", "C2"],
    5: ["C1", "M2", "C2"],
    6: ["C1", "M2", "C2"],
    7: ["M1", "C1", "M2", "C2"],
}


def brightness(r: pd.Series) -> float:
    avg_tl = (r.M1_TL + r.C1_TL + r.M2_TL + r.C2_TL) / 4
    tl = 1 - (avg_tl / 127)
    ar = (r.M1_AR + r.C1_AR + r.M2_AR + r.C2_AR) / 4 / 31
    mul = (r.M1_MUL + r.C1_MUL + r.M2_MUL + r.C2_MUL) / 4 / 15
    return max(0.0, min(1.0, tl * 0.4 + ar * 0.3 + mul * 0.3))


def row_to_params(r: pd.Series) -> dict:
    ops = {}
    for op, key in zip(OPS, ["m1", "c1", "m2", "c2"]):
        ops[key] = {
            "ar": int(r[f"{op}_AR"]),
            "d1r": int(r[f"{op}_D1R"]),
            "d2r": int(r[f"{op}_D2R"]),
            "rr": int(r[f"{op}_RR"]),
            "d1l": int(r[f"{op}_D1L"]),
            "tl": int(r[f"{op}_TL"]),
            "ks": int(r[f"{op}_KS"]),
            "mul": int(r[f"{op}_MUL"]),
            "dt1": int(r[f"{op}_DT1"]),
            "ams_en": int(r[f"{op}_AMS-EN"]),
        }
    return {
        "algorithm": int(r.CON),
        "feedback": int(r.FL),
        "ams": int(r.AMS),
        "pms": int(r.PMS),
        "lfrq": int(r.LFRQ),
        "operators": ops,
    }


def slug(s: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in s).strip("_").lower()


def is_audible(r: pd.Series) -> bool:
    con = int(r.CON)
    carriers = CARRIERS_BY_CON.get(con, ["C2"])
    open_carriers = [c for c in carriers if int(r[f"{c}_TL"]) < 100]
    if not open_carriers:
        return False
    if not any(int(r[f"{c}_AR"]) >= 8 for c in open_carriers):
        return False
    if con in (5, 6) and max(int(r[f"{op}_MUL"]) for op in OPS) == 0:
        return False
    if min(int(r[f"{c}_TL"]) for c in open_carriers) >= 96:
        return False
    return True


def pick(
    df: pd.DataFrame,
    mask: pd.Series,
    *,
    label: str,
    prefer_con: int | None = None,
    brightness_mode: str = "max",
    cue: str = "",
) -> dict:
    def _pool(use_prefer: bool) -> pd.DataFrame:
        base = df[mask].copy()
        if use_prefer and prefer_con is not None:
            preferred = base[base.CON == prefer_con]
            if len(preferred):
                base = preferred
        audible = base[base.apply(is_audible, axis=1)]
        return audible

    s = _pool(use_prefer=True)
    if len(s) == 0 and prefer_con is not None:
        s = _pool(use_prefer=False)
    if len(s) == 0:
        raise RuntimeError(f"No audible presets for {label}")

    if brightness_mode == "max":
        s = s.sort_values("B", ascending=False)
    elif brightness_mode == "min":
        car_tls: list[int] = []
        for _, r in s.iterrows():
            cars = CARRIERS_BY_CON.get(int(r.CON), ["C2"])
            open_tls = [int(r[f"{c}_TL"]) for c in cars if int(r[f"{c}_TL"]) < 100]
            car_tls.append(min(open_tls) if open_tls else 127)
        s = s.copy()
        s["car_tl"] = car_tls
        s = s.sort_values(["B", "car_tl"], ascending=[True, True])
    else:
        med = float(s.B.median())
        s = s.assign(d=(s.B - med).abs()).sort_values("d")

    r = s.iloc[0]
    aiff = f"game_{slug(label)}_con{int(r.CON)}_b{str(round(float(r.B), 3)).replace('.', 'p')}.aiff"
    return {
        "id": cue or slug(label)[:12],
        "label": label,
        "Name": str(r.Name),
        "Filename": str(r.Filename),
        "CON": int(r.CON),
        "FL": int(r.FL),
        "Brightness": round(float(r.B), 3),
        "aiff": aiff,
        "params": row_to_params(r),
    }


def startswith(df: pd.DataFrame, prefix: str) -> pd.Series:
    return df.Filename.str.startswith(prefix, na=False)


def contains(df: pd.DataFrame, needle: str) -> pd.Series:
    return df.Filename.str.contains(needle, case=False, na=False, regex=False)


def main() -> None:
    df = pd.read_csv(CSV)
    df["B"] = df.apply(brightness, axis=1)

    s3k_mask = df.Filename.str.contains(
        r"Sonic.?&.?Knuckles|Sonic_and_Knuckles|Sonic_&_Knuckles|S3&K|Sonic_3_and_Knuckles",
        case=False,
        na=False,
        regex=True,
    )

    picks = [
        pick(df, startswith(df, "Pulseman_-_"), label="Pulseman", prefer_con=5, brightness_mode="max", cue="PM"),
        pick(
            df,
            startswith(df, "Thunder_Force_IV_-_"),
            label="Thunder Force IV",
            prefer_con=0,
            brightness_mode="median",
            cue="TF4",
        ),
        pick(
            df,
            startswith(df, "Gunstar_Heroes_-_"),
            label="Gunstar Heroes",
            prefer_con=5,
            brightness_mode="median",
            cue="GH",
        ),
        pick(
            df,
            startswith(df, "Streets_of_Rage_3_-_"),
            label="Streets of Rage 3",
            prefer_con=2,
            brightness_mode="median",
            cue="SOR3",
        ),
        pick(
            df,
            startswith(df, "The_Adventures_of_Batman_and_Robin_-_"),
            label="Batman and Robin",
            brightness_mode="max",
            cue="BAR",
        ),
        pick(df, startswith(df, "Ristar_-_"), label="Ristar", brightness_mode="median", cue="RST"),
        pick(df, s3k_mask, label="Sonic 3 and Knuckles", brightness_mode="median", cue="S3K"),
        pick(df, startswith(df, "The_Tick_-_"), label="The Tick", brightness_mode="min", cue="TICK"),
        pick(df, startswith(df, "Tinhead_-_"), label="Tinhead", brightness_mode="min", cue="TIN"),
        pick(df, startswith(df, "Top_Gear_2_-_"), label="Top Gear 2", brightness_mode="min", cue="TG2"),
        # TPW dump has no open carriers — use another chart dark outlier that renders
        pick(
            df,
            contains(df, "Spider-Man") & contains(df, "X-Men"),
            label="Spider-Man and X-Men",
            brightness_mode="min",
            cue="SMX",
        ),
    ]

    for e in picks:
        ops = e["params"]["operators"]
        tls = [ops[k]["tl"] for k in ("m1", "c1", "m2", "c2")]
        print(
            f"{e['id']:6s} {e['label']:28s} CON={e['CON']} FL={e['FL']} B={e['Brightness']:.3f} "
            f"TL={tls}  {e['Filename'][:50]}"
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"note_midi": 60, "exemplars": picks}, indent=2), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
