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
