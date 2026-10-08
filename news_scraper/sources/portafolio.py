"""Scraper de Portafolio - Noticias Económicas de Perú."""

from __future__ import annotations

import logging
from datetime import date, datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from news_scraper.config import PORTAFOLIO
from news_scraper.models.noticia import Noticia
from news_scraper.services.extractor import extract_text, fetch_page, normalize_text
from news_scraper.sources.base import NewsSource


LOGGER = logging.getLogger(__name__)

SITE_URL = "https://www.portafolio.co"
LISTING_CARD_SELECTOR = ".c-articulo--mini-md"
LISTING_DATE_ATTRIBUTE = "data-publicacion"
LISTING_DATE_SELECTOR = ".c-articulo__fecha"
LISTING_LINK_SELECTOR = "a.c-articulo__titulo__txt[href]"
ARTICLE_TITLE_SELECTOR = "h1.c-articulo__titulo"
ARTICLE_PARAGRAPH_SELECTOR = ".c-cuerpo > div.paragraph"


class Portafolio(NewsSource):
    """Obtiene noticias de Perú publicadas por Portafolio."""

    @property
    def name(self) -> str:
        return "Portafolio"

    def get_news(self, target_date: date) -> list[Noticia]:
        """Obtiene las noticias de Portafolio publicadas en ``target_date``."""

        try:
            listing = self._get_listing()
        except Exception:
            LOGGER.exception("Error al obtener el listado de Portafolio")
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
                LOGGER.exception("Error al procesar noticia de Portafolio: %s", url)
                continue
            if article is not None:
                results.append(article)

        LOGGER.info("Noticias encontradas en %s: %s", self.name, len(results))
        return results

    def _get_listing(self) -> BeautifulSoup:
        """Descarga el listado de noticias económicas de Perú."""

        return fetch_page(PORTAFOLIO)

    def _extract_article_links(
        self,
        html: BeautifulSoup | str,
        target_date: date,
    ) -> list[str]:
        """Extrae URLs de tarjetas cuya fecha coincide exactamente."""

        soup = self._as_soup(html)
        links: list[str] = []
        for card in soup.select(LISTING_CARD_SELECTOR):
            published_date = self._extract_card_date(card)
            if published_date is None:
                LOGGER.warning("Noticia de Portafolio sin fecha confiable")
                continue
            if published_date != target_date:
                continue
            link = self._extract_card_link(card)
            if link is None:
                LOGGER.warning("Noticia de Portafolio sin URL identificable")
                continue
            links.append(link)
        return links

    def _extract_card_date(self, card) -> date | None:
        """Convierte la fecha real de una tarjeta en ``datetime.date``."""

        value = card.get(LISTING_DATE_ATTRIBUTE)
        if value:
            try:
                return datetime.strptime(normalize_text(value), "%Y-%m-%d").date()
            except ValueError:
                LOGGER.warning("Fecha ISO inválida en tarjeta de Portafolio: %s", value)

        node = card.select_one(LISTING_DATE_SELECTOR)
        if node is None:
            return None
        try:
            return datetime.strptime(extract_text(node), "%d.%m.%Y").date()
        except ValueError:
            return None

    def _extract_card_link(self, card) -> str | None:
        """Extrae el enlace al artículo desde el título de la tarjeta."""

        anchor = card.select_one(LISTING_LINK_SELECTOR)
        if anchor is None or not anchor.get("href"):
            return None
        return urljoin(SITE_URL, anchor["href"])

    def _get_article_detail(self, url: str) -> tuple[str, str]:
        """Obtiene título y primer párrafo editorial desde el artículo."""

        soup = fetch_page(url)
        title = extract_text(soup.select_one(ARTICLE_TITLE_SELECTOR))
        paragraph = soup.select_one(ARTICLE_PARAGRAPH_SELECTOR)
        summary = normalize_text(
            paragraph.get_text("", strip=False) if paragraph is not None else ""
        )
        if not title:
            LOGGER.error("No se pudo extraer el título: fuente=%s URL=%s", self.name, url)
        if not summary:
            LOGGER.error("No se pudo extraer el resumen: fuente=%s URL=%s", self.name, url)
        return title, summary

    def _build_news(self, url: str, target_date: date) -> Noticia | None:
        """Construye una noticia usando la bajada real del artículo."""

        title, summary = (
            normalize_text(value) for value in self._get_article_detail(url)
        )
        if not title or not summary:
            LOGGER.warning(
                "Noticia incompleta descartada: fuente=%s URL=%s",
                self.name,
                url,
            )
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
