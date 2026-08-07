"""Provenance: hashes, identifiers, versions and seeds.

Every artifact gets a sibling ``<name>.provenance.json``. Recording the machine
that produced it is not bureaucracy: when a result fails to reproduce, the first
thing you want to know is where it was generated.
"""

from __future__ import annotations

import hashlib
import json
import platform
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from . import __version__
from .paths import load_config, machine_profile

CHUNK = 1 << 20


def sha256_file(path: str | Path) -> str:
    """SHA256 of a file's bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def sha256_pcm(samples: np.ndarray) -> str:
    """SHA256 of decoded PCM samples.

    Deliberately NOT the file bytes. Two FLAC encoder versions produce different
    bytes for identical audio, so hashing the container would raise false
    divergence alarms in exactly the two-machine scenario where verification
    matters most. Hashing the sample buffer is what actually proves the render is
    reproducible.

    The buffer is canonicalised to little-endian float32 first, so the hash does
    not depend on host byte order or on an incidental dtype.
    """
    arr = np.ascontiguousarray(samples, dtype="<f4")
    return hashlib.sha256(arr.tobytes()).hexdigest()


def sha256_obj(obj: Any) -> str:
    """Stable SHA256 of a JSON-serialisable object.

    Sorted keys and fixed separators, so the digest depends on content and not on
    dict ordering or whitespace.
    """
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def config_hash(*config_names: str) -> str:
    """Hash of one or more config files by content.

    Any change to the render protocol invalidates downstream artifacts by design,
    which is the point.
    """
    payload = {name: load_config(name) for name in sorted(config_names)}
    return sha256_obj(payload)


def corpus_id(csv_sha256: str, dedup_policy: dict[str, Any]) -> str:
    """Versioned corpus identifier.

    Derived from the frozen source CSV plus the deduplication policy, because
    changing the policy changes the set of configurations even though the source
    file is untouched.
    """
    return sha256_obj({"csv": csv_sha256, "dedup": dedup_policy})[:16]


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _dependency_versions() -> dict[str, str]:
    names = [
        "numpy",
        "pandas",
        "pyarrow",
        "scipy",
        "sklearn",
        "librosa",
        "soundfile",
        "soxr",
        "umap",
        "hnswlib",
        "statsmodels",
    ]
    versions: dict[str, str] = {}
    for name in names:
        try:
            module = __import__(name)
            versions[name] = getattr(module, "__version__", "unknown")
        except ImportError:
            versions[name] = "absent"
    return versions


def environment() -> dict[str, Any]:
    """Snapshot of the execution environment."""
    profile = machine_profile()
    return {
        "package_version": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "hostname": socket.gethostname(),
        "machine_profile": profile["id"],
        "machine_label": profile.get("label"),
        "git_commit": _git_commit(),
        "dependencies": _dependency_versions(),
    }


def write(
    artifact: str | Path,
    *,
    stage: str,
    inputs: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
    seeds: dict[str, int] | None = None,
) -> Path:
    """Write ``<artifact>.provenance.json`` next to an artifact."""
    artifact = Path(artifact)
    record = {
        "stage": stage,
        "artifact": artifact.name,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "environment": environment(),
        "inputs": inputs or {},
        "params": params or {},
        "metrics": metrics or {},
        "seeds": seeds or {},
    }
    out = artifact.with_suffix(artifact.suffix + ".provenance.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, default=str)
    return out


def read(artifact: str | Path) -> dict[str, Any] | None:
    """Read the provenance record for an artifact, if present."""
    artifact = Path(artifact)
    path = artifact.with_suffix(artifact.suffix + ".provenance.json")
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)
