"""Operaciones comunes de HTTP y extracción HTML.

Este módulo no contiene selectores específicos de ninguna fuente.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

import requests
from bs4 import BeautifulSoup

from news_scraper.config import HEADERS, REQUEST_TIMEOUT


LOGGER = logging.getLogger(__name__)


def fetch_page(url: str, timeout: int = REQUEST_TIMEOUT) -> BeautifulSoup:
    """Descarga una URL y devuelve su HTML como ``BeautifulSoup``."""

    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers=HEADERS,
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.RequestException:
        LOGGER.exception("Error HTTP al acceder a URL: %s", url)
        raise
    return BeautifulSoup(response.text, "html.parser")


def fetch_post_page(
    url: str,
    data: dict[str, str],
    timeout: int = REQUEST_TIMEOUT,
) -> BeautifulSoup:
    """Envía un formulario HTTP y devuelve la respuesta como ``BeautifulSoup``."""

    try:
        response = requests.post(
            url,
            data=data,
            timeout=timeout,
            headers=HEADERS,
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.RequestException:
        LOGGER.exception("Error HTTP al enviar formulario a URL: %s", url)
        raise
    return BeautifulSoup(response.text, "html.parser")


def extract_links(soup: BeautifulSoup, selector: str = "a[href]") -> list[str]:
    """Extrae URLs de enlaces usando un selector CSS configurable."""

    return [link["href"] for link in soup.select(selector) if link.get("href")]


def normalize_text(value: str | None) -> str:
    """Normaliza espacios y saltos de línea de un texto HTML."""

    return re.sub(r"\s+", " ", value or "").strip()


def extract_text(element) -> str:
    """Obtiene texto visible de un elemento y normaliza sus espacios."""

    if element is None:
        return ""
    return normalize_text(element.get_text(" ", strip=True))


def first_valid_paragraph(
    container,
    excluded_selectors: Iterable[str] = (),
) -> str:
    """Devuelve el primer ``p`` no vacío dentro del contenedor indicado.

    El scraper de cada fuente debe pasar el contenedor principal del artículo;
    esta función deliberadamente no busca párrafos en todo el documento.
    """

    if container is None:
        return ""

    excluded = set(excluded_selectors)
    excluded_nodes = [
        node
        for selector in excluded
        for node in container.select(selector)
    ]

    def is_excluded(node) -> bool:
        return any(
            excluded_node is node or excluded_node in node.parents
            for excluded_node in excluded_nodes
        )

    for paragraph in container.select("p"):
        if is_excluded(paragraph):
            continue
        text = extract_text(paragraph)
        if text:
            return text

    # Algunas páginas de Semana Económica entregan el primer fragmento del
    # contenido como texto directo dentro del contenedor, sin envolverlo en
    # un elemento <p>. Nunca se busca un <p> globalmente: solo se inspecciona
    # el contenedor principal recibido por el scraper.
    for text_node in container.find_all(string=True):
        if is_excluded(text_node.parent):
            continue
        text = normalize_text(str(text_node))
        if text:
            return text
    return ""

