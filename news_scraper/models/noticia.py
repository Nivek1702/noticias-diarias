"""Modelo normalizado de una noticia."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class Noticia:
    """Noticia normalizada, independiente de HTML, HTTP y Excel."""

    dia: date
    fuente: str
    titulo: str
    parrafo: str
    url: str = ""

    def duplicate_key(self) -> tuple[date, str, str]:
        """Devuelve la clave inicial para detectar duplicados."""

        return (self.dia, self.fuente, self.titulo)

