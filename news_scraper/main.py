"""Punto de entrada y orquestador principal de la aplicación."""

from __future__ import annotations

import logging
import sys
from datetime import date
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from news_scraper.config import CHROME_USER_DATA_DIR, DATE_FORMAT, OUTPUT_FILE
from news_scraper.models.noticia import Noticia
from news_scraper.services.excel import ExcelService
from news_scraper.services.pdf import PdfExporter
from news_scraper.services.validator import validate_news
from news_scraper.sources.base import NewsSource
from news_scraper.sources.diario_financiero import DiarioFinanciero
from news_scraper.sources.gestion import Gestion
from news_scraper.sources.portafolio import Portafolio
from news_scraper.sources.semana_economica_indice import SemanaEconomicaIndice
from news_scraper.sources.semana_economica_sectores import SemanaEconomicaSectores


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
LOGGER = logging.getLogger(__name__)

def get_sources() -> list[NewsSource]:
    """Construye las fuentes registradas usando el contrato común."""

    return [
        SemanaEconomicaSectores(),
        DiarioFinanciero(),
        Portafolio(),
        SemanaEconomicaIndice(),
        Gestion(),
    ]


def collect_news(target_date: date) -> tuple[list[Noticia], dict[str, str], int]:
    """Ejecuta todos los scrapers y aísla los errores por fuente."""

    collected: list[Noticia] = []
    status: dict[str, str] = {}
    errors = 0

    for source in get_sources():
        try:
            news = source.get_news(target_date)
            collected.extend(news)
            status[source.name] = f"OK - {len(news)} noticias"
        except Exception:
            LOGGER.exception("Error procesando la fuente: %s", source.name)
            status[source.name] = "ERROR"
            errors += 1

    return collected, status, errors


def print_execution_summary(
    execution_date: date,
    status: dict[str, str],
    summary: dict[str, int | str],
) -> None:
    """Muestra el resumen final permitido para la ejecución."""

    print("=" * 40)
    print("RESUMEN DE EJECUCIÓN")
    print("=" * 40)
    print(f"\nFecha consultada: {execution_date.strftime(DATE_FORMAT)}\n")
    for source_name, source_status in status.items():
        print(f"{source_name}: {source_status}")
    print(f"\nTotal encontradas: {summary['encontradas']}")
    print(f"Total nuevas:       {summary['agregadas']}")
    print(f"Total duplicadas:   {summary['duplicadas']}")
    print(f"PDFs generados:      {summary['pdfs']}")
    print(f"Total errores:      {summary['errores']}")
    print(f"\nExcel: {OUTPUT_FILE}")
    print("=" * 40)


def run(target_date: date | None = None) -> dict[str, int | str]:
    """Ejecuta la extracción, validación y persistencia de noticias."""

    if CHROME_USER_DATA_DIR is None:
        raise RuntimeError(
            "Falta configurar NEWS_CHROME_USER_DATA_DIR con la ruta del "
            "perfil de Chrome autenticado. Consulta news_scraper/README.md."
        )

    execution_date = target_date or date.today()
    news, status, errors = collect_news(execution_date)
    valid_news = [item for item in news if validate_news(item, execution_date)]

    excel = ExcelService(OUTPUT_FILE)
    added = excel.append_news(valid_news)
    pdfs = PdfExporter(
        OUTPUT_FILE.parent,
        browser_user_data_dir=CHROME_USER_DATA_DIR,
    ).export_many(valid_news, execution_date)

    for source_name, source_status in status.items():
        LOGGER.info("%s: %s", source_name, source_status)

    summary = {
        "dia": execution_date.strftime(DATE_FORMAT),
        "encontradas": len(news),
        "validas": len(valid_news),
        "agregadas": added,
        "duplicadas": excel.last_duplicates,
        "pdfs": pdfs,
        "errores": errors,
    }
    LOGGER.info("Resumen: %s", summary)
    print_execution_summary(execution_date, status, summary)
    return summary


if __name__ == "__main__":
    run()

