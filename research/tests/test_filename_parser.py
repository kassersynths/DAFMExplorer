"""Filename parsing with the awkward real cases."""

from __future__ import annotations

from dafm_audio.corpus import parse_filename


def test_simple_boogerman():
    p = parse_filename("Boogerman_-_01_-_Title_Theme.opm")
    assert p.game == "Boogerman"
    assert p.track_number == 1
    assert p.track == "Title Theme"


def test_internal_hyphen_in_game():
    p = parse_filename("Spider-Man_&_X-Men_-_01_-_Title.opm")
    assert p.game == "Spider-Man & X-Men"
    assert p.track_number == 1
    assert p.track == "Title"


def test_parenthetical_suffix():
    p = parse_filename("Zam_Custom_(ME-F91-C)_-_02_-_Boss.opm")
    assert "Zam Custom (ME-F91-C)" == p.game
    assert p.track_number == 2
    assert p.track == "Boss"


def test_missing_track_number():
    p = parse_filename("Some_Game_-_Just_A_Title.opm")
    assert p.game == "Some Game"
    assert p.track_number is None
    assert p.track == "Just A Title"


def test_bare_stem():
    p = parse_filename("Lonely.opm")
    assert p.game == "Lonely"
    assert p.track == ""
