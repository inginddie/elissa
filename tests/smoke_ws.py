"""Manual smoke test: one typed turn against a running engine, printing every event.

    $env:ELISSA_PORT=8750; $env:ELISSA_TOKEN="dev"; uv run python -m elissa      # in one terminal
    uv run python tests/smoke_ws.py "hola"                                         # in another
    uv run python tests/smoke_ws.py --approve "crea notas.txt en Descargas"       # answers approval cards

Approval cards are denied unless --approve is given.
"""
import asyncio
import json
import os
import sys

import httpx
import websockets

PORT = int(os.getenv("ELISSA_PORT", "8750"))
TOKEN = os.getenv("ELISSA_TOKEN", "dev")


async def main(text: str, approve: bool) -> None:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"http://127.0.0.1:{PORT}/?t={TOKEN}")
        cookie = "; ".join(f"{k}={v}" for k, v in r.cookies.items())
    async with websockets.connect(f"ws://127.0.0.1:{PORT}/ws", additional_headers={"Cookie": cookie},
                                  open_timeout=10, ping_timeout=300) as ws:
        await ws.send(json.dumps({"type": "text", "text": text}))
        async for raw in ws:
            msg = json.loads(raw)
            if msg["type"] == "approval":
                print("APPROVAL CARD:", json.dumps({k: v for k, v in msg.items() if k != "id"}, ensure_ascii=False))
                await ws.send(json.dumps({"type": "approval_reply", "id": msg["id"], "approved": approve}))
                print("->", "approved" if approve else "denied")
            elif msg["type"] != "delta":
                print(msg if msg["type"] != "settings" else "settings")
            if msg["type"] in ("done", "error"):
                break


args = [a for a in sys.argv[1:] if a != "--approve"]
asyncio.run(main(args[0] if args else "Responde en una frase: ¿quién eres?", "--approve" in sys.argv))
