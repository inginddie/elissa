"""macOS helpers that parse what the system answers (run everywhere: no AppleScript or `say` involved)."""
from elissa.system import macos


def test_say_voice_list():
    out = """Albert              en_US    # Hello! My name is Albert.
Eddy (Spanish (Mexico)) es_MX    # ¡Hola! Me llamo Eddy.
Mónica              es_ES    # ¡Hola! Me llamo Mónica.
broken line without locale
"""
    assert macos.parse_voices(out) == [{"name": "Albert", "lang": "en_US"},
                                       {"name": "Eddy (Spanish (Mexico))", "lang": "es_MX"},
                                       {"name": "Mónica", "lang": "es_ES"}]


def test_track_parsing():
    assert macos.parse_track("De música ligera\tSoda Stereo\tCanción animal\tplaying", "Spotify") == {
        "title": "De música ligera", "artist": "Soda Stereo", "album": "Canción animal", "playing": True,
        "player": "Spotify"}
    assert macos.parse_track("", "Music") is None
    assert macos.parse_track("solo título", "Music") is None
