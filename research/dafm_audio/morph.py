"""Invertible PCA morphs in encoded parameter space.

Macro-controls are principal components of the model-space encoding. Reconstruction
always goes ``inverse_transform → from_model_space → clip/validate``. Perceptual
reparameterisation of a path adjusts *speed* along the path (arc length in feature
space when features exist; otherwise parametric arc length) but does **not** change
the geometric path itself — that limitation is intentional and documented.

Audio-guided hybrid level 1 recovers the nearest corpus neighbour in feature space
to the parametric midpoint (retrieval, not generative inversion).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from . import encoding, logs, provenance
from .encoding import DEFAULT_POLICY, EncodingPolicy, ModelSpace
from .paths import CORPUS_PARQUET, FEATURES_PARQUET, MORPH_DIR, ensure_dirs, load_config

logger = logging.getLogger(__name__)


@dataclass
class MorphModel:
    """Fitted morphable PCA over encoded parameters."""

    scaler: StandardScaler
    pca: PCA
    policy: EncodingPolicy
    feature_names: list[str]
    config_ids: np.ndarray
    X_model: np.ndarray
    X_pca: np.ndarray

    def n_components(self) -> int:
        return int(self.pca.n_components_)


def _unique_configs() -> pd.DataFrame:
    from .corpus import unique_configs

    if not CORPUS_PARQUET.exists():
        raise FileNotFoundError(CORPUS_PARQUET)
    return unique_configs(pd.read_parquet(CORPUS_PARQUET))


def fit_morph(
    *,
    n_components: int | float = 0.95,
    policy: EncodingPolicy = DEFAULT_POLICY,
    seed: int = 42,
) -> MorphModel:
    """Fit StandardScaler + PCA on encoded effective parameters."""
    configs = _unique_configs()
    space = encoding.to_model_space(configs, policy)
    scaler = StandardScaler()
    X = scaler.fit_transform(space.matrix)
    pca = PCA(n_components=n_components, random_state=seed, svd_solver="full")
    Z = pca.fit_transform(X)
    return MorphModel(
        scaler=scaler,
        pca=pca,
        policy=policy,
        feature_names=list(space.columns),
        config_ids=configs["config_id"].to_numpy(),
        X_model=space.matrix,
        X_pca=Z,
    )


def reconstruct_registers(model: MorphModel, Z: np.ndarray) -> pd.DataFrame:
    """Map PCA coordinates back to legal register configurations."""
    Z = np.atleast_2d(np.asarray(Z, dtype=np.float64))
    X_scaled = model.pca.inverse_transform(Z)
    X_model = model.scaler.inverse_transform(X_scaled)
    registers = encoding.from_model_space(
        ModelSpace(matrix=X_model, columns=model.feature_names, policy=model.policy)
    )
    ok = encoding.validate_registers(registers)
    if not bool(ok.all()):
        n_bad = int((~ok).sum())
        logger.warning("reconstruct_registers: %d rows failed validation after clip", n_bad)
    return registers


def interpolate(
    model: MorphModel,
    config_a: str,
    config_b: str,
    *,
    n_steps: int = 64,
) -> pd.DataFrame:
    """Linear interpolation between two presets in PCA space, reconstructed to registers."""
    id_to_i = {str(c): i for i, c in enumerate(model.config_ids)}
    if str(config_a) not in id_to_i or str(config_b) not in id_to_i:
        raise KeyError(f"unknown config_id in morph model: {config_a!r} / {config_b!r}")
    za = model.X_pca[id_to_i[str(config_a)]]
    zb = model.X_pca[id_to_i[str(config_b)]]
    ts = np.linspace(0.0, 1.0, int(n_steps))
    path = np.stack([(1 - t) * za + t * zb for t in ts], axis=0)
    registers = reconstruct_registers(model, path)
    registers.insert(0, "t", ts)
    registers.insert(1, "config_a", config_a)
    registers.insert(2, "config_b", config_b)
    return registers


def _feature_lookup() -> tuple[dict[str, np.ndarray], list[str]] | None:
    if not FEATURES_PARQUET.exists():
        return None
    df = pd.read_parquet(FEATURES_PARQUET)
    meta = {
        "config_id",
        "core_id",
        "audio_path",
        "sample_rate",
        "n_samples",
        "audiocommons_import_error",
    }
    cols = [
        c
        for c in df.columns
        if c not in meta
        and pd.api.types.is_numeric_dtype(df[c])
        and not c.startswith("loudness_")
        and not c.startswith("audiocommons_")
        and c.endswith("_r128")
    ]
    if not cols:
        cols = [
            c
            for c in df.columns
            if c not in meta and pd.api.types.is_numeric_dtype(df[c])
        ]
    lookup = {}
    for _, row in df.iterrows():
        vec = row[cols].to_numpy(dtype=np.float64)
        if np.isfinite(vec).all():
            lookup[str(row["config_id"])] = vec
    return lookup, cols


def perceptual_reparameterize(
    model: MorphModel,
    config_a: str,
    config_b: str,
    *,
    n_sample: int = 64,
    n_out: int = 64,
) -> dict[str, Any]:
    """Reparameterise a morph path by cumulative arc length.

    When Family A features exist for the endpoints (and ideally intermediates via
    nearest corpus neighbour), arc length is measured in feature space. Otherwise
    falls back to arc length in PCA parameter space. This corrects *speed*, not
    the path geometry.
    """
    raw = interpolate(model, config_a, config_b, n_steps=n_sample)
    id_to_i = {str(c): i for i, c in enumerate(model.config_ids)}
    za = model.X_pca[id_to_i[str(config_a)]]
    zb = model.X_pca[id_to_i[str(config_b)]]
    ts = raw["t"].to_numpy()
    path_z = np.stack([(1 - t) * za + t * zb for t in ts], axis=0)

    feat = _feature_lookup()
    if feat is not None and str(config_a) in feat[0] and str(config_b) in feat[0]:
        lookup, _ = feat
        # Sample features along the path by nearest corpus neighbour in PCA space.
        points = []
        for z in path_z:
            d = np.linalg.norm(model.X_pca - z[None, :], axis=1)
            nn = str(model.config_ids[int(np.argmin(d))])
            if nn in lookup:
                points.append(lookup[nn])
            else:
                points.append(lookup[str(config_a)])
        pts = np.asarray(points, dtype=np.float64)
        domain = "features"
    else:
        pts = path_z
        domain = "params_pca_fallback"
        logger.info(
            "perceptual_reparameterize: features unavailable; using param-space arc length"
        )

    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    total = float(cum[-1]) if cum[-1] > 0 else 1.0
    cum_n = cum / total
    # Invert: uniform perceptual (arc) coordinates -> parametric t.
    target = np.linspace(0.0, 1.0, int(n_out))
    t_warped = np.interp(target, cum_n, ts)
    path_warped = np.stack([(1 - t) * za + t * zb for t in t_warped], axis=0)
    registers = reconstruct_registers(model, path_warped)
    registers.insert(0, "s", target)
    registers.insert(1, "t_warped", t_warped)

    curve = pd.DataFrame({"s": target, "t_warped": t_warped, "t_linear": target})
    return {
        "registers": registers,
        "warp_curve": curve,
        "domain": domain,
        "total_arc_length": total,
        "note": (
            "Reparameterisation equalises speed along the path; it does not alter "
            "the geometric trajectory through parameter space."
        ),
    }


def hybrid_midpoint_retrieval(
    model: MorphModel,
    config_a: str,
    config_b: str,
) -> dict[str, Any]:
    """Audio-guided hybrid level 1: nearest feature-space neighbour to the midpoint.

    The parametric midpoint is formed in PCA space; the corpus configuration whose
    audio features are closest to the mean of the endpoint features is returned.
    This is retrieval, not generative inversion of the audio PCA.
    """
    id_to_i = {str(c): i for i, c in enumerate(model.config_ids)}
    za = model.X_pca[id_to_i[str(config_a)]]
    zb = model.X_pca[id_to_i[str(config_b)]]
    z_mid = 0.5 * (za + zb)
    registers_mid = reconstruct_registers(model, z_mid)

    feat = _feature_lookup()
    result: dict[str, Any] = {
        "config_a": config_a,
        "config_b": config_b,
        "parametric_midpoint_registers": registers_mid.iloc[0].to_dict(),
        "level": 1,
        "method": "nearest_neighbor_feature_midpoint",
    }
    if feat is None or str(config_a) not in feat[0] or str(config_b) not in feat[0]:
        # Fall back to nearest neighbour in PCA parameter space.
        d = np.linalg.norm(model.X_pca - z_mid[None, :], axis=1)
        nn_i = int(np.argmin(d))
        result["nearest_config_id"] = str(model.config_ids[nn_i])
        result["distance_domain"] = "params_pca_fallback"
        result["distance"] = float(d[nn_i])
        return result

    lookup, _ = feat
    mid_feat = 0.5 * (lookup[str(config_a)] + lookup[str(config_b)])
    ids = []
    mat = []
    for cid, vec in lookup.items():
        ids.append(cid)
        mat.append(vec)
    mat = np.asarray(mat, dtype=np.float64)
    d = np.linalg.norm(mat - mid_feat[None, :], axis=1)
    nn_i = int(np.argmin(d))
    result["nearest_config_id"] = ids[nn_i]
    result["distance_domain"] = "features"
    result["distance"] = float(d[nn_i])
    return result


def export_loadings(model: MorphModel, out_dir: str | Path | None = None) -> Path:
    """Export PCA loadings (components × model-space dimensions) as parquet + json."""
    ensure_dirs()
    out_dir = Path(out_dir) if out_dir else MORPH_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    loadings = pd.DataFrame(
        model.pca.components_.T,
        index=model.feature_names,
        columns=[f"PC{i+1}" for i in range(model.pca.n_components_)],
    )
    path = out_dir / "pca_loadings.parquet"
    loadings.to_parquet(path)
    meta = {
        "n_components": model.n_components(),
        "explained_variance_ratio": model.pca.explained_variance_ratio_.tolist(),
        "explained_variance_ratio_sum": float(model.pca.explained_variance_ratio_.sum()),
        "policy": model.policy.key(),
        "n_presets": int(len(model.config_ids)),
    }
    with (out_dir / "pca_loadings.json").open("w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    return path


def save_morph(model: MorphModel, out_dir: str | Path | None = None) -> Path:
    ensure_dirs()
    out_dir = Path(out_dir) if out_dir else MORPH_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "morph_model.joblib"
    joblib.dump(model, path)
    export_loadings(model, out_dir)
    provenance.write(
        path,
        stage="morph",
        params={"policy": model.policy.key(), "n_components": model.n_components()},
        metrics={
            "explained_variance_ratio_sum": float(model.pca.explained_variance_ratio_.sum()),
            "n_presets": int(len(model.config_ids)),
        },
        seeds={"morph": 42},
    )
    return path


def load_morph(path: str | Path | None = None) -> MorphModel:
    path = Path(path) if path else MORPH_DIR / "morph_model.joblib"
    if not path.exists():
        raise FileNotFoundError(path)
    return joblib.load(path)


def build_morph(*, n_components: int | float = 0.95) -> MorphModel:
    """Fit, export loadings and persist the morph model."""
    try:
        seed = int(load_config("features").get("determinism", {}).get("seed", 42))
    except FileNotFoundError:
        seed = 42
    with logs.stage("morph") as done:
        model = fit_morph(n_components=n_components, seed=seed)
        path = save_morph(model)
        done["n_components"] = model.n_components()
        done["artifact"] = str(path)
    return model
