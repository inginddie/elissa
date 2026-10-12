"""Spotify through its Web API: play a song, artist, album or playlist, control playback, see what is playing.

The user creates a free app in the Spotify developer dashboard and pastes its Client ID (no secret: Authorization
Code with PKCE). Playback control needs Spotify Premium. The login runs in the browser and comes back to this engine at
http://127.0.0.1:<port>/spotify/callback (registered in the dashboard without the port, as Spotify allows for
loopback). The refresh token lives in the Windows Credential Manager; Spotify makes it expire 6 months after the
login, after which Elissa asks to connect again.

Playback goes to the active device (desktop app, web player, phone…). With none, Elissa opens the desktop app if it
is installed, else the web player, and waits for it to show up.
"""
import asyncio
import base64
import hashlib
import logging
import os
import secrets
import time
import unicodedata
import webbrowser
import winreg
from difflib import SequenceMatcher
from urllib.parse import urlencode

import httpx

from .config import get_secret, set_secret

log = logging.getLogger(__name__)

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API = "https://api.spotify.com/v1"
SCOPES = ("user-modify-playback-state user-read-playback-state user-read-currently-playing "
          "playlist-read-private playlist-read-collaborative")
REFRESH_SECRET = "spotify:refresh_token"
CALLBACK_PATH = "/spotify/callback"
DEVICE_WAIT_S = 20

KINDS = {"cancion": "track", "artista": "artist", "album": "album", "playlist": "playlist"}


class SpotifyError(Exception):
    pass


class NeedsLogin(SpotifyError):
    pass


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c)).strip()


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def desktop_installed() -> bool:
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "spotify"))
        return True
    except OSError:
        return False


class Spotify:
    def __init__(self, client_id, port: int, transport: httpx.AsyncBaseTransport | None = None,
                 opener=webbrowser.open, launcher=os.startfile):
        self.client_id = client_id  # callable: the setting can change while running
        self.port = port
        self.client = httpx.AsyncClient(timeout=15, transport=transport)
        self.open_url = opener
        self.launch = launcher
        self._token = ""
        self._token_until = 0.0
        self._pending: dict[str, str] = {}  # state -> PKCE verifier, for logins in progress

    # ----- login -----

    @property
    def redirect_uri(self) -> str:
        return f"http://127.0.0.1:{self.port}{CALLBACK_PATH}"

    def connected(self) -> bool:
        return bool(self.client_id() and get_secret(REFRESH_SECRET))

    def login_url(self) -> str:
        if not self.client_id():
            raise SpotifyError("Falta el Client ID de tu app de Spotify.")
        verifier, challenge = pkce_pair()
        state = secrets.token_urlsafe(24)
        self._pending = {state: verifier}  # only the latest login attempt is valid
        return AUTH_URL + "?" + urlencode({
            "client_id": self.client_id(), "response_type": "code", "redirect_uri": self.redirect_uri,
            "code_challenge_method": "S256", "code_challenge": challenge, "state": state, "scope": SCOPES})

    async def finish_login(self, code: str, state: str) -> None:
        verifier = self._pending.pop(state, None) if state else None
        if not verifier or not code:
            raise SpotifyError("Este enlace de inicio de sesión no es válido o ya se usó. Vuelve a conectar desde Ajustes.")
        await self._token_request({"grant_type": "authorization_code", "code": code,
                                   "redirect_uri": self.redirect_uri, "code_verifier": verifier})

    def logout(self) -> None:
        set_secret(REFRESH_SECRET, "")
        self._token, self._token_until = "", 0.0

    async def _token_request(self, data: dict) -> None:
        r = await self.client.post(TOKEN_URL, data={**data, "client_id": self.client_id()})
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code != 200:
            if body.get("error") in ("invalid_grant", "invalid_client"):
                self.logout()
                raise NeedsLogin("La conexión con Spotify venció. Vuelve a conectarla en Ajustes → Integraciones.")
            raise SpotifyError(f"Spotify no aceptó el inicio de sesión ({body.get('error') or r.status_code}).")
        self._token = body["access_token"]
        self._token_until = time.monotonic() + int(body.get("expires_in", 3600)) - 60
        if body.get("refresh_token"):  # Spotify may or may not rotate it
            set_secret(REFRESH_SECRET, body["refresh_token"])

    async def _access_token(self) -> str:
        if self._token and time.monotonic() < self._token_until:
            return self._token
        refresh = get_secret(REFRESH_SECRET)
        if not (refresh and self.client_id()):
            raise NeedsLogin("Spotify no está conectado. Conéctalo en Ajustes → Integraciones.")
        await self._token_request({"grant_type": "refresh_token", "refresh_token": refresh})
        return self._token

    async def _api(self, method: str, path: str, **kw) -> httpx.Response:
        for attempt in (1, 2):
            r = await self.client.request(method, API + path,
                                          headers={"Authorization": f"Bearer {await self._access_token()}"}, **kw)
            if r.status_code == 401 and attempt == 1:  # token revoked or expired early: refresh once
                self._token_until = 0
                continue
            if r.status_code == 429:
                raise SpotifyError("Spotify está limitando las peticiones; intenta en un momento.")
            return r
        return r

    @staticmethod
    def _reason(r: httpx.Response) -> str:
        try:
            err = r.json().get("error", {})
            return err.get("reason") or err.get("message") or str(r.status_code)
        except ValueError:
            return str(r.status_code)

    # ----- devices -----

    async def devices(self) -> list[dict]:
        r = await self._api("GET", "/me/player/devices")
        return r.json().get("devices", []) if r.status_code == 200 else []

    @staticmethod
    def choose_device(devices: list[dict]) -> dict | None:
        usable = [d for d in devices if not d.get("is_restricted")]
        return (next((d for d in usable if d.get("is_active")), None)
                or next((d for d in usable if d.get("type") == "Computer"), None)
                or (usable[0] if usable else None))

    async def ensure_device(self) -> dict:
        device = self.choose_device(await self.devices())
        if device:
            return device
        if desktop_installed():
            self.launch("spotify:")
        else:
            self.open_url("https://open.spotify.com/")
        deadline = time.monotonic() + DEVICE_WAIT_S
        while time.monotonic() < deadline:
            await asyncio.sleep(1.5)
            device = self.choose_device(await self.devices())
            if device:
                return device
        raise SpotifyError("Abrí Spotify, pero no apareció como dispositivo. Inicia sesión en Spotify y vuelve a pedirlo.")

    # ----- playback -----

    async def _play_body(self, body: dict) -> None:
        device = await self.ensure_device()
        r = await self._api("PUT", "/me/player/play", params={"device_id": device["id"]}, json=body)
        if r.status_code == 403 and self._reason(r) == "PREMIUM_REQUIRED":
            r = await self._api("PUT", "/me/player/play", params={"device_id": device["id"]}, json=body)  # flaky
        if r.status_code not in (200, 202, 204):
            if self._reason(r) == "PREMIUM_REQUIRED":
                raise SpotifyError("Spotify solo deja controlar la reproducción con una cuenta Premium.")
            raise SpotifyError(f"Spotify no pudo reproducir ({self._reason(r)}).")

    async def my_playlist(self, name: str) -> dict | None:
        wanted, best, best_score = _norm(name), None, 0.0
        for offset in range(0, 200, 50):
            r = await self._api("GET", "/me/playlists", params={"limit": 50, "offset": offset})
            items = r.json().get("items", []) if r.status_code == 200 else []
            for p in items:
                have = _norm(p.get("name", ""))
                score = 1.0 if wanted in have else SequenceMatcher(None, wanted, have).ratio()
                if score > best_score:
                    best, best_score = p, score
            if len(items) < 50:
                break
        return best if best_score >= 0.6 else None

    async def search(self, query: str, kind: str) -> dict | None:
        r = await self._api("GET", "/search", params={"q": query, "type": kind, "limit": 5})
        if r.status_code != 200:
            raise SpotifyError(f"La búsqueda en Spotify falló ({self._reason(r)}).")
        items = [i for i in r.json().get(kind + "s", {}).get("items", []) if i]
        return items[0] if items else None

    async def play(self, query: str, kind: str = "cancion") -> str:
        if kind == "mi_playlist":
            found = await self.my_playlist(query)
            if not found:
                raise SpotifyError(f"No encontré una playlist tuya llamada «{query}».")
            await self._play_body({"context_uri": found["uri"]})
            return f"Reproduciendo tu playlist «{found['name']}»."
        kind_api = KINDS.get(kind)
        if not kind_api:
            raise ValueError(f"Tipo desconocido. Opciones: {', '.join([*KINDS, 'mi_playlist'])}.")
        item = await self.search(query, kind_api)
        if not item:
            raise SpotifyError(f"No encontré «{query}» en Spotify.")
        body = {"uris": [item["uri"]]} if kind_api == "track" else {"context_uri": item["uri"]}
        await self._play_body(body)
        artists = ", ".join(a["name"] for a in item.get("artists", [])[:2])
        return f"Reproduciendo «{item['name']}»" + (f" de {artists}." if artists else ".")

    async def control(self, action: str) -> str:
        calls = {"pausa": ("PUT", "/me/player/pause"), "reanudar": ("PUT", "/me/player/play"),
                 "siguiente": ("POST", "/me/player/next"), "anterior": ("POST", "/me/player/previous")}
        if action not in calls:
            raise ValueError(f"Acción desconocida. Opciones: {', '.join(calls)}.")
        method, path = calls[action]
        r = await self._api(method, path)
        if r.status_code == 404 or self._reason(r) == "NO_ACTIVE_DEVICE":
            if action == "reanudar":
                await self._play_body({})
                return "Listo."
            raise SpotifyError("No hay nada sonando en Spotify ahora.")
        if r.status_code not in (200, 202, 204):
            raise SpotifyError(f"Spotify no aceptó la orden ({self._reason(r)}).")
        return "Listo."

    async def now_playing(self) -> dict | None:
        r = await self._api("GET", "/me/player/currently-playing")
        if r.status_code != 200 or not r.content:
            return None
        body = r.json()
        item = body.get("item") or {}
        if not item:
            return None
        return {"title": item.get("name", ""), "artist": ", ".join(a["name"] for a in item.get("artists", [])),
                "album": (item.get("album") or {}).get("name", ""), "playing": bool(body.get("is_playing")),
                "player": "Spotify"}
