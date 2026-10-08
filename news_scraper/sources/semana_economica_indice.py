"""Scraper de Semana Económica - Qué está pasando."""

from __future__ import annotations

import logging
import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from news_scraper.config import SEMANA_ECONOMICA_INDICE
from news_scraper.models.noticia import Noticia
from news_scraper.services.extractor import extract_text, fetch_page, normalize_text
from news_scraper.sources.base import NewsSource


LOGGER = logging.getLogger(__name__)

MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

DATE_PATTERN = re.compile(
    r"^(?P<day>\d{1,2})\s+de\s+(?P<month>[a-záéíóú]+)\s+de\s+(?P<year>\d{4})$",
    re.IGNORECASE,
)

LISTING_CARD_SELECTOR = ".se-card--horizontal"
LISTING_DATE_SELECTOR = ".se-card__date"
LISTING_TITLE_SELECTOR = ".se-card__title"
LISTING_SUMMARY_SELECTOR = ".se-card__excerpt"
ARTICLE_LINK_FRAGMENT = "/que-esta-pasando/articulos/"
ARTICLE_TITLE_SELECTOR = "h1.se-article__title"
ARTICLE_SUMMARY_SELECTOR = ".se-article__excerpt"


class SemanaEconomicaIndice(NewsSource):
    """Extrae resúmenes de las noticias de Qué está pasando."""

    @property
    def name(self) -> str:
        return "Semana Económica - Índice"

    def get_news(self, target_date: date) -> list[Noticia]:
        """Obtiene únicamente las noticias de la fecha solicitada."""

        try:
            listing = self._get_listing(target_date)
        except Exception:
            LOGGER.exception("Error al obtener el índice para %s", target_date)
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
                LOGGER.exception("Error al procesar noticia: %s", url)
                continue
            if article is not None:
                results.append(article)

        LOGGER.info("Noticias encontradas en %s: %s", self.name, len(results))
        return results

    def _get_listing(self, target_date: date) -> BeautifulSoup:
        """Descarga la página diaria del índice."""

        url = f"{SEMANA_ECONOMICA_INDICE}/{target_date:%d-%m-%Y}"
        return fetch_page(url)

    def _extract_article_links(
        self,
        html: BeautifulSoup | str,
        target_date: date,
    ) -> list[str]:
        """Extrae enlaces de tarjetas cuya fecha coincide exactamente."""

        soup = self._as_soup(html)
        links: list[str] = []
        for card in soup.select(LISTING_CARD_SELECTOR):
            published_date = self._extract_card_date(card)
            if published_date is None:
                LOGGER.warning("No se pudo determinar la fecha de una noticia del índice")
                continue
            if published_date != target_date:
                continue
            link = self._extract_card_link(card)
            if link is None:
                LOGGER.warning("Noticia del índice sin URL identificable")
                continue
            links.append(link)
        return links

    def _extract_card_date(self, card) -> date | None:
        """Convierte la fecha española de una tarjeta en ``datetime.date``."""

        node = card.select_one(LISTING_DATE_SELECTOR)
        return self._parse_date(extract_text(node)) if node else None

    def _parse_date(self, value: str) -> date | None:
        """Analiza fechas como ``7 de octubre de 2026``."""

        match = DATE_PATTERN.match(normalize_text(value).lower())
        if not match:
            return None
        try:
            return date(
                int(match.group("year")),
                MONTHS[match.group("month")],
                int(match.group("day")),
            )
        except (KeyError, ValueError):
            return None

    def _extract_card_link(self, card) -> str | None:
        """Extrae el enlace individual de la tarjeta."""

        anchor = card.select_one(f'a[href*="{ARTICLE_LINK_FRAGMENT}"]')
        if anchor is None or not anchor.get("href"):
            return None
        return urljoin(f"{SEMANA_ECONOMICA_INDICE}/", anchor["href"])

    def _get_article_detail(self, url: str) -> tuple[str, str]:
        """Obtiene el título y la entradilla de la página individual."""

        soup = fetch_page(url)
        title = extract_text(soup.select_one(ARTICLE_TITLE_SELECTOR))
        summary = extract_text(soup.select_one(ARTICLE_SUMMARY_SELECTOR))
        if not title:
            LOGGER.error("No se pudo extraer el título: fuente=%s URL=%s", self.name, url)
        if not summary:
            LOGGER.error("No se pudo extraer el resumen: fuente=%s URL=%s", self.name, url)
        return title, summary

    def _build_news(self, url: str, target_date: date) -> Noticia | None:
        """Construye una noticia usando el resumen, nunca el primer párrafo."""

        title, summary = (
            normalize_text(value) for value in self._get_article_detail(url)
        )
        if not title or not summary:
            LOGGER.error("Noticia incompleta descartada: fuente=%s URL=%s", self.name, url)
            return None
        return Noticia(
            dia=target_date,
            fuente="Semana Económica",
            titulo=title,
            parrafo=summary,
            url=url,
        )

    @staticmethod
    def _as_soup(html: BeautifulSoup | str) -> BeautifulSoup:
        return html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")

