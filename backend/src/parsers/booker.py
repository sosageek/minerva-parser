import re
from crawl4ai import CrawlResult
from urllib.parse import urlparse, unquote
from .parser import Parser
from .schema import ParsedDocument
from ..utils.cleaning import remove_markup, normalize_whitespace


class BookerParser(Parser):
    """Parser per le pagine di thebookerprizes.com

    * isola il contenuto editoriale di news, profili autori e schede libro nel ``main`` (e ``main-page-content`` quando il template lo usa)
    * scarta i widget promozionali: teaser grid, carousel youtube/slice/media, asymmetric/vertical teaser, ...

    gli excluded selectors vengono passati direttamente a crawl4ai (non via beautiful soup come per wikipedia) perché qui i nodi da rimuovere sono section block-level e non mangiano il tail text adiacente

    in `normalize` include regole di pulizia per il rumore di formattazione che il md converter di crawl4ai lascia
    """

# ---------------------------------- SELETTORI ----------------------------------

    _TARGET_ELEMENTS = ["main", "main-page-content"]

    _EXCLUDED_SELECTORS = (
        "figcaption, "
        ".cookies-banner, .newsletter-signup-block, "
        "#block-views-block-related-features-related-features-other, "
        "#block-views-block-related-features-related-features-feature, "
        ".share-icons, .social-share, "
        ".c-path, .breadcrumb, .hidden, "
        ".relative.z-20.container.mb-4, "
        ".relative.z-20.container.mb-3, "
        ".col-span-full.relative.mt-12, "
        ".paragraph--type--slice-teaser, "
        ".paragraph--type--slice-media, "
        ".paragraph--type--asymmetric-teaser, "
        ".paragraph--type--vertical-teaser, "
        ".paragraph--type--youtube-carousel, "
        ".paragraph--type--slice-carousel, "
        "[data-js-related-carousel], "
        ".book_selling_form, "
        ".c-modal, .flickity-button, .sr-only, .c-media, .c-carousel"
    )

# ------------------------------------ REGEX -------------------------------------

    _RE_CONSECUTIVE_DUPS = re.compile(r'^(.+)(\n\1)+$', re.MULTILINE)

    def __init__(self):
        super().__init__(
            target_elements=self._TARGET_ELEMENTS,
            excluded_selector=self._EXCLUDED_SELECTORS,
        )

# ---------------------------------- METODI PUBBLICI ----------------------------------

    async def parse(self, url: str, raw_html: str | None = None) -> ParsedDocument:
        """Applica la pipeline di fetching-parsing specifica per thebookerprizes.com
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
        final_url = url if raw_html is not None else (getattr(result, "url", None) or url)

        return ParsedDocument(
            url=final_url,
            domain=urlparse(url).netloc,
            title=self._extract_title(result, final_url),
            html_text=result.cleaned_html,
            parsed_text=self.normalize(result.markdown or ""),
        )

    
    def normalize(self, text: str) -> str:
        """Applica pipeline di pulizia specifica al testo markdown
        estratto da una pagina thebookerprizes.com con crawl4ai

        include lo strip per riga (il template del cms indenta tutto), la rimozione del markup md residuo, il dedup di righe consecutive identiche (i widget ripetono headline + cta vicine) e la normalizzazione finale dello whitespace

        Args:
            text(str): testo markdown grezzo generato da crawl4ai

        Returns:
            stringa di testo markdown normalizzato
        """

        text = "\n".join(line.strip() for line in text.split('\n'))
        text = remove_markup(text)
        text = self._RE_CONSECUTIVE_DUPS.sub(r'\1', text)
        return normalize_whitespace(text).strip()


    def _extract_title(self, result: CrawlResult, url: str) -> str:
        """Estrae il titolo della pagina

        * preferisce il contenuto del tag ``<title>`` html
        * se il titolo non è disponibile usa l'ultimo segmento del path come fallback
        (che su thebookerprizes non è particolarmente opaco)

        Args:
            result(CrawlResult): risultato di crawl4ai con il metadata del tag ``<title>``
            url(str): URL completo della pagina (usato come fallback)

        Returns:
            il titolo della pagina pulito dal suffisso, o un fallback estratto dall' URL
        """

        metadata = getattr(result, "metadata", None)
        title = metadata.get("title") if isinstance(metadata, dict) else None

        if title:
            title = title.split('|', 1)[0].strip()
            if title:
                return title

        path = urlparse(url).path
        last = path.rstrip("/").rsplit("/", 1)[-1] or ""
        last = unquote(last).replace("_", " ").replace("-", " ").strip()
        return last or "(thebookerprizes.com)"
