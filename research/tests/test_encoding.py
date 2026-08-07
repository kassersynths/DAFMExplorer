"""Encoding round-trip and MUL/DT1 edge cases."""

from __future__ import annotations

import numpy as np
import pandas as pd

from dafm_audio.encoding import (
    EFFECTIVE_COLUMNS,
    canonicalize_registers,
    from_model_space,
    log2_to_mul_register,
    mul_register_to_log2,
    round_trip_matches,
    signed_to_dt1_register,
    dt1_register_to_signed,
    to_model_space,
    validate_registers,
)


def _toy_row(**overrides) -> pd.DataFrame:
    row = {c: 0 for c in EFFECTIVE_COLUMNS}
    row["CON"] = 4
    row["FL"] = 3
    for op in ("M1", "C1", "M2", "C2"):
        row[f"{op}_AR"] = 31
        row[f"{op}_RR"] = 15
        row[f"{op}_TL"] = 20
        row[f"{op}_MUL"] = 1
        row[f"{op}_DT1"] = 0
    row.update(overrides)
    return pd.DataFrame([row])


def test_mul_register_zero_is_half():
    assert mul_register_to_log2(np.array([0]))[0] == np.log2(0.5)


def test_mul_snap_prefers_log_domain():
    # Midway in log space between x1 and x2 should snap to the nearer ratio.
    mid = 0.5 * (np.log2(1.0) + np.log2(2.0))
    reg = log2_to_mul_register(np.array([mid]))[0]
    assert reg in (1, 2)


def test_dt1_four_canonicalises_to_zero():
    df = _toy_row(M1_DT1=4)
    out = canonicalize_registers(df)
    assert int(out.loc[0, "M1_DT1"]) == 0


def test_dt1_signed_round_trip():
    for reg in range(8):
        signed = dt1_register_to_signed(np.array([reg]))[0]
        back = signed_to_dt1_register(np.array([signed]))[0]
        # 4 maps to signed 0 which re-encodes as 0
        if reg == 4:
            assert back == 0
        else:
            assert back == reg


def test_full_round_trip_identity_after_canonicalize():
    df = canonicalize_registers(_toy_row(M1_MUL=0, C1_DT1=4, CON=7))
    assert bool(round_trip_matches(df).iloc[0])


def test_con_one_hot_reconstructs():
    for alg in range(8):
        df = canonicalize_registers(_toy_row(CON=alg))
        model = to_model_space(df)
        back = from_model_space(model)
        assert int(back.loc[0, "CON"]) == alg


def test_validate_registers():
    df = _toy_row()
    assert bool(validate_registers(df).iloc[0])
