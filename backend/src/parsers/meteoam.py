import re
from urllib.parse import urlparse, unquote
from .parser import Parser
from .schema import ParsedDocument
from ..utils.cleaning import remove_markup, normalize_whitespace


class MeteoAmParser(Parser):

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

    _RE_RELATED = re.compile(
        r'Potrebbe piacerti anche.*',
        re.DOTALL | re.IGNORECASE,
    )
    _RE_BACK_LINK = re.compile(r'←\s*Torna agli articoli\s*\n?', re.IGNORECASE)
    _RE_GALLERY = re.compile(r'^Galleria Fotografica\s*\n?', re.MULTILINE | re.IGNORECASE)

    def __init__(self):
        super().__init__(
            excluded_selector=self._EXCLUDED_SELECTORS,
            target_elements=self._TARGET_ELEMENTS
        )

# ---------------------------------- METODI PUBBLICI ----------------------------------

    async def parse(self, url: str, raw_html: str | None = None) -> ParsedDocument:
        result = await self._fetch(url, raw_html=raw_html)

        return ParsedDocument(
            url=url,
            domain=urlparse(url).netloc,
            title=self._extract_title(url),
            html_text=result.html,
            parsed_text=self.normalize(result.markdown),
        )

    def normalize(self, text: str) -> str:
        text = self._RE_BACK_LINK.sub('', text)
        text = self._RE_RELATED.sub('', text)
        text = self._RE_GALLERY.sub('', text)
        text = remove_markup(text)
        text = normalize_whitespace(text)
        return text.strip()
    
# ---------------------------------- HELPER PRIVATI ----------------------------------

    def _extract_title(self, url: str) -> str:
        slug = unquote(urlparse(url).path.rstrip('/').split('/')[-1]) 
        slug = slug.replace('--', ': ') # "--" negli slug meteoam codifica ": " nel titolo originale
        return slug.replace('-', ' ')
