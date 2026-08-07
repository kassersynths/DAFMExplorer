"""Corpus construction invariants against the real source CSV."""

from __future__ import annotations

import pytest

from dafm_audio import corpus as corpus_mod
from dafm_audio.paths import SOURCE_CSV


pytestmark = pytest.mark.skipif(not SOURCE_CSV.exists(), reason="source CSV absent")


def test_build_counts_and_identifiers():
    raw = corpus_mod.load_source()
    assert len(raw) == 93832
    table, stats = corpus_mod.build(raw)
    assert stats.n_presets == 93832
    assert stats.n_configs > 0
    assert stats.n_cores > 0
    assert stats.n_configs < stats.n_presets  # dedup saves work
    # Effective-only dedup + DT1 canonicalisation must not exceed the naive 56-col count
    assert stats.n_configs <= stats.n_configs_all_56_columns
    assert table["preset_id"].is_unique
    valid = table[table["is_valid"]]
    assert valid["config_id"].notna().all()
    assert valid["core_id"].notna().all()


def test_splits_disjoint_cores():
    table, _ = corpus_mod.build()
    splits = corpus_mod.make_splits(table, seed=42)
    check = corpus_mod.verify_split_disjoint(table, splits)
    assert sum(check["core_overlaps"].values()) == 0
    assert check["configs_in_multiple_splits"] == 0


def test_tl_variant_groups_labelled():
    table, _ = corpus_mod.build()
    groups = corpus_mod.tl_variant_groups(table)
    assert set(groups["group_type"]).issubset({"carrier_only", "modulator"})
    assert len(groups) > 0
