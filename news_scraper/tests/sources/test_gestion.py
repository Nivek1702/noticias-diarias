from datetime import date

from news_scraper.sources.gestion import Gestion


def test_gestion_implementa_contrato() -> None:
    source = Gestion()
    assert source.name == "Diario Gestión"
    assert source.get_news(date(2026, 10, 8)) == []

