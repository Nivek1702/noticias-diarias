from bs4 import BeautifulSoup

from news_scraper.services.extractor import (
    extract_links,
    extract_text,
    first_valid_paragraph,
    normalize_text,
)


def test_funciones_comunes_del_extractor() -> None:
    soup = BeautifulSoup(
        "<main><p>  Primer\n párrafo </p><p>Segundo</p></main>",
        "html.parser",
    )

    assert normalize_text("  hola\n mundo ") == "hola mundo"
    assert extract_text(soup.main.p) == "Primer párrafo"
    assert first_valid_paragraph(soup.main) == "Primer párrafo"


def test_extract_links_usa_selector_css() -> None:
    soup = BeautifulSoup('<a href="/uno">Uno</a><span>Sin enlace</span>', "html.parser")

    assert extract_links(soup) == ["/uno"]

