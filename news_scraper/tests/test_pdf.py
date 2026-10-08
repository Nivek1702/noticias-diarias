from datetime import date
import base64
from pathlib import Path
import shutil

from bs4 import BeautifulSoup

import news_scraper.services.pdf as pdf_module
from news_scraper.models.noticia import Noticia
from news_scraper.services.pdf import PdfExporter


def test_extrae_contenido_editorial_y_elimina_publicidad() -> None:
    exporter = PdfExporter("output")
    soup = BeautifulSoup(
        """
        <article class="u-estructura--articulo">
          <h1>Título</h1>
          <section class="u-estructura__cuerpo">
            <div class="c-cuerpo">
              <aside>Publicidad</aside>
              <div class="paragraph">Texto de la noticia.</div>
              <div class="c-leatambien">Noticia relacionada</div>
            </div>
          </section>
        </article>
        """,
        "html.parser",
    )

    article = exporter._extract_article(soup, "Portafolio")

    assert article is not None
    assert article.get_text(" ", strip=True) == "Título Texto de la noticia."


def test_exporta_noticias_en_carpeta_de_ejecucion(monkeypatch) -> None:
    tmp_path = Path(__file__).with_name("_pdf_test_output")
    shutil.rmtree(tmp_path, ignore_errors=True)
    exporter = PdfExporter(tmp_path)
    news = Noticia(
        date(2026, 10, 8),
        "Portafolio",
        "Título: noticia / prueba",
        "Párrafo",
        "https://example.test/noticia",
    )
    calls: list[tuple[str, Path]] = []

    def fake_export_one(item: Noticia, output_dir: Path) -> bool:
        calls.append((item.titulo, output_dir))
        return True

    monkeypatch.setattr(exporter, "export_one", fake_export_one)

    try:
        assert exporter.export_many([news], date(2026, 10, 8)) == 1
        assert calls == [("Título: noticia / prueba", tmp_path / "08-10-2026")]
        assert (tmp_path / "08-10-2026").is_dir()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_render_pdf_invoca_chrome(monkeypatch) -> None:
    tmp_path = Path(__file__).with_name("_pdf_test_render")
    shutil.rmtree(tmp_path, ignore_errors=True)
    tmp_path.mkdir()
    exporter = PdfExporter(tmp_path)
    output = tmp_path / "noticia.pdf"
    class FakeProcess:
        def terminate(self):
            pass

        def wait(self, timeout=None):
            pass

        def kill(self):
            pass

    def fake_popen(command, **kwargs):
        return FakeProcess()

    async def fake_print(*args, **kwargs):
        return base64.b64encode(b"pdf").decode("ascii")

    monkeypatch.setattr(pdf_module.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        PdfExporter,
        "_open_devtools_target",
        staticmethod(lambda port: "ws://example.test/devtools"),
    )
    monkeypatch.setattr(PdfExporter, "_print_article_with_devtools", fake_print)

    try:
        exporter._render_pdf(
            "chrome.exe",
            "Título",
            BeautifulSoup('<div class="c-cuerpo"><p>Contenido</p></div>', "html.parser"),
            output,
            "https://example.test/noticia",
            [],
        )

        assert output.read_bytes() == b"pdf"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
