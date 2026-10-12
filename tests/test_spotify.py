"""Spotify Web API client against a fake Spotify (httpx.MockTransport): login, play, devices, tokens, playlists."""
import asyncio
import base64
import hashlib
import json
import os
import tempfile
from urllib.parse import parse_qs, urlparse

os.environ["ELISSA_HOME"] = os.environ.get("ELISSA_HOME") or tempfile.mkdtemp()  # before importing elissa

import httpx
import pytest

from elissa import spotify as sp

CLIENT_ID = "a" * 32


class FakeSpotify:
    """Records requests; answers like the Web API. `devices` is a list of device lists, one per GET."""

    def __init__(self):
        self.calls: list[tuple[str, str, dict]] = []
        self.devices = [[{"id": "pc", "type": "Computer", "is_active": True, "is_restricted": False}]]
        self.token_error = None
        self.unauthorized_once = False
        self.play_status = 204

    def handler(self, request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        body = {}
        if request.content:
            raw = request.content.decode()
            body = dict(parse_qs(raw)) if "=" in raw and not raw.startswith("{") else json.loads(raw)
        self.calls.append((method, path, {**dict(request.url.params), **body}))
        if path == "/api/token":
            if self.token_error:
                return httpx.Response(400, json={"error": self.token_error})
            return httpx.Response(200, json={"access_token": "AT", "expires_in": 3600, "refresh_token": "RT2"})
        if self.unauthorized_once:
            self.unauthorized_once = False
            return httpx.Response(401, json={"error": {"status": 401, "message": "expired"}})
        if path == "/v1/me/player/devices":
            return httpx.Response(200, json={"devices": self.devices.pop(0) if len(self.devices) > 1 else self.devices[0]})
        if path == "/v1/search":
            kind = request.url.params["type"]
            item = {"uri": f"spotify:{kind}:1", "name": "De música ligera", "artists": [{"name": "Soda Stereo"}]}
            return httpx.Response(200, json={kind + "s": {"items": [item]}})
        if path == "/v1/me/playlists":
            return httpx.Response(200, json={"items": [{"name": "Concentración profunda", "uri": "spotify:playlist:9"},
                                                       {"name": "Rock", "uri": "spotify:playlist:2"}]})
        if path == "/v1/me/player/play":
            return httpx.Response(self.play_status)
        if path in ("/v1/me/player/pause", "/v1/me/player/next"):
            return httpx.Response(404, json={"error": {"status": 404, "reason": "NO_ACTIVE_DEVICE"}})
        return httpx.Response(404)


@pytest.fixture
def fake(monkeypatch):
    secrets_store = {sp.REFRESH_SECRET: "RT1"}
    monkeypatch.setattr(sp, "get_secret", lambda k: secrets_store.get(k, ""))
    monkeypatch.setattr(sp, "set_secret", lambda k, v: secrets_store.__setitem__(k, v))
    f = FakeSpotify()
    f.secrets = secrets_store
    f.opened, f.launched = [], []
    f.client = sp.Spotify(lambda: CLIENT_ID, 8123, transport=httpx.MockTransport(f.handler),
                          opener=f.opened.append, launcher=f.launched.append)
    return f


def run(coro):
    return asyncio.run(coro)


def test_pkce_challenge_matches_verifier():
    verifier, challenge = sp.pkce_pair()
    assert 43 <= len(verifier) <= 128
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert challenge == expected


def test_login_flow_checks_state(fake):
    fake.secrets.clear()
    url = urlparse(fake.client.login_url())
    q = parse_qs(url.query)
    assert q["redirect_uri"] == ["http://127.0.0.1:8123/spotify/callback"] and q["code_challenge_method"] == ["S256"]
    with pytest.raises(sp.SpotifyError):
        run(fake.client.finish_login("code", "wrong-state"))
    run(fake.client.finish_login("code", q["state"][0]))
    assert fake.secrets[sp.REFRESH_SECRET] == "RT2" and fake.client.connected()
    with pytest.raises(sp.SpotifyError):  # a state is single-use
        run(fake.client.finish_login("code", q["state"][0]))


def test_play_song_on_active_device(fake):
    said = run(fake.client.play("de musica ligera", "cancion"))
    assert said == "Reproduciendo «De música ligera» de Soda Stereo."
    play = [c for c in fake.calls if c[1] == "/v1/me/player/play"][0]
    assert play[2]["device_id"] == "pc" and play[2]["uris"] == ["spotify:track:1"]


def test_artist_plays_as_context(fake):
    run(fake.client.play("Soda Stereo", "artista"))
    play = [c for c in fake.calls if c[1] == "/v1/me/player/play"][0]
    assert play[2]["context_uri"] == "spotify:artist:1"


def test_no_device_opens_spotify_and_waits(fake, monkeypatch):
    async def no_sleep(_):
        return None
    monkeypatch.setattr(sp.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(sp, "desktop_installed", lambda: False)
    fake.devices = [[], [], [{"id": "web", "type": "Computer", "is_active": False}]]
    run(fake.client.play("x"))
    assert fake.opened == ["https://open.spotify.com/"] and not fake.launched
    assert [c for c in fake.calls if c[1] == "/v1/me/player/play"][0][2]["device_id"] == "web"


def test_desktop_app_is_preferred_when_installed(fake, monkeypatch):
    async def no_sleep(_):
        return None
    monkeypatch.setattr(sp.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(sp, "desktop_installed", lambda: True)
    fake.devices = [[], [{"id": "pc", "type": "Computer"}]]
    run(fake.client.play("x"))
    assert fake.launched == ["spotify:"] and not fake.opened


def test_restricted_devices_are_skipped():
    devices = [{"id": "tv", "is_active": True, "is_restricted": True}, {"id": "phone", "type": "Smartphone"}]
    assert sp.Spotify.choose_device(devices)["id"] == "phone"


def test_expired_login_asks_to_reconnect(fake):
    fake.token_error = "invalid_grant"
    with pytest.raises(sp.NeedsLogin):
        run(fake.client.play("x"))
    assert fake.secrets[sp.REFRESH_SECRET] == ""


def test_revoked_token_is_refreshed_once(fake):
    run(fake.client.devices())  # gets a token
    fake.unauthorized_once = True
    assert run(fake.client.devices())[0]["id"] == "pc"
    assert sum(1 for c in fake.calls if c[1] == "/api/token") == 2


def test_my_playlist_by_approximate_name(fake):
    assert run(fake.client.play("concentracion", "mi_playlist")) == "Reproduciendo tu playlist «Concentración profunda»."
    with pytest.raises(sp.SpotifyError):
        run(fake.client.play("jazz para cocinar", "mi_playlist"))


def test_premium_required_is_explained(fake):
    fake.play_status = 403
    fake.handler_orig = fake.handler

    def handler(request):
        if request.url.path == "/v1/me/player/play":
            return httpx.Response(403, json={"error": {"status": 403, "reason": "PREMIUM_REQUIRED"}})
        return fake.handler_orig(request)
    fake.client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(sp.SpotifyError, match="Premium"):
        run(fake.client.play("x"))


def test_pause_with_nothing_playing(fake):
    with pytest.raises(sp.SpotifyError, match="nada sonando"):
        run(fake.client.control("pausa"))


def test_music_tools_need_a_connection(fake):
    from elissa.tools import ToolRegistry
    from elissa.tools.music import register
    reg = ToolRegistry()
    register(reg, fake.client)
    assert {"que_suena", "spotify_reproducir", "spotify_control"} <= {t.name for t in reg.specs()}
    fake.secrets.clear()
    reg = ToolRegistry()
    register(reg, fake.client)
    assert {t.name for t in reg.specs()} == {"que_suena"}


def test_media_tool_prefers_windows_session_then_keys(monkeypatch):
    from elissa.tools import actions as act
    pressed = []
    monkeypatch.setattr(act.system, "press_media_key", lambda key: pressed.append(key) or True)
    sent = []

    async def session_ok(action, prefer="spotify"):
        sent.append(action)
        return True
    monkeypatch.setattr(act.media_session, "control", session_ok)
    tools = act.Actions(files=None)
    assert run(tools.media("siguiente")) == "Listo." and sent == ["next"] and not pressed

    async def no_session(action, prefer="spotify"):
        return None
    monkeypatch.setattr(act.media_session, "control", no_session)
    run(tools.media("pausa"))
    assert pressed == [0xB3]
    run(tools.media("subir_volumen", 2))  # volume always uses the keys
    assert pressed[1:] == [0xAF] * 2
