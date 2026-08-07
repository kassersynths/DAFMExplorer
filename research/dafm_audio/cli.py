"""Command-line entry point for the research pipeline."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import click

from . import __version__
from .paths import (
    ARTIFACTS_DIR,
    AUDIO_DIR,
    RENDER_DIR,
    RESEARCH_DIR,
    SCRATCH_DIR,
    ensure_dirs,
)


@click.group()
@click.version_option(__version__, prog_name="dafm")
def main() -> None:
    """Timbre similarity in FM synthesis — research pipeline."""
    ensure_dirs()


@main.command("doctor")
def doctor_cmd() -> None:
    from .doctor import main as doctor_main

    sys.exit(doctor_main())


@main.command("status")
def status_cmd() -> None:
    from .status import format_status

    click.echo(format_status())


@main.command("corpus")
@click.option("--seed", default=42, show_default=True, type=int)
def corpus_cmd(seed: int) -> None:
    from .pipeline import build_corpus

    report = build_corpus(seed=seed)
    keys = (
        "corpus_id",
        "n_presets",
        "n_presets_valid",
        "n_presets_quarantined",
        "n_configs",
        "n_cores",
        "n_games",
        "largest_game",
        "largest_game_share",
    )
    click.echo(json.dumps({k: report[k] for k in keys if k in report}, indent=2))


@main.command("check-corpus")
def check_corpus_cmd() -> None:
    from .checks import check_corpus

    sys.exit(0 if check_corpus() else 1)


@main.command("render-manifest")
def render_manifest_cmd() -> None:
    from .render_manifest import build_render_queue

    manifest = build_render_queue()
    click.echo(json.dumps({"n_configs": len(manifest)}, indent=2))


def _ensure_node_deps() -> None:
    if (RENDER_DIR / "package.json").exists() and not (RENDER_DIR / "node_modules").exists():
        subprocess.run(["npm", "install"], cwd=RENDER_DIR, check=True)


def _run_node_renderer(
    *,
    shard: str,
    mode: str,
    limit: int | None,
    gain: float | None = None,
    force: bool = False,
) -> dict:
    _ensure_node_deps()
    from .paths import RENDER_QUEUE_JSON

    if not RENDER_QUEUE_JSON.exists():
        from .render_manifest import build_render_queue

        build_render_queue()

    stats = SCRATCH_DIR / f"render_stats_{shard.replace('/', '_of_')}.jsonl"
    cmd = [
        "node",
        "--import",
        "tsx",
        str(RENDER_DIR / "render_corpus_audio.ts"),
        "--manifest",
        str(RENDER_QUEUE_JSON),
        "--shard",
        shard,
        "--mode",
        mode,
        "--out-dir",
        str(AUDIO_DIR),
        "--stats-out",
        str(stats),
    ]
    if limit is not None:
        cmd.extend(["--limit", str(limit)])
    if gain is not None:
        cmd.extend(["--gain", str(gain)])
    if force:
        cmd.append("--force")
    proc = subprocess.run(cmd, cwd=RENDER_DIR, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        click.echo(proc.stdout)
        click.echo(proc.stderr, err=True)
        raise click.ClickException(f"renderer exited {proc.returncode}")
    # Last JSON line is the summary
    summary = {}
    for line in reversed(proc.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                summary = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
    summary["stats_path"] = str(stats)
    return summary


@main.command("render-gain")
@click.option("--shard", default="0/1", show_default=True)
@click.option("--limit", default=None, type=int)
def render_gain_cmd(shard: str, limit: int | None) -> None:
    from .render_manifest import choose_global_gain

    summary = _run_node_renderer(shard=shard, mode="probe", limit=limit)
    stats_path = Path(summary["stats_path"])
    report = choose_global_gain(stats_path)
    out = ARTIFACTS_DIR / "global_gain.json"
    with out.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    click.echo(json.dumps(report, indent=2))


@main.command("render")
@click.option("--shard", default="0/1", show_default=True)
@click.option("--limit", default=None, type=int)
@click.option("--force", is_flag=True)
def render_cmd(shard: str, limit: int | None, force: bool) -> None:
    gain_path = ARTIFACTS_DIR / "global_gain.json"
    if not gain_path.exists():
        raise click.ClickException("missing global_gain.json — run `dafm render-gain` first")
    with gain_path.open(encoding="utf-8") as fh:
        gain = float(json.load(fh)["global_gain"])
    summary = _run_node_renderer(shard=shard, mode="final", limit=limit, gain=gain, force=force)
    from .render_manifest import refresh_manifest_from_sidecars

    refresh_manifest_from_sidecars()
    click.echo(json.dumps(summary, indent=2))


@main.command("encode-flac")
@click.option("--limit", default=None, type=int)
def encode_flac_cmd(limit: int | None) -> None:
    from .render_manifest import encode_all_wavs, refresh_manifest_from_sidecars

    report = encode_all_wavs(limit=limit)
    refresh_manifest_from_sidecars()
    click.echo(json.dumps(report, indent=2))


@main.command("check-render")
def check_render_cmd() -> None:
    from .checks import check_render

    sys.exit(0 if check_render() else 1)


@main.command("features")
@click.option("--limit", default=None, type=int)
@click.option("--family", type=click.Choice(["a", "b", "both"]), default="both")
def features_cmd(limit: int | None, family: str) -> None:
    from .pipeline import build_features

    report = build_features(limit=limit, family=family)
    click.echo(json.dumps(report, indent=2, default=str))


@main.command("check-features")
def check_features_cmd() -> None:
    from .checks import check_features

    sys.exit(0 if check_features() else 1)


@main.command("spaces")
@click.option("--limit", default=None, type=int)
def spaces_cmd(limit: int | None) -> None:
    from .pipeline import build_spaces

    report = build_spaces(limit=limit)
    click.echo(json.dumps(report, indent=2, default=str))


@main.command("check-spaces")
def check_spaces_cmd() -> None:
    from .checks import check_spaces

    sys.exit(0 if check_spaces() else 1)


@main.command("evaluate")
@click.option("--limit", default=None, type=int)
@click.option("--experiment", default="all")
def evaluate_cmd(limit: int | None, experiment: str) -> None:
    from .pipeline import run_evaluation

    report = run_evaluation(limit=limit, experiment=experiment)
    click.echo(json.dumps(report, indent=2, default=str))


@main.command("check-eval")
def check_eval_cmd() -> None:
    from .checks import check_eval

    sys.exit(0 if check_eval() else 1)


@main.command("morph")
@click.option("--n-components", default=8, show_default=True, type=int)
def morph_cmd(n_components: int) -> None:
    from .pipeline import build_morph

    report = build_morph(n_components=n_components)
    click.echo(json.dumps(report, indent=2, default=str))


@main.command("hf-export")
@click.option("--out", "out_dir", default=None, type=click.Path())
@click.option("--n-audio", default=100, show_default=True, type=int)
def hf_export_cmd(out_dir: str | None, n_audio: int) -> None:
    from .pipeline import export_hf

    dest = Path(out_dir) if out_dir else ARTIFACTS_DIR / "hf_export"
    report = export_hf(out_dir=dest, n_audio_samples=n_audio)
    click.echo(json.dumps(report, indent=2, default=str))


@main.command("figures")
def figures_cmd() -> None:
    from .figures import generate_all

    click.echo(json.dumps(generate_all(), indent=2, default=str))


@main.command("hw-vgm")
def hw_vgm_cmd() -> None:
    sys.path.insert(0, str(RESEARCH_DIR))
    from hardware.build_validation_vgm import main as vgm_main

    sys.exit(vgm_main([]))


@main.command("inertness-audit")
@click.option("--n-presets", default=8, show_default=True, type=int)
@click.option("--limit-columns", default=None, type=int)
def inertness_audit_cmd(n_presets: int, limit_columns: int | None) -> None:
    from .inertness_audit import run_audit

    click.echo(json.dumps(run_audit(n_presets=n_presets, limit_columns=limit_columns), indent=2))


if __name__ == "__main__":
    main()
