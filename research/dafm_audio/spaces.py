"""Representation spaces under matched transform pipelines.

Five conditions share the same StandardScaler → PCA → optional UMAP → KMeans
pipeline, fitted on the train split only:

* ``params_raw`` — effective register values (ablation)
* ``params_encoded`` — model-space encoding (primary parameter baseline)
* ``descriptors`` — Family A handcrafted features
* ``embeddings`` — Family B concatenated embeddings
* ``hybrid`` — descriptors + embeddings

Distance metric: Euclidean for handcrafted / params, cosine for embeddings.
Transformers are persisted under ``artifacts/spaces/``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from . import encoding, logs, provenance
from .paths import (
    CORPUS_PARQUET,
    EMBEDDINGS_PARQUET,
    FEATURES_PARQUET,
    SPLITS_PARQUET,
    SPACES_DIR,
    ensure_dirs,
    load_config,
)

logger = logging.getLogger(__name__)

Condition = Literal[
    "params_raw",
    "params_encoded",
    "descriptors",
    "embeddings",
    "hybrid",
]

CONDITIONS: tuple[Condition, ...] = (
    "params_raw",
    "params_encoded",
    "descriptors",
    "embeddings",
    "hybrid",
)

# Defaults used when configs omit an explicit spaces block.
DEFAULT_SPACE_PARAMS: dict[str, Any] = {
    "pca_target_variance": 0.95,
    "pca_max_components": 128,
    "umap_enabled": True,
    "umap_n_components": 2,
    "umap_n_neighbors": 15,
    "umap_min_dist": 0.1,
    "umap_metric_override": None,
    "kmeans_k": 16,
    "kmeans_n_init": 10,
    "random_state": 42,
}


def space_params() -> dict[str, Any]:
    """Merge config overrides onto defaults."""
    params = dict(DEFAULT_SPACE_PARAMS)
    for name in ("features", "eval"):
        try:
            cfg = load_config(name)
        except FileNotFoundError:
            continue
        block = cfg.get("spaces") or cfg.get("representation_spaces") or {}
        params.update({k: v for k, v in block.items() if v is not None})
    # features.yaml determinism seed wins when present
    try:
        seed = load_config("features").get("determinism", {}).get("seed")
        if seed is not None:
            params["random_state"] = int(seed)
    except FileNotFoundError:
        pass
    return params


def metric_for(condition: Condition) -> str:
    if condition == "embeddings":
        return "cosine"
    return "euclidean"


@dataclass
class FittedSpace:
    """Fitted transformers and projected matrices for one condition."""

    condition: Condition
    metric: str
    config_ids: np.ndarray
    scaler: StandardScaler
    pca: PCA
    umap_model: Any | None
    kmeans: KMeans
    X_scaled: np.ndarray
    X_pca: np.ndarray
    X_umap: np.ndarray | None
    labels: np.ndarray
    feature_names: list[str] = field(default_factory=list)
    train_mask: np.ndarray | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def artifact_dir(self) -> Path:
        return SPACES_DIR / self.condition


def _meta_columns() -> set[str]:
    return {
        "config_id",
        "core_id",
        "preset_id",
        "audio_path",
        "sample_rate",
        "n_samples",
        "audiocommons_import_error",
        "panns_error",
        "clap_error",
        "panns_available",
        "clap_available",
        "panns_dim",
        "clap_dim",
        "split",
        "stratum",
        "game",
        "track",
        "track_number",
        "is_valid",
        "corpus_id",
        "Filename",
        "Name",
        "Num",
    }


def _numeric_feature_matrix(
    df: pd.DataFrame,
    *,
    include_prefixes: tuple[str, ...] | None = None,
    exclude_prefixes: tuple[str, ...] | None = None,
) -> tuple[np.ndarray, list[str], np.ndarray]:
    """Return ``(X, column_names, config_ids)`` for modelling columns."""
    meta = _meta_columns()
    cols = []
    for c in df.columns:
        if c in meta:
            continue
        if not pd.api.types.is_numeric_dtype(df[c]):
            continue
        if include_prefixes and not any(c.startswith(p) for p in include_prefixes):
            continue
        if exclude_prefixes and any(c.startswith(p) for p in exclude_prefixes):
            continue
        # Skip loudness metadata helpers that are not timbre features.
        if c.startswith("loudness_") or c.startswith("audiocommons_"):
            continue
        cols.append(c)
    if "config_id" not in df.columns:
        raise KeyError("expected config_id column")
    sub = df.dropna(subset=cols, how="all").copy()
    X = sub[cols].to_numpy(dtype=np.float64)
    # Impute column means for residual NaNs inside otherwise valid rows.
    col_means = np.nanmean(X, axis=0)
    col_means = np.where(np.isfinite(col_means), col_means, 0.0)
    inds = np.where(~np.isfinite(X))
    if inds[0].size:
        X[inds] = np.take(col_means, inds[1])
    return X, cols, sub["config_id"].to_numpy()


def load_condition_matrix(
    condition: Condition,
) -> tuple[np.ndarray, list[str], np.ndarray, pd.DataFrame]:
    """Build the raw feature matrix for a condition before scaling."""
    if condition in ("params_raw", "params_encoded"):
        if not CORPUS_PARQUET.exists():
            raise FileNotFoundError(CORPUS_PARQUET)
        from .corpus import unique_configs

        corpus = pd.read_parquet(CORPUS_PARQUET)
        configs = unique_configs(corpus)
        if condition == "params_raw":
            cols = list(encoding.EFFECTIVE_COLUMNS)
            X = configs[cols].to_numpy(dtype=np.float64)
            return X, cols, configs["config_id"].to_numpy(), configs
        space = encoding.to_model_space(configs)
        return space.matrix, space.columns, configs["config_id"].to_numpy(), configs

    if condition == "descriptors":
        if not FEATURES_PARQUET.exists():
            raise FileNotFoundError(FEATURES_PARQUET)
        df = pd.read_parquet(FEATURES_PARQUET)
        X, cols, ids = _numeric_feature_matrix(df)
        return X, cols, ids, df

    if condition == "embeddings":
        if not EMBEDDINGS_PARQUET.exists():
            raise FileNotFoundError(EMBEDDINGS_PARQUET)
        df = pd.read_parquet(EMBEDDINGS_PARQUET)
        X, cols, ids = _numeric_feature_matrix(
            df, include_prefixes=("panns_", "clap_")
        )
        # Drop availability / dim helper columns if they slipped in.
        keep = [c for c in cols if c.startswith("panns_") or c.startswith("clap_")]
        keep = [c for c in keep if c.split("_", 1)[-1].isdigit()]
        idx = [cols.index(c) for c in keep]
        return X[:, idx], keep, ids, df

    # hybrid
    if not FEATURES_PARQUET.exists() or not EMBEDDINGS_PARQUET.exists():
        raise FileNotFoundError("hybrid needs features.parquet and embeddings.parquet")
    desc = pd.read_parquet(FEATURES_PARQUET)
    emb = pd.read_parquet(EMBEDDINGS_PARQUET)
    merged = desc.merge(emb, on="config_id", how="inner", suffixes=("", "_emb"))
    X, cols, ids = _numeric_feature_matrix(merged)
    return X, cols, ids, merged


def _train_mask(config_ids: np.ndarray) -> np.ndarray:
    if not SPLITS_PARQUET.exists() or not CORPUS_PARQUET.exists():
        logger.warning("splits missing; fitting spaces on all rows")
        return np.ones(len(config_ids), dtype=bool)
    corpus = pd.read_parquet(CORPUS_PARQUET)
    splits = pd.read_parquet(SPLITS_PARQUET)
    cfg_split = (
        corpus.loc[corpus["is_valid"], ["config_id", "core_id"]]
        .drop_duplicates("config_id")
        .merge(splits, on="core_id", how="left")
    )
    train_ids = set(cfg_split.loc[cfg_split["split"] == "train", "config_id"].astype(str))
    return np.array([str(c) in train_ids for c in config_ids], dtype=bool)


def fit_space(condition: Condition, params: dict[str, Any] | None = None) -> FittedSpace:
    """Fit the shared pipeline for one condition on the train split."""
    params = {**space_params(), **(params or {})}
    X, feature_names, config_ids, _ = load_condition_matrix(condition)
    train = _train_mask(config_ids)
    if train.sum() < 2:
        train = np.ones(len(config_ids), dtype=bool)

    scaler = StandardScaler()
    scaler.fit(X[train])
    X_scaled = scaler.transform(X)

    n_features = X_scaled.shape[1]
    max_comp = max(
        1,
        min(int(params["pca_max_components"]), n_features, int(train.sum())),
    )
    # sklearn accepts float in (0, 1) as target explained variance for PCA.
    target = float(params["pca_target_variance"])
    if 0 < target < 1:
        n_components: int | float = target
    else:
        n_components = min(int(target), max_comp)
    pca = PCA(
        n_components=n_components,
        random_state=int(params["random_state"]),
        svd_solver="full",
    )
    pca.fit(X_scaled[train])
    X_pca = pca.transform(X_scaled)

    umap_model = None
    X_umap = None
    if params.get("umap_enabled", True):
        try:
            import umap

            metric = params.get("umap_metric_override") or metric_for(condition)
            umap_model = umap.UMAP(
                n_components=int(params["umap_n_components"]),
                n_neighbors=int(params["umap_n_neighbors"]),
                min_dist=float(params["umap_min_dist"]),
                metric=metric,
                random_state=int(params["random_state"]),
            )
            umap_model.fit(X_pca[train])
            X_umap = umap_model.transform(X_pca)
        except Exception as exc:
            logger.warning("UMAP disabled for %s: %s", condition, exc)
            umap_model = None
            X_umap = None

    cluster_X = X_pca
    k = min(int(params["kmeans_k"]), max(2, int(train.sum())))
    kmeans = KMeans(
        n_clusters=k,
        n_init=int(params["kmeans_n_init"]),
        random_state=int(params["random_state"]),
    )
    kmeans.fit(cluster_X[train])
    labels = kmeans.predict(cluster_X)

    return FittedSpace(
        condition=condition,
        metric=metric_for(condition),
        config_ids=config_ids,
        scaler=scaler,
        pca=pca,
        umap_model=umap_model,
        kmeans=kmeans,
        X_scaled=X_scaled,
        X_pca=X_pca,
        X_umap=X_umap,
        labels=labels,
        feature_names=feature_names,
        train_mask=train,
        meta={
            "params": params,
            "n_rows": int(len(config_ids)),
            "n_train": int(train.sum()),
            "n_pca": int(pca.n_components_),
            "explained_variance_ratio_sum": float(pca.explained_variance_ratio_.sum()),
        },
    )


def save_space(space: FittedSpace) -> Path:
    """Persist transformers and projections under ``artifacts/spaces/<condition>/``."""
    ensure_dirs()
    out = space.artifact_dir()
    out.mkdir(parents=True, exist_ok=True)
    joblib.dump(space.scaler, out / "scaler.joblib")
    joblib.dump(space.pca, out / "pca.joblib")
    joblib.dump(space.kmeans, out / "kmeans.joblib")
    if space.umap_model is not None:
        joblib.dump(space.umap_model, out / "umap.joblib")
    np.savez_compressed(
        out / "projections.npz",
        config_ids=space.config_ids.astype(str),
        X_scaled=space.X_scaled.astype(np.float32),
        X_pca=space.X_pca.astype(np.float32),
        X_umap=space.X_umap.astype(np.float32) if space.X_umap is not None else np.array([]),
        labels=space.labels.astype(np.int32),
        train_mask=space.train_mask.astype(bool)
        if space.train_mask is not None
        else np.ones(len(space.config_ids), dtype=bool),
    )
    meta = {
        "condition": space.condition,
        "metric": space.metric,
        "feature_names": space.feature_names,
        **space.meta,
    }
    with (out / "meta.json").open("w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, default=str)
    # Also pickle the whole bundle for convenient reload.
    joblib.dump(space, out / "fitted_space.joblib")
    provenance.write(
        out / "fitted_space.joblib",
        stage="spaces",
        params={"condition": space.condition, **space.meta.get("params", {})},
        metrics={
            "n_rows": space.meta.get("n_rows"),
            "n_pca": space.meta.get("n_pca"),
            "explained_variance_ratio_sum": space.meta.get("explained_variance_ratio_sum"),
        },
        seeds={"spaces": int(space.meta.get("params", {}).get("random_state", 42))},
    )
    return out


def load_space(condition: Condition) -> FittedSpace:
    path = SPACES_DIR / condition / "fitted_space.joblib"
    if not path.exists():
        raise FileNotFoundError(path)
    return joblib.load(path)


def build_spaces(
    conditions: tuple[Condition, ...] | None = None,
    *,
    limit: int | None = None,
) -> dict[str, FittedSpace]:
    """Fit and save all (or selected) representation spaces."""
    ensure_dirs()
    conditions = conditions or CONDITIONS
    fitted: dict[str, FittedSpace] = {}
    with logs.stage("spaces", conditions=",".join(conditions)) as done:
        for condition in conditions:
            try:
                space = fit_space(condition)
                if limit is not None:
                    # Limit is applied after fit for smoke tests: truncate saved ids.
                    n = min(int(limit), len(space.config_ids))
                    space.config_ids = space.config_ids[:n]
                    space.X_scaled = space.X_scaled[:n]
                    space.X_pca = space.X_pca[:n]
                    if space.X_umap is not None:
                        space.X_umap = space.X_umap[:n]
                    space.labels = space.labels[:n]
                    if space.train_mask is not None:
                        space.train_mask = space.train_mask[:n]
                save_space(space)
                fitted[condition] = space
                logger.info(
                    "space %s: rows=%d pca=%d var=%.3f",
                    condition,
                    space.meta["n_rows"],
                    space.meta["n_pca"],
                    space.meta["explained_variance_ratio_sum"],
                )
            except FileNotFoundError as exc:
                logger.warning("skipping space %s: %s", condition, exc)
            except Exception:
                logger.exception("failed to fit space %s", condition)
                raise
        done["n_spaces"] = len(fitted)
    return fitted
