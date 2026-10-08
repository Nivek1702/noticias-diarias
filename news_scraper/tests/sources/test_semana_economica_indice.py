from datetime import date

import requests
from bs4 import BeautifulSoup

import news_scraper.sources.semana_economica_indice as indice_module
from news_scraper.sources.semana_economica_indice import SemanaEconomicaIndice


TARGET_DATE = date(2026, 10, 7)
ARTICLE_URL = (
    "https://semanaeconomica.com/que-esta-pasando/articulos/noticia-uno"
)


def listing_html() -> str:
    return f"""
    <div class="se-card--horizontal mb16">
      <p><span class="se-card__date">7 de octubre de 2026</span></p>
      <div class="se-card__body">
        <a href="{ARTICLE_URL}">
          <h2 class="se-card__title">Título uno</h2>
          <div class="se-card__excerpt"><p>Resumen del listado.</p></div>
        </a>
      </div>
    </div>
    <div class="se-card--horizontal mb16">
      <p><span class="se-card__date">6 de octubre de 2026</span></p>
      <div class="se-card__body">
        <a href="https://semanaeconomica.com/que-esta-pasando/articulos/noticia-dos">
          <h2 class="se-card__title">Título dos</h2>
          <div class="se-card__excerpt"><p>Resumen anterior.</p></div>
        </a>
      </div>
    </div>
    """


def test_implementa_contrato_y_filtra_por_fecha() -> None:
    source = SemanaEconomicaIndice()
    soup = BeautifulSoup(listing_html(), "html.parser")

    assert source.name == "Semana Económica - Índice"
    assert source._parse_date("7 de octubre de 2026") == TARGET_DATE
    assert source._extract_article_links(soup, TARGET_DATE) == [ARTICLE_URL]


def test_get_news_extrae_titulo_y_resumen_individual(monkeypatch) -> None:
    source = SemanaEconomicaIndice()
    listing = BeautifulSoup(listing_html(), "html.parser")
    monkeypatch.setattr(source, "_get_listing", lambda target_date: listing)
    monkeypatch.setattr(
        source,
        "_get_article_detail",
        lambda url: ("Título real", "Resumen real de la página individual."),
    )

    news = source.get_news(TARGET_DATE)

    assert len(news) == 1
    assert news[0].dia == TARGET_DATE
    assert news[0].fuente == "Semana Económica"
    assert news[0].titulo == "Título real"
    assert news[0].parrafo == "Resumen real de la página individual."
    assert news[0].parrafo != "Resumen del listado."


def test_selectores_individuales_no_usan_el_primer_parrafo(monkeypatch) -> None:
    source = SemanaEconomicaIndice()
    detail = BeautifulSoup(
        """
        <h1 class="se-article__title">Título real</h1>
        <div class="se-article__excerpt">
          <h2>Resumen o bajada de la noticia.</h2>
        </div>
        <div class="js-se-content">
          <p>Primer párrafo del cuerpo, que no debe utilizarse.</p>
        </div>
        """,
        "html.parser",
    )
    monkeypatch.setattr(indice_module, "fetch_page", lambda url: detail)

    title, summary = source._get_article_detail(ARTICLE_URL)

    assert title == "Título real"
    assert summary == "Resumen o bajada de la noticia."


def test_normaliza_el_resumen() -> None:
    source = SemanaEconomicaIndice()
    source._get_article_detail = lambda url: (  # type: ignore[method-assign]
        "  Título\nreal ",
        "  Resumen   con\n saltos. ",
    )

    news = source._build_news(ARTICLE_URL, TARGET_DATE)

    assert news is not None
    assert news.titulo == "Título real"
    assert news.parrafo == "Resumen con saltos."


def test_descarta_noticia_sin_resumen() -> None:
    source = SemanaEconomicaIndice()
    source._get_article_detail = lambda url: ("Título", "")  # type: ignore[method-assign]

    assert source._build_news(ARTICLE_URL, TARGET_DATE) is None


def test_previene_urls_duplicadas(monkeypatch) -> None:
    source = SemanaEconomicaIndice()
    listing = BeautifulSoup(listing_html(), "html.parser")
    duplicate = BeautifulSoup(listing_html(), "html.parser").select_one(
        ".se-card--horizontal"
    )
    listing.select_one(".se-list__column--left")
    listing.append(duplicate)
    monkeypatch.setattr(source, "_get_listing", lambda target_date: listing)
    calls: list[str] = []

    def detail(url: str) -> tuple[str, str]:
        calls.append(url)
        return "Título", "Resumen"

    monkeypatch.setattr(source, "_get_article_detail", detail)

    news = source.get_news(TARGET_DATE)

    assert len(news) == 1
    assert calls == [ARTICLE_URL]


def test_maneja_error_http_del_listado(monkeypatch) -> None:
    source = SemanaEconomicaIndice()
    monkeypatch.setattr(
        indice_module,
        "fetch_page",
        lambda url: (_ for _ in ()).throw(requests.Timeout("timeout")),
    )

    assert source.get_news(TARGET_DATE) == []

