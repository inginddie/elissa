"""Approval gate, planner (timers, reminders, tasks) and safe open: no network, no UI, nothing really opened."""
import asyncio
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

os.environ["ELISSA_HOME"] = tempfile.mkdtemp()  # must be set before importing elissa

import pytest

from elissa.llm import ToolCall
from elissa.tools import DENIED, ToolRegistry
from elissa.tools.actions import Actions
from elissa.tools.files import FileTools
from elissa.tools.planner import Planner, parse_when


def make_registry(calls):
    reg = ToolRegistry()

    def act(x: str):
        calls.append(x)
        return f"hecho {x}"

    def preview(x: str):
        if x == "malo":
            raise ValueError("argumento inválido")
        return {"title": "Hacer algo", "kind": "text", "text": x}

    reg.add("accion", "Hace algo", "Haciendo…", act, {"x": {"type": "string"}}, ["x"], preview=preview)
    return reg


def run(reg, x):
    return asyncio.run(reg.run(ToolCall("1", "accion", {"x": x})))


def test_action_runs_only_after_approval():
    calls, seen = [], []
    reg = make_registry(calls)

    async def deny(tool, card):
        seen.append((tool, card["text"]))
        return False

    reg.approver = deny
    assert run(reg, "a").content == DENIED and calls == []
    assert seen == [("accion", "a")]

    async def approve(tool, card):
        return True

    reg.approver = approve
    assert run(reg, "b").content == "hecho b" and calls == ["b"]


def test_no_approver_means_denied_and_bad_preview_fails_before_asking():
    calls = []
    reg = make_registry(calls)
    assert run(reg, "a").content == DENIED and calls == []

    async def must_not_be_called(tool, card):
        raise AssertionError("asked the user about an invalid action")

    reg.approver = must_not_be_called
    result = run(reg, "malo")
    assert result.is_error and "inválido" in result.content


def test_reminders_timers_and_due(tmp_path):
    p = Planner(tmp_path)
    assert "Temporizador" in p.timer(0.01, "té")
    soon = (datetime.now() + timedelta(days=1)).replace(second=0, microsecond=0)
    assert "Recordatorio" in p.remind("llamar a mamá", at=soon.isoformat())
    with pytest.raises(ValueError):
        p.remind("tarde", at=(datetime.now() - timedelta(hours=1)).isoformat())
    assert "llamar a mamá" in p.list_reminders()
    # make the timer due
    items = p._load()
    for i in items:
        if i["kind"] == "timer":
            i["when"] = (datetime.now() - timedelta(seconds=1)).isoformat(timespec="seconds")
    p._save(items)
    due = p.pop_due()
    assert [d["text"] for d in due] == ["té"]
    assert p.pop_due() == []  # fired once
    rid = p._load()[0]["id"]
    p.cancel_reminder(rid)
    assert "No hay" in p.list_reminders()


def test_parse_when_accepts_iso_and_clock_time():
    assert parse_when("2030-01-02T09:30") == datetime(2030, 1, 2, 9, 30)
    assert parse_when("2030-01-02 09:30") == datetime(2030, 1, 2, 9, 30)
    t = parse_when("15:30")
    assert (t.hour, t.minute) == (15, 30) and t > datetime.now()
    with pytest.raises(ValueError):
        parse_when("cuando puedas")


def test_tasks(tmp_path):
    p = Planner(tmp_path)
    p.add_task("Comprar pan")
    p.add_task("Revisar PR", due="viernes")
    assert "1. Comprar pan" in p.list_tasks()
    p.complete_task("revisar")
    assert "Revisar PR" not in p.list_tasks()
    assert "(hecha) Revisar PR (para viernes)" in p.list_tasks(include_done=True)
    assert "- [x] Revisar PR" in (tmp_path / "tareas.md").read_text("utf-8")


def test_open_refuses_executables_and_outside_folders(tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr("elissa.system.open_path", lambda p: opened.append(p))
    (tmp_path / "notas.txt").write_text("hola")
    (tmp_path / "setup.exe").write_bytes(b"MZ")
    actions = Actions(FileTools(lambda: [str(tmp_path)]))
    actions.open_path(str(tmp_path / "notas.txt"))
    with pytest.raises(PermissionError):
        actions.open_path(str(tmp_path / "setup.exe"))
    with pytest.raises(PermissionError):
        actions.open_path(str(Path(tmp_path).parent))
    assert opened == [str(tmp_path / "notas.txt")]
    with pytest.raises(ValueError):
        actions.open_web("file:///C:/Windows/System32/calc.exe")


def test_file_edits_show_a_diff_and_refuse_stale_previews(tmp_path):
    from elissa.tools.file_edit import FileEditor
    ed = FileEditor(FileTools(lambda: [str(tmp_path)]))
    f = tmp_path / "notas.md"
    card = ed.write_preview(str(f), "hola\nmundo\n")
    assert card["kind"] == "diff" and "+hola" in card["diff"]
    ed.write(str(f), "hola\nmundo\n")
    card = ed.edit_preview(str(f), "mundo", "Bogotá")
    assert "-mundo" in card["diff"] and "+Bogotá" in card["diff"]
    f.write_text("alguien lo cambió\nmundo\n", "utf-8")  # changed between preview and approval
    with pytest.raises(RuntimeError):
        ed.edit(str(f), "mundo", "Bogotá")
    with pytest.raises(LookupError):
        ed.edit_preview(str(f), "no existe", "x")
    with pytest.raises(PermissionError):
        ed.write_preview(str(tmp_path / "x.exe"), "MZ")
    with pytest.raises(PermissionError):
        ed.write_preview(str(tmp_path.parent / "fuera.txt"), "x")
    ed.move_preview(str(f), str(tmp_path / "renombrado.md"))
    ed.move(str(f), str(tmp_path / "renombrado.md"))
    assert (tmp_path / "renombrado.md").exists() and not f.exists()
    (tmp_path / "otro.md").write_text("y")
    with pytest.raises(FileExistsError):
        ed.move_preview(str(tmp_path / "otro.md"), str(tmp_path / "renombrado.md"))


def test_mail_send_preview_and_message(tmp_path, monkeypatch):
    from elissa.tools import mail_send

    sent = []

    class FakeSMTP:
        def __init__(self, host, port, context=None, timeout=None):
            self.host = host

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def login(self, user, password):
            assert user == "yo@gmail.com" and password == "app-pass"

        def send_message(self, msg):
            sent.append((self.host, msg))

    monkeypatch.setattr(mail_send.smtplib, "SMTP_SSL", FakeSMTP)
    (tmp_path / "informe.pdf").write_bytes(b"%PDF-1.4")
    settings = {"mail_user": "yo@gmail.com", "mail_server": "imap.gmail.com"}
    sender = mail_send.MailSender(lambda: settings, lambda: "app-pass", FileTools(lambda: [str(tmp_path)]))

    card = sender.preview("ana@empresa.com", "Informe", "Hola Ana", attachments=[str(tmp_path / "informe.pdf")])
    assert card["kind"] == "email" and card["to"] == "ana@empresa.com" and card["attachments"] == "informe.pdf"
    with pytest.raises(ValueError):
        sender.preview("ana", "x", "y")
    with pytest.raises(PermissionError):
        sender.preview("ana@empresa.com", "x", "y", attachments=[str(tmp_path.parent / "secreto.txt")])

    sender.send("ana@empresa.com", "Informe", "Hola Ana", cc="jefe@empresa.com",
                attachments=[str(tmp_path / "informe.pdf")])
    host, msg = sent[0]
    assert host == "smtp.gmail.com"
    assert msg["To"] == "ana@empresa.com" and msg["Cc"] == "jefe@empresa.com" and msg["Subject"] == "Informe"
    assert [p.get_filename() for p in msg.iter_attachments()] == ["informe.pdf"]


def test_keys_are_parsed_and_risky_ones_warned():
    from elissa.tools.desktop import RISKY_KEYS, parse_keys
    assert parse_keys("Ctrl + S") == ["ctrl", "s"]
    assert parse_keys("alt+f4") in [list(k) for k in RISKY_KEYS]
    with pytest.raises(ValueError):
        parse_keys("ctrl+tecla_rara")


def test_dropped_files_are_readable_but_sensitive_ones_are_not(tmp_path):
    outside = tmp_path / "fuera"
    outside.mkdir()
    (outside / "contrato.pdf").write_bytes(b"%PDF")
    (outside / ".env").write_text("SECRET=1")
    handed = set()
    ft = FileTools(lambda: [str(tmp_path / "permitida")], lambda: handed)
    with pytest.raises(PermissionError):
        ft.resolve(str(outside / "contrato.pdf"))
    handed.add(str((outside / "contrato.pdf").resolve()).lower())
    handed.add(str((outside / ".env").resolve()).lower())
    assert ft.resolve(str(outside / "contrato.pdf")).name == "contrato.pdf"
    with pytest.raises(PermissionError):
        ft.resolve(str(outside / ".env"))
