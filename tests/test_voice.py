"""Wake phrase spotting on short recordings (synthetic voices). Needs the Vosk model: it runs where Elissa already
downloaded it (or ELISSA_VOSK_MODEL points to it) and is skipped elsewhere, e.g. in CI."""
import os
import wave
from pathlib import Path

import pytest

from elissa.wake import BLOCK, MODEL_NAME, Spotter, is_wake

AUDIO = Path(__file__).parent / "audio"
MODEL = Path(os.getenv("ELISSA_VOSK_MODEL") or Path(os.getenv("APPDATA", "")) / "Elissa" / "models" / MODEL_NAME)


def test_wake_phrases_text():
    assert is_wake("hola elisa") and is_wake("oye elisa hola es")
    assert not is_wake("hola melisa") and not is_wake("ella es elisa") and not is_wake("elisa")


@pytest.mark.skipif(not (MODEL / "am").exists(), reason="Vosk model not downloaded")
@pytest.mark.parametrize("name, expected", [
    ("hola_elissa", True), ("oye_elissa", True),
    ("hola_melisa", False), ("ella_es_elisa", False), ("la_reunion_empieza_a_las_tres", False),
])
def test_spotter_on_recordings(name, expected):
    import vosk
    vosk.SetLogLevel(-1)
    spotter = Spotter(vosk.Model(str(MODEL)))
    with wave.open(str(AUDIO / f"{name}.wav")) as w:
        data = w.readframes(w.getnframes())
    woke = False
    for i, start in enumerate(range(0, len(data), BLOCK * 2)):
        woke |= spotter.feed(data[start:start + BLOCK * 2], now=i * 0.1)
    assert woke is expected
