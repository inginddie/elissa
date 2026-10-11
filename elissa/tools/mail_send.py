"""Sending e-mail over SMTP with the same app password used for reading. Off by default (Settings → Email), and
every message is shown in full on an approval card before it leaves.
"""
import mimetypes
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path
from typing import Callable

from . import ToolRegistry
from .files import FileTools

ADDRESS = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")
MAX_ATTACH_BYTES = 20 * 1024 * 1024
# (host, port, implicit TLS) by the IMAP server already configured for reading
SMTP_BY_IMAP = {
    "imap.gmail.com": ("smtp.gmail.com", 465, True),
    "outlook.office365.com": ("smtp.office365.com", 587, False),
    "imap.mail.yahoo.com": ("smtp.mail.yahoo.com", 465, True),
    "imap.mail.me.com": ("smtp.mail.me.com", 587, False),
}


def smtp_for(imap_server: str) -> tuple[str, int, bool]:
    if imap_server in SMTP_BY_IMAP:
        return SMTP_BY_IMAP[imap_server]
    return (re.sub(r"^imap\.", "smtp.", imap_server), 465, True)


def _addresses(value: str | list | None) -> list[str]:
    if not value:
        return []
    items = value if isinstance(value, list) else re.split(r"[,;]\s*", value)
    out = [a.strip() for a in items if a and a.strip()]
    bad = [a for a in out if not ADDRESS.match(a)]
    if bad:
        raise ValueError(f"Dirección inválida: {', '.join(bad)}. Pídele al usuario la dirección exacta.")
    return out


class MailSender:
    def __init__(self, settings: Callable[[], dict], password: Callable[[], str], files: FileTools):
        self.settings = settings
        self.password = password
        self.files = files

    def _attachments(self, attachments: list | None) -> list[Path]:
        paths = [self.files.resolve(a) for a in attachments or []]
        for p in paths:
            if not p.is_file():
                raise FileNotFoundError(f"No existe el adjunto {p}.")
        if sum(p.stat().st_size for p in paths) > MAX_ATTACH_BYTES:
            raise ValueError("Los adjuntos pasan de 20 MB.")
        return paths

    def preview(self, to, subject: str, body: str, cc=None, attachments: list | None = None) -> dict:
        to_list, cc_list = _addresses(to), _addresses(cc)
        if not to_list:
            raise ValueError("Falta el destinatario.")
        files = self._attachments(attachments)
        return {"title": "Enviar un correo", "kind": "email", "subtitle": f"Desde {self.settings().get('mail_user')}",
                "to": ", ".join(to_list), "cc": ", ".join(cc_list), "subject": subject.strip() or "(sin asunto)",
                "body": body, "attachments": ", ".join(p.name for p in files)}

    def send(self, to, subject: str, body: str, cc=None, attachments: list | None = None) -> str:
        s = self.settings()
        sender = s.get("mail_user", "")
        to_list, cc_list = _addresses(to), _addresses(cc)
        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = ", ".join(to_list)
        if cc_list:
            msg["Cc"] = ", ".join(cc_list)
        msg["Subject"] = subject.strip()
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain=sender.split("@")[-1] or None)
        msg.set_content(body)
        for p in self._attachments(attachments):
            ctype, _ = mimetypes.guess_type(p.name)
            main, sub = (ctype or "application/octet-stream").split("/", 1)
            msg.add_attachment(p.read_bytes(), maintype=main, subtype=sub, filename=p.name)
        host, port, implicit = smtp_for(s.get("mail_server", ""))
        context = ssl.create_default_context()
        if implicit:
            with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as smtp:
                smtp.login(sender, self.password())
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                smtp.starttls(context=context)
                smtp.login(sender, self.password())
                smtp.send_message(msg)
        return f"Correo enviado a {', '.join(to_list + cc_list)}."


def register(reg: ToolRegistry, sender: MailSender) -> None:
    reg.add("enviar_correo", "Envía un correo desde la cuenta del usuario. Escribe el correo completo y listo para "
            "enviar; el usuario lo verá tal cual y debe aprobarlo. Usa direcciones exactas (de un correo leído o "
            "dichas por el usuario), nunca inventadas.", "Preparando el correo…", sender.send,
            {"to": {"type": "string", "description": "Destinatarios separados por coma"},
             "subject": {"type": "string"}, "body": {"type": "string", "description": "Texto plano"},
             "cc": {"type": "string"},
             "attachments": {"type": "array", "items": {"type": "string"},
                             "description": "Rutas de archivos a adjuntar (dentro de las carpetas permitidas)"}},
            ["to", "subject", "body"], preview=sender.preview)
