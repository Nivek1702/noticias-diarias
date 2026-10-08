from datetime import date

from news_scraper.sources.base import NewsSource
from news_scraper.sources.diario_financiero import DiarioFinanciero
from news_scraper.sources.gestion import Gestion
from news_scraper.sources.portafolio import Portafolio
from news_scraper.sources.semana_economica_indice import SemanaEconomicaIndice
from news_scraper.sources.semana_economica_sectores import SemanaEconomicaSectores


def test_todas_las_fuentes_respetan_news_source() -> None:
    sources = [
        SemanaEconomicaSectores(),
        DiarioFinanciero(),
        Portafolio(),
        SemanaEconomicaIndice(),
        Gestion(),
    ]

    assert all(isinstance(source, NewsSource) for source in sources)
    assert all(source.name for source in sources)

