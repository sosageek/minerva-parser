"""Estrae il contenuto utile da The Booker Prizes"""

import re
from crawl4ai import CrawlResult
from urllib.parse import urlparse, unquote
from .parser import Parser
from .schema import ParsedDocument
from ..utils.cleaning import remove_markup, normalize_whitespace


class BookerParser(Parser):
    """Parser per le pagine di thebookerprizes.com"""

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
        """Prepara selettori e target del parser Booker"""
        super().__init__(
            target_elements=self._TARGET_ELEMENTS,
            excluded_selector=self._EXCLUDED_SELECTORS,
        )

# ---------------------------------- METODI PUBBLICI ----------------------------------

    async def parse(self, url: str, raw_html: str | None = None) -> ParsedDocument:
        """Applica la pipeline di fetching-parsing specifica per thebookerprizes.com"""
        
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
        """Applica pipeline di pulizia specifica al testo markdown"""

        text = "\n".join(line.strip() for line in text.split('\n'))
        text = remove_markup(text)
        text = self._RE_CONSECUTIVE_DUPS.sub(r'\1', text)
        return normalize_whitespace(text).strip()


    def _extract_title(self, result: CrawlResult, url: str) -> str:
        """Estrae il titolo della pagina"""

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
