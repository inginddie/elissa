"""Release notes come from CHANGELOG.md (release body and updater notes)."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("release_notes", ROOT / "scripts" / "release_notes.py")
release_notes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_notes)

SAMPLE = """# Cambios

## [1.1.0] - 2026-10-13

### Añadido
- Algo nuevo.

## [1.0.0] - 2026-10-12

- Lo anterior.
"""


def test_section_between_headings():
    assert release_notes.notes_for("v1.1.0", SAMPLE) == "### Añadido\n- Algo nuevo."


def test_last_section_and_no_prefix():
    assert release_notes.notes_for("1.0.0", SAMPLE) == "- Lo anterior."


def test_missing_version_fails():
    with pytest.raises(SystemExit):
        release_notes.notes_for("v2.0.0", SAMPLE)


def test_real_changelog_has_current_version():
    version = (ROOT / "pyproject.toml").read_text(encoding="utf-8").split('version = "')[1].split('"')[0]
    assert release_notes.notes_for(version, (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
