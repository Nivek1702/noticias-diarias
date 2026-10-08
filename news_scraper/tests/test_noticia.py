from datetime import date

from news_scraper.models.noticia import Noticia


def test_noticia_conserva_campos_y_clave() -> None:
    noticia = Noticia(date(2026, 10, 8), "Portafolio", "Título", "Párrafo")

    assert noticia.titulo == "Título"
    assert noticia.dia == date(2026, 10, 8)
    assert noticia.duplicate_key() == (date(2026, 10, 8), "Portafolio", "Título")

