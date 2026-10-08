"""Scraper de Diario Financiero mediante la búsqueda de ``Perú``."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from news_scraper.config import (
    DIARIO_FINANCIERO_SEARCH_TERM,
    DIARIO_FINANCIERO_SEARCH_URL,
)
from news_scraper.models.noticia import Noticia
from news_scraper.services.extractor import (
    extract_text,
    fetch_page,
    fetch_post_page,
    normalize_text,
)
from news_scraper.sources.base import NewsSource


LOGGER = logging.getLogger(__name__)

SITE_URL = "https://www.df.cl"
LISTING_CARD_SELECTOR = "article.card.card__horizontal"
LISTING_DATE_SELECTOR = ".card__date[data-date]"
LISTING_TITLE_SELECTOR = ".card__title"
ARTICLE_TITLE_SELECTOR = ".enc-main__title"
ARTICLE_SUMMARY_SELECTOR = ".enc-main__description"
PERU_TITLE_PATTERN = re.compile(r"\bperú\b", re.IGNORECASE)


class DiarioFinanciero(NewsSource):
    """Obtiene noticias de Diario Financiero relacionadas con Perú."""

    @property
    def name(self) -> str:
        return "Diario Financiero"

    def get_news(self, target_date: date) -> list[Noticia]:
        """Busca ``Perú``, filtra por fecha y consulta cada artículo."""

        try:
            listing = self._get_listing()
        except Exception:
            LOGGER.exception("Error al obtener resultados de Diario Financiero")
            return []

        results: list[Noticia] = []
        processed_urls: set[str] = set()
        for url in self._extract_article_links(listing, target_date):
            if url in processed_urls:
                continue
            processed_urls.add(url)
            try:
                article = self._build_news(url, target_date)
            except Exception:
                LOGGER.exception("Error al procesar noticia de Diario Financiero: %s", url)
                continue
            if article is not None:
                results.append(article)

        LOGGER.info("Noticias encontradas en %s: %s", self.name, len(results))
        return results

    def _get_listing(self) -> BeautifulSoup:
        """Ejecuta la búsqueda del sitio como lo hace su formulario de lupa."""

        data = {
            "search_prontus": "noticias",
            "search_idx": "all",
            "search_tmp": "search.html",
            "search_modo": "and",
            "search_orden": "cro",
            "search_texto": DIARIO_FINANCIERO_SEARCH_TERM,
        }
        return fetch_post_page(DIARIO_FINANCIERO_SEARCH_URL, data)

    def _extract_article_links(
        self,
        html: BeautifulSoup | str,
        target_date: date,
    ) -> list[str]:
        """Extrae URLs de resultados cuya fecha coincide exactamente."""

        soup = self._as_soup(html)
        links: list[str] = []
        for card in soup.select(LISTING_CARD_SELECTOR):
            published_date = self._extract_card_date(card)
            if published_date is None:
                LOGGER.warning("Resultado de Diario Financiero sin fecha confiable")
                continue
            if published_date != target_date:
                continue
            link = self._extract_card_link(card)
            if link is None:
                LOGGER.warning("Resultado de Diario Financiero sin URL identificable")
                continue
            links.append(link)
        return links

    def _extract_card_date(self, card) -> date | None:
        """Convierte ``YYYYMMDD`` del resultado en ``datetime.date``."""

        node = card.select_one(LISTING_DATE_SELECTOR)
        if node is None:
            return None
        value = node.get("data-date") or extract_text(node)
        try:
            return datetime.strptime(normalize_text(value), "%Y%m%d").date()
        except ValueError:
            try:
                return datetime.strptime(normalize_text(value), "%d/%m/%Y").date()
            except ValueError:
                return None

    def _extract_card_link(self, card) -> str | None:
        """Extrae el enlace asociado al título de la tarjeta."""

        title = card.select_one(LISTING_TITLE_SELECTOR)
        anchor = title.find_parent("a", href=True) if title else None
        if anchor is None:
            anchor = card.select_one("a[href]")
        if anchor is None or not anchor.get("href"):
            return None
        return urljoin(SITE_URL, anchor["href"])

    def _get_article_detail(self, url: str) -> tuple[str, str]:
        """Obtiene título y resumen/bajada del artículo individual."""

        soup = fetch_page(url)
        title = extract_text(soup.select_one(ARTICLE_TITLE_SELECTOR))
        summary = extract_text(soup.select_one(ARTICLE_SUMMARY_SELECTOR))
        if not title:
            LOGGER.error("No se pudo extraer el título: fuente=%s URL=%s", self.name, url)
        if not summary:
            LOGGER.error("No se pudo extraer el resumen: fuente=%s URL=%s", self.name, url)
        return title, summary

    def _build_news(self, url: str, target_date: date) -> Noticia | None:
        """Crea una noticia completa y relacionada con Perú por su título."""

        title, summary = (
            normalize_text(value) for value in self._get_article_detail(url)
        )
        if not title or not summary:
            LOGGER.error("Noticia incompleta descartada: fuente=%s URL=%s", self.name, url)
            return None
        if PERU_TITLE_PATTERN.search(title) is None:
            LOGGER.info("Noticia descartada por no mencionar Perú en el título: URL=%s", url)
            return None
        return Noticia(
            dia=target_date,
            fuente=self.name,
            titulo=title,
            parrafo=summary,
            url=url,
        )

    @staticmethod
    def _as_soup(html: BeautifulSoup | str) -> BeautifulSoup:
        return html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")

