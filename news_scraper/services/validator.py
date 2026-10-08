"""Validación y deduplicación de noticias normalizadas."""

from __future__ import annotations

from datetime import date
from collections.abc import Iterable

from news_scraper.config import SOURCES
from news_scraper.models.noticia import Noticia


def validate_news(news: Noticia, target_date: date | None = None) -> bool:
    """Valida campos obligatorios, fuente y fecha normalizada."""

    if not isinstance(news.dia, date):
        return False
    if not all((news.fuente.strip(), news.titulo.strip(), news.parrafo.strip())):
        return False
    if news.fuente not in SOURCES:
        return False
    return target_date is None or news.dia == target_date


def remove_duplicates(news_items: Iterable[Noticia]) -> list[Noticia]:
    """Conserva la primera noticia de cada clave ``dia + fuente + titulo``."""

    unique: list[Noticia] = []
    seen: set[tuple[date, str, str]] = set()
    for news in news_items:
        key = news.duplicate_key()
        if key not in seen:
            seen.add(key)
            unique.append(news)
    return unique

