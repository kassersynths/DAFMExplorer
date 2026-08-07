"""Declarative HuggingFace dataset export.

Builds parquet tables without a loading script, an opaque identifier mapping for
game/track titles (retirable), a sample of FLAC audio, and a dataset card that
quantifies known biases.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import logs, provenance
from .paths import (
    CORPUS_PARQUET,
    FEATURES_PARQUET,
    HF_EXPORT_DIR,
    SOURCE_CSV,
    audio_path,
    ensure_dirs,
)

logger = logging.getLogger(__name__)

DATASET_CARD_TEMPLATE = """---
pretty_name: DAFM Explorer YM2612 Preset Corpus
license: other
task_categories:
  - audio-classification
  - other
tags:
  - fm-synthesis
  - ym2612
  - timbre
  - presets
size_categories:
  - 10K<n<100K
---

# DAFM Explorer — YM2612 preset corpus

Declarative parquet export of the research corpus used for timbre-similarity
experiments on historical Mega Drive / YM2612 presets.

## Provenance boundary

The **only** inheritance from prior work in the source repository is the frozen
CSV `data/processed/all_instruments_final.csv`. All identifiers, splits,
descriptors and baselines are defined in the `dafm-audio` research package.

- Source CSV SHA256: `{source_sha256}`
- Corpus id: `{corpus_id}`
- Presets (catalogue rows): `{n_presets}`
- Valid presets: `{n_presets_valid}`
- Unique configurations (`config_id`): `{n_configs}`
- Timbral cores (`core_id`): `{n_cores}`
- Games: `{n_games}`

## Known biases (quantified)

- Largest game share: **{largest_game}** = {largest_game_share:.1%} of catalogue rows.
- Exact-duplicate share (1 − configs/valid presets): **{exact_duplicate_share:.1%}**.
- `Name` is auto-generated (`Instrument N`) and is **not** an instrument family label.
- Composer / GEMS metadata are **not** included in this release.

## Schema

| File | Description |
|------|-------------|
| `configs.parquet` | One row per `config_id` with effective parameters |
| `presets.parquet` | Catalogue mapping `preset_id → config_id` (no game titles) |
| `games_opaque.parquet` | Opaque `game_id` / `track_id` tables (retirable) |
| `splits.parquet` | Train/val/test by `core_id` |
| `features.parquet` | Family A descriptors (if present) |
| `sample_audio/` | Up to {n_audio_samples} FLAC renders |

## Licensing

Layered licensing: emulator code, preset parameters extracted from game soundtracks,
and rendered audio may have different constraints. See `licensing.json`. Game and
track title strings live only in `games_opaque.parquet` so they can be withdrawn
without regenerating the parameter tables.

## Citation

See the accompanying TISMIR paper (in preparation). Pin a DOI on a frozen tag
before citing numbers from this card.
"""


def _opaque_id(text: str, prefix: str) -> str:
    from . import provenance as prov

    return f"{prefix}_{prov.sha256_obj(text)[:12]}"


def build_opaque_tables(corpus: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return ``(presets_public, games_table, tracks_table)`` with opaque ids."""
    valid = corpus[corpus["is_valid"]] if "is_valid" in corpus.columns else corpus
    games = sorted(valid["game"].dropna().astype(str).unique())
    game_map = {g: _opaque_id(g, "g") for g in games}
    tracks = (
        valid[["game", "track", "track_number"]]
        .drop_duplicates()
        .assign(
            game_id=lambda d: d["game"].astype(str).map(game_map),
            track_id=lambda d: [
                _opaque_id(f"{g}|{t}|{n}", "t")
                for g, t, n in zip(d["game"], d["track"], d["track_number"], strict=False)
            ],
        )
    )
    games_table = pd.DataFrame(
        {"game_id": [game_map[g] for g in games], "game_title": games}
    )
    tracks_table = tracks[["track_id", "game_id", "track", "track_number"]].rename(
        columns={"track": "track_title"}
    )
    presets_public = valid[
        [c for c in ("preset_id", "config_id", "core_id", "Num", "Name", "Filename") if c in valid.columns]
    ].copy()
    presets_public["game_id"] = valid["game"].astype(str).map(game_map).to_numpy()
    # Attach track_id via merge keys.
    track_key = valid[["preset_id", "game", "track", "track_number"]].merge(
        tracks[["game", "track", "track_number", "track_id"]],
        on=["game", "track", "track_number"],
        how="left",
    )
    presets_public = presets_public.merge(
        track_key[["preset_id", "track_id"]], on="preset_id", how="left"
    )
    return presets_public, games_table, tracks_table


def select_sample_audio(
    config_ids: list[str],
    n: int = 100,
    *,
    seed: int = 42,
) -> list[str]:
    """Choose up to ``n`` configs that have rendered FLAC on disk."""
    rng = np.random.default_rng(seed)
    existing = [cid for cid in config_ids if audio_path(cid).exists()]
    if not existing:
        return []
    if len(existing) <= n:
        return existing
    idx = rng.choice(len(existing), size=n, replace=False)
    return [existing[i] for i in sorted(idx.tolist())]


def export_dataset(
    out_dir: str | Path | None = None,
    n_audio_samples: int = 100,
) -> Path:
    """Build the declarative HF export directory."""
    ensure_dirs()
    out_dir = Path(out_dir) if out_dir else HF_EXPORT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    with logs.stage("hf_export", out_dir=str(out_dir)) as done:
        if not CORPUS_PARQUET.exists():
            raise FileNotFoundError(CORPUS_PARQUET)
        corpus = pd.read_parquet(CORPUS_PARQUET)
        from .corpus import unique_configs
        from .paths import SPLITS_PARQUET

        configs = unique_configs(corpus)
        presets_public, games_table, tracks_table = build_opaque_tables(corpus)

        configs.to_parquet(out_dir / "configs.parquet", index=False)
        presets_public.to_parquet(out_dir / "presets.parquet", index=False)
        games_table.to_parquet(out_dir / "games_opaque.parquet", index=False)
        tracks_table.to_parquet(out_dir / "tracks_opaque.parquet", index=False)

        if SPLITS_PARQUET.exists():
            pd.read_parquet(SPLITS_PARQUET).to_parquet(out_dir / "splits.parquet", index=False)
        if FEATURES_PARQUET.exists():
            # Drop nothing structurally; card documents sensitivity.
            pd.read_parquet(FEATURES_PARQUET).to_parquet(out_dir / "features.parquet", index=False)

        sample_ids = select_sample_audio(
            configs["config_id"].astype(str).tolist(), n=n_audio_samples
        )
        audio_out = out_dir / "sample_audio"
        audio_out.mkdir(exist_ok=True)
        copied = 0
        for cid in sample_ids:
            src = audio_path(cid)
            dst = audio_out / f"{cid}.flac"
            try:
                shutil.copy2(src, dst)
                copied += 1
            except OSError as exc:
                logger.warning("could not copy %s: %s", src, exc)

        stats: dict[str, Any] = {}
        from .paths import CORPUS_STATS_JSON

        if CORPUS_STATS_JSON.exists():
            with CORPUS_STATS_JSON.open("r", encoding="utf-8") as fh:
                stats = json.load(fh)

        source_sha = provenance.sha256_file(SOURCE_CSV) if SOURCE_CSV.exists() else "unknown"
        card = DATASET_CARD_TEMPLATE.format(
            source_sha256=source_sha,
            corpus_id=stats.get("corpus_id", "unknown"),
            n_presets=stats.get("n_presets", len(corpus)),
            n_presets_valid=stats.get("n_presets_valid", int(corpus.get("is_valid", True).sum() if "is_valid" in corpus else len(corpus))),
            n_configs=stats.get("n_configs", len(configs)),
            n_cores=stats.get("n_cores", corpus["core_id"].nunique() if "core_id" in corpus else 0),
            n_games=stats.get("n_games", corpus["game"].nunique() if "game" in corpus else 0),
            largest_game=stats.get("largest_game", "unknown"),
            largest_game_share=float(stats.get("largest_game_share", 0.0)),
            exact_duplicate_share=float(stats.get("exact_duplicate_share", 0.0)),
            n_audio_samples=n_audio_samples,
        )
        (out_dir / "README.md").write_text(card, encoding="utf-8")

        licensing = {
            "layers": [
                {
                    "layer": "parameters",
                    "note": "Register values extracted from historical game soundtracks; verify redistribution rights before broad release.",
                },
                {
                    "layer": "rendered_audio",
                    "note": "Emulated YM2612 renders under the declared research protocol.",
                },
                {
                    "layer": "titles",
                    "note": "Game/track titles isolated in games_opaque.parquet / tracks_opaque.parquet and retirable.",
                },
            ]
        }
        with (out_dir / "licensing.json").open("w", encoding="utf-8") as fh:
            json.dump(licensing, fh, indent=2)

        provenance.write(
            out_dir / "configs.parquet",
            stage="hf_export",
            inputs={"corpus": str(CORPUS_PARQUET), "source_csv_sha256": source_sha},
            params={"n_audio_samples": n_audio_samples},
            metrics={"n_configs": int(len(configs)), "n_audio_copied": copied},
        )
        done["n_configs"] = len(configs)
        done["n_audio"] = copied

    return out_dir
