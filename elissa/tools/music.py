"""Music: what is playing, and Spotify (play what the user asks for) when connected."""
from .. import media_session
from ..spotify import Spotify
from . import ToolRegistry


async def now_playing(spotify: Spotify | None) -> str:
    info = await media_session.now_playing()
    if not info and spotify and spotify.connected():
        info = await spotify.now_playing()  # e.g. playing on the phone or another PC
    if not info or not info.get("title"):
        return "No hay nada sonando ahora."
    state = "Suena" if info["playing"] else "En pausa"
    by = f" de {info['artist']}" if info.get("artist") else ""
    album = f" (álbum {info['album']})" if info.get("album") else ""
    return f"{state} «{info['title']}»{by}{album} en {info['player']}."


def register(reg: ToolRegistry, spotify: Spotify | None) -> None:
    # The registry awaits only `async def` functions, hence the small wrappers (also mapping argument names).
    async def que_suena() -> str:
        return await now_playing(spotify)

    reg.add("que_suena", "Dice qué canción o video está sonando (título, artista, reproductor).",
            "Mirando qué suena…", que_suena, {})
    if not (spotify and spotify.connected()):
        return

    async def reproducir(query: str, tipo: str = "cancion") -> str:
        return await spotify.play(query, tipo or "cancion")

    async def control(accion: str) -> str:
        return await spotify.control(accion)

    reg.add("spotify_reproducir", "Reproduce en Spotify lo que el usuario pida: una canción, un artista, un álbum, "
            "una playlist pública o una playlist suya (mi_playlist). Si Spotify no está abierto, lo abre.",
            "Buscando en Spotify…", reproducir,
            {"query": {"type": "string", "description": "Qué buscar, p. ej. 'De música ligera Soda Stereo'"},
             "tipo": {"type": "string", "enum": ["cancion", "artista", "album", "playlist", "mi_playlist"],
                      "description": "Por defecto cancion"}},
            ["query"])
    reg.add("spotify_control", "Pausa, reanuda, pasa a la siguiente o vuelve a la anterior en Spotify, en cualquier "
            "dispositivo de la cuenta (también el celular).", "Ajustando Spotify…", control,
            {"accion": {"type": "string", "enum": ["pausa", "reanudar", "siguiente", "anterior"]}}, ["accion"])
