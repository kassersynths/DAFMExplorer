#!/usr/bin/env python3
"""
CON-conditioned EDA for YM2612 presets.

- Role-aware parameter histograms per algorithm (CON)
- Modal star combination: FL + MUL(primary_mod) + TL(primary_car) within each CON
- Export artifacts + figures for Ludo2026

Corpus: data/processed/all_instruments_final.csv (~93k), with light TL-aware
dedup per source file (same timbre, different mix levels collapsed).
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "processed" / "all_instruments_final.csv"
ART = ROOT / "artifacts"
FIG_DIR = ROOT / "Ludo2026-DAFMExplorer-LaTeX" / "assets"
MAGENTA, CYAN, GOLD, BLUE = "#ff02ff", "#00edff", "#f1c034", "#0089f7"
BLACK, PANEL, WHITE, MUTED = "#0a0a0a", "#161922", "#ffffff", "#929292"

# Operators: M1=1, C1=2, M2=3, C2=4 (OPM / DefleMask naming)
# Topology from standard YM2612 / OPN algorithm charts.
ROLE_BY_CON: dict[int, dict] = {
    0: {
        "label": "1→2→3→4 serial",
        "primary_mod": "M2",
        "primary_car": "C2",
        "modulators": ["M1", "C1", "M2"],
        "carriers": ["C2"],
    },
    1: {
        "label": "1→3→4 + 2→4",
        "primary_mod": "M2",
        "primary_car": "C2",
        "modulators": ["M1", "C1", "M2"],
        "carriers": ["C2"],
    },
    2: {
        "label": "1→4 + 2→3→4",
        "primary_mod": "C1",
        "primary_car": "C2",
        "modulators": ["M1", "C1", "M2"],
        "carriers": ["C2"],
    },
    3: {
        "label": "1→2→4 + 3→4",
        "primary_mod": "C1",
        "primary_car": "C2",
        "modulators": ["M1", "C1", "M2"],
        "carriers": ["C2"],
    },
    4: {
        "label": "1→2 + 3→4 (two FM voices)",
        "primary_mod": "M1",
        "primary_car": "C1",
        "modulators": ["M1", "M2"],
        "carriers": ["C1", "C2"],
    },
    5: {
        "label": "1→2+3+4 (one mod, many carriers)",
        "primary_mod": "M1",
        "primary_car": "C1",
        "modulators": ["M1"],
        "carriers": ["C1", "M2", "C2"],
    },
    6: {
        "label": "1→2 + 3 + 4",
        "primary_mod": "M1",
        "primary_car": "C1",
        "modulators": ["M1"],
        "carriers": ["C1", "M2", "C2"],
    },
    7: {
        "label": "1+2+3+4 additive (FL on M1)",
        "primary_mod": "M1",
        "primary_car": "C1",
        "modulators": ["M1"],
        "carriers": ["M1", "C1", "M2", "C2"],
    },
}

TL_COLS = ["M1_TL", "C1_TL", "M2_TL", "C2_TL"]
META_DROP = {"Num", "Name", "Filename", "Game"}


def style(ax):
    ax.set_facecolor(PANEL)
    ax.tick_params(colors=WHITE, labelsize=7)
    for s in ax.spines.values():
        s.set_color(MAGENTA)
    ax.xaxis.label.set_color(WHITE)
    ax.yaxis.label.set_color(WHITE)
    ax.title.set_color(CYAN)


def load_corpus() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    df["Game"] = (
        df["Filename"]
        .astype(str)
        .str.replace(r"_-_.*$", "", regex=True)
        .str.replace("_", " ")
    )
    # Light TL-aware dedup per source file: same non-TL params → one row
    compare_cols = [
        c
        for c in df.columns
        if c not in META_DROP
        and c not in TL_COLS
        and c != "Game"
    ]
    before = len(df)
    df = df.drop_duplicates(subset=["Filename"] + compare_cols, keep="first")
    print(f"Loaded {before} rows -> {len(df)} after TL-aware dedup per file")
    return df.reset_index(drop=True)


def add_role_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    mul_mod = np.empty(len(out), dtype=np.int16)
    tl_mod = np.empty(len(out), dtype=np.int16)
    ar_mod = np.empty(len(out), dtype=np.int16)
    mul_car = np.empty(len(out), dtype=np.int16)
    tl_car = np.empty(len(out), dtype=np.int16)
    ar_car = np.empty(len(out), dtype=np.int16)
    cons = out["CON"].to_numpy(dtype=np.int8)
    for con, role in ROLE_BY_CON.items():
        mask = cons == con
        if not mask.any():
            continue
        pm, pc = role["primary_mod"], role["primary_car"]
        mul_mod[mask] = out.loc[mask, f"{pm}_MUL"].to_numpy()
        tl_mod[mask] = out.loc[mask, f"{pm}_TL"].to_numpy()
        ar_mod[mask] = out.loc[mask, f"{pm}_AR"].to_numpy()
        mul_car[mask] = out.loc[mask, f"{pc}_MUL"].to_numpy()
        tl_car[mask] = out.loc[mask, f"{pc}_TL"].to_numpy()
        ar_car[mask] = out.loc[mask, f"{pc}_AR"].to_numpy()
    out["MUL_mod"] = mul_mod
    out["TL_mod"] = tl_mod
    out["AR_mod"] = ar_mod
    out["MUL_car"] = mul_car
    out["TL_car"] = tl_car
    out["AR_car"] = ar_car
    out["star_key"] = (
        out["FL"].astype(int).astype(str)
        + "|"
        + out["MUL_mod"].astype(int).astype(str)
        + "|"
        + out["TL_car"].astype(int).astype(str)
    )
    return out


def plot_key_histos(df: pd.DataFrame) -> None:
    cons = sorted(df["CON"].unique())
    params = [
        ("FL", "Feedback (FL)"),
        ("MUL_mod", "MUL primary modulator"),
        ("TL_car", "TL primary carrier"),
        ("AR_mod", "AR primary modulator"),
    ]
    for col, title in params:
        fig, axes = plt.subplots(2, 4, figsize=(11, 5.2), facecolor=BLACK)
        axes = axes.ravel()
        for i, con in enumerate(range(8)):
            ax = axes[i]
            sub = df[df["CON"] == con]
            n = len(sub)
            if n == 0:
                ax.set_facecolor(PANEL)
                ax.set_title(f"CON {con} (n=0)", color=MUTED, fontsize=9)
                ax.axis("off")
                continue
            vals = sub[col]
            bins = range(int(vals.min()), int(vals.max()) + 2)
            ax.hist(vals, bins=bins, color=CYAN if con % 2 == 0 else MAGENTA, edgecolor=WHITE, linewidth=0.2)
            ax.set_title(f"CON {con} (n={n})", fontsize=9)
            style(ax)
            if i < 4:
                ax.set_xlabel("")
        fig.suptitle(f"{title} by CON (role-aware)", color=GOLD, fontsize=12)
        fig.tight_layout()
        path = FIG_DIR / f"fig_con_{col.lower()}.png"
        fig.savefig(path, dpi=150, facecolor=BLACK, bbox_inches="tight")
        plt.close(fig)
        print("wrote", path.relative_to(ROOT))


def modal_combos(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for con, sub in df.groupby("CON"):
        n = len(sub)
        ctr = Counter(zip(sub["FL"].astype(int), sub["MUL_mod"].astype(int), sub["TL_car"].astype(int)))
        for rank, ((fl, mul, tl), cnt) in enumerate(ctr.most_common(5), start=1):
            rows.append(
                {
                    "CON": int(con),
                    "rank": rank,
                    "FL": fl,
                    "MUL_mod": mul,
                    "TL_car": tl,
                    "count": cnt,
                    "share_within_con": round(cnt / n, 4),
                    "n_con": n,
                    "topology": ROLE_BY_CON[int(con)]["label"],
                    "primary_mod": ROLE_BY_CON[int(con)]["primary_mod"],
                    "primary_car": ROLE_BY_CON[int(con)]["primary_car"],
                }
            )
    return pd.DataFrame(rows)


def select_stars(combo_df: pd.DataFrame) -> list[dict]:
    """Pick up to 5 narrative stars among frequent CONs, preferring audible carriers."""
    want = [4, 2, 5, 0, 7]
    stars = []
    for con in want:
        cand = combo_df[combo_df["CON"] == con].sort_values(["rank", "count"])
        # TL=127 is silence on YM2612 — skip muted carriers for listening stars
        audible = cand[cand["TL_car"] < 100]
        pool = audible if len(audible) else cand
        # Prefer high feedback for action FM, else first audible mode
        hi_fl = pool[pool["FL"] >= 6]
        row = (hi_fl if len(hi_fl) else pool).iloc[0]
        stars.append(row.to_dict())
    return stars[:5]


STAR_NARRATIVE = {
    4: (
        "Workhorse Alg.4: two parallel FM voices. Modal FL+MUL_mod+TL_car shows the "
        "default Genesis patch grammar — often max (or high) feedback on M1 with a "
        "usable carrier level so the voice still cuts on small TVs."
    ),
    2: (
        "Alg.2 stacks modulation into one carrier (C2). The modal terna tends to push "
        "richer, more intertwined spectra — denser leads/basses when composers leave the Alg.4 comfort zone."
    ),
    5: (
        "Alg.5: one modulator (M1) feeds multiple carriers — the Pulseman-style brand. "
        "A sharp modal combo means a shared wiring habit: bright, harmonically busy patches from a single mod source."
    ),
    0: (
        "Alg.0 is fully serial (1→2→3→4). Modal choices often keep the final carrier audible while "
        "earlier ops sculpt harmonics — a more 'chained' FM colour than the two-voice Alg.4 default."
    ),
    7: (
        "Alg.7 is mostly additive; feedback on M1 becomes the main spice. The modal terna here "
        "often reads as FL-driven character with carriers mixed by TL — less classic FM stack, more organ/pad grit."
    ),
}


def pick_exemplars(df: pd.DataFrame, stars: list[dict], per_star: int = 2) -> pd.DataFrame:
    rows = []
    for i, star in enumerate(stars, start=1):
        con, fl, mul, tl = int(star["CON"]), int(star["FL"]), int(star["MUL_mod"]), int(star["TL_car"])
        match = df[
            (df["CON"] == con)
            & (df["FL"] == fl)
            & (df["MUL_mod"] == mul)
            & (df["TL_car"] == tl)
        ]
        # diversify games
        picked = match.drop_duplicates(subset=["Game"]).head(per_star)
        if len(picked) < per_star:
            picked = match.head(per_star)
        for j, (_, p) in enumerate(picked.iterrows(), start=1):
            op_payload = {}
            for op in ("M1", "C1", "M2", "C2"):
                op_payload[op.lower()] = {
                    "ar": int(p[f"{op}_AR"]),
                    "d1r": int(p[f"{op}_D1R"]),
                    "d2r": int(p[f"{op}_D2R"]),
                    "rr": int(p[f"{op}_RR"]),
                    "d1l": int(p[f"{op}_D1L"]),
                    "tl": int(p[f"{op}_TL"]),
                    "ks": int(p[f"{op}_KS"]),
                    "mul": int(p[f"{op}_MUL"]),
                    "dt1": int(p[f"{op}_DT1"]),
                    "ams_en": int(p[f"{op}_AMS-EN"]),
                }
            rows.append(
                {
                    "star_id": i,
                    "exemplar": j,
                    "CON": con,
                    "FL": fl,
                    "MUL_mod": mul,
                    "TL_car": tl,
                    "Game": p["Game"],
                    "Name": p["Name"],
                    "Filename": p["Filename"],
                    "topology": ROLE_BY_CON[con]["label"],
                    "narrative": STAR_NARRATIVE.get(con, ""),
                    "share_within_con": star["share_within_con"],
                    "aiff": f"star{i}_ex{j}_con{con}_fl{fl}_mul{mul}_tl{tl}.aiff",
                    "params": {
                        "algorithm": con,
                        "feedback": fl,
                        "ams": int(p["AMS"]),
                        "pms": int(p["PMS"]),
                        "lfrq": int(p["LFRQ"]),
                        "operators": op_payload,
                    },
                }
            )
    return pd.DataFrame(rows)


def export_param_modes(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for con, sub in df.groupby("CON"):
        role = ROLE_BY_CON[int(con)]
        for col in ["FL", "MUL_mod", "TL_mod", "AR_mod", "MUL_car", "TL_car", "AR_car"]:
            mode = int(sub[col].mode().iloc[0])
            rows.append(
                {
                    "CON": int(con),
                    "param": col,
                    "mode": mode,
                    "n": len(sub),
                    "primary_mod": role["primary_mod"],
                    "primary_car": role["primary_car"],
                }
            )
    return pd.DataFrame(rows)


def main():
    ART.mkdir(exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    df = load_corpus()
    df = add_role_columns(df)
    print("Role columns added. CON counts:\n", df["CON"].value_counts().sort_index())

    plot_key_histos(df)

    modes = export_param_modes(df)
    modes.to_csv(ART / "con_param_modes.csv", index=False)

    combos = modal_combos(df)
    combos.to_csv(ART / "con_star_combos.csv", index=False)

    stars = select_stars(combos)
    exemplars = pick_exemplars(df, stars, per_star=2)
    # flatten for CSV (drop nested params)
    exemplars.drop(columns=["params"]).to_csv(ART / "con_exemplars.csv", index=False)

    summary = {
        "n_presets": int(len(df)),
        "source": str(DATA_PATH.relative_to(ROOT)),
        "dedup": "drop_duplicates on non-TL params within Filename",
        "role_by_con": ROLE_BY_CON,
        "star_definition": "Within each CON: modal (FL, MUL_primary_mod, TL_primary_car)",
        "stars": [
            {
                **{k: (float(v) if isinstance(v, (np.floating,)) else int(v) if isinstance(v, (np.integer,)) else v)
                   for k, v in s.items()},
                "narrative": STAR_NARRATIVE.get(int(s["CON"]), ""),
            }
            for s in stars
        ],
        "exemplars": [],
    }
    for _, ex in exemplars.iterrows():
        summary["exemplars"].append(
            {
                "star_id": int(ex["star_id"]),
                "exemplar": int(ex["exemplar"]),
                "CON": int(ex["CON"]),
                "FL": int(ex["FL"]),
                "MUL_mod": int(ex["MUL_mod"]),
                "TL_car": int(ex["TL_car"]),
                "Game": ex["Game"],
                "Name": ex["Name"],
                "Filename": ex["Filename"],
                "topology": ex["topology"],
                "narrative": ex["narrative"],
                "share_within_con": float(ex["share_within_con"]),
                "aiff": ex["aiff"],
                "params": ex["params"],
            }
        )

    out_json = ART / "con_eda_summary.json"
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("wrote", out_json.relative_to(ROOT))
    print("Stars:")
    for s in summary["stars"]:
        print(
            f"  CON={s['CON']} FL={s['FL']} MUL_mod={s['MUL_mod']} TL_car={s['TL_car']} "
            f"share={s['share_within_con']:.1%} n={s['n_con']}"
        )


if __name__ == "__main__":
    main()
