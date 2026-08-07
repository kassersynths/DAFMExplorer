"""Guard against Spanish sneaking into research deliverables."""

from __future__ import annotations

import re
from pathlib import Path

RESEARCH = Path(__file__).resolve().parents[1]

# Patterns built from codepoints so this file itself stays ASCII-clean.
ACCENTS = re.compile(
    "["
    + "".join(chr(c) for c in (
        0xE1, 0xE9, 0xED, 0xF3, 0xFA, 0xF1, 0xFC,
        0xC1, 0xC9, 0xCD, 0xD3, 0xDA, 0xD1, 0xDC,
        0xBF, 0xA1,
    ))
    + "]"
)

# Functional Spanish words as whole-word matches (ASCII stems + accented forms
# via explicit escapes).
SPANISH_WORDS = re.compile(
    r"\b("
    r"tambien|tambi"
    + chr(0xE9)
    + r"n|despues|despu"
    + chr(0xE9)
    + r"s|configuracion|configuraci"
    + chr(0xF3)
    + r"n|evaluacion|evaluaci"
    + chr(0xF3)
    + r"n|articulo|art"
    + chr(0xED)
    + r"culo|siguiente|parametro|par"
    + chr(0xE1)
    + r"metro|investigacion|investigaci"
    + chr(0xF3)
    + r"n|cuando|porque|ademas|adem"
    + chr(0xE1)
    + r"s"
    r")\b",
    re.IGNORECASE,
)

SCAN_GLOBS = ("**/*.py", "**/*.ts", "**/*.yaml", "**/*.md", "**/*.toml")
EXCLUDE_PARTS = {
    "node_modules",
    ".venv",
    "scratch",
    "artifacts",
    "__pycache__",
    ".egg-info",
    "references.bib",
}
# This file necessarily mentions Spanish stems in its detector; skip it.
EXCLUDE_FILES = {"test_language_guard.py"}


def _iter_files():
    for pattern in SCAN_GLOBS:
        for path in RESEARCH.glob(pattern):
            if any(part in EXCLUDE_PARTS for part in path.parts):
                continue
            if path.name in EXCLUDE_FILES:
                continue
            yield path


def test_no_spanish_in_research_sources():
    offenders: list[str] = []
    for path in _iter_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if ACCENTS.search(line) or SPANISH_WORDS.search(line):
                offenders.append(f"{path.relative_to(RESEARCH)}:{i}: {line.strip()[:120]}")
    assert not offenders, "Spanish found in research sources:\n" + "\n".join(offenders[:40])
