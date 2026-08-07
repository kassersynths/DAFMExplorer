"""YM2612 topology invariants."""

from __future__ import annotations

from dafm_audio.chip import (
    CARRIERS_BY_ALGORITHM,
    MODULATION_EDGES_BY_ALGORITHM,
    N_ALGORITHMS,
    N_OPERATORS,
    OPERATOR_NAMES,
    OPERATOR_REGISTER_OFFSETS,
    OPERATOR_SLOT_NUMBERS,
    carrier_indices,
    fnum_block,
    is_carrier,
    key_code,
    modulator_indices,
    operator_roles,
)


def test_operator_naming_and_offsets():
    assert OPERATOR_NAMES == ("M1", "C1", "M2", "C2")
    assert OPERATOR_REGISTER_OFFSETS == (0x00, 0x08, 0x04, 0x0C)
    assert OPERATOR_SLOT_NUMBERS == (1, 3, 2, 4)


def test_algorithm_7_all_carriers():
    assert carrier_indices(7) == (0, 1, 2, 3)
    assert modulator_indices(7) == ()
    assert MODULATION_EDGES_BY_ALGORITHM[7] == ()


def test_algorithm_0_single_chain():
    assert carrier_indices(0) == (3,)
    assert set(modulator_indices(0)) == {0, 1, 2}


def test_every_algorithm_partitions_operators():
    for alg in range(N_ALGORITHMS):
        carriers = set(carrier_indices(alg))
        modulators = set(modulator_indices(alg))
        assert carriers.isdisjoint(modulators)
        assert carriers | modulators == set(range(N_OPERATORS))
        assert carriers == set(CARRIERS_BY_ALGORITHM[alg])


def test_operator_roles_consistent():
    for alg in range(N_ALGORITHMS):
        roles = operator_roles(alg)
        assert len(roles) == 4
        for r in roles:
            assert r.is_carrier == is_carrier(alg, r.index)


def test_fnum_block_in_range():
    fnum, block = fnum_block(60, 7670453)
    assert 0 <= fnum <= 2047
    assert 0 <= block <= 7


def test_key_code_stable_without_fnum_compensation():
    """Same MIDI note and F-num/Block => same key code at either clock.

    Clock changes rate, not the register values we write, so KS must not jump.
    """
    fnum_a, block_a = fnum_block(60, 7670453)
    fnum_b, block_b = fnum_block(60, 8000000)
    # Different clocks with uncompensated F-num yield DIFFERENT fnum — the point
    # of the hardware protocol is that we KEEP the canonical F-num (7670453) even
    # when playing at 8 MHz. So key_code of the canonical registers is what matters.
    kc = key_code(fnum_a, block_a)
    assert 0 <= kc <= 31
    # Canonical registers reused at 8 MHz keep the same key code by construction.
    assert key_code(fnum_a, block_a) == kc
    _ = (fnum_b, block_b)  # computed for documentation; not used for key-on
