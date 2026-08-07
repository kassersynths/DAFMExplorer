"""Render queue and manifest: what to render, and whether it is done.

The TypeScript renderer reads ``artifacts/render_queue.json`` (a JSON array of
``{config_id, CON, FL, M1_AR, ...}``). This module builds that queue from the
corpus unique configurations, writes the parquet manifest, and checks completeness.

Audio path convention
---------------------
The Node renderer writes PCM24 WAV plus a ``.meta.json`` sidecar. A post-step
here converts WAV to FLAC 24-bit with ``soundfile`` (the format declared in
``render.yaml``). Completeness is defined on the FLAC path in
:func:`paths.audio_path`, with PCM SHA256 taken from the sidecar (hash target is
decoded PCM, never container bytes).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import corpus as corpus_mod
from . import logs, provenance
from .encoding import EFFECTIVE_COLUMNS
from .paths import (
    AUDIO_DIR,
    CORPUS_PARQUET,
    RENDER_INDEX_JSON,
    RENDER_MANIFEST,
    RENDER_QUEUE_JSON,
    audio_path,
    ensure_dirs,
    load_config,
)


def render_config_hash() -> str:
    """Hash of ``configs/render.yaml``; any protocol change invalidates audio."""
    return provenance.config_hash("render")


def build_render_queue(
    corpus: pd.DataFrame | None = None,
    *,
    out_json: Path | None = None,
    out_parquet: Path | None = None,
) -> pd.DataFrame:
    """Build the render queue from unique effective configurations.

    Writes ``artifacts/render_queue.json`` (for the TS renderer) and
    ``artifacts/render_manifest.parquet`` (for Python bookkeeping).
    """
    ensure_dirs()
    if corpus is None:
        if not CORPUS_PARQUET.exists():
            raise FileNotFoundError(
                f"missing {CORPUS_PARQUET}; run the corpus stage before building the render queue"
            )
        corpus = pd.read_parquet(CORPUS_PARQUET)

    configs = corpus_mod.unique_configs(corpus)
    cfg = load_config("render")
    chash = render_config_hash()
    prefix_len = int(cfg["output"]["shard_prefix_len"])

    manifest = configs.copy()
    manifest["config_hash"] = chash
    manifest["protocol_version"] = cfg["protocol_version"]
    # Stable path relative to research/: scratch/audio/<pp>/<id>.flac
    manifest["audio_relpath"] = [
        f"scratch/audio/{cid[:prefix_len]}/{cid}.flac" for cid in manifest["config_id"]
    ]
    manifest["status"] = "pending"
    manifest["pcm_sha256"] = pd.NA
    manifest["peak_dbfs"] = np.nan
    manifest["rms_dbfs"] = np.nan
    manifest["audible"] = pd.NA

    out_json = out_json or RENDER_QUEUE_JSON
    out_parquet = out_parquet or RENDER_MANIFEST

    # JSON array the TS renderer consumes: config_id + effective columns only.
    records = configs[["config_id", *EFFECTIVE_COLUMNS]].to_dict(orient="records")
    # Ensure native Python ints for JSON (numpy scalars trip some parsers).
    clean = []
    for row in records:
        clean.append({k: (int(v) if hasattr(v, "item") else v) for k, v in row.items()})
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with out_json.open("w", encoding="utf-8") as fh:
        json.dump(clean, fh, separators=(",", ":"))

    manifest = manifest.sort_values("config_id").reset_index(drop=True)
    manifest.to_parquet(out_parquet, index=False)

    index = {
        "config_hash": chash,
        "n_configs": int(len(manifest)),
        "queue_json": str(out_json),
        "manifest_parquet": str(out_parquet),
        "protocol_version": cfg["protocol_version"],
    }
    with RENDER_INDEX_JSON.open("w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=2)

    provenance.write(
        out_parquet,
        stage="render_manifest",
        inputs={"corpus": str(CORPUS_PARQUET)},
        params={"config_hash": chash},
        metrics={"n_configs": int(len(manifest))},
    )
    return manifest


def wav_path_for(config_id: str, prefix_len: int | None = None) -> Path:
    """Sibling WAV path written by the Node renderer before FLAC conversion."""
    cfg = load_config("render")
    n = prefix_len if prefix_len is not None else int(cfg["output"]["shard_prefix_len"])
    return AUDIO_DIR / config_id[:n] / f"{config_id}.wav"


def meta_path_for(config_id: str, prefix_len: int | None = None) -> Path:
    cfg = load_config("render")
    n = prefix_len if prefix_len is not None else int(cfg["output"]["shard_prefix_len"])
    return AUDIO_DIR / config_id[:n] / f"{config_id}.meta.json"


def encode_wav_to_flac(config_id: str, *, overwrite: bool = False) -> Path:
    """Convert one renderer WAV to FLAC 24-bit via soundfile."""
    import soundfile as sf

    cfg = load_config("render")
    prefix_len = int(cfg["output"]["shard_prefix_len"])
    wav = wav_path_for(config_id, prefix_len)
    flac = audio_path(config_id, prefix_len)
    if flac.exists() and not overwrite:
        return flac
    if not wav.exists():
        raise FileNotFoundError(f"missing WAV for {config_id}: {wav}")
    data, sr = sf.read(str(wav), dtype="float32", always_2d=False)
    flac.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(flac), data, sr, subtype="PCM_24", format="FLAC")
    return flac


def encode_all_wavs(*, limit: int | None = None, overwrite: bool = False) -> dict[str, Any]:
    """Convert every pending WAV under scratch/audio to FLAC."""
    ensure_dirs()
    wavs = sorted(AUDIO_DIR.rglob("*.wav"))
    if limit is not None:
        wavs = wavs[:limit]
    with logs.stage("encode_flac", items=len(wavs)) as done:
        converted = 0
        skipped = 0
        for wav in wavs:
            config_id = wav.stem
            flac = audio_path(config_id)
            if flac.exists() and not overwrite:
                skipped += 1
                continue
            encode_wav_to_flac(config_id, overwrite=overwrite)
            converted += 1
        done["converted"] = converted
        done["skipped"] = skipped
    return {"converted": converted, "skipped": skipped, "total_wavs": len(wavs)}


def refresh_manifest_from_sidecars(
    manifest: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Update manifest rows from ``.meta.json`` sidecars and FLAC presence."""
    if manifest is None:
        if not RENDER_MANIFEST.exists():
            raise FileNotFoundError(f"missing {RENDER_MANIFEST}")
        manifest = pd.read_parquet(RENDER_MANIFEST)

    cfg = load_config("render")
    prefix_len = int(cfg["output"]["shard_prefix_len"])

    statuses = []
    peaks = []
    rmss = []
    shas = []
    audibles = []
    for cid in manifest["config_id"]:
        meta_p = meta_path_for(cid, prefix_len)
        flac_p = audio_path(cid, prefix_len)
        if meta_p.exists():
            with meta_p.open("r", encoding="utf-8") as fh:
                meta = json.load(fh)
            peaks.append(meta.get("peak_dbfs"))
            rmss.append(meta.get("rms_dbfs"))
            shas.append(meta.get("pcm_sha256"))
            audibles.append(meta.get("audible"))
            if flac_p.exists():
                statuses.append("done")
            elif wav_path_for(cid, prefix_len).exists():
                statuses.append("wav")
            else:
                statuses.append("meta_only")
        elif flac_p.exists():
            statuses.append("done")
            peaks.append(np.nan)
            rmss.append(np.nan)
            shas.append(pd.NA)
            audibles.append(pd.NA)
        else:
            statuses.append("pending")
            peaks.append(np.nan)
            rmss.append(np.nan)
            shas.append(pd.NA)
            audibles.append(pd.NA)

    out = manifest.copy()
    out["status"] = statuses
    out["peak_dbfs"] = peaks
    out["rms_dbfs"] = rmss
    out["pcm_sha256"] = shas
    out["audible"] = audibles
    out.to_parquet(RENDER_MANIFEST, index=False)
    return out


def check_render_completeness(
    manifest: pd.DataFrame | None = None,
    *,
    require_flac: bool = True,
) -> dict[str, Any]:
    """Report how much of the queue is rendered and whether anything is missing."""
    if manifest is None:
        if not RENDER_MANIFEST.exists():
            raise FileNotFoundError(f"missing {RENDER_MANIFEST}")
        manifest = pd.read_parquet(RENDER_MANIFEST)

    cfg = load_config("render")
    prefix_len = int(cfg["output"]["shard_prefix_len"])
    chash = render_config_hash()

    missing = []
    stale_hash = []
    present = 0
    for cid in manifest["config_id"]:
        target = audio_path(cid, prefix_len) if require_flac else wav_path_for(cid, prefix_len)
        if not target.exists():
            missing.append(cid)
            continue
        present += 1
        meta_p = meta_path_for(cid, prefix_len)
        if meta_p.exists():
            with meta_p.open("r", encoding="utf-8") as fh:
                meta = json.load(fh)
            mh = str(meta.get("config_hash", ""))
            if mh and mh not in (chash, chash[:16]):
                stale_hash.append(cid)

    return {
        "config_hash": chash,
        "n_configs": int(len(manifest)),
        "present": present,
        "missing": len(missing),
        "missing_ids_head": missing[:20],
        "stale_hash": len(stale_hash),
        "complete": len(missing) == 0 and len(stale_hash) == 0,
        "require_flac": require_flac,
    }


def choose_global_gain(
    probe_records: list[dict[str, Any]] | Path,
    *,
    target_peak_dbfs: float | None = None,
) -> dict[str, Any]:
    """Pick one global gain from a probe-mode JSONL / list of probe records.

    ``gain_final = probe_gain * 10**((target_peak_dbfs - peak_dbfs_max) / 20)``
    where peak_dbfs_max is the loudest probe peak under the probe gain.
    """
    cfg = load_config("render")
    if target_peak_dbfs is None:
        target_peak_dbfs = float(cfg["gain"]["target_peak_dbfs"])
    probe_gain = float(cfg["gain"]["probe_gain"])

    if isinstance(probe_records, Path):
        rows = []
        with probe_records.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        probe_records = rows

    if not probe_records:
        raise ValueError("no probe records")

    peaks = [float(r["peak"]) for r in probe_records if r.get("peak") is not None]
    peak_max = max(peaks) if peaks else 0.0
    if peak_max <= 0:
        raise ValueError("all probe peaks are zero; cannot choose a gain")

    # peak is already after probe_gain; scale so max peak becomes target.
    target_linear = 10.0 ** (target_peak_dbfs / 20.0)
    scale = target_linear / peak_max
    global_gain = probe_gain * scale
    return {
        "probe_gain": probe_gain,
        "target_peak_dbfs": target_peak_dbfs,
        "peak_max_linear": peak_max,
        "peak_max_dbfs": 20.0 * np.log10(peak_max),
        "global_gain": global_gain,
        "n_probe": len(probe_records),
    }
