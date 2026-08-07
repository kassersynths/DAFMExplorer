"""Timbre similarity in FM synthesis: rendering, descriptors and evaluation.

A self-contained research package for the YM2612 preset corpus. It imports
nothing from the repository root except the emulator core, which is treated as a
measuring instrument rather than as prior analysis.

Scope boundary (deliberate and load-bearing): the only inheritance from earlier
work in this repository is the file ``data/processed/all_instruments_final.csv``.
Every representation, hyperparameter and cluster naming decision here is defined
and justified from scratch.
"""

__version__ = "0.1.0"

PACKAGE_NAME = "dafm_audio"
