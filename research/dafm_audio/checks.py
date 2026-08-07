"""Verifiable gates: green/red with the numbers that justify the verdict.

These are the same checks CI runs. A gate that passes here passes anywhere.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .paths import (
    ARTIFACTS_DIR,
    AUDIO_DIR,
    CORPUS_PARQUET,
    FEATURES_PARQUET,
    RENDER_MANIFEST,
    RESULTS_DIR,
    SPACES_DIR,
)


def _verdict(ok: bool, lines: list[str]) -> bool:
    for line in lines:
        print(line)
    print("VERDICT:", "GREEN" if ok else "RED")
    return ok


def check_corpus() -> bool:
    lines: list[str] = []
    ok = True
    stats_path = ARTIFACTS_DIR / "corpus_stats.json"
    if not CORPUS_PARQUET.exists():
        return _verdict(False, ["missing artifacts/corpus_v1.parquet — run `make corpus`"])
    if not stats_path.exists():
        return _verdict(False, ["missing artifacts/corpus_stats.json"])

    df = pd.read_parquet(CORPUS_PARQUET)
    with stats_path.open(encoding="utf-8") as fh:
        stats = json.load(fh)

    n = len(df)
    lines.append(f"rows:              {n} (expected 93832)")
    if n != 93832:
        ok = False

    if "is_valid" in df.columns:
        n_valid = int(df["is_valid"].sum())
        lines.append(f"valid rows:        {n_valid}")
        lines.append(f"quarantined:       {int((~df['is_valid']).sum())}")
    else:
        n_valid = n

    n_configs = int(df.loc[df.get("is_valid", True), "config_id"].nunique()) if "config_id" in df.columns else -1
    n_cores = int(df.loc[df.get("is_valid", True), "core_id"].nunique()) if "core_id" in df.columns else -1
    lines.append(f"unique configs:    {n_configs}  (stats says {stats.get('n_configs')})")
    lines.append(f"timbral cores:     {n_cores}  (stats says {stats.get('n_cores')})")
    lines.append(f"games:             {df['game'].nunique() if 'game' in df.columns else '?'}")

    splits = ARTIFACTS_DIR / "splits.parquet"
    if splits.exists():
        sp = pd.read_parquet(splits)
        lines.append(f"split cores:       {len(sp)}  sizes={sp['split'].value_counts().to_dict()}")
    else:
        lines.append("splits:            MISSING")
        ok = False

    tl = ARTIFACTS_DIR / "tl_variant_groups.parquet"
    if tl.exists():
        tg = pd.read_parquet(tl)
        lines.append(f"TL groups:         {len(tg)}  {tg['group_type'].value_counts().to_dict()}")
    else:
        lines.append("TL groups:         MISSING")
        ok = False

    if stats.get("n_configs") != n_configs:
        lines.append("mismatch between parquet and corpus_stats.json for n_configs")
        ok = False

    return _verdict(ok, lines)


def check_render() -> bool:
    lines: list[str] = []
    ok = True
    if not RENDER_MANIFEST.exists():
        return _verdict(False, ["missing render_manifest.parquet — run `make render-manifest`"])

    manifest = pd.read_parquet(RENDER_MANIFEST)
    lines.append(f"manifest rows:     {len(manifest)}")

    audio_files = list(AUDIO_DIR.rglob("*.flac")) + list(AUDIO_DIR.rglob("*.wav"))
    lines.append(f"audio files:       {len(audio_files)}")

    if "pcm_sha256" in manifest.columns:
        hashed = int(manifest["pcm_sha256"].notna().sum())
        lines.append(f"pcm hashes:        {hashed}/{len(manifest)}")
        if hashed == 0:
            ok = False
    else:
        lines.append("pcm hashes:        column absent")
        ok = False

    if "clipped" in manifest.columns:
        n_clip = int(manifest["clipped"].fillna(False).sum())
        lines.append(f"clipped:           {n_clip} (must be 0)")
        if n_clip:
            ok = False

    if "audible" in manifest.columns:
        n_aud = int(manifest["audible"].fillna(False).astype("boolean").fillna(False).sum())
        lines.append(f"audible:           {n_aud}/{len(manifest)}")

    if "status" in manifest.columns:
        n_done = int((manifest["status"] == "done").sum())
        lines.append(f"status=done:       {n_done}/{len(manifest)}")

    if len(audio_files) == 0:
        lines.append("no audio files under scratch/audio")
        ok = False
    elif len(audio_files) < len(manifest):
        lines.append(
            f"render incomplete ({len(audio_files)}/{len(manifest)}); "
            "partial multi-machine work is OK — gate stays RED until full"
        )
        ok = False

    gain_path = ARTIFACTS_DIR / "global_gain.json"
    if gain_path.exists():
        with gain_path.open(encoding="utf-8") as fh:
            gain = json.load(fh)
        lines.append(
            f"global gain:       {gain.get('global_gain')}  "
            f"peak_dbfs={gain.get('peak_max_dbfs', gain.get('true_peak'))}"
        )
    else:
        lines.append("global gain:       NOT SET — run `make render-gain` before final encode")
        ok = False

    return _verdict(ok, lines)


def check_features() -> bool:
    lines: list[str] = []
    ok = True
    if not FEATURES_PARQUET.exists():
        return _verdict(False, ["missing features.parquet — run `make features`"])

    df = pd.read_parquet(FEATURES_PARQUET)
    lines.append(f"rows:              {len(df)}")
    feat_cols = [c for c in df.columns if c not in {"config_id", "corpus_id", "config_hash", "feature_version", "audible", "loudness_path"}]
    lines.append(f"feature cols:      {len(feat_cols)}")
    if feat_cols:
        nan_count = int(df[feat_cols].isna().sum().sum())
        lines.append(f"NaN cells:         {nan_count}")
        if nan_count:
            ok = False
        if np.isinf(df[feat_cols].to_numpy(dtype=np.float64)).any():
            lines.append("Inf values:        PRESENT")
            ok = False
        else:
            lines.append("Inf values:        none")
    else:
        ok = False

    return _verdict(ok, lines)


def check_spaces() -> bool:
    lines: list[str] = []
    ok = True
    if not SPACES_DIR.exists():
        return _verdict(False, ["missing artifacts/spaces/ — run `make spaces`"])
    found = list(SPACES_DIR.glob("*"))
    lines.append(f"space artifacts:   {len(found)}")
    expected = {"params_raw", "params_encoded", "descriptors", "embeddings", "hybrid"}
    names = {p.stem.split(".")[0] for p in found}
    missing = expected - names
    if missing:
        lines.append(f"missing conditions:{sorted(missing)}")
        # embeddings/hybrid may be absent if Family B not run
        soft = missing - {"embeddings", "hybrid"}
        if soft:
            ok = False
        else:
            lines.append("(embeddings/hybrid optional until Family B runs)")
    meta = SPACES_DIR / "metrics.json"
    if meta.exists():
        with meta.open(encoding="utf-8") as fh:
            m = json.load(fh)
        lines.append(f"distance metrics:  {m}")
    return _verdict(ok, lines)


def check_eval() -> bool:
    lines: list[str] = []
    ok = True
    if not RESULTS_DIR.exists():
        return _verdict(False, ["missing artifacts/results/ — run `make evaluate`"])
    required = ["e1_carrier_vs_modulator", "e1_tl_carrier_vs_modulator", "evaluate_all"]
    found_any_required = False
    for name in required:
        hits = list(RESULTS_DIR.glob(f"{name}*"))
        lines.append(f"{name}: {'OK' if hits else 'absent'}")
        if hits:
            found_any_required = True
    if not found_any_required:
        ok = False
    others = sorted({p.name for p in RESULTS_DIR.iterdir()})
    lines.append(f"all results:       {others}")
    return _verdict(ok, lines)
