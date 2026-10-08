"""Contrato abstracto común para todas las fuentes de noticias."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from news_scraper.models.noticia import Noticia


class NewsSource(ABC):
    """Interfaz común para todas las fuentes de noticias."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre de la fuente."""

    @abstractmethod
    def get_news(self, target_date: date) -> list[Noticia]:
        """Obtiene todas las noticias publicadas en ``target_date``."""

