"""Offline voices: Windows' built-in SAPI voices (e.g. "Microsoft Sabina - Spanish (Mexico)").

Used when the user picks one, and as a fallback when the online Edge voice can't be reached.
"""
import io
import threading
import wave

SAMPLE_RATE = 22050
_FORMAT_22KHZ_16BIT_MONO = 22  # SpeechAudioFormatType.SAFT22kHz16BitMono
_lock = threading.Lock()  # SAPI objects are created per call, but one synthesis at a time keeps it predictable

# LCIDs (hex, as SAPI reports them) of Spanish variants, to pick a fallback voice.
SPANISH = {"80A", "C0A", "40A", "240A", "2C0A", "540A", "1C0A", "340A", "280A", "380A", "200A"}


def _voices():
    import comtypes.client
    return comtypes.client.CreateObject("SAPI.SpVoice")


def list_voices() -> list[dict]:
    with _lock:
        import comtypes
        comtypes.CoInitialize()
        try:
            voice = _voices()
            items = voice.GetVoices()
            out = []
            for i in range(items.Count):
                token = items.Item(i)
                out.append({"name": token.GetDescription(), "lang": token.GetAttribute("Language").split(";")[0]})
            return out
        finally:
            comtypes.CoUninitialize()


def synthesize(text: str, name: str = "", rate: float = 1.0) -> bytes:
    """Speaks `text` into a WAV (22 kHz mono). `name` picks a voice by its description; default: a Spanish one."""
    import comtypes
    import comtypes.client
    with _lock:
        comtypes.CoInitialize()
        try:
            voice = _voices()
            items = voice.GetVoices()
            tokens = [items.Item(i) for i in range(items.Count)]
            chosen = next((t for t in tokens if t.GetDescription() == name), None) or next(
                (t for t in tokens if t.GetAttribute("Language").split(";")[0].upper() in SPANISH), None)
            if chosen is not None:
                voice.Voice = chosen
            voice.Rate = max(-10, min(10, round((rate - 1) * 10)))
            stream = comtypes.client.CreateObject("SAPI.SpMemoryStream")
            stream.Format.Type = _FORMAT_22KHZ_16BIT_MONO
            voice.AudioOutputStream = stream
            voice.Speak(text)
            pcm = bytes(stream.GetData())
        finally:
            comtypes.CoUninitialize()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return buf.getvalue()
