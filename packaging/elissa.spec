# PyInstaller spec: builds dist/elissa-engine/elissa-engine.exe, the Python engine the desktop shell starts
# (one-folder, no console window).
# Run from the repo root:  uv run pyinstaller packaging/elissa.spec --noconfirm
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).parent

datas = [(str(ROOT / "elissa" / "static"), "elissa/static")]
binaries = []
hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("elissa")
    + ["keyring.backends.Windows"]
)
for pkg in ("ddgs", "primp", "edge_tts"):
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
    excludes=["tkinter", "matplotlib", "numpy", "pytest", "setuptools"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="elissa-engine",
    icon=str(ROOT / "packaging" / "elissa.ico"),
    console=False,
    version=str(ROOT / "packaging" / "version_info.txt"),
)
coll = COLLECT(exe, a.binaries, a.datas, name="elissa-engine")
