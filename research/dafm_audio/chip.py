"""YM2612 FM topology, re-derived from hardware documentation.

Scope note: this module is written from the chip documentation rather than
imported from any existing script in this repository, so the research package is
self-contained and auditable. The carrier/modulator topology of the eight
algorithms is nobody's intellectual contribution: it is a documented property of
the hardware.

References
----------
Yamaha YM2612 (OPN2) application manual and the register map consolidated by the
Sega Retro / SpritesMind hardware documentation effort, cross-checked against the
genesis-plus-gx emulation core. Chowning, J. M. (1973), "The synthesis of complex
audio spectra by means of frequency modulation", JAES 21(7), 526-534, supplies
the theory that makes the carrier/modulator distinction predictive rather than
merely descriptive.

Why this distinction carries the paper
--------------------------------------
In FM the modulation index controls the spectral bandwidth of the result. An
operator's Total Level is its output level, so lowering the TL of a CARRIER
changes essentially amplitude, while lowering the TL of a MODULATOR changes the
modulation index and therefore spectral content.

In parameter space the two cases are indistinguishable: a change of 20 on M1 and a
change of 20 on C2 sit at exactly the same Euclidean distance. In audio space,
theory predicts they cannot. That is experiment E1.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Operator naming
# ---------------------------------------------------------------------------
# The corpus uses the VOPM operator names M1, C1, M2, C2 in that column order.
# On the chip these are slots 1..4, and the register offsets are NOT in the same
# order as the slot numbers: the hardware interleaves them as
# slot1 = +0x00, slot2 = +0x08, slot3 = +0x04, slot4 = +0x0C.
#
# Mapping the corpus column order (M1, C1, M2, C2) onto slots (1, 3, 2, 4) is the
# convention used by every VOPM-derived tool, which is why the register offsets
# below look shuffled. Getting this wrong silently transposes operators and
# produces plausible-sounding but wrong audio, so it is asserted in the tests.
OPERATOR_NAMES: tuple[str, ...] = ("M1", "C1", "M2", "C2")
OPERATOR_REGISTER_OFFSETS: tuple[int, ...] = (0x00, 0x08, 0x04, 0x0C)

# Slot index (1-based, as the documentation numbers them) per corpus column.
OPERATOR_SLOT_NUMBERS: tuple[int, ...] = (1, 3, 2, 4)


# ---------------------------------------------------------------------------
# Algorithm topology
# ---------------------------------------------------------------------------
# CARRIERS_BY_ALGORITHM[algorithm] gives the indices (into OPERATOR_NAMES) of the
# operators whose output reaches the channel output. Everything else is a
# modulator: its output is fed into another operator's phase input.
#
# Derived from the eight algorithm diagrams in the OPN2 documentation, using the
# corpus column order (M1, C1, M2, C2) = (slot1, slot3, slot2, slot4).
#
#   alg 0: M1 -> C1 -> M2 -> C2                      (single chain)
#   alg 1: (M1, C1) -> M2 -> C2                      (two in parallel, then chain)
#   alg 2: M1 -> ... , C1 -> M2 -> C2 summed at M2's input
#   alg 3: M1 -> C1 -> ... , M2 -> C2
#   alg 4: M1 -> C1 , M2 -> C2                       (two independent 2-op chains)
#   alg 5: M1 -> (C1, M2, C2)                        (one modulator, three carriers)
#   alg 6: M1 -> C1 , M2 , C2                        (one 2-op chain + two carriers)
#   alg 7: M1 , C1 , M2 , C2                         (four independent carriers)
CARRIERS_BY_ALGORITHM: dict[int, tuple[int, ...]] = {
    0: (3,),
    1: (3,),
    2: (3,),
    3: (3,),
    4: (1, 3),
    5: (1, 2, 3),
    6: (1, 2, 3),
    7: (0, 1, 2, 3),
}

# Modulation edges per algorithm: (source operator index, destination index).
# Present for documentation and for the diagnostic VGM battery, which needs to
# build a known modulator -> carrier chain explicitly.
MODULATION_EDGES_BY_ALGORITHM: dict[int, tuple[tuple[int, int], ...]] = {
    0: ((0, 1), (1, 2), (2, 3)),
    1: ((0, 2), (1, 2), (2, 3)),
    2: ((0, 3), (1, 2), (2, 3)),
    3: ((0, 1), (1, 3), (2, 3)),
    4: ((0, 1), (2, 3)),
    5: ((0, 1), (0, 2), (0, 3)),
    6: ((0, 1),),
    7: (),
}

N_ALGORITHMS = 8
N_OPERATORS = 4

# Operator 1 (M1) is the only one with a feedback path on this chip.
FEEDBACK_OPERATOR_INDEX = 0


# ---------------------------------------------------------------------------
# Register map, limited to what the render protocol actually writes
# ---------------------------------------------------------------------------
REG_LFO = 0x22
REG_KEY_ON_OFF = 0x28
REG_DAC_DATA = 0x2A
REG_DAC_ENABLE = 0x2B
REG_MODE = 0x27
REG_DT1_MUL = 0x30
REG_TL = 0x40
REG_KS_AR = 0x50
REG_AMS_EN_D1R = 0x60
REG_D2R = 0x70
REG_D1L_RR = 0x80
REG_SSG_EG = 0x90
REG_FNUM_LOW = 0xA0
REG_BLOCK_FNUM_HIGH = 0xA4
REG_FB_ALGORITHM = 0xB0
REG_PAN_AMS_PMS = 0xB4

# Legal register ranges, used by the morph validator and by the encoding layer.
PARAM_RANGES: dict[str, tuple[int, int]] = {
    "CON": (0, 7),
    "FL": (0, 7),
    "AR": (0, 31),
    "D1R": (0, 31),
    "D2R": (0, 31),
    "RR": (0, 15),
    "D1L": (0, 15),
    "TL": (0, 127),
    "KS": (0, 3),
    "MUL": (0, 15),
    "DT1": (0, 7),
}

PER_OPERATOR_PARAMS: tuple[str, ...] = (
    "AR",
    "D1R",
    "D2R",
    "RR",
    "D1L",
    "TL",
    "KS",
    "MUL",
    "DT1",
)
GLOBAL_PARAMS: tuple[str, ...] = ("CON", "FL")


@dataclass(frozen=True)
class OperatorRole:
    """Role of one operator within one algorithm."""

    index: int
    name: str
    is_carrier: bool
    modulates: tuple[int, ...]
    modulated_by: tuple[int, ...]


def is_carrier(algorithm: int, operator_index: int) -> bool:
    """Whether an operator's output reaches the channel output."""
    _check_algorithm(algorithm)
    _check_operator(operator_index)
    return operator_index in CARRIERS_BY_ALGORITHM[algorithm]


def carrier_indices(algorithm: int) -> tuple[int, ...]:
    _check_algorithm(algorithm)
    return CARRIERS_BY_ALGORITHM[algorithm]


def modulator_indices(algorithm: int) -> tuple[int, ...]:
    _check_algorithm(algorithm)
    carriers = set(CARRIERS_BY_ALGORITHM[algorithm])
    return tuple(i for i in range(N_OPERATORS) if i not in carriers)


def operator_roles(algorithm: int) -> tuple[OperatorRole, ...]:
    """Full role description of the four operators under one algorithm."""
    _check_algorithm(algorithm)
    edges = MODULATION_EDGES_BY_ALGORITHM[algorithm]
    roles = []
    for i in range(N_OPERATORS):
        roles.append(
            OperatorRole(
                index=i,
                name=OPERATOR_NAMES[i],
                is_carrier=is_carrier(algorithm, i),
                modulates=tuple(dst for src, dst in edges if src == i),
                modulated_by=tuple(src for src, dst in edges if dst == i),
            )
        )
    return tuple(roles)


def carrier_columns(algorithm: int, param: str = "TL") -> tuple[str, ...]:
    """Corpus column names of the carrier operators for a parameter."""
    return tuple(f"{OPERATOR_NAMES[i]}_{param}" for i in carrier_indices(algorithm))


def modulator_columns(algorithm: int, param: str = "TL") -> tuple[str, ...]:
    """Corpus column names of the modulator operators for a parameter."""
    return tuple(f"{OPERATOR_NAMES[i]}_{param}" for i in modulator_indices(algorithm))


def _check_algorithm(algorithm: int) -> None:
    if not 0 <= algorithm < N_ALGORITHMS:
        raise ValueError(f"algorithm out of range: {algorithm}")


def _check_operator(index: int) -> None:
    if not 0 <= index < N_OPERATORS:
        raise ValueError(f"operator index out of range: {index}")


# ---------------------------------------------------------------------------
# Pitch: F-number / Block, and the key code that drives key scaling
# ---------------------------------------------------------------------------
def fnum_block(midi_note: int, clock_hz: int) -> tuple[int, int]:
    """F-number and Block for a MIDI note at a given master clock.

    The chip generates ``f_out = F-num * clock / (144 * 2**20) * 2**(Block-1)``,
    so for fixed registers the output frequency scales LINEARLY with the master
    clock. That is why an 8 MHz instrument plays the same registers 4.3 % sharp.
    """
    freq = 440.0 * 2.0 ** ((midi_note - 69) / 12.0)
    block = max(0, min(7, (midi_note - 12) // 12))
    scale = (freq * (1 << 20) * 144.0) / clock_hz
    fnum = round(scale / 2.0 ** (block - 1))
    while fnum > 2047 and block < 7:
        block += 1
        fnum = round(scale / 2.0 ** (block - 1))
    return min(fnum, 2047), block


def key_code(fnum: int, block: int) -> int:
    """Key code (KC) derived from Block and the high bits of F-number.

    Key scaling shifts envelope rates in DISCRETE steps as a function of this
    value, which is why it matters for the hardware validation: if changing the
    clock moved the key code, the envelope rates would jump by far more than the
    4 % the clock alone accounts for, and the temporal descriptors would be
    contaminated.

    The documented derivation uses F11 and a function of F10..F8::

        N3 = F11
        N2 = F11 & (F10 | F9 | F8) | (~F11 & F10 & F9 & F8)
        KC = (Block << 2) | (N3 << 1) | N2
    """
    f11 = (fnum >> 10) & 1
    f10 = (fnum >> 9) & 1
    f9 = (fnum >> 8) & 1
    f8 = (fnum >> 7) & 1
    n3 = f11
    n2 = (f11 & (f10 | f9 | f8)) | ((1 - f11) & f10 & f9 & f8)
    return ((block & 7) << 2) | (n3 << 1) | n2


# ---------------------------------------------------------------------------
# Multiplier and detune decoding, needed by the encoding layer
# ---------------------------------------------------------------------------
# MUL register 0 means x0.5; registers 1..15 mean x1..x15. So REGISTER ORDER IS
# NOT MULTIPLIER ORDER, which is the trap the encoding layer exists to avoid.
MUL_REGISTER_TO_MULTIPLIER: tuple[float, ...] = (
    0.5,
    1.0,
    2.0,
    3.0,
    4.0,
    5.0,
    6.0,
    7.0,
    8.0,
    9.0,
    10.0,
    11.0,
    12.0,
    13.0,
    14.0,
    15.0,
)

# DT1 is sign-magnitude, not an ordered scale: 0..3 are increasing positive
# detune and 4..7 increasing negative detune, so register 4 is "minus zero" and is
# functionally identical to register 0.
DT1_REGISTER_TO_SIGNED: tuple[int, ...] = (0, 1, 2, 3, 0, -1, -2, -3)

# TL is already logarithmic at roughly 0.75 dB per step.
TL_DB_PER_STEP = 0.75
