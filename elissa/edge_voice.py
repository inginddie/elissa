"""Edge's online voices (edge-tts), resilient to Microsoft moving the service.

In October 2026 the legacy host started answering 403 in many regions; Edge itself now talks to
api.msedgeservices.com with the same client key (rany2/edge-tts#490). We try the legacy host and switch to the new one
on a 403, and stay there for the rest of the session.
"""
import logging

import edge_tts
import edge_tts.communicate as communicate
from edge_tts.constants import TRUSTED_CLIENT_TOKEN

log = logging.getLogger(__name__)

NEW_WSS_URL = ("wss://api.msedgeservices.com/tts/cognitiveservices/websocket/v1"
               f"?Ocp-Apim-Subscription-Key={TRUSTED_CLIENT_TOKEN}")
LEGACY_WSS_URL = communicate.WSS_URL


def _is_forbidden(error: Exception) -> bool:
    return getattr(error, "status", None) == 403 or "403" in str(error)[:80]


async def _stream(text: str, voice: str, rate: str) -> bytes:
    audio = bytearray()
    async for chunk in edge_tts.Communicate(text, voice, rate=rate).stream():
        if chunk["type"] == "audio":
            audio += chunk["data"]
    if not audio:
        raise RuntimeError("Edge no devolvió audio")
    return bytes(audio)


async def synthesize(text: str, voice: str, speed: float = 1.0) -> bytes:
    rate = f"{round((speed - 1) * 100):+d}%"
    try:
        return await _stream(text, voice, rate)
    except Exception as e:
        if not _is_forbidden(e) or communicate.WSS_URL == NEW_WSS_URL:
            raise
        log.info("Edge voice host answered 403; switching to api.msedgeservices.com")
        communicate.WSS_URL = NEW_WSS_URL
        return await _stream(text, voice, rate)
