import re
from urllib.parse import urlparse, unquote
from .parser import Parser
from .schema import ParsedDocument
from ..utils.cleaning import remove_markup, normalize_whitespace


class NpsParser(Parser):
    """Parser per le pagine di nps.gov

    isola il contenuto gold effettivo ignorando l'interfaccia pesante del cms(?)

    include regole di pulizia specifiche per cancellare breadcrumb vari, modali nascoste sezioni di contatto a fine pagina
    """

    _EXCLUDED_SELECTORS = (
        "#modal-contact-us, .visually-hidden, "
        ".VideoHero, .video-js, .vjs-control-bar, .vjs-menu, "
        ".vjs-modal-dialog, .vjs-text-track-display, "  
        "#touchpoints-survey, .touchpoints-form-wrapper, "
        "#ParkFooter, .ParkFooter, "
        "div.FeatureGrid, div.ContentPromos, .CaptionedImage, "
        "figure.-right, figure.-left, figure.-center, "
        "figcaption, .figcredit, .picture-caption, "
        ".stateListLinks, .stateThumbnail, "
        ".parkListServiceLinks, .combinedStats, .finding-park-search, "
        ".view-filters, .pagination, "             
        "script, style, noscript, iframe"
    )
    _TARGET_ELEMENTS = ["#main", ".MainContent", "[role='main']"]

    # potenzialmente inutili con i giusti excluded selectors ma teniamo come safety net 
    # non si sa mai qualche redattore faccia porcherie nell'editor di testo principale
    _RE_TERMINAL_SECTIONS = re.compile(
        r'^#{1,6}\s+(?:Contact\s+Us|Contact\s+the\s+Park'
        r'|Stay\s+Connected|Related\s+Links|More\s+Information'
        r'|Tools|Downloads?|Last\s+updated|By\s+The\s+Numbers)\s*$',
        re.MULTILINE | re.IGNORECASE,
    )

    _RE_LAST_UPDATED = re.compile(r'^\s*Last\s+updated\s*:?.*$', re.MULTILINE | re.IGNORECASE,)
    _RE_TRAILING_ARTIFACTS = re.compile(r'[\s|>\-]+$')

    _RE_URL_PAREN = re.compile(r'\(https?://(?:[^\s)\\]|\\.)+\)')
    _RE_URL_BARE  = re.compile(r'https?://(?:[^\s)\\]|\\.)*[^\s)\\.,;:!?]')

    _RE_IMAGE_ALT = re.compile(r'^!.*$', re.MULTILINE)
    _RE_SYMBOL_ONLY_LINE = re.compile(r'^[\s\ufeff/;.,\-\d]+$', re.MULTILINE)

    _RE_TITLE_SUFFIX = re.compile(
        r'\s*[-–|]\s*\(?\s*U\.?S\.?\s+National\s+Park\s+Service\)?\s*$',
        re.IGNORECASE,
    )
    _RE_TITLE_SUFFIX_PLAIN = re.compile(
        r'\s*\(\s*U\.?S\.?\s+National\s+Park\s+Service\s*\)\s*$',
        re.IGNORECASE,
    )

    def __init__(self):
            super().__init__(
                excluded_selector=self._EXCLUDED_SELECTORS,
                target_elements=self._TARGET_ELEMENTS,
            )

    async def parse(self, url: str, raw_html: str | None = None) -> ParsedDocument:
        result = await self._fetch(url, raw_html=raw_html)
        final_url = url if raw_html is not None else (getattr(result, "url", None) or url)

        return ParsedDocument(
            url=final_url,
            domain=urlparse(final_url).netloc,
            title=self._extract_title(result, final_url),
            html_text=result.cleaned_html,
            parsed_text=self.normalize(result.markdown),
        )

    def normalize(self, text: str) -> str:
        text = self._truncate_terminal_sections(text)
        text = self._RE_LAST_UPDATED.sub('', text)
        text = self._RE_IMAGE_ALT.sub('', text)
        text = self._remove_urls(text)
        text = remove_markup(text)
        text = self._RE_SYMBOL_ONLY_LINE.sub('', text)
        text = self._RE_TRAILING_ARTIFACTS.sub('', text)
        text = normalize_whitespace(text)
        return text.strip()

    def _truncate_terminal_sections(self, text: str) -> str:
        """Tronca alle sezioni terminali tipiche di nps.gov (Contact Us, ecc)"""
        return self._RE_TERMINAL_SECTIONS.split(text, maxsplit=1)[0]

    def _remove_urls(self, text: str) -> str:
        """Cancella url residui"""
        text = self._RE_URL_PAREN.sub('', text)
        text = self._RE_URL_BARE.sub('', text)
        return text

    def _extract_title(self, result, url: str) -> str:
        """Estrae il titolo della pagina

        * preferisce il contenuto del tag ``<title>`` html
        (perché a quanto pare gli url di nps.gov sono opachi a differenza di wikipedia)
        * rimuove il suffisso ricorrente U.S. National Park Service

        se il titolo non è disponibile usa ultimo segmento del path come fallback
        """
        metadata = getattr(result, "metadata", None)
        title = metadata.get("title") if isinstance(metadata, dict) else None

        if title:
            title = self._RE_TITLE_SUFFIX_PLAIN.sub('', title)
            title = self._RE_TITLE_SUFFIX.sub('', title)
            title = title.strip()
            if title:
                return title

        path = urlparse(url).path
        last = path.rstrip("/").rsplit("/", 1)[-1] or ""
        if "." in last:
            last = last.rsplit(".", 1)[0]
        last = unquote(last).replace("_", " ").replace("-", " ").strip()
        return last or "(nps.gov)"
