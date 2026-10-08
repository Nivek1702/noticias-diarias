"""Fuente Diario Gestión - Perú Quiosco."""

from __future__ import annotations

import logging
from datetime import date

from news_scraper.models.noticia import Noticia
from news_scraper.services.extractor import normalize_text
from news_scraper.sources.base import NewsSource


LOGGER = logging.getLogger(__name__)


class Gestion(NewsSource):
    """Scraper preparado para los selectores de Diario Gestión."""

    @property
    def name(self) -> str:
        return "Diario Gestión"

    def get_news(self, target_date: date) -> list[Noticia]:
        """Obtiene noticias del listado y luego sus detalles individuales."""

        LOGGER.warning("%s aún no tiene selectores HTML implementados.", self.name)
        listing = self._get_listing()
        news: list[Noticia] = []
        processed_urls: set[str] = set()
        for url in self._extract_article_links(listing, target_date):
            if url in processed_urls:
                continue
            processed_urls.add(url)
            article = self._build_news(url, target_date)
            if article is not None:
                news.append(article)
        return news

    def _get_listing(self) -> str:
        """Obtiene el HTML del listado de la fuente."""

        return ""

    def _extract_article_links(self, html: str, target_date: date) -> list[str]:
        """Filtra del listado las URLs de noticias de la fecha solicitada."""

        return []

    def _get_article_detail(self, url: str) -> tuple[str, str]:
        """Obtiene título y primer párrafo desde una página individual."""

        return "", ""

    def _build_news(self, url: str, target_date: date) -> Noticia | None:
        """Construye una noticia a partir del detalle individual."""

        title, paragraph = (
            normalize_text(value) for value in self._get_article_detail(url)
        )
        if not title or not paragraph:
            LOGGER.error(
                "No se pudo extraer título o primer párrafo: fuente=%s URL=%s",
                self.name,
                url,
            )
            return None
        return Noticia(
            dia=target_date,
            fuente=self.name,
            titulo=title,
            parrafo=paragraph,
        )

