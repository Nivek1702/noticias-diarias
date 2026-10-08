# Automatización de búsqueda y extracción de noticias

Aplicación base en Python para buscar diariamente noticias en cinco fuentes,
entrar a la página individual de cada noticia, extraer el título y el contenido
solicitado, guardar los resultados en `output/noticias.xlsx` y generar un PDF
por noticia en la carpeta de la fecha de ejecución.

La arquitectura se mantiene modular y los selectores HTML se implementan
fuente por fuente. Ya están implementadas y probadas las fuentes de Semana
Económica, Diario Financiero y Portafolio; Gestión continúa como punto de
extensión pendiente.

El modelo `Noticia` utiliza `date` para `dia`. La conversión a `DD/MM/YYYY`
se realiza únicamente al escribir en Excel.

Los módulos implementados de `sources/` cumplen el contrato común y tienen
separados los pasos de listado y detalle. Los selectores se inspeccionan de
forma independiente para cada sitio.

### Investigación: Semana Económica – Sectores y Empresas

La estructura real inspeccionada utiliza:

| Elemento | Selector/estrategia |
| --- | --- |
| Tarjeta del listado | `.se-card` |
| Fecha | `.se-card__date` |
| Enlace | `a[href*="/sectores-empresas/"]`, excluyendo la ruta base y enlaces de sector/tag |
| Título individual | `h1.se-article__title` |
| Contenedor del artículo | `.js-se-content` |
| Resumen individual | `.se-article__excerpt` |
| Paginación | `?category_id=1&page=N#sectores`, con límite de páginas y parada por falta de URLs nuevas/fechas anteriores |

Para Semana Económica, el campo `parrafo` se llena con el resumen/entradilla
de la página individual (`.se-article__excerpt`), según la decisión específica
de esta fuente. No se utiliza el resumen del listado ni se intenta evadir el
paywall.

### Investigación: Semana Económica – Qué está pasando

Esta fuente utiliza una página diaria con el formato
`/que-esta-pasando/indice/DD-MM-YYYY`; no requiere paginación numérica.

| Elemento | Selector/estrategia |
| --- | --- |
| Tarjeta del listado | `.se-card--horizontal` |
| Fecha | `.se-card__date` |
| Título del listado | `.se-card__title` |
| Enlace | `a[href*="/que-esta-pasando/articulos/"]` |
| Resumen del listado | `.se-card__excerpt` |
| Título individual | `h1.se-article__title` |
| Resumen individual | `.se-article__excerpt` |

El scraper usa el listado para fecha y URL, pero obtiene el título y el
resumen desde la página individual. El campo `parrafo` contiene la bajada o
entradilla, no el primer párrafo del cuerpo.

### Investigación: Diario Financiero

La URL de búsqueda cacheada indicada inicialmente puede caducar y actualmente
responde 404. Por ello, el scraper utiliza el formulario de búsqueda estable de
Diario Financiero mediante `POST` a `/cgi-bin/prontus_search.cgi`, enviando el
término `Perú`.

| Elemento | Selector/estrategia |
| --- | --- |
| Tarjeta del listado | `article.card.card__horizontal` |
| Fecha | `.card__date[data-date]`, formato `YYYYMMDD` |
| Enlace | Enlace que contiene `.card__title` |
| Título individual | `.enc-main__title` |
| Resumen individual | `.enc-main__description` |

El listado se usa para identificar las noticias de la fecha solicitada y sus
URLs. El título y el `parrafo` se extraen desde cada página individual; el
`parrafo` corresponde al resumen/bajada, no al primer párrafo del cuerpo.

### Investigación: Portafolio – Noticias Económicas de Perú

La página de categoría entrega las noticias en HTML estático y no mostró
paginación en la inspección realizada. Se encontraron 16 tarjetas ordenadas
por fecha descendente.

| Elemento | Selector/estrategia |
| --- | --- |
| Tarjeta del listado | `.c-articulo--mini-md` |
| Fecha | Atributo `data-publicacion` en formato `YYYY-MM-DD` |
| Enlace y título del listado | `a.c-articulo__titulo__txt[href]` |
| Título individual | `h1.c-articulo__titulo` |
| Primer párrafo editorial individual | `.c-cuerpo > div.paragraph` |

El listado no contiene una bajada completa. Por eso, Portafolio obtiene el
título y el primer párrafo editorial desde la página individual. La bajada
`h2.c-lead__titulo` no se utiliza. La fecha se toma estrictamente del atributo de la tarjeta y
solo se procesan las URLs cuya fecha coincide con `target_date`.

## Arquitectura

- `main.py`: orquesta las fuentes, valida resultados y actualiza Excel.
- `config.py`: URLs, rutas y parámetros comunes.
- `sources/`: un módulo independiente por fuente y la interfaz abstracta `NewsSource`.
- `models/`: modelo normalizado `Noticia`.
- `services/extractor.py`: HTTP y utilidades HTML reutilizables.
- `services/validator.py`: validación y deduplicación.
- `services/excel.py`: lectura y escritura exclusiva del archivo Excel.
- `services/pdf.py`: extracción del contenedor editorial y generación de PDFs con Chrome o Edge usando un perfil autenticado.
- `tests/`: pruebas unitarias reproducibles, sin depender de páginas reales.

Todas las fuentes implementan `NewsSource`, con las operaciones públicas
`name` y `get_news(target_date)`. Cada scraper mantiene separados los pasos
`_get_listing()`, `_extract_article_links()` y `_get_article_detail()` para
que el orquestador no dependa de la estructura HTML de cada sitio.

Los PDFs se guardan en `output/DD-MM-YYYY/`, donde la carpeta corresponde a la
fecha en que se ejecuta la automatización. El nombre de cada archivo es el
título de la noticia, sanitizado para Windows. La exportación imprime solo el
contenedor editorial de cada fuente y excluye publicidad, paywalls y bloques
de noticias relacionadas.

## Perfil autenticado del navegador

Semana Económica y Diario Financiero pueden mostrar únicamente una vista
previa cuando no existe una sesión iniciada. Para que los PDFs incluyan el
contenido completo, la aplicación utiliza un perfil de datos persistente de
Chrome que debe configurarse localmente.

El perfil debe ser exclusivo para este proyecto y ubicarse fuera del
repositorio y de OneDrive. No se guardan contraseñas en el código: Chrome
conserva localmente las cookies y sesiones iniciadas.

### Preparación inicial en Windows

1. Elige una carpeta local para el perfil. Este es un placeholder; reemplaza
   la ruta por la que utilizarás en tu equipo:

   ```text
   C:\RUTA\LOCAL\NoticiasDiarias\chrome-profile
   ```

2. Abre Chrome usando esa carpeta como perfil de datos:

   ```powershell
   $chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
   & $chrome --user-data-dir="C:\RUTA\LOCAL\NoticiasDiarias\chrome-profile"
   ```

3. En esa ventana, inicia sesión en Google, Semana Económica y Diario
   Financiero. Después cierra Chrome antes de ejecutar la automatización.

4. Configura la variable de entorno en PowerShell, usando la misma ruta:

   ```powershell
   $env:NEWS_CHROME_USER_DATA_DIR = "C:\RUTA\LOCAL\NoticiasDiarias\chrome-profile"
   ```

   La variable debe estar configurada en cada nueva ventana de PowerShell. Si
   deseas conservarla para tu usuario de Windows, puedes establecerla con:

   ```powershell
   [Environment]::SetEnvironmentVariable(
       "NEWS_CHROME_USER_DATA_DIR",
       "C:\RUTA\LOCAL\NoticiasDiarias\chrome-profile",
       "User"
   )
   ```

La ruta configurada es la raíz usada por `--user-data-dir`; no se debe copiar
la subcarpeta `Default` ni una contraseña al repositorio. Si una sesión expira,
la aplicación detiene la ejecución antes de producir PDFs incompletos y será
necesario iniciar sesión nuevamente en ese perfil.

## Fuentes configuradas

1. Semana Económica – Sectores y Empresas
2. Diario Financiero
3. Portafolio – Noticias Económicas de Perú
4. Semana Económica – Qué está pasando / Índice
5. Diario Gestión – Perú Quiosco

## Instalación en Windows PowerShell

Desde la carpeta que contiene `news_scraper`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r .\news_scraper\requirements.txt
```

Si PowerShell bloquea la activación del entorno, se puede ejecutar el Python
del entorno directamente:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\news_scraper\requirements.txt
```

## Ejecución

Con el entorno activado:

```powershell
cd .\news_scraper
python main.py
```

La ejecución requiere que `NEWS_CHROME_USER_DATA_DIR` esté configurada. Si no
lo está, el programa muestra un error indicando que falta el perfil
autenticado.

También puede ejecutarse desde la carpeta raíz del proyecto:

```powershell
python -m news_scraper.main
```

La aplicación crea `output/noticias.xlsx` con las columnas:

```text
dia | fuente | titulo | parrafo
```

La fecha se normaliza como `DD/MM/YYYY` y los duplicados se identifican por
`dia + fuente + titulo`.

## Tests

```powershell
python -m pytest -q -p no:cacheprovider .\news_scraper\tests
```

## Estructura

```text
news_scraper/
├── main.py
├── config.py
├── requirements.txt
├── README.md
├── .gitignore
├── sources/
├── models/
├── services/
├── tests/
└── output/
    └── noticias.xlsx
```

