"""Generate paper figures into TISMIR-SoundSimilarity-LaTeX/figures/.

Called by ``dafm figures`` / ``make figures``. Each plot reads from
``artifacts/results`` (and related parquet/npz) when present; missing inputs
are skipped with a clear status instead of failing the whole batch.

No fabricated numerical results are drawn: if an experiment artifact is absent,
we record ``skipped`` and leave the previous file untouched (or omit creation).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .paths import PAPER_DIR, RESULTS_DIR, ensure_dirs

FIGURES_DIR = PAPER_DIR / "figures"
TABLES_DIR = PAPER_DIR / "tables"


def _ensure_paper_dirs() -> None:
    ensure_dirs()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)


def _result_path(*parts: str) -> Path:
    return RESULTS_DIR.joinpath(*parts)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _load_parquet(path: Path) -> pd.DataFrame | None:
    if not path.is_file():
        return None
    return pd.read_parquet(path)


def _savefig(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, bbox_inches="tight")
    plt.close()


def fig_e1_tl_carrier_vs_modulator() -> dict[str, Any]:
    """E1: modulator vs carrier TL distance distributions."""
    out = FIGURES_DIR / "e1_tl_carrier_vs_modulator.pdf"
    candidates = [
        _result_path("e1_tl_carrier_vs_modulator.parquet"),
        _result_path("e1", "distances.parquet"),
        _result_path("e1.json"),
    ]
    df = None
    meta = None
    for c in candidates:
        if c.suffix == ".json":
            meta = _load_json(c)
        else:
            df = _load_parquet(c)
        if df is not None or meta is not None:
            break
    if df is None and meta is None:
        return {"figure": out.name, "status": "skipped", "reason": "missing E1 artifacts"}

    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    if df is not None and {"group", "distance"}.issubset(df.columns):
        for name, sub in df.groupby("group"):
            ax.hist(sub["distance"], bins=40, alpha=0.5, density=True, label=str(name))
        ax.legend(frameon=False)
        ax.set_xlabel("Audio / feature distance")
        ax.set_ylabel("Density")
    elif meta is not None:
        # Structured summary without inventing per-sample values.
        labels = list(meta.get("group_labels", ["carrier_tl", "modulator_tl"]))
        means = meta.get("group_means")
        if means is None:
            return {
                "figure": out.name,
                "status": "skipped",
                "reason": "E1 JSON lacks plottable fields",
            }
        ax.bar(labels, means, color=["#4c6a8a", "#c47b5a"])
        ax.set_ylabel("Mean distance (from artifacts)")
    else:
        return {
            "figure": out.name,
            "status": "skipped",
            "reason": "E1 artifact schema unrecognized",
        }
    ax.set_title("E1: carrier TL vs modulator TL")
    _savefig(out)
    return {"figure": out.name, "status": "wrote", "path": str(out)}


def fig_e2_perturbation_sensitivity() -> dict[str, Any]:
    """E2: per-parameter sensitivity curves."""
    out = FIGURES_DIR / "e2_perturbation_sensitivity.pdf"
    path = _result_path("e2_perturbation_sensitivity.parquet")
    alt = _result_path("e2", "sensitivity.parquet")
    df = _load_parquet(path) or _load_parquet(alt)
    if df is None:
        return {"figure": out.name, "status": "skipped", "reason": "missing E2 artifacts"}
    need = {"param", "delta", "distance"}
    if not need.issubset(df.columns):
        return {"figure": out.name, "status": "skipped", "reason": "E2 schema unrecognized"}

    fig, ax = plt.subplots(figsize=(6.0, 3.6))
    # Plot top-N params by mean absolute effect to keep the figure readable.
    rank = (
        df.groupby("param")["distance"]
        .mean()
        .abs()
        .sort_values(ascending=False)
        .head(12)
        .index
    )
    sub = df[df["param"].isin(rank)]
    for param, g in sub.groupby("param"):
        g = g.sort_values("delta")
        ax.plot(g["delta"], g["distance"], marker="o", ms=3, label=str(param))
    ax.axhline(0.0, color="0.5", lw=0.6)
    ax.set_xlabel("Parameter delta")
    ax.set_ylabel("Mean distance")
    ax.set_title("E2: perturbation sensitivity (top parameters)")
    ax.legend(fontsize=7, ncol=2, frameon=False)
    _savefig(out)
    return {"figure": out.name, "status": "wrote", "path": str(out)}


def fig_spaces_overview() -> dict[str, Any]:
    """2D overview of one audio space if a projection artifact exists."""
    out = FIGURES_DIR / "spaces_overview.pdf"
    candidates = [
        _result_path("spaces_umap.parquet"),
        _result_path("spaces", "umap.parquet"),
        _result_path("e4_rank_correlation.json"),
    ]
    df = None
    meta = None
    for c in candidates:
        if c.suffix == ".json":
            meta = _load_json(c)
        else:
            df = _load_parquet(c)
        if df is not None or meta is not None:
            break
    if df is None and meta is None:
        return {"figure": out.name, "status": "skipped", "reason": "missing space artifacts"}

    fig, ax = plt.subplots(figsize=(5.2, 4.2))
    if df is not None and {"x", "y"}.issubset(df.columns):
        color = df["label"] if "label" in df.columns else None
        if color is not None:
            for lab, g in df.groupby("label"):
                ax.scatter(g["x"], g["y"], s=4, alpha=0.5, label=str(lab))
            ax.legend(markerscale=3, fontsize=7, frameon=False)
        else:
            ax.scatter(df["x"], df["y"], s=3, alpha=0.4, c="#3d5a73")
        ax.set_xlabel("Dim 1")
        ax.set_ylabel("Dim 2")
        ax.set_title("Audio-space overview")
    elif meta is not None and "spearman_by_condition" in meta:
        conds = list(meta["spearman_by_condition"].keys())
        vals = [meta["spearman_by_condition"][k] for k in conds]
        ax.barh(conds, vals, color="#3d5a73")
        ax.set_xlabel("Spearman rho (from artifacts)")
        ax.set_title("E4: rank correlation summary")
    else:
        plt.close()
        return {
            "figure": out.name,
            "status": "skipped",
            "reason": "space artifact schema unrecognized",
        }
    _savefig(out)
    return {"figure": out.name, "status": "wrote", "path": str(out)}


def fig_e5_mfccd() -> dict[str, Any]:
    """E5: MFCCD distribution with optional published threshold lines."""
    out = FIGURES_DIR / "e5_mfccd.pdf"
    path = _result_path("e5_mfccd.parquet")
    alt = _result_path("e5", "mfccd.parquet")
    df = _load_parquet(path) or _load_parquet(alt)
    meta = _load_json(_result_path("e5_mfccd.json")) or _load_json(
        _result_path("e5", "summary.json")
    )
    if df is None and meta is None:
        return {"figure": out.name, "status": "skipped", "reason": "missing E5 artifacts"}

    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    if df is not None and "mfccd" in df.columns:
        ax.hist(df["mfccd"].to_numpy(), bins=50, color="#3d5a73", alpha=0.85)
        ax.set_xlabel("MFCCD")
        ax.set_ylabel("Count")
    elif meta is not None and "histogram" in meta:
        edges = np.asarray(meta["histogram"]["edges"])
        counts = np.asarray(meta["histogram"]["counts"])
        ax.bar(edges[:-1], counts, width=np.diff(edges), align="edge", color="#3d5a73")
        ax.set_xlabel("MFCCD")
        ax.set_ylabel("Count")
    else:
        plt.close()
        return {"figure": out.name, "status": "skipped", "reason": "E5 schema unrecognized"}

    for thr in (10.0, 15.0):
        ax.axvline(thr, color="#c47b5a", ls="--", lw=1.0)
    ax.set_title("E5: MFCCD (thresholds from published anchors)")
    _savefig(out)
    return {"figure": out.name, "status": "wrote", "path": str(out)}


FIGURE_BUILDERS: list[tuple[str, Callable[[], dict[str, Any]]]] = [
    ("e1_tl_carrier_vs_modulator", fig_e1_tl_carrier_vs_modulator),
    ("e2_perturbation_sensitivity", fig_e2_perturbation_sensitivity),
    ("spaces_overview", fig_spaces_overview),
    ("e5_mfccd", fig_e5_mfccd),
]


def generate_all() -> dict[str, Any]:
    """Run all figure builders; never raise on missing results."""
    _ensure_paper_dirs()
    reports: list[dict[str, Any]] = []
    for name, fn in FIGURE_BUILDERS:
        try:
            reports.append({"name": name, **fn()})
        except Exception as exc:  # defensive: one bad plot must not abort the paper batch
            reports.append(
                {
                    "name": name,
                    "status": "error",
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            )
    wrote = sum(1 for r in reports if r.get("status") == "wrote")
    skipped = sum(1 for r in reports if r.get("status") == "skipped")
    return {
        "figures_dir": str(FIGURES_DIR),
        "n_wrote": wrote,
        "n_skipped": skipped,
        "n_error": sum(1 for r in reports if r.get("status") == "error"),
        "reports": reports,
        "note": (
            "TODO: insert numerical claims in the paper only from artifacts/results; "
            "skipped figures mean those artifacts are not ready yet."
        ),
    }
