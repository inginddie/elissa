"""Download history (scripts/stats.py): daily snapshots, reruns, and what the summary says."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("stats", ROOT / "scripts" / "stats.py")
stats = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stats)


def releases(exe: int, dmg: int, checks: int) -> list[dict]:
    return [{"tag_name": "v1.7.0", "draft": False, "assets": [
        {"name": "Elissa_1.7.0_x64-setup.exe", "download_count": exe},
        {"name": "Elissa_1.7.0_x64-setup.exe.sig", "download_count": exe},
        {"name": "Elissa_1.7.0_aarch64.dmg", "download_count": dmg},
        {"name": "latest.json", "download_count": checks}]},
        {"tag_name": "v1.8.0", "draft": True, "assets": [{"name": "latest.json", "download_count": 5}]}]


def test_collect_snapshots_and_reruns(tmp_path):
    path = tmp_path / "downloads.csv"
    assert stats.collect(path, releases(10, 0, 39), "2026-10-12") == 3  # .sig and drafts are left out
    stats.collect(path, releases(11, 1, 45), "2026-10-12")  # a rerun the same day replaces it
    stats.collect(path, releases(13, 2, 60), "2026-10-13")
    lines = path.read_text("utf-8").splitlines()
    assert lines[0] == "date,version,file,downloads" and len(lines) == 1 + 3 + 3
    report = stats.summary(path)
    assert "update-check                       60" in report
    assert "macos-install                      2" in report
    growth = [line.split() for line in report.split("Crecimiento")[1].splitlines() if "update-check" in line][0]
    assert growth == ["update-check", "15", "/", "15"]  # growth since the first day


def test_kinds():
    assert stats.kind("latest.json") == "update-check"
    assert stats.kind("Elissa_aarch64.app.tar.gz") == "macos-update"
    assert stats.kind("Elissa_1.7.0_amd64.deb") == "linux-install-deb"
