"""Environment and dependency checks for the research pipeline.

Reports what is available (CPU-only, GPU, optional ANN, AudioCommons, embedding
packages) without failing the import of the rest of the package.
"""

from __future__ import annotations

import importlib
import platform
import sys
from dataclasses import dataclass, field
from typing import Any

from .paths import SOURCE_CSV, EMULATOR_CORE, RESEARCH_DIR, load_config, machine_profile


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""
    level: str = "info"  # info | warn | error


@dataclass
class DoctorReport:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(c.level == "error" and not c.ok for c in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "checks": [
                {"name": c.name, "ok": c.ok, "detail": c.detail, "level": c.level}
                for c in self.checks
            ],
        }


def _try_import(name: str) -> tuple[bool, str]:
    try:
        mod = importlib.import_module(name)
        version = getattr(mod, "__version__", "unknown")
        return True, f"{name} {version}"
    except ImportError as exc:
        return False, f"{name} absent ({exc})"


def run_doctor() -> DoctorReport:
    """Run all environment checks and return a structured report."""
    report = DoctorReport()

    report.checks.append(
        CheckResult(
            "python",
            sys.version_info[:2] == (3, 12),
            f"{sys.version.split()[0]} on {platform.platform()}",
            level="error" if sys.version_info[:2] != (3, 12) else "info",
        )
    )

    report.checks.append(
        CheckResult(
            "source_csv",
            SOURCE_CSV.exists(),
            str(SOURCE_CSV),
            level="error" if not SOURCE_CSV.exists() else "info",
        )
    )
    report.checks.append(
        CheckResult(
            "emulator_core",
            EMULATOR_CORE.exists(),
            str(EMULATOR_CORE),
            level="warn" if not EMULATOR_CORE.exists() else "info",
        )
    )

    try:
        profile = machine_profile()
        report.checks.append(
            CheckResult(
                "machine_profile",
                True,
                f"id={profile['id']} label={profile.get('label')} gpu={profile.get('gpu')}",
            )
        )
    except Exception as exc:
        report.checks.append(
            CheckResult("machine_profile", False, str(exc), level="error")
        )

    for name in (
        "numpy",
        "pandas",
        "sklearn",
        "librosa",
        "soundfile",
        "soxr",
        "pyloudnorm",
        "umap",
        "statsmodels",
        "joblib",
    ):
        ok, detail = _try_import(name)
        report.checks.append(
            CheckResult(f"dep:{name}", ok, detail, level="error" if not ok else "info")
        )

    for name, level in (
        ("torch", "warn"),
        ("torchaudio", "warn"),
        ("panns_inference", "warn"),
        ("laion_clap", "warn"),
        ("timbral_models", "warn"),
        ("hnswlib", "warn"),
    ):
        ok, detail = _try_import(name)
        report.checks.append(CheckResult(f"optional:{name}", ok, detail, level=level))

    # CUDA usability (never fatal here).
    try:
        import torch

        cuda = torch.cuda.is_available()
        detail = f"cuda_available={cuda}"
        if cuda:
            detail += f" device0={torch.cuda.get_device_name(0)}"
        report.checks.append(CheckResult("cuda", cuda, detail, level="warn"))
    except ImportError:
        report.checks.append(
            CheckResult("cuda", False, "torch absent", level="warn")
        )

    # Configs parse.
    for cfg_name in ("features", "eval", "machines", "render"):
        try:
            load_config(cfg_name)
            report.checks.append(CheckResult(f"config:{cfg_name}", True, "ok"))
        except Exception as exc:
            report.checks.append(
                CheckResult(f"config:{cfg_name}", False, str(exc), level="error")
            )

    report.checks.append(
        CheckResult("research_dir", RESEARCH_DIR.exists(), str(RESEARCH_DIR))
    )
    return report


def main() -> int:
    """CLI-friendly entry: print checks, exit 0/1.

    Missing optional packages (torch, timbral_models, hnswlib) are warnings, not
    hard failures: Family A and exact NN still run without them.
    """
    report = run_doctor()
    for c in report.checks:
        if c.ok:
            flag = "OK  "
        elif c.level == "warn":
            flag = "WARN"
        else:
            flag = "FAIL"
        print(f"[{flag}] {c.name}: {c.detail}")
    print("VERDICT:", "GREEN" if report.ok else "RED")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
