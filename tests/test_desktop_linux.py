"""Linux computer use: key parsing, risky combinations, AT-SPI state bits and when the capability is on (no desktop
needed). The end-to-end test runs only against a real AT-SPI session: set ELISSA_ATSPI_FORM=1 with a window titled
"Formulario de prueba" open (a GTK form with a "Nombre" field, a password field and a "Guardar" button that writes the
name in a label, like the one used to build this module)."""
import os
import time

import pytest

from elissa.system import linux
from elissa.tools import desktop_linux as dl


def test_keys_parse_and_keysyms():
    assert dl.parse_keys("Ctrl + S") == ["ctrl", "s"]
    assert dl.parse_keys("control+mayús+z") == ["control", "mayus", "z"]
    assert dl.parse_keys("enter") == ["enter"]
    for bad in ("", "ctrl", "ctrl+shift", "hyper+x"):
        with pytest.raises(ValueError):
            dl.parse_keys(bad)
    assert dl.keysym("enter") == 0xFF0D and dl.keysym("f1") == 0xFFBE and dl.keysym("f12") == 0xFFC9
    assert dl.keysym("a") == ord("a") and dl.keysym("7") == ord("7")


def test_risky_combination_whatever_the_word():
    for combo in ("control+w", "ctrl+q", "alt+f4", "supr"):
        assert tuple(dl._canonical(p) for p in dl.parse_keys(combo)) in dl.RISKY_KEYS
    assert tuple(dl._canonical(p) for p in dl.parse_keys("ctrl+s")) not in dl.RISKY_KEYS


def test_state_bits_across_both_words():
    states = [1 << dl.ACTIVE | 1 << dl.EDITABLE, 0]
    assert dl._has(states, dl.ACTIVE) and dl._has(states, dl.EDITABLE)
    assert dl._has([0, 1 << 2], 34) and not dl._has([0], 34)


def test_computer_use_only_on_x11(monkeypatch):
    monkeypatch.setattr(linux, "_has_session_bus", lambda: True)
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    assert "computer_use" in linux._caps()
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")  # XWayland's DISPLAY is not enough: input injection is blocked
    assert "computer_use" not in linux._caps()
    monkeypatch.delenv("XDG_SESSION_TYPE")
    monkeypatch.delenv("DISPLAY")
    assert "computer_use" not in linux._caps()


@pytest.mark.skipif(not os.getenv("ELISSA_ATSPI_FORM"), reason="needs a desktop session with the test form open")
def test_reads_types_and_clicks_a_real_window():
    d = dl.DesktopLinux(lambda: set())
    assert "Formulario de prueba" in d.list_windows()
    d.focus("Formulario de prueba")
    text = d.read("Formulario de prueba")
    assert "clave" not in text and "Contraseña" not in text  # the password field is never read
    numbers = {line.split("]")[1].strip(): int(line[1:line.index("]")]) for line in text.splitlines()
               if line.startswith("[")}
    field = next(n for k, n in numbers.items() if "Nombre" in k)
    button = next(n for k, n in numbers.items() if "Guardar" in k)
    d.type_text("borrar", field)
    d.press_keys("ctrl+a")
    d.type_text("Ñandú á", field)
    d.click(button)
    time.sleep(0.5)
    assert "guardado (Ñandú á)" in d.read("Formulario de prueba")
