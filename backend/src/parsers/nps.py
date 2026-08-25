"""Estrae il contenuto utile da National Park Service"""

import re
from crawl4ai import CrawlResult
from urllib.parse import urlparse, unquote
from .parser import Parser
from .schema import ParsedDocument
from ..utils.cleaning import remove_markup, normalize_whitespace


class NpsParser(Parser):
    """Parser per le pagine di nps.gov"""
# ---------------------------------- SELETTORI ----------------------------------

    _EXCLUDED_SELECTORS = (
        "#modal-contact-us, .visually-hidden, "
        ".VideoHero, .video-js, .vjs-control-bar, .vjs-menu, .vjs-modal-dialog, .vjs-text-track-display, "
        "#touchpoints-survey, .touchpoints-form-wrapper, "
        "#back_button_container, .return-button, "
        "#ParkFooter, .ParkFooter, "
        "#CS_Element_FeatureContainer, .ContentPromos, .CarouselGallery, .RelatedGrid, .CS_Element_Layout .FeatureGrid, "
        ".CaptionedImage, figure.-right, figure.-left, figure.-center, figcaption, .figcredit, .picture-caption, "
        ".stateListLinks, .stateThumbnail, .parkListServiceLinks, .combinedStats, .finding-park-search, "
        ".view-filters, .pagination, .SharedContentTags, .info-micro-filter, .ListingResults-loading, .FilterTags, .ResultsFooter, .resultsPaginationArea, #nps-calendar, "
        "img, picture, svg, "
        "script, style, noscript, iframe"
    )
    _TARGET_ELEMENTS = ["#main", ".MainContent", "[role='main']"]

# ----------------------------------- REGEX ------------------------------------

    # potenzialmente inutili con i giusti excluded selectors ma teniamo come safety net 
    # non si sa mai qualche redattore faccia porcherie nell'editor di testo principale
    # edit: lo fanno (gabriele)
    _RE_TERMINAL_SECTIONS = re.compile(
        r'^#{1,6}\s+(?:Contact\s+Us|Contact\s+the\s+Park'
        r'|Stay\s+Connected|Related\s+Links|(?:For\s+)?More\s+Information'
        r'|Tools|Downloads?|Last\s+updated|By\s+The\s+Numbers'
        r'|_*Tags?|You\s+Might\s+Also\s+Like|Calendar\s+of\s+Events)\s*$',
        re.MULTILINE | re.IGNORECASE,
    )

    _RE_LAST_UPDATED = re.compile(r'^\s*Last\s+updated\s*:?.*$', re.MULTILINE | re.IGNORECASE,)
    _RE_INLINE_TAGS = re.compile(r'^\s*Tags\s*:.*$', re.MULTILINE | re.IGNORECASE)
    _RE_TRAILING_ARTIFACTS = re.compile(r'[\s|>\-]+$') # volutamente senza flag multiline perché è cleanup di coda documento
    _RE_FUSED_HEADING = re.compile(r'(?<=\S)(#{1,6})\s*')
    
    _RE_JUNK_PROMOS = re.compile( # le inseriscono anche come plain text nei paragrafi, non hanno pudore
        r'^\s*#*\s*(?:Follow\s+Us\s+on\s+Social\s+Media|Download\s+the\s+NPS\s+App).*\n.*\n?', 
        re.MULTILINE | re.IGNORECASE
    )
    _RE_VIEW_DETAILS = re.compile(r'^\s*View\s+Details\s*$', re.MULTILINE | re.IGNORECASE)
    _RE_STRAY_HASH = re.compile(r'\s+#+\s*$', re.MULTILINE)

    _RE_URL_PAREN = re.compile(r'\(https?://(?:[^\s)\\]|\\.)+\)')
    _RE_URL_BARE  = re.compile(r'https?://(?:[^\s)\\]|\\.)*[^\s)\\.,;:!?]')

    _RE_IMAGE_ALT = re.compile(r'^!.*$', re.MULTILINE)
    _RE_SYMBOL_ONLY_LINE = re.compile(r'^[\s\ufeff/;.,\-\d\[\]]+$', re.MULTILINE)

    _RE_TITLE_SUFFIX = re.compile(
        r'\s*[-–|]\s*\(?\s*U\.?S\.?\s+National\s+Park\s+Service\)?\s*$',
        re.IGNORECASE,
    )
    _RE_TITLE_SUFFIX_PLAIN = re.compile(
        r'\s*\(\s*U\.?S\.?\s+National\s+Park\s+Service\s*\)\s*$',
        re.IGNORECASE,
    )


    def __init__(self):
        """Prepara selettori e target del parser NPS"""
        super().__init__(
            excluded_selector=self._EXCLUDED_SELECTORS,
            target_elements=self._TARGET_ELEMENTS,
        )

# ---------------------------------- METODI PUBBLICI ----------------------------------

    async def parse(self, url: str, raw_html: str | None = None) -> ParsedDocument:
        """Applica la pipeline di fetching-parsing specifica per nps.gov"""

        result = await self._fetch(url, raw_html=raw_html)
        final_url = url if raw_html is not None else (getattr(result, "url", None) or url)

        return ParsedDocument(
            url=final_url,
            domain=urlparse(final_url).netloc,
            title=self._extract_title(result, final_url),
            html_text=result.cleaned_html,
            parsed_text=self.normalize(result.markdown or ""),
        )


    def normalize(self, text: str) -> str:
        """Applica pipeline di pulizia specifica al testo markdown"""

        text = self._RE_TERMINAL_SECTIONS.split(text, maxsplit=1)[0]
        text = self._RE_LAST_UPDATED.sub('', text)
        text = self._RE_INLINE_TAGS.sub('', text)
        text = self._RE_IMAGE_ALT.sub('', text)
        text = self._RE_FUSED_HEADING.sub(r'\n\1 ', text)
        text = self._remove_urls(text)
        text = remove_markup(text)
        text = self._RE_JUNK_PROMOS.sub('', text)
        text = self._RE_VIEW_DETAILS.sub('', text)
        text = self._RE_STRAY_HASH.sub('', text)
        text = self._RE_SYMBOL_ONLY_LINE.sub('', text)
        text = self._RE_TRAILING_ARTIFACTS.sub('', text)
        text = normalize_whitespace(text)
        return text.strip()


# ---------------------------------- HELPER PRIVATI ----------------------------------

    def _remove_urls(self, text: str) -> str:
        """Cancella URL residui sia tra parentesi tonde sia nudi nel testo"""

        text = self._RE_URL_PAREN.sub('', text)
        text = self._RE_URL_BARE.sub('', text)
        return text


    def _extract_title(self, result: CrawlResult, url: str) -> str:
        """Estrae il titolo della pagina"""

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
