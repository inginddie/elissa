"""Read-only e-mail over IMAP (Gmail, Outlook, Yahoo... with an app password).

The mailbox is opened with EXAMINE (read-only) and bodies are fetched with BODY.PEEK, so nothing is
ever marked as read, moved or deleted. Attachments are saved to Downloads/Elissa adjuntos.
"""
import email
import imaplib
import re
import unicodedata
from datetime import date, timedelta
from email import policy
from email.message import EmailMessage
from pathlib import Path
from typing import Callable

from bs4 import BeautifulSoup

from ..config import DOWNLOADS
from . import ToolRegistry

ATTACH_DIR = DOWNLOADS / "Elissa adjuntos"
BODY_CHARS = 10000
KNOWN_SERVERS = {
    "gmail.com": "imap.gmail.com", "googlemail.com": "imap.gmail.com",
    "outlook.com": "outlook.office365.com", "hotmail.com": "outlook.office365.com",
    "live.com": "outlook.office365.com", "yahoo.com": "imap.mail.yahoo.com", "icloud.com": "imap.mail.me.com",
}


def guess_server(address: str) -> str:
    domain = address.split("@")[-1].lower().strip()
    return KNOWN_SERVERS.get(domain, f"imap.{domain}")


def _ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().replace('"', "")


def _body_text(msg: EmailMessage) -> str:
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    content = part.get_content()
    if part.get_content_subtype() == "html":
        content = BeautifulSoup(content, "html.parser").get_text("\n", strip=True)
    return re.sub(r"\n{3,}", "\n\n", content).strip()


def _attachments(msg: EmailMessage) -> list[EmailMessage]:
    return [p for p in msg.walk() if not p.is_multipart() and p.get_filename()]


def _safe_name(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .") or "adjunto"


class MailTools:
    def __init__(self, settings: Callable[[], dict], password: Callable[[], str]):
        self.settings = settings
        self.password = password

    def _connect(self) -> imaplib.IMAP4_SSL:
        s = self.settings()
        if not (s.get("mail_enabled") and s.get("mail_user")):
            raise RuntimeError("El correo no está configurado. Actívalo en Ajustes > Correo.")
        server = s.get("mail_server") or guess_server(s["mail_user"])
        conn = imaplib.IMAP4_SSL(server, 993, timeout=30)
        try:
            conn.login(s["mail_user"], self.password())
        except imaplib.IMAP4.error as e:
            raise RuntimeError("El servidor rechazó el usuario o la contraseña de aplicación.") from e
        conn.select("INBOX", readonly=True)
        return conn

    def _is_gmail(self) -> bool:
        s = self.settings()
        return "gmail" in (s.get("mail_server") or guess_server(s.get("mail_user", "")))

    def _fetch(self, conn, uid: str) -> EmailMessage:
        typ, data = conn.uid("FETCH", uid, "(BODY.PEEK[])")
        if typ != "OK" or not data or not isinstance(data[0], tuple):
            raise LookupError(f"No encontré el correo {uid}.")
        return email.message_from_bytes(data[0][1], policy=policy.default)

    # ----- tools -----

    def search(self, query: str = "", sender: str = "", subject: str = "", days: int = 14,
               unread_only: bool = False, limit: int = 10) -> str:
        conn = self._connect()
        try:
            if self._is_gmail():
                parts = [query] + ([f"from:{sender}"] if sender else []) + ([f"subject:({subject})"] if subject else [])
                parts += [f"newer_than:{max(1, days)}d"] + (["is:unread"] if unread_only else [])
                raw = " ".join(p for p in parts if p).strip()
                conn.literal = raw.encode("utf-8")
                typ, data = conn.uid("SEARCH", "CHARSET", "UTF-8", "X-GM-RAW")
            else:
                crit = [f'SINCE {(date.today() - timedelta(days=max(1, days))).strftime("%d-%b-%Y")}']
                if sender:
                    crit.append(f'FROM "{_ascii(sender)}"')
                if subject:
                    crit.append(f'SUBJECT "{_ascii(subject)}"')
                if query:
                    crit.append(f'TEXT "{_ascii(query)}"')
                if unread_only:
                    crit.append("UNSEEN")
                typ, data = conn.uid("SEARCH", None, *crit)
            uids = data[0].split() if typ == "OK" and data and data[0] else []
            if not uids:
                return "No encontré correos con esos criterios."
            lines = []
            for uid in reversed(uids[-max(1, min(limit, 30)):]):
                typ, d = conn.uid("FETCH", uid, "(FLAGS BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE CONTENT-TYPE)])")
                if typ != "OK" or not d or not isinstance(d[0], tuple):
                    continue
                h = email.message_from_bytes(d[0][1], policy=policy.default)
                unread = "" if b"\\Seen" in d[0][0] else " [no leído]"
                clip = " [adjuntos]" if "multipart/mixed" in str(h.get("content-type", "")).lower() else ""
                lines.append(f"id={uid.decode()} | {h.get('date', '')} | De: {h.get('from', '')} | "
                             f"Asunto: {h.get('subject', '')}{unread}{clip}")
            return "\n".join(lines)
        finally:
            conn.logout()

    def read(self, email_id: str) -> str:
        conn = self._connect()
        try:
            msg = self._fetch(conn, str(email_id))
        finally:
            conn.logout()
        files = [f"{p.get_filename()} ({p.get_content_type()})" for p in _attachments(msg)]
        body = _body_text(msg)
        if len(body) > BODY_CHARS:
            body = body[:BODY_CHARS] + "\n…(correo recortado)"
        return (f"De: {msg.get('from', '')}\nPara: {msg.get('to', '')}\nFecha: {msg.get('date', '')}\n"
                f"Asunto: {msg.get('subject', '')}\nAdjuntos: {', '.join(files) or 'ninguno'}\n\n{body}")

    def save_attachments(self, email_id: str) -> str:
        conn = self._connect()
        try:
            msg = self._fetch(conn, str(email_id))
        finally:
            conn.logout()
        ATTACH_DIR.mkdir(parents=True, exist_ok=True)
        saved = []
        for part in _attachments(msg):
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            base = Path(_safe_name(part.get_filename()))
            path, n = ATTACH_DIR / base, 1
            while path.exists() and path.read_bytes() != payload:
                path, n = ATTACH_DIR / f"{base.stem} ({n}){base.suffix}", n + 1
            path.write_bytes(payload)
            saved.append(str(path))
        if not saved:
            return "Ese correo no tiene adjuntos."
        return "Adjuntos guardados (léelos con leer_archivo):\n" + "\n".join(saved)

    def test(self) -> str:
        conn = self._connect()
        try:
            typ, data = conn.status("INBOX", "(MESSAGES UNSEEN)")
            return data[0].decode() if typ == "OK" else "Conectado."
        finally:
            conn.logout()


def register(reg: ToolRegistry, mail: MailTools) -> None:
    reg.add("buscar_correos", "Busca correos en la bandeja de entrada (solo lectura). Filtra por texto, remitente, "
            "asunto, días hacia atrás y no leídos. Devuelve ids para leer_correo.", "Revisando tu correo…",
            mail.search,
            {"query": {"type": "string", "description": "Palabras a buscar (opcional)"},
             "sender": {"type": "string", "description": "Remitente: nombre o dirección (opcional)"},
             "subject": {"type": "string", "description": "Palabras del asunto (opcional)"},
             "days": {"type": "integer", "description": "Cuántos días hacia atrás (por defecto 14)"},
             "unread_only": {"type": "boolean"}, "limit": {"type": "integer"}})
    reg.add("leer_correo", "Lee un correo completo por su id (remitente, asunto, cuerpo y lista de adjuntos).",
            "Abriendo el correo…", mail.read, {"email_id": {"type": "string"}}, ["email_id"])
    reg.add("guardar_adjuntos", "Descarga los adjuntos de un correo a la carpeta Descargas/Elissa adjuntos y "
            "devuelve sus rutas para leerlos con leer_archivo.", "Descargando adjuntos…", mail.save_attachments,
            {"email_id": {"type": "string"}}, ["email_id"])
