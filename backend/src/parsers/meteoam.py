import re
from urllib.parse import urlparse
from crawl4ai import AsyncWebCrawler
from .parser import Parser
from .schema import ParsedDocument
from ..utils.cleaning import strip_markdown_syntax, normalize_whitespace


class MeteoAmParser(Parser):

    # Sezione "articoli correlati" che può sfuggire all'excluded_selector
    _RE_RELATED = re.compile(
        r'Potrebbe piacerti anche.*',
        re.DOTALL | re.IGNORECASE,
    )

    # Link "← Torna agli articoli" che può apparire come testo nel markdown
    _RE_BACK_LINK = re.compile(r'←\s*Torna agli articoli\s*\n?', re.IGNORECASE)

    def __init__(self):
        super().__init__(
            target_elements=["section#details_news_page"],
            excluded_selector=(
                "a.news-details-header-go-back, "
                "div.news-details-side-col, "
                "section[data-wcs-title='Potrebbe piacerti anche']"
            ),
        )

    async def parse(self, url: str) -> ParsedDocument:
        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            result = await crawler.arun(url=url, config=self.crawler_config)

        if not result.success:
            raise ValueError(f"errore: impossibile raggiungere {url}")

        return ParsedDocument(
            url=url,
            domain=urlparse(url).netloc,
            title=self._extract_title(url),
            html_text=result.cleaned_html,
            parsed_text=self.clean_markdown(result.markdown),
        )

    def clean_markdown(self, text: str) -> str:
        text = self._RE_BACK_LINK.sub('', text)
        text = self._RE_RELATED.sub('', text)
        text = strip_markdown_syntax(text)
        text = normalize_whitespace(text)
        return text.strip()

    def _extract_title(self, url: str) -> str:
        slug = urlparse(url).path.rstrip('/').split('/')[-1]
        # "--" nei slug meteoam codifica ": " nel titolo originale
        slug = slug.replace('--', ': ')
        return slug.replace('-', ' ')
