"""Converte a resposta da Gmail API (`format=full`) em NormalizedMessage."""
import base64
import re
from dataclasses import dataclass
from email.header import decode_header, make_header
from email.utils import parseaddr
from html.parser import HTMLParser
from typing import Optional


@dataclass
class NormalizedMessage:
    gmail_id: str                 # id estável da mensagem no Gmail
    internal_date_ms: int         # `internalDate` do Gmail (epoch ms, UTC)
    sender_name: str = ""
    sender_email: str = ""
    subject: str = ""
    snippet: str = ""             # prévia curta; se vazia, o banco deriva do corpo
    body: str = ""                # texto simples (sem anexos nesta versão)
    thread_id: Optional[str] = None
    is_read: bool = True          # False quando o Gmail marca a mensagem com UNREAD
    category: str = "Outros"      # definida pelo classificador


class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "head", "title"}
    _BREAK = {"br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4", "table"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip += 1
        elif tag in self._BREAK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip:
            self._skip -= 1
        elif tag in self._BREAK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    text = "".join(parser.parts).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def _decode_header(value: str) -> str:
    try:
        return str(make_header(decode_header(value or ""))).strip()
    except Exception:
        return (value or "").strip()


def _b64(data: str) -> str:
    raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    return raw.decode("utf-8", errors="replace")


def _find_body(part: dict, mime: str) -> str:
    """Primeira parte `mime` (percorrendo multipart) com conteúdo; ignora anexos."""
    if part.get("filename"):
        return ""
    data = (part.get("body") or {}).get("data")
    if part.get("mimeType") == mime and data:
        return _b64(data)
    for child in part.get("parts") or []:
        found = _find_body(child, mime)
        if found:
            return found
    return ""


def extract_body(payload: dict) -> str:
    text = _find_body(payload, "text/plain")
    if text.strip():
        return text.strip()
    html = _find_body(payload, "text/html")
    return html_to_text(html) if html else ""


def normalize_message(raw: dict) -> NormalizedMessage:
    """Resposta de messages.get(format=full) -> NormalizedMessage (sem categoria)."""
    payload = raw.get("payload") or {}
    headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
    name, address = parseaddr(_decode_header(headers.get("from", "")))
    return NormalizedMessage(
        gmail_id=raw["id"],
        thread_id=raw.get("threadId"),
        internal_date_ms=int(raw.get("internalDate", 0)),
        sender_name=name,
        sender_email=address,
        subject=_decode_header(headers.get("subject", "")),
        snippet=raw.get("snippet", ""),
        body=extract_body(payload),
        is_read="UNREAD" not in (raw.get("labelIds") or []),
    )
