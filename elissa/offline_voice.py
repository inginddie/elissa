"""Voices that work without internet: Windows' SAPI voices, or macOS' system voices (`say`).

Used when the user picks one, and as a fallback when the online Edge voice can't be reached. Voice ids carry a
prefix; on Windows it stays "windows:" so voices chosen before keep working.
"""
from . import system, windows_tts

PREFIX = "windows:" if system.IS_WINDOWS else "say:"
LABEL = "Windows" if system.IS_WINDOWS else "macOS"


def available() -> bool:
    return system.has("offline_voice")


def is_offline(voice_id: str) -> bool:
    return voice_id.startswith(PREFIX)


def list_voices(lang: str) -> list[dict]:
    """[{"id", "name"}] for the speech language ("es", "en"…)."""
    if system.IS_WINDOWS:
        out = []
        for v in windows_tts.list_voices():
            if v["lang"].upper() in windows_tts.SPANISH or lang != "es":
                out.append({"id": PREFIX + v["name"],
                            "name": v["name"].replace("Microsoft ", "").replace(" Desktop", "")})
        return out
    from .system import macos
    return [{"id": PREFIX + v["name"], "name": v["name"]} for v in macos.say_voices()
            if v["lang"].lower().startswith(lang)]


def synthesize(text: str, voice_id: str, speed: float, lang: str = "es") -> bytes:
    """A WAV of `text`. Without a voice (the Edge fallback) it picks one of the speech language."""
    name = voice_id.removeprefix(PREFIX) if is_offline(voice_id) else ""
    if system.IS_WINDOWS:
        return windows_tts.synthesize(text, name, speed)
    from .system import macos
    if not name:
        name = next((v["name"] for v in macos.say_voices() if v["lang"].lower().startswith(lang)), "")
    return macos.say_synthesize(text, name, speed)
