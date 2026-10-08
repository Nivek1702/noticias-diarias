from datetime import date

from bs4 import BeautifulSoup

import news_scraper.sources.semana_economica_sectores as sectores_module
from news_scraper.sources.semana_economica_sectores import SemanaEconomicaSectores


TARGET_DATE = date(2026, 10, 8)


def listing_html() -> str:
    return """
    <div class="se-card">
      <span class="se-card__date">8 de octubre de 2026</span>
      <a href="/sectores-empresas/tecnologia/noticia-uno">Noticia uno</a>
      <p class="excerpt">Este resumen no debe ser utilizado.</p>
    </div>
    <div class="se-card">
      <span class="se-card__date">7 de octubre de 2026</span>
      <a href="/sectores-empresas/energia/noticia-anterior">Noticia anterior</a>
    </div>
    """


def test_semana_economica_sectores_implementa_contrato() -> None:
    source = SemanaEconomicaSectores()
    assert source.name == "Semana Económica"


def test_extrae_urls_y_fechas_y_filtra_por_target_date() -> None:
    source = SemanaEconomicaSectores()
    soup = BeautifulSoup(listing_html(), "html.parser")

    assert source._parse_date("8 de octubre de 2026") == TARGET_DATE
    assert source._parse_date("fecha desconocida") is None
    assert source._extract_article_links(soup, TARGET_DATE) == [
        "https://semanaeconomica.com/sectores-empresas/tecnologia/noticia-uno"
    ]


def test_extrae_titulo_y_resumen_del_detalle() -> None:
    source = SemanaEconomicaSectores()
    source._get_article_detail = lambda url: (  # type: ignore[method-assign]
        "  Título\nreal  ",
        "  Resumen   de la\nnoticia. ",
    )

    noticia = source._build_news("https://example.test/noticia", TARGET_DATE)

    assert noticia is not None
    assert noticia.titulo == "Título real"
    assert noticia.parrafo == "Resumen de la noticia."
    assert noticia.dia == TARGET_DATE


def test_selectores_del_detalle_usan_h1_y_entradilla(monkeypatch) -> None:
    source = SemanaEconomicaSectores()
    detail = BeautifulSoup(
        """
        <nav><p>Texto de navegación</p></nav>
        <h1 class="se-article__title">Título de la noticia</h1>
        <div class="se-article__excerpt">
          <h2>Este es el resumen que debe extraerse.</h2>
        </div>
        <div class="js-se-content">
          Primer párrafo real del artículo, que no se utilizará.
          <div class="se-article__overlay">Publicidad</div>
        </div>
        """,
        "html.parser",
    )
    monkeypatch.setattr(sectores_module, "fetch_page", lambda url: detail)

    title, paragraph = source._get_article_detail("https://example.test/noticia")

    assert title == "Título de la noticia"
    assert paragraph == "Este es el resumen que debe extraerse."


def test_get_news_accede_a_detalles_y_guarda_el_resumen(monkeypatch) -> None:
    source = SemanaEconomicaSectores()
    listing = BeautifulSoup(listing_html(), "html.parser")
    monkeypatch.setattr(
        source,
        "_get_listing",
        lambda page=1: listing if page == 1 else BeautifulSoup("", "html.parser"),
    )
    monkeypatch.setattr(
        source,
        "_get_article_detail",
        lambda url: ("Título real", "Resumen de la página individual."),
    )

    news = source.get_news(TARGET_DATE)

    assert len(news) == 1
    assert news[0].parrafo == "Resumen de la página individual."


def test_omite_noticia_sin_primer_parrafo() -> None:
    source = SemanaEconomicaSectores()
    source._get_article_detail = lambda url: ("Título", "")  # type: ignore[method-assign]

    assert source._build_news("https://example.test/noticia", TARGET_DATE) is None

