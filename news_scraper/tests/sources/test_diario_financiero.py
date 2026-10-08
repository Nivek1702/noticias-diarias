from datetime import date

import requests
from bs4 import BeautifulSoup

import news_scraper.sources.diario_financiero as df_module
from news_scraper.sources.diario_financiero import DiarioFinanciero


TARGET_DATE = date(2026, 10, 6)
ARTICLE_URL = "https://www.df.cl/empresas/retail/noticia-uno"


def listing_html() -> str:
    return f"""
    <article class="card card__horizontal card__horizontal--full mt-40">
      <div class="card__content">
        <a class="card__tag card__tag--orange" href="/tax">
          Empresas | <span class="card__date" data-date="20261006">20261006</span>
        </a>
        <a href="{ARTICLE_URL}">
          <h3 class="card__title">Título de Perú</h3>
        </a>
      </div>
    </article>
    <article class="card card__horizontal card__horizontal--full mt-40">
      <div class="card__content">
        <a class="card__tag">Empresas | <span class="card__date" data-date="20261007">20261007</span></a>
        <a href="https://www.df.cl/empresas/retail/noticia-dos">
          <h3 class="card__title">Otra fecha</h3>
        </a>
      </div>
    </article>
    """


def test_extrae_urls_y_filtra_por_fecha() -> None:
    source = DiarioFinanciero()
    soup = BeautifulSoup(listing_html(), "html.parser")

    assert source._extract_card_date(soup.select_one("article")) == TARGET_DATE
    assert source._extract_article_links(soup, TARGET_DATE) == [ARTICLE_URL]


def test_get_news_extrae_titulo_y_resumen(monkeypatch) -> None:
    source = DiarioFinanciero()
    listing = BeautifulSoup(listing_html(), "html.parser")
    monkeypatch.setattr(source, "_get_listing", lambda: listing)
    monkeypatch.setattr(
        source,
        "_get_article_detail",
        lambda url: ("Título real sobre Perú", "Resumen real de Diario Financiero."),
    )

    news = source.get_news(TARGET_DATE)

    assert len(news) == 1
    assert news[0].dia == TARGET_DATE
    assert news[0].fuente == "Diario Financiero"
    assert news[0].titulo == "Título real sobre Perú"
    assert news[0].parrafo == "Resumen real de Diario Financiero."


def test_detalle_usa_encabezado_y_bajada_no_primer_p(monkeypatch) -> None:
    source = DiarioFinanciero()
    detail = BeautifulSoup(
        """
        <h1 class="enc-main__title">Título real</h1>
        <p class="enc-main__description">Resumen o bajada real.</p>
        <main><p>Primer párrafo del cuerpo, no es el resumen.</p></main>
        """,
        "html.parser",
    )
    monkeypatch.setattr(df_module, "fetch_page", lambda url: detail)

    title, summary = source._get_article_detail(ARTICLE_URL)

    assert title == "Título real"
    assert summary == "Resumen o bajada real."


def test_normaliza_texto_y_descarta_resumen_vacio() -> None:
    source = DiarioFinanciero()
    source._get_article_detail = lambda url: (  # type: ignore[method-assign]
        "  Título sobre PERÚ\nreal ",
        "  Resumen   normalizado\n. ",
    )
    news = source._build_news(ARTICLE_URL, TARGET_DATE)

    assert news is not None
    assert news.titulo == "Título sobre PERÚ real"
    assert news.parrafo == "Resumen normalizado ."

    source._get_article_detail = lambda url: ("Título sobre Perú", "")  # type: ignore[method-assign]
    assert source._build_news(ARTICLE_URL, TARGET_DATE) is None


def test_descarta_noticia_sin_peru_en_el_titulo() -> None:
    source = DiarioFinanciero()
    source._get_article_detail = lambda url: (  # type: ignore[method-assign]
        "Mercados globales suben con fuerza",
        "Resumen válido, pero sin referencia en el título.",
    )

    assert source._build_news(ARTICLE_URL, TARGET_DATE) is None


def test_maneja_error_http_en_la_busqueda(monkeypatch) -> None:
    source = DiarioFinanciero()
    monkeypatch.setattr(
        df_module,
        "fetch_post_page",
        lambda url, data: (_ for _ in ()).throw(requests.Timeout("timeout")),
    )

    assert source.get_news(TARGET_DATE) == []


def test_evita_urls_duplicadas(monkeypatch) -> None:
    source = DiarioFinanciero()
    listing = BeautifulSoup(listing_html(), "html.parser")
    duplicate = BeautifulSoup(listing_html(), "html.parser").select_one("article")
    listing.append(duplicate)
    monkeypatch.setattr(source, "_get_listing", lambda: listing)
    calls: list[str] = []

    def detail(url: str) -> tuple[str, str]:
        calls.append(url)
        return "Título de Perú", "Resumen"

    monkeypatch.setattr(source, "_get_article_detail", detail)

    news = source.get_news(TARGET_DATE)

    assert len(news) == 1
    assert calls == [ARTICLE_URL]

