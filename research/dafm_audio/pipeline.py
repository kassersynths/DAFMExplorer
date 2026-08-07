"""Stage orchestration: the functions the Makefile and CLI call.

Each stage writes its artifacts plus a provenance record, emits sentinel log lines
and is idempotent. Stages never depend on interactive state, which is what makes
them resumable and testable in CI.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from . import corpus as corpus_mod
from . import encoding, inertness, logs, provenance
from .paths import (
    ARTIFACTS_DIR,
    CORPUS_PARQUET,
    CORPUS_STATS_JSON,
    FEATURES_PARQUET,
    QUARANTINE_PARQUET,
    SOURCE_CSV,
    SPLITS_PARQUET,
    TL_GROUPS_PARQUET,
    ensure_dirs,
    load_config,
)


def build_corpus(*, seed: int = 42) -> dict[str, Any]:
    """Phase 0A + 0B: freeze the source, build identifiers, splits and TL groups."""
    ensure_dirs()
    with logs.stage("corpus") as done:
        csv_sha = provenance.sha256_file(SOURCE_CSV)
        policy = corpus_mod.DEFAULT_DEDUP
        cid = provenance.corpus_id(csv_sha, policy.key())

        raw = corpus_mod.load_source()
        table, stats = corpus_mod.build(raw, policy)
        table["corpus_id"] = cid

        valid = table[table["is_valid"]]
        round_trip = encoding.round_trip_matches(valid)
        if not bool(round_trip.all()):
            raise AssertionError(
                f"encoding round trip failed for {int((~round_trip).sum())} valid rows"
            )

        splits = corpus_mod.make_splits(table, seed=seed)
        split_check = corpus_mod.verify_split_disjoint(table, splits)
        leaked = sum(split_check["core_overlaps"].values())
        if leaked or split_check["configs_in_multiple_splits"]:
            raise AssertionError(f"split leakage detected: {split_check}")

        tl_groups = corpus_mod.tl_variant_groups(table)

        table.to_parquet(CORPUS_PARQUET, index=False)
        splits.to_parquet(SPLITS_PARQUET, index=False)
        tl_groups.to_parquet(TL_GROUPS_PARQUET, index=False)
        table[~table["is_valid"]].to_parquet(QUARANTINE_PARQUET, index=False)

        report = {
            "corpus_id": cid,
            "source_csv_sha256": csv_sha,
            "dedup_policy": policy.key(),
            "encoding_policy": encoding.DEFAULT_POLICY.key(),
            "inertness": inertness.summary(),
            "split_check": split_check,
            "tl_groups": tl_groups["group_type"].value_counts().to_dict(),
            "tl_groups_total": int(len(tl_groups)),
            "seed": seed,
            **stats.to_dict(),
        }
        with CORPUS_STATS_JSON.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)

        provenance.write(
            CORPUS_PARQUET,
            stage="corpus",
            inputs={"source_csv": str(SOURCE_CSV), "source_csv_sha256": csv_sha},
            params={"dedup": policy.key(), "encoding": encoding.DEFAULT_POLICY.key()},
            metrics=stats.to_dict(),
            seeds={"splits": seed},
        )

        done["presets"] = stats.n_presets
        done["configs"] = stats.n_configs
        done["cores"] = stats.n_cores
        done["quarantined"] = stats.n_presets_quarantined
        done["corpus_id"] = cid
    return report


def load_corpus() -> pd.DataFrame:
    if not CORPUS_PARQUET.exists():
        raise FileNotFoundError(
            f"missing {CORPUS_PARQUET}. Run `make corpus` (step 2 of the runbook) first."
        )
    return pd.read_parquet(CORPUS_PARQUET)


def load_corpus_stats() -> dict[str, Any]:
    if not CORPUS_STATS_JSON.exists():
        return {}
    with CORPUS_STATS_JSON.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def corpus_id() -> str:
    stats = load_corpus_stats()
    return stats.get("corpus_id", "unknown")


def render_config_hash() -> str:
    return provenance.config_hash("render")


def resolved_render_config() -> dict[str, Any]:
    return load_config("render")


def build_features(*, limit: int | None = None, family: str = "both") -> dict[str, Any]:
    """Phase 2: Family A descriptors and/or Family B embeddings."""
    ensure_dirs()
    from . import descriptors as descriptors_mod

    report: dict[str, Any] = {"family": family}
    with logs.stage("features", family=family, limit=limit) as done:
        if family in ("a", "both"):
            desc = descriptors_mod.extract_corpus(limit=limit)
            report["descriptors_rows"] = int(len(desc))
            report["descriptors_cols"] = int(desc.shape[1]) if len(desc) else 0
        if family in ("b", "both"):
            try:
                from . import embeddings as embeddings_mod

                emb = embeddings_mod.extract_embeddings(limit=limit)
                report["embeddings_rows"] = int(len(emb))
            except ImportError as exc:
                report["embeddings_rows"] = 0
                report["embeddings_error"] = str(exc)
        if FEATURES_PARQUET.exists():
            provenance.write(
                FEATURES_PARQUET,
                stage="features",
                params={"limit": limit, "family": family},
                metrics=report,
            )
        done.update({k: v for k, v in report.items() if k != "family"})
    return report


def build_spaces(*, limit: int | None = None) -> dict[str, Any]:
    """Phase 3: fit representation spaces and check ANN recall."""
    from . import index as index_mod
    from . import spaces as spaces_mod

    fitted = spaces_mod.build_spaces(limit=limit)
    recall_reports: dict[str, Any] = {}
    for name, space in fitted.items():
        try:
            recall_reports[name] = index_mod.verify_ann_recall(
                space.X_pca,
                metric=space.metric,  # type: ignore[arg-type]
                n_queries=min(100, len(space.config_ids)),
                seed=42,
            )
        except Exception as exc:  # noqa: BLE001
            recall_reports[name] = {"skipped": True, "reason": str(exc)}
    return {
        "conditions": list(fitted.keys()),
        "n_spaces": len(fitted),
        "rows": {k: int(v.meta.get("n_rows", 0)) for k, v in fitted.items()},
        "ann_recall": recall_reports,
    }


def run_evaluation(
    *,
    limit: int | None = None,
    experiment: str = "all",
    execute_e2: bool = False,
) -> dict[str, Any]:
    """Phase 4: run E1–E7 (or a named subset)."""
    from . import evaluate as evaluate_mod

    if experiment.lower() in ("all", "*"):
        return evaluate_mod.run_all(limit=limit, execute_e2=execute_e2)

    key = experiment.upper()
    if not key.startswith("E"):
        key = f"E{key}"
    if key == "E2":
        return {"E2": evaluate_mod.e2_perturbation_plan(limit=limit, execute=execute_e2)}
    mapping = {
        "E1": evaluate_mod.e1_carrier_vs_modulator,
        "E3": evaluate_mod.e3_mcadams_cca,
        "E4": evaluate_mod.e4_rank_correlation,
        "E5": evaluate_mod.e5_mfccd_summary,
        "E6": evaluate_mod.e6_listening_triads,
        "E7": evaluate_mod.e7_game_footprint,
    }
    if key not in mapping:
        raise ValueError(f"unknown experiment {experiment!r}; choose E1..E7 or all")
    return {key: mapping[key](limit=limit)}


def build_morph(*, n_components: int | float = 8) -> dict[str, Any]:
    """Phase 6 Capacity A: PCA macro-controls on encoded parameters."""
    from . import morph as morph_mod

    model = morph_mod.build_morph(n_components=n_components)
    return {
        "n_components": model.n_components(),
        "explained_variance_ratio_sum": float(model.pca.explained_variance_ratio_.sum()),
        "n_presets": int(len(model.config_ids)),
        "path": str(ARTIFACTS_DIR / "morph"),
    }


def export_hf(*, out_dir=None, n_audio_samples: int = 100) -> dict[str, Any]:
    """Phase 5: declarative HuggingFace export."""
    from . import hf_export as hf_export_mod

    path = hf_export_mod.export_dataset(out_dir=out_dir, n_audio_samples=n_audio_samples)
    return {"out_dir": str(path), "n_audio_samples": n_audio_samples}
