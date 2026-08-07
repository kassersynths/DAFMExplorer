"""Pipeline progress: which artifacts exist and what to run next."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .paths import (
    AUDIO_DIR,
    CORPUS_PARQUET,
    CORPUS_STATS_JSON,
    EMBEDDINGS_PARQUET,
    FEATURES_PARQUET,
    HF_EXPORT_DIR,
    MORPH_DIR,
    RENDER_MANIFEST,
    RESULTS_DIR,
    SPLITS_PARQUET,
    SPACES_DIR,
    TL_GROUPS_PARQUET,
)


@dataclass(frozen=True)
class StageInfo:
    name: str
    command: str
    artifacts: tuple[Path, ...]
    optional_artifacts: tuple[Path, ...] = ()

    def complete(self) -> bool:
        return all(p.exists() for p in self.artifacts)

    def present(self) -> list[str]:
        found = []
        for p in self.artifacts + self.optional_artifacts:
            if p.exists():
                found.append(str(p))
        return found


STAGES: tuple[StageInfo, ...] = (
    StageInfo(
        "corpus",
        "dafm corpus / make corpus",
        (CORPUS_PARQUET, SPLITS_PARQUET, TL_GROUPS_PARQUET, CORPUS_STATS_JSON),
    ),
    StageInfo(
        "render",
        "make render (Phase 1)",
        (RENDER_MANIFEST,),
        optional_artifacts=(AUDIO_DIR,),
    ),
    StageInfo(
        "features",
        "dafm features / make features",
        (FEATURES_PARQUET,),
        optional_artifacts=(EMBEDDINGS_PARQUET,),
    ),
    StageInfo(
        "spaces",
        "dafm spaces / make spaces",
        (SPACES_DIR / "params_encoded" / "fitted_space.joblib",),
        optional_artifacts=tuple(
            SPACES_DIR / c / "fitted_space.joblib"
            for c in (
                "params_raw",
                "descriptors",
                "embeddings",
                "hybrid",
            )
        ),
    ),
    StageInfo(
        "evaluate",
        "dafm evaluate / make evaluate",
        (RESULTS_DIR / "evaluate_all.json",),
        optional_artifacts=(
            RESULTS_DIR / "e1_carrier_vs_modulator.json",
            RESULTS_DIR / "e4_rank_correlation.json",
        ),
    ),
    StageInfo(
        "morph",
        "dafm morph / make morph",
        (MORPH_DIR / "morph_model.joblib",),
        optional_artifacts=(MORPH_DIR / "pca_loadings.parquet",),
    ),
    StageInfo(
        "hf_export",
        "dafm export-hf / make hf-export",
        (HF_EXPORT_DIR / "configs.parquet", HF_EXPORT_DIR / "README.md"),
    ),
)


def pipeline_status() -> dict[str, Any]:
    """Return a machine-readable status snapshot."""
    rows = []
    next_command = None
    for stage in STAGES:
        done = stage.complete()
        rows.append(
            {
                "stage": stage.name,
                "complete": done,
                "command": stage.command,
                "artifacts_present": stage.present(),
                "artifacts_required": [str(p) for p in stage.artifacts],
            }
        )
        if not done and next_command is None:
            next_command = stage.command
    return {
        "stages": rows,
        "next_command": next_command,
        "all_complete": next_command is None,
    }


def format_status(status: dict[str, Any] | None = None) -> str:
    """Human-readable status block for `make status`."""
    status = status or pipeline_status()
    lines = ["DAFM pipeline status", "===================="]
    for row in status["stages"]:
        mark = "x" if row["complete"] else " "
        lines.append(f"[{mark}] {row['stage']:12}  {row['command']}")
    lines.append("")
    if status["all_complete"]:
        lines.append("Next: nothing pending — pipeline artifacts look complete.")
    else:
        lines.append(f"Next: {status['next_command']}")
    return "\n".join(lines)


def main() -> int:
    print(format_status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
