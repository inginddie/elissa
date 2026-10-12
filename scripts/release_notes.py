"""Print the CHANGELOG section of one version, for the release body and the updater notes (latest.json).

Usage: uv run python scripts/release_notes.py v1.1.0 [--release]
--release adds the footer for the GitHub release page (links required by the code signing policy).
"""

import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
REPO = "https://github.com/inginddie/elissa/blob/main"
FOOTER = f"\n\n---\n[Code signing policy]({REPO}/docs/CODE_SIGNING.md) · [Privacy policy]({REPO}/PRIVACY.md)"


def notes_for(version: str, text: str) -> str:
    version = version.removeprefix("v")
    heading = re.compile(rf"^## \[{re.escape(version)}\][^\n]*\n", re.M)
    match = heading.search(text)
    if not match:
        raise SystemExit(f"CHANGELOG.md has no section for {version}")
    rest = text[match.end():]
    following = re.search(r"^## \[", rest, re.M)
    return rest[: following.start() if following else len(rest)].strip()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    notes = notes_for(sys.argv[1], CHANGELOG.read_text(encoding="utf-8"))
    print(notes + (FOOTER if "--release" in sys.argv[2:] else ""))
