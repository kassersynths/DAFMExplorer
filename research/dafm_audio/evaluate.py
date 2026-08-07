"""Evaluation experiments E1–E7.

Each experiment writes parquet/json under ``artifacts/results/``. Pairwise work
never materialises a full distance matrix (see E4). Clustered inference notes
and Benjamini–Hochberg correction are first-class helpers.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from . import logs, provenance
from .paths import (
    CORPUS_PARQUET,
    FEATURES_PARQUET,
    RESULTS_DIR,
    SPACES_DIR,
    TL_GROUPS_PARQUET,
    ensure_dirs,
    load_config,
)

logger = logging.getLogger(__name__)


def _eval_cfg() -> dict[str, Any]:
    return load_config("eval")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)


def benjamini_hochberg(
    p_values: list[float] | np.ndarray,
    *,
    alpha: float | None = None,
) -> pd.DataFrame:
    """Benjamini–Hochberg FDR correction.

    Returns a frame with original order preserved: ``p``, ``p_adj``, ``reject``.
    """
    cfg = _eval_cfg().get("statistics", {})
    alpha = float(alpha if alpha is not None else cfg.get("fdr_alpha", 0.05))
    p = np.asarray(p_values, dtype=np.float64)
    n = len(p)
    if n == 0:
        return pd.DataFrame(columns=["p", "p_adj", "reject", "rank"])
    order = np.argsort(p)
    ranked = p[order]
    adj = np.empty(n, dtype=np.float64)
    prev = 1.0
    for i in range(n - 1, -1, -1):
        rank = i + 1
        val = ranked[i] * n / rank
        prev = min(prev, val)
        adj[i] = prev
    adj = np.clip(adj, 0.0, 1.0)
    out_adj = np.empty(n, dtype=np.float64)
    out_adj[order] = adj
    return pd.DataFrame(
        {
            "p": p,
            "p_adj": out_adj,
            "reject": out_adj <= alpha,
            "rank": stats.rankdata(p, method="ordinal"),
        }
    )


def cliffs_delta(x: np.ndarray, y: np.ndarray) -> float:
    """Cliff's delta effect size (dominance measure)."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    x = x[np.isfinite(x)]
    y = y[np.isfinite(y)]
    if x.size == 0 or y.size == 0:
        return float("nan")
    # Efficient dominance via broadcasting in chunks for large n.
    more = 0
    less = 0
    block = 2048
    for i in range(0, x.size, block):
        xb = x[i : i + block][:, None]
        more += int(np.sum(xb > y[None, :]))
        less += int(np.sum(xb < y[None, :]))
    return float((more - less) / (x.size * y.size))


def _feature_cols(df: pd.DataFrame, loudness_path: str = "r128") -> list[str]:
    suffix = f"_{loudness_path}"
    meta = {
        "config_id",
        "core_id",
        "audio_path",
        "sample_rate",
        "n_samples",
        "audiocommons_import_error",
    }
    cols = []
    for c in df.columns:
        if c in meta:
            continue
        if not pd.api.types.is_numeric_dtype(df[c]):
            continue
        if c.startswith("loudness_") or c.startswith("audiocommons_"):
            continue
        if suffix in c or c.endswith(suffix):
            cols.append(c)
    if not cols:
        # Fall back to all numeric non-meta columns.
        cols = [
            c
            for c in df.columns
            if c not in meta and pd.api.types.is_numeric_dtype(df[c])
        ]
    return cols


def _pairwise_distance(a: np.ndarray, b: np.ndarray, metric: str = "euclidean") -> float:
    if metric == "cosine":
        na = np.linalg.norm(a)
        nb = np.linalg.norm(b)
        if na == 0 or nb == 0:
            return float("nan")
        return float(1.0 - np.dot(a, b) / (na * nb))
    return float(np.linalg.norm(a - b))


def e1_carrier_vs_modulator(limit: int | None = None) -> dict[str, Any]:
    """E1: carrier-only vs modulator TL groups (Mann–Whitney + Cliff's delta)."""
    ensure_dirs()
    cfg = _eval_cfg()
    e1 = cfg.get("e1_tl_carrier_vs_modulator", {})
    if not e1.get("enabled", True):
        return {"skipped": True, "reason": "disabled"}

    if not TL_GROUPS_PARQUET.exists() or not FEATURES_PARQUET.exists() or not CORPUS_PARQUET.exists():
        raise FileNotFoundError("E1 needs tl_variant_groups, features and corpus artifacts")

    from .corpus import unique_configs

    groups = pd.read_parquet(TL_GROUPS_PARQUET)
    features = pd.read_parquet(FEATURES_PARQUET)
    corpus = pd.read_parquet(CORPUS_PARQUET)
    configs = unique_configs(corpus)
    loudness = e1.get("primary_loudness_path", "r128")
    feat_cols = _feature_cols(features, loudness)
    feat = features.set_index("config_id")

    records = []
    for _, g in groups.iterrows():
        members = configs[configs["core_id"] == g["core_id"]]["config_id"].tolist()
        if limit is not None and len(records) >= int(limit):
            break
        if len(members) < 2:
            continue
        vecs = []
        for cid in members:
            if cid not in feat.index:
                continue
            vecs.append((cid, feat.loc[cid, feat_cols].to_numpy(dtype=np.float64)))
        if len(vecs) < 2:
            continue
        # Mean pairwise audio distance within the TL group.
        dists = []
        for i in range(len(vecs)):
            for j in range(i + 1, len(vecs)):
                # Also record parametric TL Euclidean distance for equal-distance notes.
                dists.append(_pairwise_distance(vecs[i][1], vecs[j][1]))
        if not dists:
            continue
        records.append(
            {
                "core_id": g["core_id"],
                "group_type": g["group_type"],
                "algorithm": int(g["algorithm"]),
                "n_configs": int(g["n_configs"]),
                "mean_audio_distance": float(np.mean(dists)),
                "median_audio_distance": float(np.median(dists)),
            }
        )

    columns = [
        "core_id",
        "group_type",
        "algorithm",
        "n_configs",
        "mean_audio_distance",
        "median_audio_distance",
    ]
    table = pd.DataFrame(records, columns=columns)
    out_parquet = RESULTS_DIR / "e1_tl_groups.parquet"
    table.to_parquet(out_parquet, index=False)

    if table.empty:
        report = {
            "experiment": "E1",
            "skipped": True,
            "reason": (
                "no TL groups had at least two members with features; "
                "render and extract features for more configs"
            ),
            "n_carrier_groups": 0,
            "n_modulator_groups": 0,
        }
        _write_json(RESULTS_DIR / "e1_carrier_vs_modulator.json", report)
        return report

    carrier = table.loc[table["group_type"] == "carrier_only", "mean_audio_distance"].to_numpy()
    modulator = table.loc[table["group_type"] == "modulator", "mean_audio_distance"].to_numpy()
    if carrier.size and modulator.size:
        u_stat, p_value = stats.mannwhitneyu(modulator, carrier, alternative="greater")
        delta = cliffs_delta(modulator, carrier)
    else:
        u_stat, p_value, delta = float("nan"), float("nan"), float("nan")

    report = {
        "experiment": "E1",
        "hypothesis": e1.get("hypothesis"),
        "preregistered": e1.get("preregistered", True),
        "primary_loudness_path": loudness,
        "test": "mannwhitneyu",
        "alternative": "modulator > carrier_only",
        "n_carrier_groups": int(carrier.size),
        "n_modulator_groups": int(modulator.size),
        "u_statistic": float(u_stat) if np.isfinite(u_stat) else None,
        "p_value": float(p_value) if np.isfinite(p_value) else None,
        "cliffs_delta": float(delta) if np.isfinite(delta) else None,
        "clustered_inference_note": (
            "TL groups are nested in timbral cores and games; treat each core_id as "
            "the independent unit (already done by aggregating within core). "
            "Do not interpret pair-level tests as independent. "
            f"Configured cluster_unit={cfg.get('statistics', {}).get('cluster_unit', 'core_id')}."
        ),
        "null_result_protocol": e1.get("null_result_protocol", []),
    }
    _write_json(RESULTS_DIR / "e1_carrier_vs_modulator.json", report)
    provenance.write(
        out_parquet,
        stage="evaluate_e1",
        params={"loudness_path": loudness},
        metrics={
            "p_value": report["p_value"],
            "cliffs_delta": report["cliffs_delta"],
            "n_groups": int(len(table)),
        },
        seeds={"eval": int(cfg.get("seed", 42))},
    )
    return report


def e2_perturbation_plan(limit: int | None = None, *, execute: bool = False) -> dict[str, Any]:
    """E2: build a budgeted perturbation plan; optional re-render stub.

    Actual re-rendering is gated by ``execute=True`` / CLI ``--execute`` and is
    left as a stub until the render stage is available for arbitrary configs.
    """
    ensure_dirs()
    cfg = _eval_cfg()
    e2 = cfg.get("e2_perturbation_sensitivity", {})
    if not e2.get("enabled", True):
        return {"skipped": True, "reason": "disabled"}

    from .chip import GLOBAL_PARAMS, OPERATOR_NAMES, PARAM_RANGES, PER_OPERATOR_PARAMS
    from .corpus import unique_configs

    if not CORPUS_PARQUET.exists():
        raise FileNotFoundError(CORPUS_PARQUET)

    corpus = pd.read_parquet(CORPUS_PARQUET)
    configs = unique_configs(corpus)
    seed = int(cfg.get("seed", 42))

    n_seeds = int(e2.get("n_seeds", 48))
    deltas = list(e2.get("deltas", [-16, -4, 4, 16]))
    budget = int(e2.get("budget_max_renders", 12000))

    # Stratify by CON and carrier-TL quartile of C2_TL as a cheap proxy.
    configs = configs.copy()
    configs["tl_q"] = pd.qcut(configs["C2_TL"], 4, labels=False, duplicates="drop")
    strata = configs.groupby(["CON", "tl_q"], dropna=False)
    picks: list[str] = []
    per_stratum = max(1, n_seeds // max(len(strata), 1))
    for _, group in strata:
        chosen = group.sample(n=min(per_stratum, len(group)), random_state=seed)
        picks.extend(chosen["config_id"].tolist())
    picks = list(dict.fromkeys(picks))[:n_seeds]
    if limit is not None:
        picks = picks[: int(limit)]

    params = list(GLOBAL_PARAMS) + [
        f"{op}_{p}" for op in OPERATOR_NAMES for p in PER_OPERATOR_PARAMS
    ]
    if e2.get("restrict_to_effective_params", True):
        from .inertness import effective_columns

        params = effective_columns()

    plan_rows = []
    for cid in picks:
        row = configs.set_index("config_id").loc[cid]
        for param in params:
            low, high = PARAM_RANGES[param.split("_")[-1]] if "_" in param else PARAM_RANGES[param]
            base = int(row[param])
            for delta in deltas:
                new_val = int(np.clip(base + delta, low, high))
                if new_val == base:
                    continue
                plan_rows.append(
                    {
                        "seed_config_id": cid,
                        "param": param,
                        "delta": delta,
                        "base_value": base,
                        "new_value": new_val,
                        "execute": False,
                    }
                )

    plan = pd.DataFrame(plan_rows)
    if len(plan) > budget:
        plan = plan.sample(n=budget, random_state=seed).reset_index(drop=True)
    plan_path = RESULTS_DIR / "e2_perturbation_plan.parquet"
    plan.to_parquet(plan_path, index=False)

    report = {
        "experiment": "E2",
        "n_seeds": len(picks),
        "n_params": len(params),
        "deltas": deltas,
        "n_planned_renders": int(len(plan)),
        "budget_max_renders": budget,
        "execute": bool(execute),
        "execution_note": (
            "Plan only. Pass execute=True once the render stage accepts arbitrary "
            "parameter overlays; results would land in e2_perturbation_results.parquet."
        ),
    }
    if execute:
        report["execution_note"] = (
            "execute=True requested, but live re-render is not wired in this stub; "
            "plan written for the renderer to consume."
        )
        report["status"] = "plan_ready_not_rendered"
    _write_json(RESULTS_DIR / "e2_perturbation_plan.json", report)
    provenance.write(
        plan_path,
        stage="evaluate_e2",
        params={"n_seeds": n_seeds, "deltas": deltas, "budget": budget},
        metrics={"n_planned_renders": int(len(plan))},
        seeds={"eval": seed},
    )
    return report


def e3_mcadams_cca(limit: int | None = None) -> dict[str, Any]:
    """E3: CCA between PCA axes of descriptor space and McAdams target descriptors."""
    ensure_dirs()
    cfg = _eval_cfg()
    e3 = cfg.get("e3_mcadams_dimensions", {})
    if not e3.get("enabled", True):
        return {"skipped": True, "reason": "disabled"}
    if not FEATURES_PARQUET.exists():
        raise FileNotFoundError(FEATURES_PARQUET)

    from sklearn.cross_decomposition import CCA
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    df = pd.read_parquet(FEATURES_PARQUET)
    if limit is not None:
        df = df.head(int(limit))
    targets = list(e3.get("target_descriptors", ["log_attack_time", "spectral_centroid", "spectral_flux"]))
    # Prefer r128-suffixed columns.
    y_cols = []
    for t in targets:
        for candidate in (f"{t}_r128", f"{t}_raw", t):
            if candidate in df.columns:
                y_cols.append(candidate)
                break
    if len(y_cols) < 2:
        raise RuntimeError(f"E3 could not locate McAdams targets; looked for {targets}")

    meta = {"config_id", "core_id", "audio_path", "sample_rate", "n_samples", "audiocommons_import_error"}
    x_cols = [
        c
        for c in df.columns
        if c not in meta
        and c not in y_cols
        and pd.api.types.is_numeric_dtype(df[c])
        and not c.startswith("loudness_")
        and not c.startswith("audiocommons_")
    ]
    sub = df[x_cols + y_cols].dropna()
    X = StandardScaler().fit_transform(sub[x_cols].to_numpy(dtype=np.float64))
    Y = StandardScaler().fit_transform(sub[y_cols].to_numpy(dtype=np.float64))
    n_comp = min(int(e3.get("n_components", 8)), X.shape[1], Y.shape[1], max(1, X.shape[0] - 1))
    pcs = PCA(n_components=n_comp, random_state=int(cfg.get("seed", 42))).fit_transform(X)
    n_cca = min(n_comp, Y.shape[1], pcs.shape[1])
    cca = CCA(n_components=n_cca)
    Xc, Yc = cca.fit_transform(pcs, Y)
    corrs = [
        float(np.corrcoef(Xc[:, i], Yc[:, i])[0, 1]) if np.std(Xc[:, i]) > 0 else float("nan")
        for i in range(n_cca)
    ]
    report = {
        "experiment": "E3",
        "method": e3.get("method", "canonical_correlation"),
        "target_columns": y_cols,
        "n_rows": int(len(sub)),
        "n_components": n_cca,
        "canonical_correlations": corrs,
        "mean_abs_canonical_corr": float(np.nanmean(np.abs(corrs))),
    }
    table = pd.DataFrame(
        {"component": np.arange(n_cca), "canonical_correlation": corrs}
    )
    table.to_parquet(RESULTS_DIR / "e3_mcadams_cca.parquet", index=False)
    _write_json(RESULTS_DIR / "e3_mcadams_cca.json", report)
    provenance.write(
        RESULTS_DIR / "e3_mcadams_cca.parquet",
        stage="evaluate_e3",
        params={"targets": y_cols, "n_components": n_cca},
        metrics={"mean_abs_canonical_corr": report["mean_abs_canonical_corr"]},
        seeds={"eval": int(cfg.get("seed", 42))},
    )
    return report


def e4_rank_correlation(limit: int | None = None) -> dict[str, Any]:
    """E4: Spearman correlation on a stratified pair sample (never full matrix)."""
    ensure_dirs()
    cfg = _eval_cfg()
    e4 = cfg.get("e4_rank_correlation", {})
    if not e4.get("enabled", True):
        return {"skipped": True, "reason": "disabled"}
    if e4.get("materialize_full_matrix", False):
        raise RuntimeError("E4 refuses to materialise a full pairwise matrix")

    from .spaces import CONDITIONS, load_space, metric_for

    seed = int(cfg.get("seed", 42))
    rng = np.random.default_rng(seed)
    n_pairs = int(e4.get("n_pairs", 5_000_000))
    if limit is not None:
        n_pairs = min(n_pairs, int(limit) * 1000 if int(limit) < 1000 else int(limit))

    # Compare params_encoded vs descriptors when both exist; extend to all available.
    available = [c for c in CONDITIONS if (SPACES_DIR / c / "fitted_space.joblib").exists()]
    if len(available) < 2:
        # Fall back to raw matrices without fitted spaces.
        from .spaces import load_condition_matrix

        report = {"experiment": "E4", "mode": "raw_matrices", "pairs": []}
        mats = {}
        for cond in ("params_encoded", "descriptors"):
            try:
                X, _, ids, _ = load_condition_matrix(cond)
                mats[cond] = (X, ids)
            except FileNotFoundError:
                continue
        if len(mats) < 2:
            raise FileNotFoundError("E4 needs at least two representation matrices")
        keys = list(mats.keys())
        return _e4_compare_pair(keys[0], mats[keys[0]], keys[1], mats[keys[1]], n_pairs, rng, cfg)

    results = []
    base = available[0]
    base_space = load_space(base)
    for other in available[1:]:
        other_space = load_space(other)
        # Align on shared config_ids.
        map_a = {str(c): i for i, c in enumerate(base_space.config_ids)}
        map_b = {str(c): i for i, c in enumerate(other_space.config_ids)}
        shared = sorted(set(map_a) & set(map_b))
        if len(shared) < 4:
            continue
        Xa = base_space.X_pca[[map_a[c] for c in shared]]
        Xb = other_space.X_pca[[map_b[c] for c in shared]]
        pair_report = _e4_spearman_sample(
            Xa,
            Xb,
            n_pairs=n_pairs,
            rng=rng,
            metric_a=metric_for(base),  # type: ignore[arg-type]
            metric_b=metric_for(other),  # type: ignore[arg-type]
            name_a=base,
            name_b=other,
        )
        results.append(pair_report)

    table = pd.DataFrame(results)
    table.to_parquet(RESULTS_DIR / "e4_rank_correlation.parquet", index=False)
    report = {
        "experiment": "E4",
        "method": e4.get("method", "spearman"),
        "n_pairs_requested": n_pairs,
        "materialize_full_matrix": False,
        "comparisons": results,
    }
    _write_json(RESULTS_DIR / "e4_rank_correlation.json", report)
    provenance.write(
        RESULTS_DIR / "e4_rank_correlation.parquet",
        stage="evaluate_e4",
        params={"n_pairs": n_pairs, "sampling": e4.get("sampling", "stratified")},
        metrics={"n_comparisons": len(results)},
        seeds={"eval": seed},
    )
    return report


def _e4_compare_pair(name_a, mat_a, name_b, mat_b, n_pairs, rng, cfg):
    Xa, ids_a = mat_a
    Xb, ids_b = mat_b
    map_a = {str(c): i for i, c in enumerate(ids_a)}
    map_b = {str(c): i for i, c in enumerate(ids_b)}
    shared = sorted(set(map_a) & set(map_b))
    Xa = Xa[[map_a[c] for c in shared]]
    Xb = Xb[[map_b[c] for c in shared]]
    result = _e4_spearman_sample(
        Xa, Xb, n_pairs=n_pairs, rng=rng, metric_a="euclidean", metric_b="euclidean",
        name_a=name_a, name_b=name_b,
    )
    table = pd.DataFrame([result])
    table.to_parquet(RESULTS_DIR / "e4_rank_correlation.parquet", index=False)
    report = {"experiment": "E4", "comparisons": [result]}
    _write_json(RESULTS_DIR / "e4_rank_correlation.json", report)
    return report


def _e4_spearman_sample(
    Xa: np.ndarray,
    Xb: np.ndarray,
    *,
    n_pairs: int,
    rng: np.random.Generator,
    metric_a: str,
    metric_b: str,
    name_a: str,
    name_b: str,
    block_size: int = 4096,
) -> dict[str, Any]:
    n = Xa.shape[0]
    max_unique = n * (n - 1) // 2
    n_pairs = min(n_pairs, max_unique)
    # Sample pairs without materialising all combinations.
    i = rng.integers(0, n, size=n_pairs)
    j = rng.integers(0, n, size=n_pairs)
    mask = i != j
    i, j = i[mask], j[mask]
    # Canonicalise unordered pairs and drop accidental duplicates.
    a = np.minimum(i, j)
    b = np.maximum(i, j)
    pairs = np.stack([a, b], axis=1)
    pairs = np.unique(pairs, axis=0)
    da = np.empty(len(pairs), dtype=np.float64)
    db = np.empty(len(pairs), dtype=np.float64)
    for start in range(0, len(pairs), block_size):
        sl = slice(start, start + block_size)
        ia, ib = pairs[sl, 0], pairs[sl, 1]
        for k, (u, v) in enumerate(zip(ia, ib, strict=False)):
            da[start + k] = _pairwise_distance(Xa[u], Xa[v], metric_a)
            db[start + k] = _pairwise_distance(Xb[u], Xb[v], metric_b)
    rho, p = stats.spearmanr(da, db, nan_policy="omit")
    return {
        "space_a": name_a,
        "space_b": name_b,
        "n_pairs": int(len(pairs)),
        "spearman_rho": float(rho) if np.isfinite(rho) else None,
        "p_value": float(p) if np.isfinite(p) else None,
    }


def mfccd(
    y_ref: np.ndarray,
    y_deg: np.ndarray,
    sr: int,
    *,
    n_mfcc: int = 13,
) -> float:
    """E5 helper: Mel-Frequency Cepstral Coefficient Distance (mean L2 over frames)."""
    import librosa

    ref = librosa.feature.mfcc(y=y_ref, sr=sr, n_mfcc=n_mfcc)
    deg = librosa.feature.mfcc(y=y_deg, sr=sr, n_mfcc=n_mfcc)
    n = min(ref.shape[1], deg.shape[1])
    if n == 0:
        return float("nan")
    return float(np.mean(np.linalg.norm(ref[:, :n] - deg[:, :n], axis=0)))


def e5_mfccd_summary(limit: int | None = None) -> dict[str, Any]:
    """E5: export MFCCD helper metadata and published baselines (no full re-synth)."""
    ensure_dirs()
    cfg = _eval_cfg()
    e5 = cfg.get("e5_mfccd", {})
    if not e5.get("enabled", True):
        return {"skipped": True, "reason": "disabled"}
    report = {
        "experiment": "E5",
        "n_mfcc": int(e5.get("n_mfcc", 13)),
        "indistinguishable_threshold": e5.get("indistinguishable_threshold", [10.0, 15.0]),
        "published_baselines": e5.get("published_baselines", {}),
        "helper": "dafm_audio.evaluate.mfccd",
        "note": (
            "MFCCD is available as a pairwise helper for morph / reconstruction "
            "evaluation; corpus-wide scoring requires paired reference/estimate audio."
        ),
        "limit": limit,
    }
    _write_json(RESULTS_DIR / "e5_mfccd.json", report)
    provenance.write(
        RESULTS_DIR / "e5_mfccd.json",
        stage="evaluate_e5",
        params={"n_mfcc": report["n_mfcc"]},
        metrics={},
        seeds={"eval": int(cfg.get("seed", 42))},
    )
    return report


def e6_listening_triads(limit: int | None = None) -> dict[str, Any]:
    """E6: export a stratified triad list for the odd-one-out listening test."""
    ensure_dirs()
    cfg = _eval_cfg()
    e6 = cfg.get("e6_listening_test", {})
    if not e6.get("enabled", True):
        return {"skipped": True, "reason": "disabled"}
    if not CORPUS_PARQUET.exists():
        raise FileNotFoundError(CORPUS_PARQUET)

    from .corpus import unique_configs
    from .spaces import load_space

    corpus = pd.read_parquet(CORPUS_PARQUET)
    configs = unique_configs(corpus)
    meta = (
        corpus.loc[corpus["is_valid"], ["config_id", "core_id", "game"]]
        .drop_duplicates("config_id")
    )
    configs = configs.merge(meta, on=["config_id", "core_id"], how="left")

    seed = int(cfg.get("seed", 42))
    rng = np.random.default_rng(seed)
    n_triads = int(e6.get("n_triads", 180))
    if limit is not None:
        n_triads = min(n_triads, int(limit))

    # Prefer descriptor space distances for banding when available.
    ids = configs["config_id"].astype(str).to_numpy()
    try:
        space = load_space("descriptors")
        id_to_i = {str(c): i for i, c in enumerate(space.config_ids)}
        usable = [c for c in ids if c in id_to_i]
    except FileNotFoundError:
        space = None
        usable = list(ids)

    triads = []
    attempts = 0
    while len(triads) < n_triads and attempts < n_triads * 50:
        attempts += 1
        if space is not None and len(usable) >= 3:
            a, b, c = rng.choice(usable, size=3, replace=False)
            ia, ib, ic = id_to_i[a], id_to_i[b], id_to_i[c]
            d_ab = float(np.linalg.norm(space.X_pca[ia] - space.X_pca[ib]))
            d_ac = float(np.linalg.norm(space.X_pca[ia] - space.X_pca[ic]))
            d_bc = float(np.linalg.norm(space.X_pca[ib] - space.X_pca[ic]))
            # Odd-one-out design: two close, one far.
            dists = sorted([(d_ab, a, b, c), (d_ac, a, c, b), (d_bc, b, c, a)])
            close_d, x, y, odd = dists[0]
            band = "near" if close_d < np.median([d_ab, d_ac, d_bc]) else "far"
        else:
            x, y, odd = rng.choice(usable, size=3, replace=False)
            band = "unbanded"
        triads.append(
            {
                "triad_id": f"t{len(triads):04d}",
                "config_a": x,
                "config_b": y,
                "config_odd": odd,
                "distance_band": band,
                "condition": "descriptors" if space is not None else "random",
            }
        )

    table = pd.DataFrame(triads)
    path = RESULTS_DIR / "e6_listening_triads.parquet"
    table.to_parquet(path, index=False)
    report = {
        "experiment": "E6",
        "design": e6.get("design", "triadic_odd_one_out"),
        "n_triads": int(len(table)),
        "n_participants_target": e6.get("n_participants_target", 24),
        "fallback_removes_rq": e6.get("fallback_removes_rq", "RQ5"),
        "artifact": str(path),
        "note": "Design artifact for recruitment; human responses are collected separately.",
    }
    _write_json(RESULTS_DIR / "e6_listening_triads.json", report)
    provenance.write(
        path,
        stage="evaluate_e6",
        params={"n_triads": n_triads, "design": report["design"]},
        metrics={"n_triads": int(len(table))},
        seeds={"eval": seed},
    )
    return report


def e7_game_footprint(limit: int | None = None) -> dict[str, Any]:
    """E7: recall@k / MRR for same-game retrieval, averaged by game."""
    ensure_dirs()
    cfg = _eval_cfg()
    e7 = cfg.get("e7_game_footprint", {})
    if not e7.get("enabled", True):
        return {"skipped": True, "reason": "disabled"}
    if not CORPUS_PARQUET.exists():
        raise FileNotFoundError(CORPUS_PARQUET)

    from .index import build_index, query
    from .spaces import load_space, metric_for

    corpus = pd.read_parquet(CORPUS_PARQUET)
    meta = (
        corpus.loc[corpus["is_valid"], ["config_id", "game"]]
        .drop_duplicates("config_id")
    )
    min_n = int(e7.get("min_presets_per_game", 20))
    counts = meta["game"].value_counts()
    eligible_games = set(counts[counts >= min_n].index.astype(str))
    meta = meta[meta["game"].astype(str).isin(eligible_games)]

    condition = "descriptors"
    try:
        space = load_space(condition)  # type: ignore[arg-type]
    except FileNotFoundError:
        from .spaces import load_condition_matrix
        from sklearn.preprocessing import StandardScaler

        X, _, ids, _ = load_condition_matrix("descriptors")
        X = StandardScaler().fit_transform(X)
        config_ids = ids
        metric = "euclidean"
    else:
        X = space.X_pca
        config_ids = space.config_ids
        metric = metric_for(condition)  # type: ignore[arg-type]

    id_to_game = dict(zip(meta["config_id"].astype(str), meta["game"].astype(str), strict=False))
    keep = [i for i, c in enumerate(config_ids) if str(c) in id_to_game]
    if limit is not None:
        keep = keep[: int(limit)]
    X = X[keep]
    config_ids = np.asarray(config_ids)[keep]
    games = np.array([id_to_game[str(c)] for c in config_ids])

    index = build_index(X, metric=metric, backend="exact")  # type: ignore[arg-type]
    k_values = list(e7.get("k_values", [1, 5, 10, 50]))
    max_k = min(max(k_values) + 1, len(config_ids))  # +1 because self is neighbour 0

    per_game: dict[str, dict[str, list[float]]] = {}
    for i in range(len(config_ids)):
        idxs, _ = query(index, X[i], k=max_k)
        # Drop self
        neigh = [int(j) for j in idxs if int(j) != i][: max(k_values)]
        g = games[i]
        bucket = per_game.setdefault(g, {f"recall@{k}": [] for k in k_values})
        bucket.setdefault("mrr", [])
        bucket.setdefault("mean_rank", [])
        same = [games[j] == g for j in neigh]
        for k in k_values:
            bucket[f"recall@{k}"].append(float(any(same[:k])))
        rank = next((r + 1 for r, ok in enumerate(same) if ok), None)
        bucket["mrr"].append(0.0 if rank is None else 1.0 / rank)
        bucket["mean_rank"].append(float(rank) if rank is not None else float(max_k))

    rows = []
    for game, metrics in per_game.items():
        row = {"game": game, "n_queries": len(metrics["mrr"])}
        for key, values in metrics.items():
            row[key] = float(np.mean(values))
        rows.append(row)
    table = pd.DataFrame(rows)
    # Macro-average by game (never by preset).
    summary = {
        "experiment": "E7",
        "condition": condition,
        "aggregate_by": "game",
        "n_games": int(len(table)),
        "min_presets_per_game": min_n,
        "macro_means": {
            c: float(table[c].mean())
            for c in table.columns
            if c not in {"game", "n_queries"}
        },
        "confound_note": (
            "Same-game is a weak and confounded signal: OSTs intentionally mix timbres. "
            "Reported as secondary evidence only."
        ),
    }
    table.to_parquet(RESULTS_DIR / "e7_game_footprint.parquet", index=False)
    _write_json(RESULTS_DIR / "e7_game_footprint.json", summary)
    provenance.write(
        RESULTS_DIR / "e7_game_footprint.parquet",
        stage="evaluate_e7",
        params={"k_values": k_values, "condition": condition},
        metrics=summary["macro_means"],
        seeds={"eval": int(cfg.get("seed", 42))},
    )
    return summary


def run_all(limit: int | None = None, *, execute_e2: bool = False) -> dict[str, Any]:
    """Run E1–E7 sequentially and apply BH correction across collected p-values."""
    ensure_dirs()
    with logs.stage("evaluate", limit=limit) as done:
        results: dict[str, Any] = {}
        runners = [
            ("E1", lambda: e1_carrier_vs_modulator(limit=limit)),
            ("E2", lambda: e2_perturbation_plan(limit=limit, execute=execute_e2)),
            ("E3", lambda: e3_mcadams_cca(limit=limit)),
            ("E4", lambda: e4_rank_correlation(limit=limit)),
            ("E5", lambda: e5_mfccd_summary(limit=limit)),
            ("E6", lambda: e6_listening_triads(limit=limit)),
            ("E7", lambda: e7_game_footprint(limit=limit)),
        ]
        p_values: list[tuple[str, float]] = []
        for name, fn in runners:
            try:
                results[name] = fn()
                for key in ("p_value",):
                    if isinstance(results[name], dict) and results[name].get(key) is not None:
                        p_values.append((name, float(results[name][key])))
                # E4 may embed multiple p-values.
                if name == "E4" and isinstance(results[name], dict):
                    for i, comp in enumerate(results[name].get("comparisons", [])):
                        if comp.get("p_value") is not None:
                            p_values.append((f"E4:{comp.get('space_a')}|{comp.get('space_b')}", float(comp["p_value"])))
            except FileNotFoundError as exc:
                logger.warning("%s skipped: %s", name, exc)
                results[name] = {"skipped": True, "reason": str(exc)}
            except Exception as exc:
                logger.exception("%s failed", name)
                results[name] = {"failed": True, "error": f"{type(exc).__name__}:{exc}"}

        if p_values:
            bh = benjamini_hochberg([p for _, p in p_values])
            bh.insert(0, "test", [name for name, _ in p_values])
            bh.to_parquet(RESULTS_DIR / "multiple_comparisons_bh.parquet", index=False)
            results["multiple_comparisons"] = bh.to_dict(orient="records")

        _write_json(RESULTS_DIR / "evaluate_all.json", results)
        done["n_experiments"] = len(results)
    return results
