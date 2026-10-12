"""Wake phrase spotting on short recordings (synthetic voices). Needs the Vosk models: they run where Elissa already
downloaded them (or ELISSA_VOSK_MODELS points to their folder) and are skipped elsewhere, e.g. in CI."""
import os
import wave
from pathlib import Path

import pytest

from elissa.wake import BLOCK, LANGUAGES, Spotter, is_wake, language_for

AUDIO = Path(__file__).parent / "audio"
MODELS = Path(os.getenv("ELISSA_VOSK_MODELS") or Path(os.getenv("APPDATA", "")) / "Elissa" / "models")


def test_wake_phrases_text():
    es, en = LANGUAGES["es"], LANGUAGES["en"]
    assert is_wake("hola elisa", es) and is_wake("oye elisa hola es", es)
    assert not is_wake("hola melisa", es) and not is_wake("ella es elisa", es) and not is_wake("elisa", es)
    assert is_wake("hey alyssa", en) and is_wake("okay alyssa", en)
    assert not is_wake("hey lisa", en) and not is_wake("she is alyssa", en) and not is_wake("hola elisa", en)


def test_language_follows_speech_setting():
    assert language_for("en-US") is LANGUAGES["en"] and language_for("en-GB") is LANGUAGES["en"]
    assert language_for("es-CO") is LANGUAGES["es"] and language_for("fr-FR") is LANGUAGES["es"]


@pytest.mark.parametrize("lang, name, expected", [
    ("es", "hola_elissa", True), ("es", "oye_elissa", True),
    ("es", "hola_melisa", False), ("es", "ella_es_elisa", False), ("es", "la_reunion_empieza_a_las_tres", False),
    ("en", "hey_elissa", True), ("en", "okay_elissa", True),
    ("en", "hey_lisa", False), ("en", "hey_melissa", False), ("en", "hey_listen_to_this", False),
    ("en", "the_meeting_starts_at_three", False),
])
def test_spotter_on_recordings(lang, name, expected):
    model_dir = MODELS / LANGUAGES[lang].model
    if not (model_dir / "am").exists():
        pytest.skip("Vosk model not downloaded")
    import vosk
    vosk.SetLogLevel(-1)
    spotter = Spotter(vosk.Model(str(model_dir)), LANGUAGES[lang])
    with wave.open(str(AUDIO / f"{name}.wav")) as w:
        data = w.readframes(w.getnframes())
    woke = False
    for i, start in enumerate(range(0, len(data), BLOCK * 2)):
        woke |= spotter.feed(data[start:start + BLOCK * 2], now=i * 0.1)
    assert woke is expected
