"""Web search (DuckDuckGo via ddgs, no API key) and page reading."""
import io
import re

import httpx
from bs4 import BeautifulSoup

from . import ToolRegistry

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
PAGE_CHARS = 12000


def web_search(query: str, max_results: int = 6) -> str:
    from ddgs import DDGS
    results = DDGS().text(query, region="co-es", max_results=max(1, min(max_results, 10)))
    if not results:
        return "Sin resultados."
    return "\n\n".join(f"{r.get('title')}\n{r.get('href')}\n{r.get('body')}" for r in results)


def read_webpage(url: str) -> str:
    if not re.match(r"https?://", url):
        url = "https://" + url
    r = httpx.get(url, headers={"User-Agent": UA, "Accept-Language": "es-CO,es;q=0.9,en;q=0.5"},
                  follow_redirects=True, timeout=20)
    r.raise_for_status()
    ctype = r.headers.get("content-type", "")
    if "pdf" in ctype:
        from pypdf import PdfReader
        text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(r.content)).pages)
    else:
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "form", "svg"]):
            tag.decompose()
        title = soup.title.get_text(strip=True) if soup.title else ""
        main = soup.find("main") or soup.find("article") or soup.body or soup
        text = title + "\n" + main.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:PAGE_CHARS] + ("\n…(página recortada)" if len(text) > PAGE_CHARS else "")


def register(reg: ToolRegistry) -> None:
    reg.add("buscar_web", "Busca en internet (noticias, precios, datos actuales). Devuelve títulos, enlaces y "
            "fragmentos; usa leer_pagina para el detalle.", "Buscando en la web…", web_search,
            {"query": {"type": "string"}, "max_results": {"type": "integer"}}, ["query"])
    reg.add("leer_pagina", "Descarga una página web (o PDF en línea) y devuelve su texto.", "Leyendo la página…",
            read_webpage, {"url": {"type": "string"}}, ["url"])
