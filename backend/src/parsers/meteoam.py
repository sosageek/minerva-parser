import re
from crawl4ai import CrawlResult
from urllib.parse import urlparse, unquote
from .parser import Parser
from .schema import ParsedDocument
from ..utils.cleaning import remove_markup, normalize_whitespace


class MeteoAmParser(Parser):
    """Parser per le pagine di meteoam.it

    * isola il contenuto editoriale degli articoli news
    * scarta header articolo, side col, gallerie immagini e i moduli potrebbe piacerti anche / articoli recenti

    gli excluded selectors vengono passati direttamente a crawl4ai (non via beautiful soup come per wikipedia) perché qui i nodi da rimuovere sono section/div ben delimitati e non mangiano il tail text adiacente
    """

# ---------------------------------- SELETTORI ----------------------------------

    _EXCLUDED_SELECTORS = (
        "a.news-details-header-go-back, "
        "div.news-details-side-col, "
        "section[data-wcs-title='Potrebbe piacerti anche'], "
        "section[data-wcs-title='Articoli recenti'], "
        "section[data-web-app='EditorImageGallery'], "
        "section[data-web-app='ArticleHeader']"
    )
    _TARGET_ELEMENTS = ["section#details_news_page"]

# ------------------------------------ REGEX -------------------------------------

    # safety net se articoli correlati e photo gallery dovessero resistere alla rimozione degli excluded selectors
    _RE_RELATED = re.compile(
        r'Potrebbe piacerti anche.*',
        re.DOTALL | re.IGNORECASE,
    )
    _RE_BACK_LINK = re.compile(r'←\s*Torna agli articoli\s*\n?', re.IGNORECASE)
    _RE_GALLERY = re.compile(r'^Galleria Fotografica\s*\n?', re.MULTILINE | re.IGNORECASE)

    _RE_TITLE_BRAND = re.compile(
        r'^\s*Meteo\s+Aeronautica\s+Militare\s*\|\s*'
        r'|\s*\|\s*Meteo\s+Aeronautica\s+Militare\s*$',
        re.IGNORECASE,
    )

    def __init__(self):
        super().__init__(
            excluded_selector=self._EXCLUDED_SELECTORS,
            target_elements=self._TARGET_ELEMENTS
        )

# ---------------------------------- METODI PUBBLICI ----------------------------------

    async def parse(self, url: str, raw_html: str | None = None) -> ParsedDocument:
        """Applica la pipeline di fetching-parsing specifica per meteoam.it
        a partire dall'url o dall'html della pagina

        Args:
            url(str): url della pagina da scaricare
            raw_html(str | None): HTML sorgente opzionale

        Returns:
            istanza di ``ParsedDocument`` con ``url``, ``domain``, ``title``, ``html_text`` e ``parsed_text``

        Raises:
            CrawlError: se il fetch della pagina fallisce (lo lancia la chiamata interna a ``_fetch``)
        """

        result = await self._fetch(url, raw_html=raw_html)

        return ParsedDocument(
            url=url,
            domain=urlparse(url).netloc,
            title=self._extract_title(result, url),
            html_text=result.html,
            parsed_text=self.normalize(result.markdown),
        )

    def normalize(self, text: str) -> str:
        """Applica pipeline di pulizia specifica al testo markdown
        estratto da una pagina meteoam.it con crawl4ai

        include la rimozione del link "torna agli articoli", il taglio della coda "potrebbe piacerti anche" residua, la cancellazione del sottotitolo "Galleria Fotografica" rimasto orfano e la pulizia del markup md generale

        Args:
            text(str): testo markdown grezzo generato da crawl4ai

        Returns:
            stringa di testo normalizzato
        """

        text = self._RE_BACK_LINK.sub('', text)
        text = self._RE_RELATED.sub('', text)
        text = self._RE_GALLERY.sub('', text)
        text = remove_markup(text)
        text = normalize_whitespace(text)
        return text.strip()
    
# ---------------------------------- HELPER PRIVATI ----------------------------------

    def _extract_title(self, result: CrawlResult, url: str) -> str:
        """Estrae il titolo della pagina

        * preferisce il contenuto del tag ``<title>`` html
        * rimuove il brand Meteo Aeronautica Militare sia che se prefisso sia se suffisso
        * fallback sull'ultimo segmento del path

        Args:
            result(CrawlResult): risultato di crawl4ai con il metadata del tag ``<title>``
            url(str): URL completo della pagina (usato come fallback)

        Returns:
            il titolo della pagina pulito dal brand, o un fallback estratto dall'URL
        """

        metadata = getattr(result, "metadata", None)
        title = metadata.get("title") if isinstance(metadata, dict) else None

        if title:
            title = self._RE_TITLE_BRAND.sub('', title).strip()
            if title:
                return title

        slug = unquote(urlparse(url).path.rstrip('/').split('/')[-1])
        slug = slug.replace('--', ': ')  # "--" negli slug meteoam codifica ": " nel titolo originale
        slug = slug.replace('-', ' ').strip()
        return slug or "(meteoam.it)"
