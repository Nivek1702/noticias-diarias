from datetime import date

import requests
from bs4 import BeautifulSoup

import news_scraper.sources.portafolio as portafolio_module
from news_scraper.sources.portafolio import Portafolio


TARGET_DATE = date(2026, 9, 30)
ARTICLE_URL = "https://www.portafolio.co/economia/finanzas/noticia-uno-503608"


def listing_html() -> str:
    return f"""
    <div class="c-articulo--mini-md" data-publicacion="2026-09-30" data-id="503608">
      <div class="c-articulo__fecha">30.09.2026</div>
      <h3 class="c-articulo__titulo">
        <a class="c-articulo__titulo__txt" href="{ARTICLE_URL}">
          Título del listado
        </a>
      </h3>
    </div>
    <div class="c-articulo--mini-md" data-publicacion="2026-09-29" data-id="503500">
      <div class="c-articulo__fecha">29.09.2026</div>
      <h3 class="c-articulo__titulo">
        <a class="c-articulo__titulo__txt" href="/economia/noticia-dos-503500">
          Otra fecha
        </a>
      </h3>
    </div>
    <div class="c-articulo--mini-md" data-publicacion="fecha-invalida" data-id="503400">
      <h3 class="c-articulo__titulo">
        <a class="c-articulo__titulo__txt" href="/economia/noticia-tres-503400">
          Fecha inválida
        </a>
      </h3>
    </div>
    """


def test_extrae_urls_y_filtra_por_fecha() -> None:
    source = Portafolio()
    soup = BeautifulSoup(listing_html(), "html.parser")

    assert source._extract_card_date(soup.select_one(".c-articulo--mini-md")) == TARGET_DATE
    assert source._extract_article_links(soup, TARGET_DATE) == [ARTICLE_URL]


def test_get_news_extrae_titulo_y_resumen(monkeypatch) -> None:
    source = Portafolio()
    monkeypatch.setattr(
        source,
        "_get_listing",
        lambda: BeautifulSoup(listing_html(), "html.parser"),
    )
    monkeypatch.setattr(
        source,
        "_get_article_detail",
        lambda url: ("Título real", "Resumen real de Portafolio."),
    )

    news = source.get_news(TARGET_DATE)

    assert len(news) == 1
    assert news[0].dia == TARGET_DATE
    assert news[0].fuente == "Portafolio"
    assert news[0].titulo == "Título real"
    assert news[0].parrafo == "Resumen real de Portafolio."


def test_detalle_usa_primer_parrafo_editorial(monkeypatch) -> None:
    source = Portafolio()
    detail = BeautifulSoup(
        """
        <article class="u-estructura u-estructura--articulo">
          <h1 class="c-articulo__titulo">Título del artículo</h1>
          <div class="c-lead"><h2 class="c-lead__titulo">Bajada oficial que no se usa.</h2></div>
          <section class="u-estructura__cuerpo">
            <div class="c-cuerpo">
              <div class="paragraph"><b>Plenti </b>cerró una ronda seed de US$3 millones liderada por <b>Tether</b>.</div>
              <div class="paragraph">Segundo párrafo del artículo.</div>
            </div>
          </section>
        </article>
        """,
        "html.parser",
    )
    monkeypatch.setattr(portafolio_module, "fetch_page", lambda url: detail)

    title, summary = source._get_article_detail(ARTICLE_URL)

    assert title == "Título del artículo"
    assert summary == "Plenti cerró una ronda seed de US$3 millones liderada por Tether."


def test_normaliza_texto() -> None:
    source = Portafolio()
    source._get_article_detail = lambda url: (  # type: ignore[method-assign]
        "  Título\ncon espacios ",
        "  Resumen   con\n espacios y tildes: Perú. ",
    )

    news = source._build_news(ARTICLE_URL, TARGET_DATE)

    assert news is not None
    assert news.titulo == "Título con espacios"
    assert news.parrafo == "Resumen con espacios y tildes: Perú."


def test_descarta_noticia_sin_resumen() -> None:
    source = Portafolio()
    source._get_article_detail = lambda url: (  # type: ignore[method-assign]
        "Título completo",
        "",
    )

    assert source._build_news(ARTICLE_URL, TARGET_DATE) is None


def test_maneja_error_http_en_listado(monkeypatch) -> None:
    source = Portafolio()
    monkeypatch.setattr(
        portafolio_module,
        "fetch_page",
        lambda url: (_ for _ in ()).throw(requests.Timeout("timeout")),
    )

    assert source.get_news(TARGET_DATE) == []


def test_evita_urls_duplicadas(monkeypatch) -> None:
    source = Portafolio()
    listing = BeautifulSoup(listing_html(), "html.parser")
    duplicate = BeautifulSoup(listing_html(), "html.parser").select_one(
        ".c-articulo--mini-md"
    )
    listing.append(duplicate)
    monkeypatch.setattr(source, "_get_listing", lambda: listing)
    calls: list[str] = []

    def detail(url: str) -> tuple[str, str]:
        calls.append(url)
        return "Título", "Resumen"

    monkeypatch.setattr(source, "_get_article_detail", detail)

    news = source.get_news(TARGET_DATE)

    assert len(news) == 1
    assert calls == [ARTICLE_URL]


def test_descarta_fecha_no_confiable() -> None:
    source = Portafolio()
    soup = BeautifulSoup(listing_html(), "html.parser")
    invalid_card = soup.select('[data-publicacion="fecha-invalida"]')[0]

    assert source._extract_card_date(invalid_card) is None
