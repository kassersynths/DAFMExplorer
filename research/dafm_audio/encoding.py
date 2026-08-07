"""Bijective mapping between register space and model space.

The mistake this module exists to prevent is treating the raw register values as
continuous variables in a Euclidean space. They are not: categorical, logarithmic,
ratio and sign-magnitude encodings live side by side in the same vector.

Two functions do the work, :func:`to_model_space` and :func:`from_model_space`, so
that PCA, distances and interpolation all operate in a space where Euclidean
geometry is far less wrong.

Why this also improves the paper, not just the morph
---------------------------------------------------
The Phase 3 parameter baseline uses this same layer. Without it a reviewer has an
easy and legitimate objection: "your parameter space performs badly because you
built it badly, treating categoricals and ratios as continuous". With the encoding
done properly the finding becomes much stronger, because it turns into "even with
a carefully encoded parameter space, it still does not predict perception".

Both baseline variants (raw and encoded) are therefore reported as a cheap
ablation that defuses the objection before it is raised.

The DT1 catch, and why canonicalisation comes first
--------------------------------------------------
DT1 registers 0 and 4 are functionally the same value ("plus zero" and "minus
zero"). A strict round trip therefore CANNOT be the identity on raw registers:
register 4 decodes to signed 0 and re-encodes to register 0. That is not a bug in
the encoding, it is a property of the hardware encoding, and it is exactly why
:func:`canonicalize_registers` must run before deduplication. Two presets
differing only in that bit are identical to the ear but different byte for byte,
so without canonicalisation the unique-configuration count is inflated.

The round-trip invariant that does hold, and which the tests assert over the whole
corpus, is::

    from_model_space(to_model_space(canonicalize(x))) == canonicalize(x)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .chip import (
    DT1_REGISTER_TO_SIGNED,
    GLOBAL_PARAMS,
    MUL_REGISTER_TO_MULTIPLIER,
    N_ALGORITHMS,
    OPERATOR_NAMES,
    PARAM_RANGES,
    PER_OPERATOR_PARAMS,
    TL_DB_PER_STEP,
)

# ---------------------------------------------------------------------------
# Column layout
# ---------------------------------------------------------------------------
EFFECTIVE_COLUMNS: tuple[str, ...] = tuple(GLOBAL_PARAMS) + tuple(
    f"{op}_{param}" for op in OPERATOR_NAMES for param in PER_OPERATOR_PARAMS
)
"""The 38 parameters that reach the chip under the declared render protocol.

Two global (CON, FL) plus nine per operator across four operators. Everything else
in the 56-column corpus is either written but inert (the LFO-dependent group) or
never written at all; see :mod:`dafm_audio.inertness`.
"""

# Precomputed log2 of the legal multipliers, for snapping in the log domain.
_MUL_LOG2 = np.log2(np.asarray(MUL_REGISTER_TO_MULTIPLIER, dtype=np.float64))

# D1L register to real attenuation in dB. The register is 4 bits at roughly 3 dB
# per step, except that 15 means "fully attenuated" rather than 45 dB, which is a
# genuine discontinuity worth encoding rather than smoothing over.
_D1L_DB = np.array(
    [0.0, 3.0, 6.0, 9.0, 12.0, 15.0, 18.0, 21.0, 24.0, 27.0, 30.0, 33.0, 36.0, 39.0, 42.0, 93.0],
    dtype=np.float64,
)


@dataclass(frozen=True)
class EncodingPolicy:
    """Switches for the parts of the encoding that are still open questions.

    MUL and DT1 are settled: their register encodings are demonstrably wrong for
    Euclidean use, so they are always transformed. The envelope rates and D1L are
    lower priority; the hook is here so the decision can be made with data rather
    than by assertion, which is what the plan asks for.
    """

    # Settled.
    one_hot_algorithm: bool = True
    mul_as_log2_multiplier: bool = True
    dt1_as_signed: bool = True
    tl_in_db: bool = True
    # Open, default off. Turning these on changes the geometry of the parameter
    # baseline, so it is an ablation rather than a silent default.
    rates_as_log_time: bool = False
    d1l_as_db: bool = False

    def key(self) -> dict[str, bool]:
        return {
            "one_hot_algorithm": self.one_hot_algorithm,
            "mul_as_log2_multiplier": self.mul_as_log2_multiplier,
            "dt1_as_signed": self.dt1_as_signed,
            "tl_in_db": self.tl_in_db,
            "rates_as_log_time": self.rates_as_log_time,
            "d1l_as_db": self.d1l_as_db,
        }


DEFAULT_POLICY = EncodingPolicy()


@dataclass
class ModelSpace:
    """A matrix in model space plus the metadata needed to invert it."""

    matrix: np.ndarray
    columns: list[str]
    policy: EncodingPolicy
    index: pd.Index | None = field(default=None, repr=False)

    @property
    def n_dims(self) -> int:
        return self.matrix.shape[1]

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.matrix, columns=self.columns, index=self.index)


# ---------------------------------------------------------------------------
# Canonicalisation
# ---------------------------------------------------------------------------
def canonicalize_registers(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse register encodings that are functionally identical.

    Currently one rule, and it is consequential: ``DT1 = 4`` becomes ``DT1 = 0``,
    because both mean zero detune. Applied BEFORE deduplication, this reduces the
    unique-configuration count, and that number ends up in the abstract.
    """
    out = df.copy()
    for op in OPERATOR_NAMES:
        col = f"{op}_DT1"
        if col in out.columns:
            out[col] = out[col].where(out[col] != 4, 0)
    return out


def count_canonicalization_changes(df: pd.DataFrame) -> dict[str, int]:
    """How many rows each canonicalisation rule actually touches.

    Reported rather than assumed, because if the corpus never uses ``DT1 = 4`` the
    rule is a no-op and saying so is more honest than implying a saving.
    """
    counts = {}
    for op in OPERATOR_NAMES:
        col = f"{op}_DT1"
        if col in df.columns:
            counts[col] = int((df[col] == 4).sum())
    counts["rows_affected"] = int(
        np.any([df[f"{op}_DT1"] == 4 for op in OPERATOR_NAMES if f"{op}_DT1" in df.columns], axis=0).sum()
    )
    return counts


# ---------------------------------------------------------------------------
# Per-parameter transforms
# ---------------------------------------------------------------------------
def mul_register_to_log2(reg: np.ndarray) -> np.ndarray:
    """MUL register to log2 of the real frequency multiplier.

    Two problems are fixed at once. First, register 0 means x0.5 while 1..15 mean
    x1..x15, so REGISTER ORDER IS NOT MULTIPLIER ORDER and a linear treatment puts
    x0.5 adjacent to x1 as though the step were the same size as x14 to x15.
    Second, the meaning is musical and therefore logarithmic: x1 to x2 is an
    octave, whereas x7 to x8 is a little over a whole tone.
    """
    reg = np.asarray(reg, dtype=np.int64)
    return _MUL_LOG2[np.clip(reg, 0, 15)]


def log2_to_mul_register(value: np.ndarray) -> np.ndarray:
    """Inverse of :func:`mul_register_to_log2`, snapping in the LOG domain.

    Snapping in the log domain rather than the linear one is the whole point: it
    picks the nearest frequency RATIO instead of the nearest integer, which is what
    a musician would hear as closest.
    """
    value = np.atleast_1d(np.asarray(value, dtype=np.float64))
    distances = np.abs(value[:, None] - _MUL_LOG2[None, :])
    return np.argmin(distances, axis=1).astype(np.int64)


def dt1_register_to_signed(reg: np.ndarray) -> np.ndarray:
    """DT1 register to a signed integer in -3..+3.

    The register is sign-magnitude: 0..3 are increasing positive detune and 4..7
    increasing negative detune. Decoded to a signed value it becomes an ordinal,
    symmetric scale on which distance and interpolation mean something.
    """
    reg = np.asarray(reg, dtype=np.int64)
    table = np.asarray(DT1_REGISTER_TO_SIGNED, dtype=np.int64)
    return table[np.clip(reg, 0, 7)]


def signed_to_dt1_register(value: np.ndarray) -> np.ndarray:
    """Inverse of :func:`dt1_register_to_signed`.

    Maps ``s >= 0`` to ``s`` and ``s < 0`` to ``4 + |s|``. Note that signed 0 maps
    to register 0, never to register 4, which is what makes the canonicalised round
    trip exact.
    """
    value = np.rint(np.asarray(value, dtype=np.float64)).astype(np.int64)
    value = np.clip(value, -3, 3)
    return np.where(value >= 0, value, 4 + np.abs(value)).astype(np.int64)


def tl_register_to_db(reg: np.ndarray) -> np.ndarray:
    """TL register to attenuation in dB.

    TL is already logarithmic at about 0.75 dB per step, so for CARRIERS the
    register is a reasonable domain: loudness is perceived roughly in dB. For
    MODULATORS no encoding fixes it, because there TL controls the modulation index
    and its effect is oscillatory through Bessel functions. That non-linearity is
    irreducible and is exactly what the perceptual reparameterisation in
    :mod:`dafm_audio.morph` addresses.
    """
    return np.asarray(reg, dtype=np.float64) * TL_DB_PER_STEP


def db_to_tl_register(value: np.ndarray) -> np.ndarray:
    return np.clip(np.rint(np.asarray(value, dtype=np.float64) / TL_DB_PER_STEP), 0, 127).astype(np.int64)


def rate_register_to_log_time(reg: np.ndarray, max_reg: int) -> np.ndarray:
    """Envelope rate register to a monotone log-time-like scale.

    Higher register means faster, so this flips the sense and compresses it, giving
    an axis on which "twice as slow" is a constant step. Kept behind a policy flag
    because it is not yet established that it improves the baseline.
    """
    reg = np.asarray(reg, dtype=np.float64)
    return np.log2(1.0 + (max_reg - reg))


def log_time_to_rate_register(value: np.ndarray, max_reg: int) -> np.ndarray:
    value = np.asarray(value, dtype=np.float64)
    reg = max_reg - (np.power(2.0, value) - 1.0)
    return np.clip(np.rint(reg), 0, max_reg).astype(np.int64)


def d1l_register_to_db(reg: np.ndarray) -> np.ndarray:
    """D1L register to real sustain attenuation in dB, including the 15 = silence step."""
    reg = np.asarray(reg, dtype=np.int64)
    return _D1L_DB[np.clip(reg, 0, 15)]


def db_to_d1l_register(value: np.ndarray) -> np.ndarray:
    value = np.atleast_1d(np.asarray(value, dtype=np.float64))
    distances = np.abs(value[:, None] - _D1L_DB[None, :])
    return np.argmin(distances, axis=1).astype(np.int64)


# ---------------------------------------------------------------------------
# Forward transform
# ---------------------------------------------------------------------------
def model_space_columns(policy: EncodingPolicy = DEFAULT_POLICY) -> list[str]:
    """Names of the model-space dimensions, in order."""
    names: list[str] = []
    if policy.one_hot_algorithm:
        names += [f"CON_onehot_{k}" for k in range(N_ALGORITHMS)]
    else:
        names.append("CON")
    names.append("FL")
    for op in OPERATOR_NAMES:
        for param in PER_OPERATOR_PARAMS:
            if param == "TL" and policy.tl_in_db:
                names.append(f"{op}_TL_db")
            elif param == "MUL" and policy.mul_as_log2_multiplier:
                names.append(f"{op}_MUL_log2")
            elif param == "DT1" and policy.dt1_as_signed:
                names.append(f"{op}_DT1_signed")
            elif param == "D1L" and policy.d1l_as_db:
                names.append(f"{op}_D1L_db")
            elif param in ("AR", "D1R", "D2R", "RR") and policy.rates_as_log_time:
                names.append(f"{op}_{param}_logtime")
            else:
                names.append(f"{op}_{param}")
    return names


def to_model_space(
    df: pd.DataFrame,
    policy: EncodingPolicy = DEFAULT_POLICY,
) -> ModelSpace:
    """Encode register-space parameters into model space.

    Expects the 38 effective columns. Anything else in the frame is ignored, which
    is deliberate: the inert columns must not leak into the parameter baseline or a
    reviewer will rightly point out that the space contains pure noise.
    """
    missing = [c for c in EFFECTIVE_COLUMNS if c not in df.columns]
    if missing:
        raise KeyError(f"missing effective parameter columns: {missing}")

    blocks: list[np.ndarray] = []

    con = df["CON"].to_numpy(dtype=np.int64)
    if policy.one_hot_algorithm:
        # Categorical: CON defines the routing topology, so interpolating between
        # algorithm 2 and algorithm 6 and landing on 4 is not a blend, it is a
        # different thing entirely. One-hot before PCA, argmax on reconstruction.
        onehot = np.zeros((len(df), N_ALGORITHMS), dtype=np.float64)
        onehot[np.arange(len(df)), np.clip(con, 0, N_ALGORITHMS - 1)] = 1.0
        blocks.append(onehot)
    else:
        blocks.append(con.astype(np.float64)[:, None])

    # FL is ordinal and left as-is, but its effect is strongly non-linear at high
    # values, which is documented rather than encoded away.
    blocks.append(df["FL"].to_numpy(dtype=np.float64)[:, None])

    for op in OPERATOR_NAMES:
        for param in PER_OPERATOR_PARAMS:
            reg = df[f"{op}_{param}"].to_numpy()
            if param == "TL" and policy.tl_in_db:
                col = tl_register_to_db(reg)
            elif param == "MUL" and policy.mul_as_log2_multiplier:
                col = mul_register_to_log2(reg)
            elif param == "DT1" and policy.dt1_as_signed:
                col = dt1_register_to_signed(reg).astype(np.float64)
            elif param == "D1L" and policy.d1l_as_db:
                col = d1l_register_to_db(reg)
            elif param in ("AR", "D1R", "D2R", "RR") and policy.rates_as_log_time:
                col = rate_register_to_log_time(reg, PARAM_RANGES[param][1])
            else:
                col = np.asarray(reg, dtype=np.float64)
            blocks.append(col.astype(np.float64)[:, None])

    matrix = np.hstack(blocks)
    return ModelSpace(
        matrix=matrix,
        columns=model_space_columns(policy),
        policy=policy,
        index=df.index,
    )


# ---------------------------------------------------------------------------
# Inverse transform
# ---------------------------------------------------------------------------
def from_model_space(
    space: ModelSpace | np.ndarray,
    policy: EncodingPolicy | None = None,
    index: pd.Index | None = None,
) -> pd.DataFrame:
    """Decode model space back to legal register values.

    Every output column is rounded, snapped according to its type and clipped to
    the legal register range, so the result is always a playable configuration.
    That guarantee is what the morph validator relies on.
    """
    if isinstance(space, ModelSpace):
        matrix = space.matrix
        policy = policy or space.policy
        index = index if index is not None else space.index
    else:
        matrix = np.asarray(space, dtype=np.float64)
        policy = policy or DEFAULT_POLICY
    matrix = np.atleast_2d(matrix)

    out: dict[str, np.ndarray] = {}
    cursor = 0

    if policy.one_hot_algorithm:
        block = matrix[:, cursor : cursor + N_ALGORITHMS]
        # argmax, never a rounded interpolation: the result must be one of the
        # eight real algorithms.
        out["CON"] = np.argmax(block, axis=1).astype(np.int64)
        cursor += N_ALGORITHMS
    else:
        out["CON"] = np.clip(np.rint(matrix[:, cursor]), 0, 7).astype(np.int64)
        cursor += 1

    out["FL"] = np.clip(np.rint(matrix[:, cursor]), 0, 7).astype(np.int64)
    cursor += 1

    for op in OPERATOR_NAMES:
        for param in PER_OPERATOR_PARAMS:
            column = matrix[:, cursor]
            cursor += 1
            name = f"{op}_{param}"
            if param == "TL" and policy.tl_in_db:
                out[name] = db_to_tl_register(column)
            elif param == "MUL" and policy.mul_as_log2_multiplier:
                out[name] = log2_to_mul_register(column)
            elif param == "DT1" and policy.dt1_as_signed:
                out[name] = signed_to_dt1_register(column)
            elif param == "D1L" and policy.d1l_as_db:
                out[name] = db_to_d1l_register(column)
            elif param in ("AR", "D1R", "D2R", "RR") and policy.rates_as_log_time:
                out[name] = log_time_to_rate_register(column, PARAM_RANGES[param][1])
            else:
                low, high = PARAM_RANGES[param]
                out[name] = np.clip(np.rint(column), low, high).astype(np.int64)

    if cursor != matrix.shape[1]:
        raise ValueError(
            f"model space width mismatch: consumed {cursor} of {matrix.shape[1]} columns"
        )

    frame = pd.DataFrame(out, index=index)
    return frame[list(EFFECTIVE_COLUMNS)]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_registers(df: pd.DataFrame) -> pd.Series:
    """Per-row legality of a register configuration.

    Used as a hard gate on every reconstruction produced by the morph, because a
    vector that leaves the legal range is not a preset.
    """
    ok = pd.Series(True, index=df.index)
    for param in GLOBAL_PARAMS:
        low, high = PARAM_RANGES[param]
        ok &= df[param].between(low, high)
    for op in OPERATOR_NAMES:
        for param in PER_OPERATOR_PARAMS:
            low, high = PARAM_RANGES[param]
            ok &= df[f"{op}_{param}"].between(low, high)
    return ok


def round_trip_matches(
    df: pd.DataFrame,
    policy: EncodingPolicy = DEFAULT_POLICY,
) -> pd.Series:
    """Per-row result of ``from_model_space(to_model_space(x)) == x``.

    Run on CANONICALISED registers. On raw registers it will legitimately fail for
    any row using ``DT1 = 4``, which is information rather than a defect.
    """
    subset = df[list(EFFECTIVE_COLUMNS)]
    restored = from_model_space(to_model_space(subset, policy), policy, index=subset.index)
    return (restored == subset).all(axis=1)
