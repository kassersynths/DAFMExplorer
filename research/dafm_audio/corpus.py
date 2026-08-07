"""Corpus construction: parsing, canonicalisation, three-level dedup and splits.

Starting point is ``data/processed/all_instruments_final.csv``, which is the single
inheritance from earlier work in this repository. The original ``OPM presets.zip``
is not available, so this CSV is the canonical origin and the reproducible chain
starts here. That is a limitation, and it is declared rather than hidden: the CSV is
frozen with a SHA256 and published alongside the dataset so everything downstream is
reproducible bit for bit from a verifiable point.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from . import provenance
from .chip import OPERATOR_NAMES
from .encoding import EFFECTIVE_COLUMNS, canonicalize_registers, count_canonicalization_changes
from .inertness import NON_PARAMETER_COLUMNS, effective_columns
from .paths import SOURCE_CSV

# ---------------------------------------------------------------------------
# Filename parsing
# ---------------------------------------------------------------------------
# Filenames look like "Boogerman_-_01_-_Title_Theme.opm": game, then track number,
# then track title, separated by "_-_".
#
# The separator is deliberately the full "_-_" and not a bare hyphen, because game
# titles contain internal hyphens ("Spider-Man_&_X-Men") and splitting on "-" would
# mangle them. Underscores stand in for spaces.
_SEPARATOR = "_-_"
_TRACK_NUMBER = re.compile(r"^(\d+)$")


@dataclass(frozen=True)
class ParsedFilename:
    game: str
    track_number: int | None
    track: str


def parse_filename(filename: str) -> ParsedFilename:
    """Split a source filename into game, track number and track title.

    Source values are preserved verbatim apart from turning underscores back into
    spaces. Game and track titles come from the data and are NOT normalised beyond
    that: normalising them, including their non-ASCII characters and
    transliterations, would corrupt the provenance.
    """
    stem = filename
    for suffix in (".opm", ".OPM"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break

    parts = stem.split(_SEPARATOR)
    game_raw = parts[0] if parts else stem

    track_number: int | None = None
    track_parts: list[str] = []
    if len(parts) >= 2:
        candidate = parts[1]
        if _TRACK_NUMBER.match(candidate):
            track_number = int(candidate)
            track_parts = parts[2:]
        else:
            track_parts = parts[1:]

    track_raw = _SEPARATOR.join(track_parts) if track_parts else ""
    return ParsedFilename(
        game=_unescape(game_raw),
        track_number=track_number,
        track=_unescape(track_raw),
    )


def _unescape(text: str) -> str:
    return text.replace("_", " ").strip()


# ---------------------------------------------------------------------------
# Deduplication policy
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DedupPolicy:
    """The three levels of granularity, made explicit.

    Level 1 (``preset``) is the catalogue unit: every row of the source CSV.

    Level 2 (``config``) is the render and feature-extraction unit: distinct values
    of the EFFECTIVE parameters after canonicalisation. Deduplicating on the
    effective set rather than all 56 columns is what stops us rendering the same
    audio twice for presets that differ only in an inert column.

    Level 3 (``core``) is the timbral core: distinct effective parameters ignoring
    TL. This is the split unit, because the real leakage risk is not composer
    identity but near-duplicates shared across games by reusing the same sound
    driver.
    """

    canonicalize_dt1: bool = True
    dedup_on_effective_only: bool = True
    core_ignores_tl: bool = True
    version: str = "v1"

    def key(self) -> dict[str, Any]:
        return {
            "canonicalize_dt1": self.canonicalize_dt1,
            "dedup_on_effective_only": self.dedup_on_effective_only,
            "core_ignores_tl": self.core_ignores_tl,
            "version": self.version,
        }


DEFAULT_DEDUP = DedupPolicy()


def _core_columns() -> list[str]:
    tl_columns = {f"{op}_TL" for op in OPERATOR_NAMES}
    return [c for c in EFFECTIVE_COLUMNS if c not in tl_columns]


def _hash_rows(df: pd.DataFrame, columns: list[str], length: int = 16) -> pd.Series:
    """Stable content hash per row over the given columns.

    Built from a canonical text join rather than pandas' own hashing, so the same
    rows produce the same identifier across machines and pandas versions. That
    matters because these ids end up in filenames and in the published dataset.
    """
    joined = df[columns].astype(np.int64).astype(str).agg("|".join, axis=1)
    prefix = "|".join(columns)
    return joined.map(lambda row: provenance.sha256_obj({"c": prefix, "v": row})[:length])


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Range validation and quarantine
# ---------------------------------------------------------------------------
def validate_effective_ranges(df: pd.DataFrame) -> pd.DataFrame:
    """Per-row, per-column legality of the effective register values.

    Necessary because the source CSV contains a handful of rows whose values are
    impossible for the hardware: a Total Level in the millions, a multiplier of
    -1. Those are upstream extraction damage, not exotic presets.

    They must not be silently clipped. The renderer masks with ``& 127`` and
    ``& 15``, so clipping would quietly turn corruption into arbitrary but
    plausible-sounding audio. Worse, a TL of 2.29e6 sitting in the parameter
    baseline would dominate ``StandardScaler`` and hijack the leading principal
    components, wrecking the very comparison the paper is about.

    So they are detected, quarantined, counted and reported.
    """
    from .chip import GLOBAL_PARAMS as _GLOBALS
    from .chip import PARAM_RANGES, PER_OPERATOR_PARAMS

    checks: dict[str, pd.Series] = {}
    for param in _GLOBALS:
        low, high = PARAM_RANGES[param]
        checks[param] = df[param].between(low, high)
    for op in OPERATOR_NAMES:
        for param in PER_OPERATOR_PARAMS:
            col = f"{op}_{param}"
            low, high = PARAM_RANGES[param]
            checks[col] = df[col].between(low, high)
    return pd.DataFrame(checks, index=df.index)


@dataclass
class CorpusStats:
    n_presets: int = 0
    n_presets_valid: int = 0
    n_presets_quarantined: int = 0
    n_configs: int = 0
    n_cores: int = 0
    n_games: int = 0
    n_configs_before_canonicalization: int = 0
    n_configs_all_56_columns: int = 0
    canonicalization_changes: dict[str, int] = field(default_factory=dict)
    quarantined_by_column: dict[str, int] = field(default_factory=dict)
    inert_column_cardinality: dict[str, int] = field(default_factory=dict)
    largest_game: str = ""
    largest_game_share: float = 0.0
    exact_duplicate_share: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_presets": self.n_presets,
            "n_presets_valid": self.n_presets_valid,
            "n_presets_quarantined": self.n_presets_quarantined,
            "n_configs": self.n_configs,
            "n_cores": self.n_cores,
            "n_games": self.n_games,
            "n_configs_before_canonicalization": self.n_configs_before_canonicalization,
            "n_configs_all_56_columns": self.n_configs_all_56_columns,
            "canonicalization_changes": self.canonicalization_changes,
            "quarantined_by_column": self.quarantined_by_column,
            "inert_column_cardinality": self.inert_column_cardinality,
            "largest_game": self.largest_game,
            "largest_game_share": self.largest_game_share,
            "exact_duplicate_share": self.exact_duplicate_share,
        }


def load_source(csv_path=None) -> pd.DataFrame:
    """Read the frozen source CSV."""
    path = csv_path or SOURCE_CSV
    if not path.exists():
        raise FileNotFoundError(
            f"missing canonical corpus CSV: {path}. This file is the declared "
            "starting point of the reproducible chain and cannot be regenerated "
            "from the published artifacts."
        )
    return pd.read_csv(path)


def build(
    df: pd.DataFrame | None = None,
    policy: DedupPolicy = DEFAULT_DEDUP,
) -> tuple[pd.DataFrame, CorpusStats]:
    """Build the canonical corpus table with the three identifier levels.

    Returns one row per source preset, carrying ``preset_id``, ``config_id`` and
    ``core_id`` plus the parsed ``game``/``track`` metadata, so the mapping back from
    a rendered configuration to every catalogue entry that uses it is never lost.
    """
    if df is None:
        df = load_source()

    stats = CorpusStats()
    stats.n_presets = len(df)

    effective = effective_columns()
    missing = [c for c in effective if c not in df.columns]
    if missing:
        raise KeyError(f"source CSV lacks effective parameter columns: {missing}")

    # Measured for the record rather than assumed: how many unique configurations
    # the naive "all 56 columns" view reports, versus the effective-parameter view.
    # Reporting both is what makes the correction auditable.
    param_columns_all = [c for c in df.columns if c not in NON_PARAMETER_COLUMNS]
    stats.n_configs_all_56_columns = int(df[param_columns_all].drop_duplicates().shape[0])
    stats.n_configs_before_canonicalization = int(df[effective].drop_duplicates().shape[0])

    # How much variation each inert column actually carries. In this corpus the
    # answer turns out to be none at all, which changes the practical consequence
    # of the inertness finding and is therefore recorded explicitly.
    from .inertness import inert_columns as _inert

    stats.inert_column_cardinality = {
        col: int(df[col].nunique()) for col in _inert() if col in df.columns
    }

    out = df.copy()

    # Quarantine before anything else, so corrupt rows cannot reach the identifier
    # hashes, the dedup counts, the splits or the render queue.
    validity = validate_effective_ranges(out)
    row_valid = validity.all(axis=1)
    stats.quarantined_by_column = {
        col: int((~validity[col]).sum()) for col in validity.columns if not validity[col].all()
    }
    stats.n_presets_quarantined = int((~row_valid).sum())
    stats.n_presets_valid = int(row_valid.sum())
    out["is_valid"] = row_valid.to_numpy()

    if policy.canonicalize_dt1:
        stats.canonicalization_changes = count_canonicalization_changes(out)
        out = canonicalize_registers(out)

    parsed = out["Filename"].map(parse_filename)
    out["game"] = [p.game for p in parsed]
    out["track_number"] = [p.track_number for p in parsed]
    out["track"] = [p.track for p in parsed]

    out["preset_id"] = [f"p{i:06d}" for i in range(len(out))]
    # Quarantined rows get no configuration or core identity: they are catalogue
    # entries only, and nothing downstream may pick them up by accident.
    out["config_id"] = _hash_rows(out, effective).where(out["is_valid"], pd.NA)
    out["core_id"] = _hash_rows(out, _core_columns()).where(out["is_valid"], pd.NA)

    valid = out[out["is_valid"]]
    stats.n_configs = int(valid["config_id"].nunique())
    stats.n_cores = int(valid["core_id"].nunique())
    stats.n_games = int(out["game"].nunique())

    game_counts = out["game"].value_counts()
    if len(game_counts):
        stats.largest_game = str(game_counts.index[0])
        stats.largest_game_share = float(game_counts.iloc[0] / len(out))
    stats.exact_duplicate_share = float(1.0 - stats.n_configs / max(len(valid), 1))

    ordered = [
        "preset_id",
        "config_id",
        "core_id",
        "is_valid",
        "game",
        "track_number",
        "track",
        "Num",
        "Name",
        "Filename",
    ]
    remaining = [c for c in out.columns if c not in ordered]
    return out[ordered + remaining], stats


def unique_configs(corpus: pd.DataFrame) -> pd.DataFrame:
    """One row per configuration to render, quarantined rows excluded.

    The first occurrence wins, so the representative is deterministic given the
    source ordering.
    """
    effective = effective_columns()
    valid = corpus[corpus["is_valid"]] if "is_valid" in corpus.columns else corpus
    configs = valid.drop_duplicates(subset="config_id", keep="first")
    return configs[["config_id", "core_id", *effective]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Splits
# ---------------------------------------------------------------------------
def make_splits(
    corpus: pd.DataFrame,
    *,
    fractions: tuple[float, float, float] = (0.7, 0.15, 0.15),
    seed: int = 42,
) -> pd.DataFrame:
    """Assign train/val/test at the level of the timbral CORE.

    The real leakage here is not composer identity, which we do not have anyway, but
    near-duplicates shared across games because studios reused the same sound driver.
    Splitting by core therefore guarantees that no TL variant of one core lands in
    two splits, which a naive per-preset split would allow.

    Stratified by the core's dominant game so that no single title concentrates in
    one split, and seeded so the assignment is reproducible.

    Methodological note: PCA, UMAP and KMeans are unsupervised, so the split only
    matters for fitting transforms and thresholds. Those are fitted on train and
    applied frozen, which is documented in the paper rather than left implicit.
    """
    if not np.isclose(sum(fractions), 1.0):
        raise ValueError(f"split fractions must sum to 1, got {fractions}")

    valid = corpus[corpus["is_valid"]] if "is_valid" in corpus.columns else corpus
    core_game = (
        valid.groupby("core_id")["game"]
        .agg(lambda s: s.value_counts().index[0])
        .rename("stratum")
        .reset_index()
    )

    rng = np.random.default_rng(seed)
    assignments: list[pd.DataFrame] = []
    train_f, val_f, _ = fractions

    for stratum, group in core_game.groupby("stratum", sort=True):
        cores = group["core_id"].to_numpy()
        # Sort before shuffling so the permutation depends only on the seed and not
        # on incoming row order.
        cores = np.sort(cores)
        rng.shuffle(cores)
        n = len(cores)
        n_train = int(round(n * train_f))
        n_val = int(round(n * val_f))
        # With very few cores in a stratum, rounding can overflow; clamp so test is
        # never negative and every core is assigned exactly once.
        n_train = min(n_train, n)
        n_val = min(n_val, n - n_train)
        labels = np.array(["test"] * n, dtype=object)
        labels[:n_train] = "train"
        labels[n_train : n_train + n_val] = "val"
        assignments.append(
            pd.DataFrame({"core_id": cores, "split": labels, "stratum": stratum})
        )

    splits = pd.concat(assignments, ignore_index=True)
    return splits[["core_id", "split", "stratum"]]


def verify_split_disjoint(corpus: pd.DataFrame, splits: pd.DataFrame) -> dict[str, Any]:
    """Check that no timbral core and no configuration appears in two splits."""
    valid = corpus[corpus["is_valid"]] if "is_valid" in corpus.columns else corpus
    merged = valid.merge(splits, on="core_id", how="left")
    if merged["split"].isna().any():
        raise AssertionError("some cores were not assigned to a split")

    cores_per_split = merged.groupby("split")["core_id"].apply(set)
    overlaps: dict[str, int] = {}
    names = sorted(cores_per_split.index)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            overlaps[f"{a}|{b}"] = len(cores_per_split[a] & cores_per_split[b])

    config_split_counts = merged.groupby("config_id")["split"].nunique()
    return {
        "core_overlaps": overlaps,
        "configs_in_multiple_splits": int((config_split_counts > 1).sum()),
        "sizes": merged["split"].value_counts().to_dict(),
    }


# ---------------------------------------------------------------------------
# TL variant groups: the structure that carries E1
# ---------------------------------------------------------------------------
def tl_variant_groups(corpus: pd.DataFrame) -> pd.DataFrame:
    """Groups of configurations that differ ONLY in TL, labelled by which operators move.

    This is the ground truth for E1 and it costs nothing to obtain: it comes from
    the chip's own topology rather than from any annotation. Each group is one
    timbral core containing more than one configuration, and the label says whether
    the differing TLs belong exclusively to carriers or involve a modulator.

    The distinction is the falsifiable part. Chowning (1973) says the modulation
    index sets spectral bandwidth, so a carrier-TL change is essentially amplitude
    while a modulator-TL change is spectral content. In parameter space both are the
    same Euclidean distance; in audio space they cannot be.
    """
    from .chip import carrier_indices

    configs = unique_configs(corpus)

    sizes = configs.groupby("core_id").size()
    multi = sizes[sizes > 1].index
    subset = configs[configs["core_id"].isin(multi)]

    records = []
    for core_id, group in subset.groupby("core_id", sort=True):
        algorithm = int(group["CON"].iloc[0])
        carriers = set(carrier_indices(algorithm))
        varying: list[str] = []
        for idx, op in enumerate(OPERATOR_NAMES):
            col = f"{op}_TL"
            if group[col].nunique() > 1:
                varying.append(op)
        if not varying:
            continue
        varying_indices = {OPERATOR_NAMES.index(op) for op in varying}
        involves_modulator = bool(varying_indices - carriers)
        records.append(
            {
                "core_id": core_id,
                "algorithm": algorithm,
                "n_configs": int(len(group)),
                "varying_operators": ",".join(varying),
                "group_type": "modulator" if involves_modulator else "carrier_only",
            }
        )

    return pd.DataFrame.from_records(
        records,
        columns=["core_id", "algorithm", "n_configs", "varying_operators", "group_type"],
    )
