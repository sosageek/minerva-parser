import re
from urllib.parse import urlparse
from .parser import Parser
from .schema import ParsedDocument
from ..utils.cleaning import remove_markup, normalize_whitespace


class BookerParser(Parser):

    # ---------------------------------- SELETTORI ----------------------------------
      #aggiunto altri selector dopo aver ispezionato ulteriormente il dominio, che permettono
      #di eliminare blocchi interi di caroselli di immagini7video, link affiliati, e varia pubblicita 
      #semplificando il codice 

    _TARGET_ELEMENTS = ["main", "main-page-content"]

    _EXCLUDED_SELECTORS = (
        "nav, footer, header, aside, figcaption,"
        ".cookies-banner, .newsletter-signup-block, "
        "#block-views-block-related-features-related-features-other,"
        "#block-views-block-related-features-related-features-feature,"
        ".share-icons, .social-share,"
        ".section.youtube-carousel, .c-path, .breadcrumb, .hidden,"
        ".relative.z-20.container.mb-4,"
        ".relative.z-20.container.mb-3,"
        ".col-span-full.relative.mt-12,"
        ".paragraph--type--slice-teaser,"
        ".paragraph--type--slice-media,"
        ".paragraph--type--asymmetric-teaser,"
        ".paragraph--type--vertical-teaser,"
        ".paragraph--type--youtube-carousel,"
        ".paragraph--type--slice-carousel,"
        ".book_selling_form, .book-selling-retailers, .book-selling-formats, "
        ".c-modal, .flickity-button, .sr-only, .c-media, .c-carousel"
    )

# ------------------------------------ REGEX -------------------------------------

    _RE_URL = re.compile(r'https?://\S+')

    def __init__(self):
        super().__init__(
            target_elements=self._TARGET_ELEMENTS,
            excluded_selector=self._EXCLUDED_SELECTORS,
        )

# ---------------------------------- METODI PUBBLICI ----------------------------------

    async def parse(self, url: str) -> ParsedDocument:
        result = await self._fetch(url)

        title = result.metadata.get('title', '')
        if not title or "|" in title:
            m = re.search(r'<h1[^>]*>(.*?)</h1>', result.html, re.DOTALL | re.IGNORECASE)
            if m:
                title = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        return ParsedDocument(
            url=url,
            domain=urlparse(url).netloc,
            title=title,
            html_text=result.cleaned_html,
            parsed_text=self.normalize(result.markdown),
        )

    def normalize(self, text: str) -> str:
        if not text:
            return ""
        
        text = "\n".join(line.strip() for line in text.split('\n'))

        text = remove_markup(text)
        text = re.sub(r'^(.+)(\n\1)+$', r'\1', text, flags=re.MULTILINE)
        text = self._RE_URL.sub('', text)
        text = text.replace("—", "-")
        text = text.replace("#", "").replace("*", "").replace("_", "").replace(">", "")
        text = text.replace("’", "'").replace('‘', "'")

        return normalize_whitespace(text).strip()