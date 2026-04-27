import re
from crawl4ai import CacheMode, CrawlerRunConfig, CrawlResult
from urllib.parse import urlparse, unquote
from .parser import Parser
from .schema import ParsedDocument
from ..utils.cleaning import remove_markup, normalize_whitespace


class MeteoAmParser(Parser):
    """Parser per pagine di meteoam

    * isola il contenuto
    * scarta header articolo, side col, gallerie immagini, moduli potrebbe piacerti anche / articoli recenti 
    """

# ---------------------------------- SELETTORI ----------------------------------

    _EXCLUDED_SELECTORS = (
        "a.news-details-header-go-back, "
        "div.news-details-side-col, "
        "section[data-wcs-title='Potrebbe piacerti anche'], "
        "section[data-wcs-title='Articoli recenti'], "
        "section[data-web-app='EditorImageGallery'], "
        "section[data-web-app='ArticleHeader'], "
        # banner cookie iubenda: su GS sta già fuori da
        # section#details_news_page, qui serve solo per fallback (Mazz)
        "#iubenda-cs-banner, "
        ".iubenda-cs-container, "
        "[id^='iubenda-cs']"
    )
    _TARGET_ELEMENTS = ["section#details_news_page"]

# ---------------------------------- REGEX ----------------------------------

    #se articoli correlati e photo gallery resistono alla rimozione da excluded selectors
    _RE_RELATED = re.compile(
        r'Potrebbe piacerti anche.*',
        re.DOTALL | re.IGNORECASE,
    )
    _RE_BACK_LINK = re.compile(r'←\s*Torna agli articoli\s*\n?', re.IGNORECASE)
    _RE_GALLERY = re.compile(r'^Galleria Fotografica\s*\n?', re.MULTILINE | re.IGNORECASE)

    # widget satellite (vedi /meteosat): titolo CMS + heading "Caricamento Dati"
    # + timestamp dinamico GMT+n + "Refresh automatico attivo" + slide indicator
    # del carousel. Tutti dinamici, non sono nel gold. (Mazz)
    _RE_WIDGET_TITLE = re.compile(r'^Widget semplice con gallerie multiple\s*$', re.MULTILINE)
    _RE_LOADING = re.compile(r'^#####\s*Caricamento Dati\s*$', re.MULTILINE)
    _RE_TIMESTAMP = re.compile(
        r'^\d{1,2}\s+[a-zA-Z]+\s+\d{4},\s*\d{1,2}:\d{2}(?::\d{2})?\s*GMT[+\-]\d+\s*$',
        re.MULTILINE,
    )
    _RE_REFRESH = re.compile(r'^\(Refresh automatico attivo\)\s*$', re.MULTILINE)
    _RE_SLIDE = re.compile(
        # niente ^$ anchors: catturiamo il pattern ovunque sia, anche con
        # leading/trailing junk. IGNORECASE per AM/PM/UTC/utc.
        r'\d{1,2}/\d{1,2}:\s*\d{1,2}\s+[a-zA-Z]+\s+\d{4}\s*\|\s*\d{1,2}:\d{2}\s*(?:AM|PM)\s*UTC',
        re.IGNORECASE,
    )
    # i gold di meteoam non usano i marker ## per i sottotitoli, li strippiamo
    # mantenendo solo il testo. cattura anche i casi orfani (## su riga vuota)
    _RE_HEADING_MARK = re.compile(r'^#{1,6}[ \t]*', re.MULTILINE)

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

# ---------------------------------- METODI PUBBLICI -------------------------------

    async def parse(self, url: str, raw_html: str | None = None) -> ParsedDocument:
        """Applica la pipeline di parsing

        Args:
            url(str): pagina da scaricare
            raw_html(str | None): HTML sorgente opzionale

        Returns:
            istanza di ParsedDocument con url, domain, title, html_text e parsed_text

        Raises:
            CrawlError: se il fetch della pagina fallisce (lo lancia la chiamata interna a ``_fetch``)
        """

        # /meteosat ha 5 widget gallery che si idratano lato client: senza delay
        # mancano i loro <h2>. Solo qui paghiamo 3s, gli altri URL restano veloci. (Mazz)
        self.crawler_config.delay_before_return_html = 3.0 if "/meteosat" in url else 0
        result = await self._fetch(url, raw_html=raw_html)

        #a pagine non-articolo target_elements filtra tutto e il markdown esce vuoto.
        # rifacciamo giro senza target restrittivi, tenendo solo gli excluded selectors
        if not (result.markdown or "").strip():
            result = await self._fetch(url, raw_html=raw_html, config=self._fallback_config())

        return ParsedDocument(
            url=url,
            domain=urlparse(url).netloc,
            title=self._extract_title(result, url),
            html_text=result.html,
            parsed_text=self.normalize(result.markdown),
        )

    def normalize(self, text: str) -> str:
        """Applica pipeline di pulizia al testo markdown

        include rimozione del link "torna agli articoli", il taglio della coda "potrebbe piacerti anche" residua,
        cancellazione del sottotitolo "Galleria Fotografica" rimasto orfano e la pulizia del markup md generale

        Args:
            text(str): testo markdown grezzo da crawl4ai

        Returns:
            stringa di testo normalizzato
        """

        # crawl4ai a volte mette nbsp (\xa0) che NON viene matchato da \s in alcune
        # combinazioni regex: formatta a spazio ascii per sicurezza (Mazz)
        text = text.replace('\xa0', ' ')
        text = self._RE_BACK_LINK.sub('', text)
        text = self._RE_RELATED.sub('', text)
        text = self._RE_GALLERY.sub('', text)
        text = self._RE_WIDGET_TITLE.sub('', text)
        text = self._RE_LOADING.sub('', text)
        text = self._RE_TIMESTAMP.sub('', text)
        text = self._RE_REFRESH.sub('', text)
        text = self._RE_SLIDE.sub('', text)
        text = self._RE_HEADING_MARK.sub('', text)
        text = remove_markup(text)
        text = normalize_whitespace(text)
        return text.strip()
    


    def _fallback_config(self) -> CrawlerRunConfig:
        """Config alternativa per pagine meteoam senza section#details_news_page

        nota: stessi excluded selectors e stessi excluded tags della config principale,
        ma target_elements vuoto così crawl4ai estrae tutto il body al netto di nav/aside

        Returns:
            CrawlerRunConfig da usare come secondo tentativo se primo torna vuoto
        """

        return CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            excluded_tags=["nav", "header", "footer", "aside"],
            word_count_threshold=10,
            remove_forms=True,
            excluded_selector=self._EXCLUDED_SELECTORS,
        )

    def _extract_title(self, result: CrawlResult, url: str) -> str:
        """Estrae il titolo della pagina

        * preferisce il contenuto del tag ``<title>`` html
        * rimuove brand Meteo Aeronautica Militare sia che se prefisso sia se suffisso
        * fallback sull'ultimo segmento del path

        Args:
            result(CrawlResult): risultato di crawl4ai con metadata del tag <title>
            url(str): URL completo della pagina (usato come fallback)

        Returns:
            titolo della pagina pulito dal brand, o fallback estratto dall'URL
        """

        metadata = getattr(result, "metadata", None)
        title = metadata.get("title") if isinstance(metadata, dict) else None

        if title:
            title = self._RE_TITLE_BRAND.sub('', title).strip()
            if title:
                return title

        slug = unquote(urlparse(url).path.rstrip('/').split('/')[-1])
        slug = re.sub(r'-\d{8}$', '', slug)  # toglie suffisso data ISO (es. "-20250422") (Mazz)
        slug = slug.replace('--', ': ')  # "--" negli slug meteoam codifica ": " nel titolo originale
        slug = slug.replace('-', ' ').strip()
        return slug or "(meteoam.it)"
