"""Scraper de Semana Económica - Sectores y Empresas."""

from __future__ import annotations

import logging
import re
from datetime import date
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from news_scraper.config import SEMANA_ECONOMICA_SECTORES
from news_scraper.models.noticia import Noticia
from news_scraper.services.extractor import (
    extract_text,
    fetch_page,
    normalize_text,
)
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
    r"^(?P<day>\d{1,2})\s+(?:de\s+)?(?P<month>[a-záéíóú]+)"
    r"\s+(?:de\s+)?(?P<year>\d{4})$",
    re.IGNORECASE,
)

LISTING_CARD_SELECTOR = ".se-card"
LISTING_DATE_SELECTOR = ".se-card__date"
ARTICLE_TITLE_SELECTOR = "h1.se-article__title"
ARTICLE_SUMMARY_SELECTOR = ".se-article__excerpt"
ARTICLE_LINK_FRAGMENT = "/sectores-empresas/"
MAX_PAGES = 100


class SemanaEconomicaSectores(NewsSource):
    """Extrae noticias de la sección Sectores y Empresas."""

    @property
    def name(self) -> str:
        return "Semana Económica"

    def get_news(self, target_date: date) -> list[Noticia]:
        """Busca noticias de ``target_date`` y obtiene cada detalle individual."""

        results: list[Noticia] = []
        processed_urls: set[str] = set()
        seen_page_urls: set[str] = set()

        for page in range(1, MAX_PAGES + 1):
            try:
                listing = self._get_listing(page)
            except Exception:
                LOGGER.exception("Error al obtener listado de %s, página %s", self.name, page)
                break

            page_records = self._extract_page_records(listing)
            page_urls = [url for _, url in page_records]
            new_page_urls = set(page_urls) - seen_page_urls
            if page > 1 and not new_page_urls:
                LOGGER.info("No hay URLs nuevas en la página %s; se detiene la paginación", page)
                break
            new_dated_records = [
                (published_date, url)
                for published_date, url in page_records
                if published_date is not None and url not in seen_page_urls
            ]
            if (
                page > 1
                and new_dated_records
                and not any(published_date == target_date for published_date, _ in new_dated_records)
                and all(published_date < target_date for published_date, _ in new_dated_records)
            ):
                LOGGER.info(
                    "Las nuevas noticias de la página %s son anteriores a la fecha objetivo; "
                    "se detiene la paginación",
                    page,
                )
                break
            seen_page_urls.update(page_urls)

            links = self._extract_article_links(listing, target_date)
            for url in links:
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

            if self._page_is_older_than_target(listing, target_date):
                break
            if not self._has_article_cards(listing):
                break

        LOGGER.info("Noticias encontradas en %s: %s", self.name, len(results))
        return results

    def _get_listing(self, page: int = 1) -> BeautifulSoup:
        """Descarga una página del listado, incluida su paginación."""

        url = SEMANA_ECONOMICA_SECTORES
        if page > 1:
            url = f"{url}?category_id=1&page={page}#sectores"
        return fetch_page(url)

    def _extract_article_links(
        self,
        html: BeautifulSoup | str,
        target_date: date,
    ) -> list[str]:
        """Devuelve URLs de tarjetas cuya fecha coincide exactamente."""

        soup = self._as_soup(html)
        links: list[str] = []
        for card in soup.select(LISTING_CARD_SELECTOR):
            published_date = self._extract_card_date(card)
            if published_date is None:
                LOGGER.warning("No se pudo determinar la fecha de una tarjeta del listado")
                continue
            if published_date != target_date:
                continue
            link = self._extract_card_link(card)
            if link is None:
                LOGGER.warning(
                    "Noticia de %s sin URL identificable", target_date.strftime("%d/%m/%Y")
                )
                continue
            links.append(link)
        return links

    def _extract_all_article_links(self, html: BeautifulSoup | str) -> list[str]:
        """Devuelve todos los enlaces de artículo de una página de listado."""

        return [url for _, url in self._extract_page_records(html)]

    def _extract_page_records(
        self,
        html: BeautifulSoup | str,
    ) -> list[tuple[date | None, str]]:
        """Devuelve pares fecha/URL para medir el avance de la paginación."""

        soup = self._as_soup(html)
        records: list[tuple[date | None, str]] = []
        for card in soup.select(LISTING_CARD_SELECTOR):
            link = self._extract_card_link(card)
            if link is not None:
                records.append((self._extract_card_date(card), link))
        return records

    def _extract_card_date(self, card) -> date | None:
        """Convierte la fecha española de una tarjeta en ``datetime.date``."""

        date_node = card.select_one(LISTING_DATE_SELECTOR)
        return self._parse_date(extract_text(date_node)) if date_node else None

    def _parse_date(self, value: str) -> date | None:
        """Analiza fechas como ``6 de octubre de 2026``."""

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
        """Extrae el enlace de artículo, excluyendo enlaces de sector y tags."""

        for anchor in card.select(f'a[href*="{ARTICLE_LINK_FRAGMENT}"]'):
            href = anchor.get("href")
            if href and self._is_article_url(href):
                return urljoin(SEMANA_ECONOMICA_SECTORES, href)
        return None

    def _is_article_url(self, url: str) -> bool:
        """Comprueba que una URL pertenece a un artículo de la sección."""

        parsed = urlparse(urljoin(SEMANA_ECONOMICA_SECTORES, url))
        path = parsed.path.rstrip("/")
        section = "/sectores-empresas/"
        return path.startswith(section) and len(path.split("/")) >= 4

    def _get_article_detail(self, url: str) -> tuple[str, str]:
        """Obtiene título y resumen desde la página individual."""

        soup = fetch_page(url)
        title_node = soup.select_one(ARTICLE_TITLE_SELECTOR)
        summary_node = soup.select_one(ARTICLE_SUMMARY_SELECTOR)
        title = extract_text(title_node)
        paragraph = extract_text(summary_node)
        if not title:
            LOGGER.error("No se pudo extraer el título: fuente=%s URL=%s", self.name, url)
        if not paragraph:
            LOGGER.error("No se pudo extraer el resumen: fuente=%s URL=%s", self.name, url)
        return title, paragraph

    def _build_news(self, url: str, target_date: date) -> Noticia | None:
        """Crea una noticia solo si el detalle tiene título y resumen."""

        title, paragraph = (
            normalize_text(value) for value in self._get_article_detail(url)
        )
        if not title or not paragraph:
            return None
        return Noticia(
            dia=target_date,
            fuente=self.name,
            titulo=title,
            parrafo=paragraph,
            url=url,
        )

    def _page_is_older_than_target(
        self,
        listing: BeautifulSoup | str,
        target_date: date,
    ) -> bool:
        """Detiene la paginación cuando toda la página es anterior a la fecha."""

        dates = [
            parsed
            for card in self._as_soup(listing).select(LISTING_CARD_SELECTOR)
            if (parsed := self._extract_card_date(card)) is not None
        ]
        return bool(dates) and max(dates) < target_date

    def _has_article_cards(self, listing: BeautifulSoup | str) -> bool:
        """Indica si la página contiene tarjetas de noticias procesables."""

        return bool(self._as_soup(listing).select(LISTING_CARD_SELECTOR))

    @staticmethod
    def _as_soup(html: BeautifulSoup | str) -> BeautifulSoup:
        return html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")

