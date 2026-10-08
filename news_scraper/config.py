"""Configuración centralizada de la aplicación."""

import os
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "output"
OUTPUT_FILE = OUTPUT_DIR / "noticias.xlsx"

# Ruta raíz del perfil de datos de Chrome que contiene las sesiones autenticadas.
# Se configura fuera del repositorio para no versionar cookies ni credenciales.
_chrome_user_data_dir = os.getenv("NEWS_CHROME_USER_DATA_DIR")
CHROME_USER_DATA_DIR = (
    Path(_chrome_user_data_dir).expanduser()
    if _chrome_user_data_dir
    else None
)

DATE_FORMAT = "%d/%m/%Y"
REQUEST_TIMEOUT = 20
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
}

SEMANA_ECONOMICA_SECTORES = "https://semanaeconomica.com/sectores-empresas"
DIARIO_FINANCIERO = (
    "https://www.df.cl/noticias/site/cache/search/pags/search17914820211745263.html"
)
DIARIO_FINANCIERO_SEARCH_URL = "https://www.df.cl/cgi-bin/prontus_search.cgi"
DIARIO_FINANCIERO_SEARCH_TERM = "Perú"
PORTAFOLIO = "https://www.portafolio.co/noticias-economicas/peru"
SEMANA_ECONOMICA_INDICE = "https://semanaeconomica.com/que-esta-pasando/indice"
GESTION = "https://visor.peruquiosco.pe/diario-gestion"

SOURCES = {
    "Semana Económica": SEMANA_ECONOMICA_SECTORES,
    "Semana Económica - Sectores y Empresas": SEMANA_ECONOMICA_SECTORES,
    "Diario Financiero": DIARIO_FINANCIERO,
    "Portafolio": PORTAFOLIO,
    "Semana Económica - Índice": SEMANA_ECONOMICA_INDICE,
    "Diario Gestión": GESTION,
}

