from datetime import date

from news_scraper.models.noticia import Noticia
from news_scraper.services.validator import remove_duplicates, validate_news


def test_validate_news_acepta_noticia_completa() -> None:
    noticia = Noticia(date(2026, 10, 8), "Portafolio", "Título", "Párrafo")

    assert validate_news(noticia, date(2026, 10, 8)) is True


def test_validate_news_rechaza_fecha_distinta_y_campos_vacios() -> None:
    fecha_distinta = Noticia(date(2026, 10, 7), "Portafolio", "Título", "Párrafo")
    incompleta = Noticia(date(2026, 10, 8), "Portafolio", "", "Párrafo")

    assert validate_news(fecha_distinta, date(2026, 10, 8)) is False
    assert validate_news(incompleta, date(2026, 10, 8)) is False


def test_remove_duplicates_usa_dia_fuente_y_titulo() -> None:
    items = [
        Noticia(date(2026, 10, 8), "Portafolio", "Misma", "Uno"),
        Noticia(date(2026, 10, 8), "Portafolio", "Misma", "Dos"),
        Noticia(date(2026, 10, 8), "Portafolio", "Otra", "Tres"),
    ]

    assert remove_duplicates(items) == [items[0], items[2]]

