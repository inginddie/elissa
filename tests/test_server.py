"""Engine HTTP/WebSocket tests: session token, speech-service choice. No network, no API keys."""
import os
import tempfile

os.environ["ELISSA_HOME"] = tempfile.mkdtemp()  # must be set before importing elissa
os.environ["ELISSA_TOKEN"] = "test-token"

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from elissa import server


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server, "get_secret", lambda name: "")
    monkeypatch.setattr(server, "TOKEN", "test-token")  # another test module may have imported the server first
    with TestClient(server.app) as c:
        yield c


def test_api_requires_the_session_cookie(client):
    assert client.get("/api/settings").status_code == 403
    assert client.get("/").status_code == 403
    assert client.get("/?t=wrong").status_code == 403
    page = client.get("/?t=test-token")
    assert page.status_code == 200
    assert "elissa_session" in page.cookies
    assert client.get("/api/settings").status_code == 200  # the client now carries the cookie


def test_websocket_rejects_strangers(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()
    client.get("/?t=test-token")
    with pytest.raises(WebSocketDisconnect):  # right cookie, but a web page from another site
        with client.websocket_connect("/ws", headers={"origin": "https://evil.example"}) as ws:
            ws.receive_text()
    with client.websocket_connect("/ws", headers={"origin": "http://127.0.0.1:8740"}) as ws:
        assert '"settings"' in ws.receive_text()


def test_stt_service_choice(monkeypatch):
    keys = {}
    monkeypatch.setattr(server, "get_secret", lambda name: keys.get(name, ""))
    s = {"stt": "auto", "stt_url": "", "provider": "ollama"}
    assert server.stt_service(s) is None
    s["stt_url"] = "http://127.0.0.1:2022/v1/audio/transcriptions"
    assert server.stt_service(s) == "endpoint"
    keys["api_key:groq"] = "g"
    assert server.stt_service(s) == "groq"  # a cloud key beats the local endpoint in auto mode
    keys["api_key:openai"] = "o"
    s["provider"] = "openai"
    assert server.stt_service(s) == "openai"  # the chat provider's own service comes first
    s["stt"] = "endpoint"
    assert server.stt_service(s) == "endpoint"  # an explicit choice always wins


def test_custom_sounds_are_listed_and_confined(client, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "SOUNDS_DIR", tmp_path)
    (tmp_path / "listen.wav").write_bytes(b"RIFF....WAVE")
    (tmp_path / "notes.txt").write_text("x")
    (tmp_path.parent / "secret.wav").write_bytes(b"x")
    client.get("/?t=test-token")
    assert client.get("/api/sounds").json() == [{"name": "listen", "url": "/api/sounds/listen.wav"}]
    assert client.get("/api/sounds/listen.wav").status_code == 200
    assert client.get("/api/sounds/notes.txt").status_code == 404
    assert client.get("/api/sounds/..%2Fsecret.wav").status_code == 404


def test_approval_needs_the_right_id_and_a_window():
    import asyncio

    class FakeHub:
        def __init__(self):
            self.clients = {object()}
            self.sent = []

        async def broadcast(self, msg):
            self.sent.append(msg)

    async def scenario():
        hub = FakeHub()
        brain = server.Brain(hub)
        card = {"title": "Enviar correo", "kind": "text", "text": "hola"}

        task = asyncio.create_task(brain.request_approval("enviar_correo", card))
        await asyncio.sleep(0)
        shown = hub.sent[0]
        assert shown["type"] == "approval" and shown["title"] == "Enviar correo"
        brain.answer_approval("adivinado", True)  # a wrong id changes nothing
        await asyncio.sleep(0)
        assert not task.done()
        brain.answer_approval(shown["id"], True)
        assert await task is True
        assert hub.sent[-1] == {"type": "approval_done", "id": shown["id"]}

        task = asyncio.create_task(brain.request_approval("enviar_correo", card))
        await asyncio.sleep(0)
        brain.deny_all_approvals()  # the window went away
        assert await task is False

        hub.clients = set()
        assert await brain.request_approval("enviar_correo", card) is False

    asyncio.run(scenario())


def test_stt_rejects_empty_and_corrupt_audio_without_calling_the_service(client, monkeypatch):
    calls = []

    class NoNetwork:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            calls.append(a)
            raise AssertionError("should not reach the speech service")

    monkeypatch.setattr(server.httpx, "AsyncClient", NoNetwork)
    monkeypatch.setattr(server, "get_secret", lambda name: "key" if name == "api_key:groq" else "")
    client.get("/?t=test-token")
    client.post("/api/settings", json={"stt": "groq"})
    tiny = client.post("/api/stt", files={"file": ("a.webm", b"\x1a\x45\xdf\xa3" + b"0" * 100, "audio/webm")})
    assert tiny.status_code == 200 and tiny.json() == {"text": ""}
    corrupt = client.post("/api/stt", files={"file": ("a.webm", b"\x00" * 5000, "audio/webm")})
    assert corrupt.status_code == 422 and "intenta de nuevo" in corrupt.json()["error"]
    assert calls == []


def test_stt_error_messages_are_plain():
    assert "API key" in server.stt_error_message(401, "")
    assert "audio" in server.stt_error_message(400, '{"code":"invalid_media_file"}')


def test_tts_falls_back_to_the_windows_voice(client, monkeypatch):
    async def edge_down(*a):
        raise OSError("sin internet")

    spoken = []
    monkeypatch.setattr(server, "_edge_tts", edge_down)
    monkeypatch.setattr(server.windows_tts, "synthesize", lambda text, name, rate: spoken.append((text, name)) or b"RIFFwav")
    client.get("/?t=test-token")
    r = client.get("/api/tts", params={"text": "hola"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav" and spoken == [("hola", "")]
    client.post("/api/settings", json={"voice": "windows:Microsoft Sabina Desktop - Spanish (Mexico)"})
    client.get("/api/tts", params={"text": "chao"})
    assert spoken[-1] == ("chao", "Microsoft Sabina Desktop - Spanish (Mexico)")


def test_local_stt_route(client, monkeypatch):
    seen = []

    async def fake_local(audio, s):
        seen.append(audio[:4])
        return {"text": "hola"}

    monkeypatch.setattr(server, "transcribe_locally", fake_local)
    monkeypatch.setattr(server, "prepare_local_stt", lambda brain: None)  # no downloads in tests
    client.get("/?t=test-token")
    client.post("/api/settings", json={"stt": "local"})
    r = client.post("/api/stt", files={"file": ("audio.wav", b"RIFF" + b"0" * 3000, "audio/wav")})
    assert r.json() == {"text": "hola"} and seen == [b"RIFF"]
