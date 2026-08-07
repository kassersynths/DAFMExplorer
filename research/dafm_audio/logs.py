"""Logging with stable sentinel lines.

Long stages write to a file and emit sentinel lines in a fixed format, e.g.::

    STAGE_DONE stage=render shard=3/16 items=4770 elapsed_s=612

That gives progress at a glance and can be monitored by pattern, so nobody has to
sit watching a console. The format is deliberately parseable by both a human and
an agent.
"""

from __future__ import annotations

import logging
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .paths import LOG_DIR

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"
_configured = False


def setup(stage: str, *, verbose: bool = False) -> logging.Logger:
    """Configure root logging for a stage, writing to console and to a log file."""
    global _configured
    logger = logging.getLogger(f"dafm.{stage}")
    if _configured:
        return logger

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    root.handlers.clear()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(_FORMAT))
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    root.addHandler(console)

    file_handler = logging.FileHandler(LOG_DIR / f"{stage}.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(_FORMAT))
    file_handler.setLevel(logging.DEBUG)
    root.addHandler(file_handler)

    _configured = True
    return logger


def _fields(fields: dict[str, Any]) -> str:
    parts = []
    for key, value in fields.items():
        text = "" if value is None else str(value)
        # Sentinel lines are whitespace-delimited key=value, so a value with a
        # space would break parsing.
        if " " in text:
            text = text.replace(" ", "_")
        parts.append(f"{key}={text}")
    return " ".join(parts)


def sentinel(kind: str, **fields: Any) -> None:
    """Emit a sentinel line. ``kind`` is typically STAGE_START/STAGE_DONE/STAGE_FAIL."""
    logging.getLogger("dafm.sentinel").info("%s %s", kind, _fields(fields))


@contextmanager
def stage(name: str, **fields: Any):
    """Bracket a stage with START/DONE sentinels and an elapsed time.

    On failure it emits STAGE_FAIL and re-raises, so a monitor watching for
    ``STAGE_(DONE|FAIL)`` never misses a terminal event.
    """
    logger = setup(name)
    started = time.perf_counter()
    sentinel("STAGE_START", stage=name, **fields)
    extra: dict[str, Any] = {}
    try:
        yield extra
    except BaseException as exc:
        sentinel(
            "STAGE_FAIL",
            stage=name,
            error=type(exc).__name__,
            elapsed_s=f"{time.perf_counter() - started:.1f}",
            **fields,
        )
        raise
    elapsed = time.perf_counter() - started
    sentinel("STAGE_DONE", stage=name, **fields, **extra, elapsed_s=f"{elapsed:.1f}")
    logger.info("stage %s finished in %.1f s", name, elapsed)


def log_path(stage_name: str) -> Path:
    return LOG_DIR / f"{stage_name}.log"
