"""Compare hardware vs emulator geometry with a Mantel test (Phase 1 stub).

Acceptance (from hardware_validation.yaml) is NOT waveform fidelity. The primary
pre-registered metric is a Spearman Mantel correlation between the two distance
matrices in the study's own feature space. This module implements that test and
reports secondary/tertiary hooks; when features are not yet available (Phase 2)
it exits cleanly with a structured placeholder.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from dafm_audio.paths import HW_DIR, ensure_dirs, load_config


def pairwise_distances(X: np.ndarray) -> np.ndarray:
    """Euclidean condensed-to-square distance matrix."""
    from scipy.spatial.distance import cdist

    return cdist(X, X, metric="euclidean")


def mantel_spearman(
    d_hw: np.ndarray,
    d_emu: np.ndarray,
    *,
    n_permutations: int = 10000,
    seed: int = 0,
) -> dict[str, Any]:
    """Mantel test correlating two square distance matrices (Spearman).

    Uses upper-triangle entries only. Permutations shuffle one matrix's row/column
    order jointly (standard Mantel).
    """
    from scipy.stats import spearmanr

    if d_hw.shape != d_emu.shape or d_hw.ndim != 2 or d_hw.shape[0] != d_hw.shape[1]:
        raise ValueError("distance matrices must be square and equally shaped")
    n = d_hw.shape[0]
    iu = np.triu_indices(n, k=1)
    a = d_hw[iu]
    b = d_emu[iu]
    obs, _ = spearmanr(a, b)

    rng = np.random.default_rng(seed)
    null = np.empty(n_permutations, dtype=np.float64)
    idx = np.arange(n)
    for i in range(n_permutations):
        perm = rng.permutation(idx)
        bp = d_emu[np.ix_(perm, perm)][iu]
        null[i], _ = spearmanr(a, bp)

    # One-sided: larger positive correlation is better.
    p_value = float((np.sum(null >= obs) + 1) / (n_permutations + 1))
    return {
        "correlation": "spearman",
        "r": float(obs),
        "p_value": p_value,
        "n_permutations": n_permutations,
        "n_items": n,
        "null_mean": float(null.mean()),
        "null_std": float(null.std(ddof=1)),
    }


def load_feature_matrices(
    hw_features: Path | None,
    emu_features: Path | None,
) -> tuple[np.ndarray, np.ndarray, list[str]] | None:
    """Load aligned feature tables (parquet/csv) with a shared ``test_id`` column.

    Returns (X_hw, X_emu, test_ids) or None if inputs are missing.
    """
    import pandas as pd

    if hw_features is None or emu_features is None:
        return None
    if not hw_features.exists() or not emu_features.exists():
        return None

    def _read(path: Path) -> pd.DataFrame:
        if path.suffix == ".parquet":
            return pd.read_parquet(path)
        return pd.read_csv(path)

    hw = _read(hw_features)
    emu = _read(emu_features)
    if "test_id" not in hw.columns or "test_id" not in emu.columns:
        raise KeyError("feature tables must include a test_id column")
    merged = hw.merge(emu, on="test_id", suffixes=("_hw", "_emu"))
    if merged.empty:
        raise ValueError("no overlapping test_id between hardware and emulator features")
    ids = merged["test_id"].astype(str).tolist()
    hw_cols = [c for c in merged.columns if c.endswith("_hw")]
    emu_cols = [c.replace("_hw", "_emu") for c in hw_cols]
    X_hw = merged[hw_cols].to_numpy(dtype=np.float64)
    X_emu = merged[emu_cols].to_numpy(dtype=np.float64)
    return X_hw, X_emu, ids


def nearest_neighbour_agreement(d_hw: np.ndarray, d_emu: np.ndarray) -> dict[str, Any]:
    """Fraction of items whose nearest neighbour is unchanged across spaces."""
    n = d_hw.shape[0]
    agree = 0
    for i in range(n):
        hw_nn = int(np.argmin(np.where(np.arange(n) == i, np.inf, d_hw[i])))
        emu_nn = int(np.argmin(np.where(np.arange(n) == i, np.inf, d_emu[i])))
        if hw_nn == emu_nn:
            agree += 1
    return {"agreement": agree / max(n, 1), "n_agree": agree, "n": n}


def compare(
    *,
    hw_features: Path | None = None,
    emu_features: Path | None = None,
    out_path: Path | None = None,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = cfg or load_config("hardware_validation")
    ensure_dirs()
    acceptance = cfg["acceptance"]
    primary = acceptance["primary"]

    loaded = load_feature_matrices(hw_features, emu_features)
    if loaded is None:
        report = {
            "status": "features_missing",
            "message": (
                "Hardware/emulator feature matrices are not available yet. "
                "Phase 2 extracts descriptors; re-run this script with "
                "--hw-features and --emu-features pointing at aligned tables."
            ),
            "acceptance": {
                "metric": primary["metric"],
                "correlation": primary["correlation"],
                "threshold": primary["threshold"],
                "preregistered": primary["preregistered"],
                "n_permutations": primary["n_permutations"],
            },
            "diagnostics_reported_separately": acceptance.get(
                "report_diagnostics_separately", True
            ),
        }
    else:
        X_hw, X_emu, ids = loaded
        d_hw = pairwise_distances(X_hw)
        d_emu = pairwise_distances(X_emu)
        mantel = mantel_spearman(
            d_hw,
            d_emu,
            n_permutations=int(primary["n_permutations"]),
        )
        nn = nearest_neighbour_agreement(d_hw, d_emu)
        passed = mantel["r"] >= float(primary["threshold"])
        report = {
            "status": "ok",
            "test_ids": ids,
            "mantel": mantel,
            "threshold": float(primary["threshold"]),
            "passed": passed,
            "nearest_neighbour": nn,
            "secondary": acceptance.get("secondary"),
            "tertiary": acceptance.get("tertiary"),
            "note": (
                "Secondary per-descriptor relative errors require Phase 2 descriptor "
                "columns; hook reserved."
            ),
        }

    out_path = out_path or (HW_DIR / "compare_hw_emu.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mantel comparison hardware vs emulator")
    parser.add_argument("--hw-features", type=Path, default=None)
    parser.add_argument("--emu-features", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    report = compare(
        hw_features=args.hw_features,
        emu_features=args.emu_features,
        out_path=args.out,
    )
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
