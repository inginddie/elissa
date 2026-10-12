# PyInstaller spec: builds dist/elissa-engine/elissa-engine(.exe), the Python engine the desktop shell starts
# (one-folder, no console window). It has to run on each system it targets: PyInstaller doesn't cross-compile.
# Run from the repo root:  uv run pyinstaller packaging/elissa.spec --noconfirm
import importlib.util
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).parent
WINDOWS = sys.platform == "win32"
KEYRING_BACKEND = {"win32": "keyring.backends.Windows", "darwin": "keyring.backends.macOS"}.get(
    sys.platform, "keyring.backends.SecretService")

datas = [(str(ROOT / "elissa" / "static"), "elissa/static")]
binaries = []
hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("elissa")
    + [KEYRING_BACKEND]
)
if WINDOWS:
    # uiautomation drives Windows UI Automation through comtypes; its generated COM wrappers (comtypes.gen) are
    # created when uiautomation is first imported, so the build imports it before collecting.
    import uiautomation  # noqa: E402,F401

# Only MCP's client side: mcp.cli needs typer (and exits without it) and Elissa never runs an MCP server.
hiddenimports += collect_submodules("mcp", filter=lambda name: not name.startswith(("mcp.cli", "mcp.server")))

PACKAGES = ["ddgs", "primp", "edge_tts", "vosk", "sounddevice", "_sounddevice_data", "httpx2"]
PACKAGES += (["uiautomation", "comtypes", "winrt", "pycaw"] if WINDOWS
             else ["secretstorage", "jeepney", "pywhispercpp"])
if sys.platform == "darwin":  # computer use: Accessibility API and Quartz events through pyobjc
    PACKAGES += ["objc", "Foundation", "AppKit", "ApplicationServices", "HIServices", "Quartz", "CoreFoundation"]
for pkg in PACKAGES:
    if importlib.util.find_spec(pkg) is None:  # e.g. _sounddevice_data on Linux (it uses the system's PortAudio)
        continue
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [str(ROOT / "elissa" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    # numpy is only needed by pywhispercpp (macOS, Linux)
    excludes=["tkinter", "matplotlib", "pytest", "setuptools"] + (["numpy"] if WINDOWS else []),
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="elissa-engine",
    icon=str(ROOT / "packaging" / "elissa.ico") if WINDOWS else None,
    console=False,
    version=str(ROOT / "packaging" / "version_info.txt") if WINDOWS else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="elissa-engine")
