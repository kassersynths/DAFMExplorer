"""Family B: pretrained audio embeddings (PANNs, LAION-CLAP).

Torch-first extractors with graceful ``ImportError`` handling. Resampling always
starts from the original FLAC via soxr VHQ at the rates declared in
``features.yaml`` (32 kHz PANNs, 48 kHz CLAP). Weight SHA256 is recorded in
provenance when a checkpoint path is available.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from tqdm import tqdm

from . import logs, provenance
from .descriptors import is_inaudible, load_audio, resample_audio
from .paths import (
    CORPUS_PARQUET,
    EMBEDDINGS_PARQUET,
    RENDER_MANIFEST,
    audio_path,
    ensure_dirs,
    load_config,
    machine_profile,
)

logger = logging.getLogger(__name__)


def _features_cfg() -> dict[str, Any]:
    return load_config("features")


def _resolve_device(requested: str | None = None) -> str:
    profile = machine_profile()
    device = requested or profile.get("embedding_device", "cpu")
    if device == "cuda":
        try:
            import torch

            if not torch.cuda.is_available():
                logger.warning("CUDA requested but unavailable; falling back to CPU")
                return "cpu"
        except ImportError:
            logger.warning("torch missing; embeddings unavailable on CUDA path")
            return "cpu"
    return device


def _configure_torch(seed: int = 42) -> None:
    cfg = _features_cfg().get("determinism", {})
    try:
        import torch

        torch.manual_seed(int(cfg.get("seed", seed)))
        if cfg.get("torch_deterministic", True):
            torch.use_deterministic_algorithms(True, warn_only=True)
        if torch.cuda.is_available():
            torch.backends.cudnn.benchmark = bool(cfg.get("cudnn_benchmark", False))
    except ImportError:
        return


def _checkpoint_sha256(path: str | Path | None) -> str | None:
    if path is None:
        return None
    p = Path(path)
    if not p.exists():
        return None
    return provenance.sha256_file(p)


def _jobs(limit: int | None) -> pd.DataFrame:
    if RENDER_MANIFEST.exists():
        manifest = pd.read_parquet(RENDER_MANIFEST)
        cols = [c for c in ("config_id", "core_id", "audio_path") if c in manifest.columns]
        out = manifest[cols].drop_duplicates("config_id")
    elif CORPUS_PARQUET.exists():
        from .corpus import unique_configs

        configs = unique_configs(pd.read_parquet(CORPUS_PARQUET))
        out = configs[["config_id", "core_id"]].copy()
        out["audio_path"] = out["config_id"].map(lambda cid: str(audio_path(cid)))
    else:
        raise FileNotFoundError("need render manifest or corpus parquet before embeddings")
    if limit is not None:
        out = out.head(int(limit))
    return out.reset_index(drop=True)


def extract_panns(
    path: str | Path,
    *,
    device: str | None = None,
    model: Any | None = None,
    model_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract a PANNs CNN14 embedding for one file.

    Returns a dict with ``panns_available``, optional error, and ``panns_0..``.
    """
    model_cfg = model_cfg or {}
    target_sr = int(model_cfg.get("sample_rate", 32000))
    dim = int(model_cfg.get("dim", 2048))
    out: dict[str, Any] = {"panns_available": 0.0, "panns_error": ""}
    for i in range(dim):
        out[f"panns_{i}"] = float("nan")

    try:
        import torch
        from panns_inference import AudioTagging
    except ImportError as exc:
        out["panns_error"] = f"ImportError:{exc}"
        return out

    device = _resolve_device(device)
    y, sr = load_audio(path)
    if is_inaudible(y, sr):
        out["panns_error"] = "inaudible"
        return out
    if sr != target_sr:
        y = resample_audio(y, sr, target_sr)

    if model is None:
        checkpoint_path = model_cfg.get("checkpoint_path")
        model = AudioTagging(checkpoint_path=checkpoint_path, device=device)

    with torch.no_grad():
        # panns-inference expects shape (batch, samples)
        waveform = y[None, :]
        _, embedding = model.inference(waveform)

    emb = np.asarray(embedding, dtype=np.float32).reshape(-1)
    out["panns_available"] = 1.0
    for i, value in enumerate(emb[:dim]):
        out[f"panns_{i}"] = float(value)
    out["panns_dim"] = int(min(len(emb), dim))
    return out


def extract_clap(
    path: str | Path,
    *,
    device: str | None = None,
    model: Any | None = None,
    model_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract a LAION-CLAP audio embedding for one file."""
    model_cfg = model_cfg or {}
    target_sr = int(model_cfg.get("sample_rate", 48000))
    dim = int(model_cfg.get("dim", 512))
    out: dict[str, Any] = {"clap_available": 0.0, "clap_error": ""}
    for i in range(dim):
        out[f"clap_{i}"] = float("nan")

    try:
        import laion_clap
        import torch
    except ImportError as exc:
        out["clap_error"] = f"ImportError:{exc}"
        return out

    device = _resolve_device(device)
    y, sr = load_audio(path)
    if is_inaudible(y, sr):
        out["clap_error"] = "inaudible"
        return out
    if sr != target_sr:
        y = resample_audio(y, sr, target_sr)

    if model is None:
        model = laion_clap.CLAP_Module(enable_fusion=False, device=device)
        ckpt = model_cfg.get("checkpoint_path")
        if ckpt:
            model.load_ckpt(ckpt)
        else:
            model.load_ckpt()

    with torch.no_grad():
        # CLAP expects (batch, samples) at 48 kHz.
        emb = model.get_audio_embedding_from_data(x=y[None, :], use_tensor=False)

    emb = np.asarray(emb, dtype=np.float32).reshape(-1)
    out["clap_available"] = 1.0
    for i, value in enumerate(emb[:dim]):
        out[f"clap_{i}"] = float(value)
    out["clap_dim"] = int(min(len(emb), dim))
    return out


def _model_cfgs() -> dict[str, dict[str, Any]]:
    family = _features_cfg().get("family_b", {})
    return {m["name"]: m for m in family.get("models", [])}


def extract_embeddings(limit: int | None = None) -> pd.DataFrame:
    """Batch-extract Family B embeddings with parquet checkpointing."""
    ensure_dirs()
    cfg = _features_cfg()
    family = cfg.get("family_b", {})
    if not family.get("enabled", True):
        logger.warning("family_b disabled in features.yaml")
        return pd.DataFrame()

    _configure_torch(int(cfg.get("determinism", {}).get("seed", 42)))
    profile = machine_profile()
    device = _resolve_device(profile.get("embedding_device"))
    models = _model_cfgs()
    panns_cfg = models.get("panns_cnn14", {"sample_rate": 32000, "dim": 2048})
    clap_cfg = models.get("laion_clap_htsat", {"sample_rate": 48000, "dim": 512})
    checkpoint_every = int(family.get("batch_checkpoint_every", 512))

    weight_hashes = {
        "panns_checkpoint_sha256": _checkpoint_sha256(panns_cfg.get("checkpoint_path"))
        or panns_cfg.get("checkpoint_sha256"),
        "clap_checkpoint_sha256": _checkpoint_sha256(clap_cfg.get("checkpoint_path"))
        or clap_cfg.get("checkpoint_sha256"),
    }

    jobs = _jobs(limit)
    frames: list[pd.DataFrame] = []
    done: set[str] = set()
    if EMBEDDINGS_PARQUET.exists():
        existing = pd.read_parquet(EMBEDDINGS_PARQUET)
        done = set(existing["config_id"].astype(str))
        frames.append(existing)

    pending = jobs[~jobs["config_id"].astype(str).isin(done)]
    logger.info(
        "Family B: %d pending of %d on device=%s (limit=%s)",
        len(pending),
        len(jobs),
        device,
        limit,
    )

    panns_model = None
    clap_model = None
    # Lazy-load once; tolerate missing optional packages.
    try:
        from panns_inference import AudioTagging

        panns_model = AudioTagging(
            checkpoint_path=panns_cfg.get("checkpoint_path"), device=device
        )
    except ImportError as exc:
        logger.warning("PANNs unavailable: %s", exc)

    try:
        import laion_clap

        clap_model = laion_clap.CLAP_Module(enable_fusion=False, device=device)
        if clap_cfg.get("checkpoint_path"):
            clap_model.load_ckpt(clap_cfg["checkpoint_path"])
        else:
            clap_model.load_ckpt()
    except ImportError as exc:
        logger.warning("LAION-CLAP unavailable: %s", exc)
    except Exception as exc:  # pragma: no cover - checkpoint / CUDA issues
        logger.warning("LAION-CLAP failed to initialise: %s", exc)
        clap_model = None

    with logs.stage("embeddings", pending=len(pending), device=device) as done_fields:
        batch: list[dict[str, Any]] = []
        for _, job in tqdm(pending.iterrows(), total=len(pending), desc="embeddings"):
            cid = str(job["config_id"])
            path = (
                Path(job["audio_path"])
                if "audio_path" in job and pd.notna(job["audio_path"])
                else audio_path(cid)
            )
            row: dict[str, Any] = {"config_id": cid}
            if "core_id" in job and pd.notna(job["core_id"]):
                row["core_id"] = job["core_id"]
            if not path.exists():
                row["panns_available"] = 0.0
                row["clap_available"] = 0.0
                row["panns_error"] = "missing_audio"
                row["clap_error"] = "missing_audio"
            else:
                if panns_model is not None:
                    row.update(
                        extract_panns(
                            path, device=device, model=panns_model, model_cfg=panns_cfg
                        )
                    )
                else:
                    row.update(extract_panns(path, device=device, model_cfg=panns_cfg))
                if clap_model is not None:
                    row.update(
                        extract_clap(path, device=device, model=clap_model, model_cfg=clap_cfg)
                    )
                else:
                    row.update(extract_clap(path, device=device, model_cfg=clap_cfg))
            batch.append(row)
            if len(batch) >= checkpoint_every:
                frames.append(pd.DataFrame(batch))
                pd.concat(frames, ignore_index=True).to_parquet(EMBEDDINGS_PARQUET, index=False)
                batch.clear()

        if batch:
            frames.append(pd.DataFrame(batch))
        result = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if len(result):
            result.to_parquet(EMBEDDINGS_PARQUET, index=False)

        provenance.write(
            EMBEDDINGS_PARQUET,
            stage="embeddings",
            inputs={"n_jobs": len(jobs)},
            params={
                "device": device,
                "machine_profile": profile.get("id"),
                "precision": profile.get("embedding_precision"),
                **{k: v for k, v in weight_hashes.items() if v},
            },
            metrics={
                "n_rows": int(len(result)),
                "panns_ok": int(result["panns_available"].fillna(0).sum())
                if len(result) and "panns_available" in result.columns
                else 0,
                "clap_ok": int(result["clap_available"].fillna(0).sum())
                if len(result) and "clap_available" in result.columns
                else 0,
            },
            seeds={"embeddings": int(cfg.get("determinism", {}).get("seed", 42))},
        )
        done_fields["rows"] = len(result)
        done_fields["device"] = device

    return result
