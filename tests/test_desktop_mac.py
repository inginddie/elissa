"""macOS computer use: key parsing and the risky-combination warning (no Accessibility API needed)."""
import pytest

from elissa.tools import desktop_mac as dm


def test_keys_parse_and_codes():
    assert dm.parse_keys("Cmd + S") == ["cmd", "s"]
    assert dm.parse_keys("comando+mayús+z") == ["comando", "mayus", "z"]
    assert dm.parse_keys("enter") == ["enter"]
    for bad in ("", "cmd", "cmd+shift", "hyper+x"):
        with pytest.raises(ValueError):
            dm.parse_keys(bad)
    letters = "abcdefghijklmnopqrstuvwxyz0123456789"
    assert all(ch in dm.KEYCODES for ch in letters)
    assert len({dm.KEYCODES[ch] for ch in letters}) == len(letters)  # no two keys share a code


def test_risky_combination_whatever_the_word():
    assert tuple(dm._canonical(p) for p in dm.parse_keys("command+q")) in dm.RISKY_KEYS
    assert tuple(dm._canonical(p) for p in dm.parse_keys("comando+w")) in dm.RISKY_KEYS
