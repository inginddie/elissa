"""Download history of Elissa's releases (F10.1): collect GitHub's counters every day, and summarize them.

GitHub only keeps the current total per release file, so a daily snapshot is what gives a history:

    python scripts/stats.py collect data/downloads.csv     # CI, daily: today's counters (replaces today's rows)
    python scripts/stats.py summary data/downloads.csv     # what the numbers mean, by system and version

Reading the counters: a file counts every download, the updater's included. Manual installs are the .dmg and .deb
(the updater uses .app.tar.gz and the AppImage); on Windows the updater downloads the same setup .exe, so installs
and updates can't be told apart there. latest.json is fetched by every installed copy when it checks for updates: its
daily growth approximates how many copies are in use (checks, not people). Standard library only.
"""
import csv
import datetime as dt
import json
import os
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

REPO = os.environ.get("GITHUB_REPOSITORY", "inginddie/elissa")
FIELDS = ["date", "version", "file", "downloads"]


def kind(name: str) -> str:
    """What a release file is: (system, purpose)."""
    if name == "latest.json":
        return "update-check"
    if name.endswith("setup.exe"):
        return "windows-install-or-update"
    if name.endswith(".dmg"):
        return "macos-install"
    if name.endswith(".app.tar.gz"):
        return "macos-update"
    if name.endswith(".deb"):
        return "linux-install-deb"
    if name.endswith(".AppImage"):
        return "linux-appimage-install-or-update"
    return "other"


def fetch(repo: str = REPO) -> list[dict]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "elissa-stats"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    releases, page = [], 1
    while True:
        req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases?per_page=100&page={page}",
                                     headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            batch = json.load(r)
        releases += batch
        if len(batch) < 100:
            return releases
        page += 1


def rows_from(releases: list[dict], date: str) -> list[dict]:
    return [{"date": date, "version": rel["tag_name"], "file": a["name"], "downloads": a["download_count"]}
            for rel in releases if not rel.get("draft")
            for a in rel.get("assets", []) if not a["name"].endswith(".sig")]


def collect(path: Path, releases: list[dict] | None = None, today: str | None = None) -> int:
    today = today or dt.date.today().isoformat()
    new = rows_from(releases if releases is not None else fetch(), today)
    old = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as f:
            old = [r for r in csv.DictReader(f) if r["date"] != today]  # a rerun the same day replaces that day
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(old + new)
    return len(new)


def summary(path: Path) -> str:
    with path.open(newline="", encoding="utf-8") as f:
        rows = [{**r, "downloads": int(r["downloads"])} for r in csv.DictReader(f)]
    if not rows:
        return "Sin datos todavía."
    days = sorted({r["date"] for r in rows})
    by_day: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))  # day -> kind -> total so far
    for r in rows:
        by_day[r["date"]][kind(r["file"])] += r["downloads"]
    last = by_day[days[-1]]
    lines = [f"Descargas acumuladas al {days[-1]} ({len(days)} días con datos):"]
    lines += [f"  {k:34s} {v}" for k, v in sorted(last.items())]

    def growth(k: str, span: int) -> int | None:
        if len(days) < 2:
            return None
        start = days[max(0, len(days) - 1 - span)]
        return last.get(k, 0) - by_day[start].get(k, 0)
    lines.append("Crecimiento (últimos 7 / 30 días):")
    for k in sorted(last):
        g7, g30 = growth(k, 7), growth(k, 30)
        lines.append(f"  {k:34s} {'—' if g7 is None else g7:>6} / {'—' if g30 is None else g30}")
    per_version: dict[str, int] = defaultdict(int)
    for r in rows:
        if r["date"] == days[-1] and kind(r["file"]) != "update-check":
            per_version[r["version"]] += r["downloads"]
    lines.append("Por versión (instaladores y actualizaciones):")
    lines += [f"  {v:10s} {n}" for v, n in sorted(per_version.items(), key=lambda x: x[0])]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 3 or sys.argv[1] not in ("collect", "summary"):
        sys.exit(__doc__)
    target = Path(sys.argv[2])
    if sys.argv[1] == "collect":
        print(f"{collect(target)} filas para hoy en {target}")
    else:
        print(summary(target))
