"""The conversation itself: end it (and hide the window), and the system volume."""
from typing import Callable

from ..audio_mixer import Mixer
from . import ToolRegistry


def register(reg: ToolRegistry, mixer: Mixer, emit: Callable[[dict], None]) -> None:
    async def terminar(ocultar: bool = False) -> str:
        emit({"type": "end_conversation", "hide": bool(ocultar)})
        return "Conversación terminada: no vuelvas a preguntar nada; despídete en pocas palabras."

    async def volumen(porcentaje: int | None = None, cambio: int | None = None, silenciar: bool | None = None) -> str:
        if porcentaje is None and cambio is None and silenciar is None:
            v = await mixer.volume()
        else:
            v = await mixer.set_volume(porcentaje, cambio, silenciar)
        return f"Volumen del sistema: {v['percent']} %" + (" (silenciado)." if v["muted"] else ".")

    reg.add("terminar_conversacion", "Termina la conversación cuando el usuario se despide o dice que ya no necesita "
            "nada ('listo, gracias', 'eso es todo', 'ya puedes descansar'): Elissa deja de escuchar. Con ocultar=true "
            "además se minimiza ('escóndete', 'minimízate').", "Terminando…", terminar,
            {"ocultar": {"type": "boolean"}})
    reg.add("volumen", "Consulta o cambia el volumen general del sistema: porcentaje exacto (0-100), un cambio relativo "
            "(p. ej. -20 para 'baja el volumen', -10 para 'un poquito') o silenciar.", "Ajustando el volumen…",
            volumen, {"porcentaje": {"type": "integer"}, "cambio": {"type": "integer"},
                      "silenciar": {"type": "boolean"}})
