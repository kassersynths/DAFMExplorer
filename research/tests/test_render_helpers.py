"""Renderer helper invariants that do not need a full corpus render."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from dafm_audio.paths import EMULATOR_CORE, RENDER_DIR


pytestmark = pytest.mark.skipif(not EMULATOR_CORE.exists(), reason="emulator absent")


def test_node_render_smoke_deterministic(tmp_path: Path):
    """Same patch rendered twice yields the same PCM SHA256."""
    if not (RENDER_DIR / "node_modules").exists():
        pytest.skip("npm install not run in research/render")

    patch = {
        "config_id": "smoke0001",
        "CON": 7,
        "FL": 0,
        "M1_AR": 31,
        "M1_D1R": 0,
        "M1_D2R": 0,
        "M1_RR": 15,
        "M1_D1L": 0,
        "M1_TL": 0,
        "M1_KS": 0,
        "M1_MUL": 1,
        "M1_DT1": 0,
    }
    for op in ("C1", "M2", "C2"):
        for p, v in [
            ("AR", 31),
            ("D1R", 0),
            ("D2R", 0),
            ("RR", 15),
            ("D1L", 0),
            ("TL", 127),
            ("KS", 0),
            ("MUL", 1),
            ("DT1", 0),
        ]:
            patch[f"{op}_{p}"] = v

    queue = tmp_path / "q.json"
    queue.write_text(json.dumps([patch]), encoding="utf-8")
    hashes = []
    for i in range(2):
        stats = tmp_path / f"s{i}.jsonl"
        cmd = [
            "node",
            "--import",
            "tsx",
            str(RENDER_DIR / "render_corpus_audio.ts"),
            "--manifest",
            str(queue),
            "--shard",
            "0/1",
            "--mode",
            "probe",
            "--out-dir",
            str(tmp_path / "audio"),
            "--stats-out",
            str(stats),
            "--force",
        ]
        proc = subprocess.run(cmd, cwd=RENDER_DIR, capture_output=True, text=True, check=False)
        assert proc.returncode == 0, proc.stderr
        meta = json.loads(stats.read_text(encoding="utf-8").splitlines()[0])
        hashes.append(meta["pcm_sha256"])
    assert hashes[0] == hashes[1]
    assert len(hashes[0]) == 64
