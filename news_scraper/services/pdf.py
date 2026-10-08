"""Generación de PDFs con el contenido editorial de cada noticia."""

from __future__ import annotations

import asyncio
import base64
from contextlib import ExitStack
import html
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from news_scraper.models.noticia import Noticia
from news_scraper.services.extractor import fetch_page, normalize_text


LOGGER = logging.getLogger(__name__)

ARTICLE_SELECTORS = {
    "Semana Económica": ".se-article",
    "Semana Económica - Índice": ".se-article",
    "Diario Financiero": ".grid__col.g-xs-12.g-sm-12.g-md-12.g-lg-9.g-xl-9",
    "Portafolio": ".u-estructura--articulo",
}

REMOVE_SELECTORS = (
    "script",
    "style",
    "noscript",
    "aside",
    ".se-article__overlay",
    ".se-article__advertisement-desktop",
    ".se-paywall",
    ".se-article__related",
    ".se-article__share",
    ".c-leatambien",
    ".c-add",
    ".c-articulo__compartir-modal",
    ".c-articulo__compartir",
    ".c-articulo__autor",
    ".c-articulo__firma",
    ".c-lead__link",
    ".c-cuerpo__media__thumb__zoom",
    ".se-article__author",
    ".se-article__authors",
    ".c-cuerpo__media--audio",
    ".u-estructura__inferior",
    ".u-estructura__lateral",
    ".c-caja--temasrelacionados",
    ".c-caja--pontealdia",
    ".enc-main__share",
)

PORTAFOLIO_PRINT_CSS = """
  .u-estructura--articulo {
    width: 100% !important;
    max-width: none !important;
    margin: 0 !important;
  }
  .u-estructura__cabecera,
  .u-estructura__cuerpo,
  .c-cuerpo {
    width: 100% !important;
    max-width: none !important;
  }
  .c-articulo__titulo {
    color: #111 !important;
    font-family: Georgia, "Times New Roman", serif !important;
    font-size: 22px !important;
    line-height: 1.05 !important;
    margin: 0 0 22px !important;
  }
  .c-lead__titulo {
    color: #666 !important;
    font-family: Arial, sans-serif !important;
    font-size: 14px !important;
    font-weight: 400 !important;
    line-height: 1.35 !important;
    margin: 0 0 12px !important;
  }
  .c-lead__link {
    color: #029581 !important;
    display: block !important;
    font-family: Arial, sans-serif !important;
    font-size: 16px !important;
    line-height: 1.35 !important;
    margin: 0 0 7px !important;
  }
  .c-lead {
    margin: 0 !important;
    padding: 0 !important;
  }
  .c-articulo-apertura__media,
  .c-articulo-apertura__media__thumb {
    margin: 0 !important;
    width: 100% !important;
  }
  .c-articulo-apertura__media__thumb img {
    display: block !important;
    height: auto !important;
    width: 100% !important;
  }
  .c-articulo-apertura__media__txt {
    color: #666 !important;
    font-family: Arial, sans-serif !important;
    font-size: 12px !important;
    margin: 10px 0 14px !important;
  }
  .c-articulo__info {
    margin: 0 0 18px !important;
  }
  .c-articulo__autor__recipiente {
    align-items: center !important;
    display: flex !important;
  }
  .c-articulo__autor__recipiente picture,
  .c-articulo__autor__recipiente picture img {
    border-radius: 50% !important;
    display: block !important;
    height: 60px !important;
    object-fit: cover !important;
    width: 60px !important;
  }
  .c-articulo__autor__txt {
    margin-left: 12px !important;
  }
  .c-articulo__autor__nombre,
  .c-articulo__autor__grupo,
  .c-articulo__autor__fecha {
    font-family: Arial, sans-serif !important;
  }
  .c-articulo__compartir {
    display: block !important;
    margin: 12px 0 26px !important;
    max-width: 40% !important;
  }
  .c-articulo__compartir-media {
    border-bottom: 1px solid #ddd !important;
    border-top: 1px solid #ddd !important;
    display: flex !important;
    justify-content: flex-start !important;
    padding: 12px 0 !important;
  }
  .c-articulo__compartir-media__elemento {
    background: transparent !important;
    border: 0 !important;
    display: flex !important;
    flex-direction: column !important;
    margin-right: 20px !important;
  }
  .c-articulo__compartir-media__elemento--resumen-ia,
  .c-articulo__compartir-modal,
  .c-cuerpo__media--audio {
    display: none !important;
  }
  .c-articulo__compartir-media__icono {
    height: 28px !important;
    margin: 0 auto 5px !important;
    width: 28px !important;
  }
  .c-articulo__compartir-media__texto {
    color: #666 !important;
    font-family: Arial, sans-serif !important;
    font-size: 11px !important;
    margin: 0 !important;
  }
  .c-cuerpo .paragraph {
    font-family: Arial, sans-serif !important;
    font-size: 18px !important;
    line-height: 1.55 !important;
    margin: 0 0 16px !important;
  }
  .c-cuerpo h2 {
    font-family: Arial, sans-serif !important;
    font-size: 24px !important;
    line-height: 1.2 !important;
  }
"""

WINDOWS_BROWSER_PATHS = (
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
)


class PdfExporter:
    """Renderiza el contenido editorial de una noticia en un PDF."""

    def __init__(
        self,
        output_root: str | Path,
        browser_user_data_dir: str | Path | None = None,
    ):
        self.output_root = Path(output_root)
        self.browser_user_data_dir = (
            Path(browser_user_data_dir).expanduser()
            if browser_user_data_dir
            else None
        )
        self.last_errors = 0

    def export_many(self, news_items: list[Noticia], execution_date: date) -> int:
        """Exporta todas las noticias con URL y devuelve cuántos PDFs creó."""

        output_dir = self.output_root / execution_date.strftime("%d-%m-%Y")
        output_dir.mkdir(parents=True, exist_ok=True)
        self.last_errors = 0
        saved = 0
        for news in news_items:
            if self.export_one(news, output_dir):
                saved += 1
        return saved

    def export_one(self, news: Noticia, output_dir: Path) -> bool:
        """Exporta una noticia y aísla los errores de las demás."""

        if not news.url:
            LOGGER.warning("Noticia sin URL; no se puede generar PDF: %s", news.titulo)
            return False

        try:
            browser = self._find_browser()
            output_path = self._unique_path(output_dir, news.titulo)
            self._render_pdf(
                browser,
                news.titulo,
                None,
                output_path,
                news.url,
                (),
                news.fuente,
            )
            return output_path.exists() and output_path.stat().st_size > 0
        except Exception:
            self.last_errors += 1
            LOGGER.exception("No se pudo generar PDF para: %s", news.titulo)
            return False

    def _extract_article(self, soup: BeautifulSoup, source_name: str):
        selector = ARTICLE_SELECTORS.get(source_name)
        if selector is None:
            return None
        article = soup.select_one(selector)
        if article is None:
            return None
        clean = BeautifulSoup(str(article), "html.parser")
        for node in clean.select(",".join(REMOVE_SELECTORS)):
            node.decompose()
        return clean.select_one(selector) or clean

    @staticmethod
    def _extract_styles(soup: BeautifulSoup, source_url: str) -> list[str]:
        """Conserva las hojas CSS del sitio para aproximar su impresión nativa."""

        styles: list[str] = []
        for link in soup.select('link[rel="stylesheet"][href]'):
            styles.append(urljoin(source_url, link["href"]))
        return styles

    def _render_pdf(
        self,
        browser: str,
        title: str,
        article,
        output_path: Path,
        source_url: str,
        styles: list[str] | tuple[str, ...] = (),
        source_name: str = "",
    ) -> None:
        with ExitStack() as stack:
            if self.browser_user_data_dir is None:
                # Se conserva un perfil temporal solo para compatibilidad con
                # pruebas unitarias directas de _render_pdf. La ejecución
                # normal exige un perfil persistente configurado desde main.py.
                temp_dir = stack.enter_context(
                    tempfile.TemporaryDirectory(
                        prefix="news-pdf-",
                        ignore_cleanup_errors=True,
                    )
                )
                profile_path = Path(temp_dir) / "chrome-profile"
            else:
                profile_path = self.browser_user_data_dir
                profile_path.mkdir(parents=True, exist_ok=True)

            port = self._free_port()
            command = [
                browser,
                "--headless=new",
                "--disable-gpu",
                "--disable-extensions",
                "--no-first-run",
                "--no-pdf-header-footer",
                f"--remote-debugging-port={port}",
                "--remote-allow-origins=*",
                f"--user-data-dir={profile_path}",
                "about:blank",
            ]
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
            try:
                last_error: Exception | None = None
                for attempt in range(3):
                    try:
                        websocket_url = self._open_devtools_target(port)
                        encoded_pdf = asyncio.run(
                            self._print_article_with_devtools(
                                websocket_url,
                                ARTICLE_SELECTORS.get(source_name, "body"),
                                source_url,
                                source_name,
                            )
                        )
                        break
                    except Exception as error:
                        last_error = error
                        if attempt == 2:
                            raise
                        time.sleep(0.5)
                else:
                    raise last_error or RuntimeError("No se pudo imprimir la noticia")
                output_path.write_bytes(base64.b64decode(encoded_pdf))
            finally:
                process_id = getattr(process, "pid", None)
                if os.name == "nt" and process_id:
                    subprocess.run(
                        ["taskkill", "/PID", str(process_id), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                else:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()

    @staticmethod
    def _free_port() -> int:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    @staticmethod
    def _open_devtools_target(port: int) -> str:
        """Inicia un target CDP y devuelve su WebSocket de control."""

        deadline = time.monotonic() + 20
        version_url = f"http://127.0.0.1:{port}/json/version"
        target_url = f"http://127.0.0.1:{port}/json/new?about:blank"
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(version_url, timeout=2):
                    request = urllib.request.Request(target_url, method="PUT")
                    with urllib.request.urlopen(request, timeout=5) as response:
                        target = json.load(response)
                    return str(target["webSocketDebuggerUrl"])
            except (OSError, KeyError, json.JSONDecodeError):
                time.sleep(0.2)
        raise TimeoutError("Chrome no habilitó el protocolo de impresión")

    @staticmethod
    async def _print_article_with_devtools(
        websocket_url: str,
        selector: str,
        source_url: str,
        source_name: str = "",
    ) -> str:
        from websockets.asyncio.client import connect

        async with connect(
            websocket_url,
            max_size=None,
            open_timeout=20,
            origin=None,
        ) as socket:
            counter = 0

            async def command(method: str, params: dict | None = None) -> dict:
                nonlocal counter
                counter += 1
                message_id = counter
                await socket.send(
                    json.dumps(
                        {"id": message_id, "method": method, "params": params or {}}
                    )
                )
                while True:
                    response = json.loads(await socket.recv())
                    if response.get("id") != message_id:
                        continue
                    if "error" in response:
                        raise RuntimeError(response["error"])
                    return response.get("result", {})

            await command("Page.enable")
            await command("Runtime.enable")
            await command(
                "Emulation.setDeviceMetricsOverride",
                {
                    "width": 1280,
                    "height": 2000,
                    "deviceScaleFactor": 1,
                    "mobile": False,
                    "screenWidth": 1280,
                    "screenHeight": 2000,
                },
            )
            await command("Page.navigate", {"url": source_url})
            await asyncio.sleep(2.5)

            script = f"""
                (async () => {{
                    const root = document.querySelector({json.dumps(selector)});
                    if (!root) throw new Error("No se encontró el bloque editorial");
                    const protectedSources = new Set([
                        "Semana Económica",
                        "Semana Económica - Índice",
                        "Diario Financiero",
                    ]);
                    if (protectedSources.has({json.dumps(source_name)})) {{
                        const visible = (node) => {{
                            if (!node) return false;
                            const style = window.getComputedStyle(node);
                            return style.display !== "none"
                                && style.visibility !== "hidden"
                                && node.getBoundingClientRect().height > 0;
                        }};
                        const gateSelectors = [
                            ".se-paywall",
                            ".se-article__overlay",
                            ".enc-main__paywall",
                            ".enc-main__login",
                            "[class*='paywall' i]",
                            "[class*='subscription' i]",
                        ];
                        if (gateSelectors.some((candidate) =>
                            Array.from(document.querySelectorAll(candidate)).some(visible)
                        )) {{
                            throw new Error("La noticia requiere una sesión autenticada");
                        }}
                        const rootText = (root.innerText || "").replace(/\\s+/g, " ").trim();
                        if (/(inicia sesión|iniciar sesión|suscríbete|suscribete|contenido exclusivo)/i.test(rootText)) {{
                            throw new Error("La noticia requiere una sesión autenticada");
                        }}
                    }}
                    document.querySelectorAll('[role="dialog"], [class*="modal" i], [class*="popup" i]').forEach((node) => node.remove());
                    let current = root;
                    while (current && current !== document.body) {{
                        for (const sibling of current.parentElement?.children || []) {{
                            if (sibling !== current) sibling.setAttribute("data-pdf-hidden", "true");
                        }}
                        current = current.parentElement;
                    }}
                    const remove = {json.dumps(REMOVE_SELECTORS)};
                    root.querySelectorAll(remove.join(",")).forEach((node) => node.remove());
                    const excludedHeadings = /^(más en|temas relacionados|sugerencias|recomendaciones|portafolio google news|síguenos en google news|ponte al día|nuestros portales)/i;
                    root.querySelectorAll("h1, h2, h3, h4, h5, h6, p, div").forEach((node) => {{
                        const text = (node.textContent || "").replace(/\\s+/g, " ").trim();
                        if (!excludedHeadings.test(text)) return;
                        const block = node.closest("section, aside") || node.parentElement?.parentElement;
                        if (block && block !== root) block.remove();
                    }});
                    root.querySelectorAll("[class*='related' i], [class*='recommend' i], [class*='suger' i]").forEach((node) => node.remove());
                    const paragraphs = Array.from(root.querySelectorAll(".c-cuerpo .paragraph"));
                    const authorIndex = paragraphs.findIndex((node, index) => {{
                        const current = (node.textContent || "").replace(/\\s+/g, " ").trim();
                        const next = (paragraphs[index + 1]?.textContent || "").replace(/\\s+/g, " ").trim();
                        return /^[A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ .'-]{{5,}}$/.test(current)
                            && /^periodista|^redacción|^redaccion/i.test(next);
                    }});
                    if (authorIndex >= 0) paragraphs.slice(authorIndex).forEach((node) => node.remove());
                    const style = document.createElement("style");
                    style.textContent = `
                        @page {{ size: A4; margin: 12mm 10mm; }}
                        [data-pdf-hidden] {{ display: none !important; }}
                        @media print {{
                            html, body {{ background: #fff !important; }}
                            img {{ max-width: 100%; height: auto; }}
                        }}
                    `;
                    document.head.append(style);
                    await document.fonts.ready;
                    await Promise.all(Array.from(document.images).map((image) =>
                        image.complete ? Promise.resolve() : new Promise((resolve) => {{
                            image.addEventListener("load", resolve, {{ once: true }});
                            image.addEventListener("error", resolve, {{ once: true }});
                        }})
                    ));
                    return true;
                }})()
            """
            await command(
                "Runtime.evaluate",
                {"expression": script, "awaitPromise": True, "returnByValue": True},
            )
            result = await command(
                "Page.printToPDF",
                {
                    "printBackground": True,
                    "preferCSSPageSize": True,
                    "displayHeaderFooter": False,
                },
            )
            return str(result["data"])

    @staticmethod
    def _find_browser() -> str:
        for path in WINDOWS_BROWSER_PATHS:
            if path.exists():
                return str(path)
        for name in ("chrome", "chrome.exe", "msedge", "msedge.exe"):
            found = shutil.which(name)
            if found:
                return found
        raise FileNotFoundError("No se encontró Chrome ni Microsoft Edge para imprimir PDFs")

    @staticmethod
    def _unique_path(output_dir: Path, title: str) -> Path:
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", normalize_text(title))
        safe = safe.rstrip(" .")[:180] or "noticia"
        return output_dir / f"{safe}.pdf"
