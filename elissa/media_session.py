"""What is playing, and play/pause/next/previous, through Windows' media controls (the ones in the volume flyout).

Unlike the media keys, this targets one player (Spotify first, desktop or in the browser) and can tell what is
playing. No account or network is involved. Returns None when the API is unavailable so callers can fall back.
"""
import logging

log = logging.getLogger(__name__)

ACTIONS = ("toggle", "play", "pause", "next", "previous")


async def _sessions():
    try:
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as Manager
    except ImportError:
        return None, []
    manager = await Manager.request_async()
    return manager, list(manager.get_sessions())


def _app(session) -> str:
    return (session.source_app_user_model_id or "").lower()


async def pick_session(prefer: str = "spotify"):
    """The preferred player's session (by app id or, for web players, by what it reports), else the current one."""
    manager, sessions = await _sessions()
    if manager is None:
        return None
    for s in sessions:
        if prefer in _app(s):
            return s
    for s in sessions:  # Spotify's web player runs inside the browser: look at the session's media instead
        try:
            props = await s.try_get_media_properties_async()
        except OSError:
            continue
        if prefer in f"{props.album_title} {props.subtitle}".lower():
            return s
    return manager.get_current_session()


async def now_playing(prefer: str = "spotify") -> dict | None:
    try:
        session = await pick_session(prefer)
        if session is None:
            return None
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status
        props = await session.try_get_media_properties_async()
        status = Status(session.get_playback_info().playback_status).name.lower()
    except OSError as e:
        log.warning("media session: %s", e)
        return None
    app = _app(session)
    player = "Spotify" if "spotify" in app else app.split("!")[0].removesuffix(".exe") or "?"
    return {"title": props.title, "artist": props.artist, "album": props.album_title, "playing": status == "playing",
            "player": player}


async def control(action: str, prefer: str = "spotify") -> bool | None:
    """True if the player took the command, False if it refused, None if there is no session or API."""
    if action not in ACTIONS:
        raise ValueError(f"Acción desconocida: {action}")
    try:
        session = await pick_session(prefer)
        if session is None:
            return None
        fn = {"toggle": session.try_toggle_play_pause_async, "play": session.try_play_async,
              "pause": session.try_pause_async, "next": session.try_skip_next_async,
              "previous": session.try_skip_previous_async}[action]
        return bool(await fn())
    except OSError as e:
        log.warning("media session: %s", e)
        return None
