"""Canonical filesystem locations and config loading.

Everything the package writes lives under ``research/``. The repository root is
read-only from here, with exactly two exceptions that are read, never written:
the source CSV and the emulator core.
"""

from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Any

import yaml

RESEARCH_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = RESEARCH_DIR.parent

CONFIG_DIR = RESEARCH_DIR / "configs"
ARTIFACTS_DIR = RESEARCH_DIR / "artifacts"
SCRATCH_DIR = RESEARCH_DIR / "scratch"
AUDIO_DIR = SCRATCH_DIR / "audio"
LOG_DIR = SCRATCH_DIR / "logs"
RENDER_DIR = RESEARCH_DIR / "render"
HARDWARE_DIR = RESEARCH_DIR / "hardware"
PAPER_DIR = REPO_ROOT / "TISMIR-SoundSimilarity-LaTeX"

# The two read-only dependencies on the repository root.
SOURCE_CSV = REPO_ROOT / "data" / "processed" / "all_instruments_final.csv"
EMULATOR_CORE = REPO_ROOT / "webapp" / "services" / "audio" / "ym2612_core.ts"

CORPUS_PARQUET = ARTIFACTS_DIR / "corpus_v1.parquet"
CORPUS_STATS_JSON = ARTIFACTS_DIR / "corpus_stats.json"
SPLITS_PARQUET = ARTIFACTS_DIR / "splits.parquet"
TL_GROUPS_PARQUET = ARTIFACTS_DIR / "tl_variant_groups.parquet"
QUARANTINE_PARQUET = ARTIFACTS_DIR / "quarantined_presets.parquet"
RENDER_MANIFEST = ARTIFACTS_DIR / "render_manifest.parquet"
RENDER_QUEUE_JSON = ARTIFACTS_DIR / "render_queue.json"
RENDER_INDEX_JSON = ARTIFACTS_DIR / "render_index.json"
PARAM_INERTNESS = ARTIFACTS_DIR / "param_inertness.parquet"
AUDIO_STATS = ARTIFACTS_DIR / "audio_stats.parquet"
FEATURES_PARQUET = ARTIFACTS_DIR / "features.parquet"
FEATURES_EXCLUDED_PARQUET = ARTIFACTS_DIR / "features_excluded.parquet"
EMBEDDINGS_PARQUET = ARTIFACTS_DIR / "embeddings.parquet"
SPACES_DIR = ARTIFACTS_DIR / "spaces"
RESULTS_DIR = ARTIFACTS_DIR / "results"
MORPH_DIR = ARTIFACTS_DIR / "morph"
HF_EXPORT_DIR = ARTIFACTS_DIR / "hf_export"
HW_DIR = ARTIFACTS_DIR / "hw"


def ensure_dirs() -> None:
    """Create the writable tree. Safe to call repeatedly."""
    for d in (
        ARTIFACTS_DIR,
        SCRATCH_DIR,
        AUDIO_DIR,
        LOG_DIR,
        SPACES_DIR,
        RESULTS_DIR,
        MORPH_DIR,
        HF_EXPORT_DIR,
        HW_DIR,
    ):
        d.mkdir(parents=True, exist_ok=True)


@functools.lru_cache(maxsize=None)
def load_config(name: str) -> dict[str, Any]:
    """Load ``configs/<name>.yaml``.

    Cached, because config contents feed into ``config_hash`` and must not change
    within a single run.
    """
    path = CONFIG_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"missing config: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def machine_profile() -> dict[str, Any]:
    """Resolve the active machine profile.

    Selected by ``DAFM_MACHINE`` (``a`` or ``b``), falling back to the configured
    default. Keeping this in config rather than in code is what lets the same
    command run well on both boxes.
    """
    cfg = load_config("machines")
    key = os.environ.get("DAFM_MACHINE", cfg.get("default", "a")).lower()
    profiles = cfg["profiles"]
    if key not in profiles:
        raise ValueError(f"unknown machine profile {key!r}; available: {sorted(profiles)}")
    profile = dict(profiles[key])
    profile["id"] = key
    profile["policy"] = cfg.get("policy", {})
    return profile


def audio_path(config_id: str, prefix_len: int = 2) -> Path:
    """Location of the rendered FLAC for a configuration.

    Partitioned by hash prefix: tens of thousands of files in one directory is
    painful on Windows.
    """
    return AUDIO_DIR / config_id[:prefix_len] / f"{config_id}.flac"
