# Desarrolladores

Elissa es de código abierto con licencia MIT: [github.com/inginddie/elissa](https://github.com/inginddie/elissa).
Los issues y pull requests son bienvenidos; lee primero
[CONTRIBUTING.md](https://github.com/inginddie/elissa/blob/main/CONTRIBUTING.md) (en inglés).

## Correr desde el código

Necesitas [uv](https://docs.astral.sh/uv/), Node 22 y [Rust](https://rustup.rs/).

```bash
uv sync
cd desktop && npm install && npx tauri dev   # la app completa; el shell arranca el motor de Python con uv
uv run python -m elissa --browser            # solo el motor, con la interfaz en tu navegador
uv run pytest -q                             # pruebas (sin red ni API keys)
```

Construir el instalador de Windows en `dist\`:

```powershell
powershell -File packaging\build.ps1   # motor (PyInstaller) + instalador (Tauri/NSIS)
```

`tests/smoke_ws.py` corre un turno real contra un motor en marcha y puede responder tarjetas de aprobación
(`--approve`): sirve para probar un cambio de punta a punta sin hacer clic.

## Arquitectura

![Arquitectura: el shell de Tauri aloja la interfaz y habla por HTTP y WebSocket en 127.0.0.1, con un token por sesión, con el motor de Python, que tiene el ciclo del agente, los proveedores, las herramientas y la voz](media/architecture.jpg)

- **El shell** (`desktop/`, Tauri 2, Rust): la ventana transparente, la bandeja, el atajo global, el inicio con el
  sistema, las actualizaciones firmadas y el ciclo de vida del motor.
- **El motor** (`elissa/`, Python): un servidor local en `127.0.0.1` que solo la ventana de Elissa puede usar, con un
  token por sesión y revisión de origen. Corre el ciclo del agente, los proveedores, las herramientas y la voz.
- **La interfaz** (`elissa/static/`): HTML y JavaScript simples, servidos por el motor. Elissa se dibuja en un canvas
  en `character.js`.

| Ruta | Qué hay ahí |
|---|---|
| `desktop/` | Shell nativo: modos de ventana, bandeja, actualizador, ciclo de vida del motor |
| `elissa/server.py` | API local y WebSocket, voz, configuración guiada, aprobaciones |
| `elissa/agent.py` | Ciclo del agente, neutral al proveedor, y el prompt del sistema |
| `elissa/llm/` | Adaptadores de proveedores; uno compatible con OpenAI es una entrada en `PROVIDERS` |
| `elissa/tools/` | Herramientas; todo lo que cambia algo tiene un `preview` y pasa por aprobación |
| `elissa/system/` | Lo que cambia entre Windows, macOS y Linux, y las capacidades de cada sistema |
| `elissa/mcp_client.py` | Integraciones MCP |
| `elissa/static/` | Interfaz: `character.js`, `sounds.js`, `i18n.js`, `app.js` |
| `docs/` | Esta wiki ([MkDocs Material](https://squidfunk.github.io/mkdocs-material/)) |

## Reglas básicas

- **Primero la seguridad.** Una herramienta que envía, escribe, mueve, hace clic, escribe texto o ejecuta algo debe
  tener un `preview` que muestre exactamente lo que va a pasar. Nada puede borrar datos del usuario. Lee
  [Seguridad](security.md) antes de tocar herramientas, aprobaciones o la API del motor.
- **Secretos solo en el llavero** (`elissa.config.set_secret`). Nunca en ajustes, registros ni el repositorio.
- **Sin telemetría.** Solo llamadas de red a servicios que el usuario configuró.
- **Pruebas** para cada comportamiento que cambies; todo `tests/` pasa sin red ni claves.
- **Textos de la interfaz** en español; agrega el inglés en `elissa/static/i18n.js`.

## Editar esta wiki

La wiki vive en `docs/`: las páginas en inglés son `pagina.md` y las de español `pagina.es.md`. Para verla:

```bash
uv run --group docs mkdocs serve
```

Las capturas de la ventana de Elissa (`docs/media/screens/`) salen de la app real, en los dos idiomas, con una
carpeta de datos desechable. Después de cambiar la interfaz, regéneralas (necesita Microsoft Edge):

```bash
uv run --with playwright==1.63.0 python scripts/wiki_screenshots.py
```

Cada push a `main` publica la wiki en GitHub Pages. También puedes usar el botón :material-file-edit-outline: arriba de
cada página.

## Versiones

Las versiones siguen [SemVer](https://semver.org): los parches son solo arreglos, las menores agregan funciones, y una
etiqueta publicada nunca se mueve. Los pasos están en
[CONTRIBUTING.md](https://github.com/inginddie/elissa/blob/main/CONTRIBUTING.md#releasing-maintainers) y los cambios
de cada versión en el [changelog](https://github.com/inginddie/elissa/blob/main/CHANGELOG.md).
