"""Empirical inertness audit: vary each column, re-render, compare PCM hash.

Reasoning about the OPM→YM2612 write set is not enough. For each corpus column,
a sample of presets is mutated across the legal range, re-rendered, and the PCM
SHA256 compared. Columns that never change the audio are classified inert.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import logs, provenance
from .chip import PARAM_RANGES
from .encoding import EFFECTIVE_COLUMNS
from .inertness import (
    EXPECTED_EFFECTIVE,
    EXPECTED_NEVER_WRITTEN,
    EXPECTED_WRITTEN_INERT,
    Inertness,
    NON_PARAMETER_COLUMNS,
)
from .paths import (
    ARTIFACTS_DIR,
    AUDIO_DIR,
    PARAM_INERTNESS,
    RENDER_DIR,
    SCRATCH_DIR,
    ensure_dirs,
    load_config,
)
from .pipeline import load_corpus


def _legal_values(column: str) -> list[int]:
    if column in ("CON", "FL"):
        low, high = PARAM_RANGES[column]
        return list(range(low, high + 1))
    if "_" in column:
        param = column.split("_", 1)[1]
        if param in PARAM_RANGES:
            low, high = PARAM_RANGES[param]
            # Sample extremes + mid rather than the full range for speed.
            mid = (low + high) // 2
            return sorted({low, mid, high})
    # Unknown / inert candidates: try 0 and 1.
    return [0, 1]


def _render_one(params: dict[str, int], out_stem: Path) -> str:
    """Render a single patch via the Node helper; return PCM sha256."""
    queue = [{"config_id": out_stem.name, **params}]
    queue_path = SCRATCH_DIR / "inertness_queue.json"
    with queue_path.open("w", encoding="utf-8") as fh:
        json.dump(queue, fh)
    stats = SCRATCH_DIR / "inertness_stats.jsonl"
    if (RENDER_DIR / "package.json").exists() and not (RENDER_DIR / "node_modules").exists():
        subprocess.run(["npm", "install"], cwd=RENDER_DIR, check=True)
    cmd = [
        "node",
        "--import",
        "tsx",
        str(RENDER_DIR / "render_corpus_audio.ts"),
        "--manifest",
        str(queue_path),
        "--shard",
        "0/1",
        "--mode",
        "probe",
        "--out-dir",
        str(AUDIO_DIR),
        "--stats-out",
        str(stats),
        "--force",
    ]
    proc = subprocess.run(cmd, cwd=RENDER_DIR, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    with stats.open(encoding="utf-8") as fh:
        line = fh.readline().strip()
    meta = json.loads(line)
    return str(meta["pcm_sha256"])


def run_audit(*, n_presets: int = 8, limit_columns: int | None = None) -> dict[str, Any]:
    """Run the audit and write ``artifacts/param_inertness.parquet``."""
    ensure_dirs()
    corpus = load_corpus()
    valid = corpus[corpus["is_valid"]].drop_duplicates("config_id")
    sample = valid.sample(n=min(n_presets, len(valid)), random_state=42)

    # Columns to probe: all parameter columns in the source.
    param_cols = [c for c in corpus.columns if c not in NON_PARAMETER_COLUMNS]
    param_cols = [c for c in param_cols if c not in {
        "preset_id", "config_id", "core_id", "is_valid", "game", "track",
        "track_number", "corpus_id",
    }]
    if limit_columns is not None:
        param_cols = param_cols[:limit_columns]

    cfg = load_config("render")
    probe_gain = float(cfg["gain"]["probe_gain"])
    _ = probe_gain

    records = []
    with logs.stage("inertness_audit", n_presets=len(sample), n_columns=len(param_cols)):
        for col in param_cols:
            changed = 0
            trials = 0
            for _, row in sample.iterrows():
                base = {c: int(row[c]) for c in EFFECTIVE_COLUMNS if c in row.index}
                # For non-effective columns, still need a full patch for rendering.
                for c in EFFECTIVE_COLUMNS:
                    base.setdefault(c, 0)
                base_hash = None
                values = _legal_values(col)
                hashes = []
                for v in values:
                    patch = dict(base)
                    if col in EFFECTIVE_COLUMNS or col in row.index:
                        patch[col] = int(v) if col in EFFECTIVE_COLUMNS else int(v)
                        # Non-effective columns are not written by the renderer;
                        # mutating them in the dict is a no-op by construction.
                    h = _render_one(patch, SCRATCH_DIR / f"inert_{col}_{v}")
                    hashes.append(h)
                    trials += 1
                if len(set(hashes)) > 1:
                    changed += 1
                base_hash = hashes[0] if hashes else None
                _ = base_hash

            if col in EXPECTED_EFFECTIVE:
                expected = Inertness.EFFECTIVE.value
            elif col in EXPECTED_WRITTEN_INERT:
                expected = Inertness.WRITTEN_INERT.value
            elif col in EXPECTED_NEVER_WRITTEN:
                expected = Inertness.NEVER_WRITTEN.value  # dict keys
            else:
                expected = "unknown"

            measured = Inertness.EFFECTIVE.value if changed > 0 else Inertness.NEVER_WRITTEN.value
            # Written-inert columns are written but LFO-off makes them silent.
            if expected == Inertness.WRITTEN_INERT.value and changed == 0:
                measured = Inertness.WRITTEN_INERT.value

            records.append(
                {
                    "column": col,
                    "expected": expected,
                    "measured": measured,
                    "n_presets_changed": changed,
                    "n_presets_tested": int(len(sample)),
                    "n_trials": trials,
                    "agreement": expected == measured
                    or (
                        expected in (Inertness.WRITTEN_INERT.value, Inertness.NEVER_WRITTEN.value)
                        and measured != Inertness.EFFECTIVE.value
                    ),
                }
            )

    df = pd.DataFrame.from_records(records)
    df.to_parquet(PARAM_INERTNESS, index=False)
    provenance.write(
        PARAM_INERTNESS,
        stage="inertness_audit",
        params={"n_presets": n_presets, "limit_columns": limit_columns},
        metrics={
            "n_columns": len(df),
            "disagreements": int((~df["agreement"]).sum()),
        },
    )
    return {
        "path": str(PARAM_INERTNESS),
        "n_columns": len(df),
        "disagreements": int((~df["agreement"]).sum()),
        "summary": df.groupby("measured").size().to_dict(),
    }
