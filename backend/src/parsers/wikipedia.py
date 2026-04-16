import re
from urllib.parse import urlparse
from crawl4ai import AsyncWebCrawler
from .parser import Parser
from ..utils.cleaning import strip_markdown_syntax, normalize_whitespace

class WikipediaParser(Parser):

    def __init__(self):
        super().__init__(
            excluded_selector=".mw-navigation, #mw-head, #mw-panel, .navbox, .sidebar, .toc, .hatnote, .ambox, .infobox, .shortdescription, .geo-dec, .geo-dms, .coordinates, #coordinates",
            target_elements=["#mw-content-text"]
        )

    _TERMINAL_SECTIONS = re.compile(
        r'^#{1,6}\s+(?:Notes|References|Bibliography|See also|Further reading'
        r'|External links|Categories|Career statistics|Honours|Honors|Awards'
        r'|Discography|Filmography|Selected works|Publications)\s*$',
        re.MULTILINE
    )

    async def parse(self, url: str) -> dict:
        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            result = await crawler.arun(url=url, config=self.crawler_config)

        #TODO: risolvere bottleneck di AsyncWebCrawler che apre e chiude chromium a ogni chiamata di parse
        
        if not result.success:
            raise ValueError(f"errore: impossibile raggiungere {url}")
        
        return {
            "url": url,
            "domain": urlparse(url).netloc,
            "title": self._extract_title(url),
            "html_text": result.cleaned_html,
            "parsed_text": self.clean_markdown(result.markdown)
        }

    def clean_markdown(self, text: str) -> str:
        text = self._normalize_wiki_links(text)
        text = strip_markdown_syntax(text)
        text = normalize_whitespace(text)
        text = self._remove_urls(text)
        text = self._remove_wiki_metadata(text)
        text = self._truncate_terminal_sections(text)
        return text.strip()

    def _normalize_wiki_links(self, text: str) -> str:
        """Converte link IPA con alfabeto fonetico e cancella citazioni con doppie quadre"""
        text = re.sub(r'\[\[([^\]]*)\]\]\([^)]*Help:IPA[^)]*\)', r'/\1/', text)
        text = re.sub(r'\[\[[^\]]*\]\]\([^)]*\)', '', text)
        return text

    def _remove_urls(self, text: str) -> str:
        """Cancella URL (anche tra parentesi con eventuali caption)"""
        text = re.sub(r'\(https?://(?:[^\s)\\]|\\.)+\)(?=\S)[^\n]*', '', text)
        text = re.sub(r'\(https?://(?:[^\s)\\]|\\.)+\)', '', text)
        text = re.sub(r'https?://(?:[^\s)\\]|\\.)+', '', text)
        return text

    def _remove_wiki_metadata(self, text: str) -> str:
        """Cancella disambiguazione, coordinate, attributi title residui"""
        text = re.sub(r'^Disambiguation\s*[–—-][^\n]*\n?', '', text, flags=re.MULTILINE)
        text = re.sub(r'^.*(?:WikiMiniAtlas|\d+°\d+[′\']\d+[″"][NSEW]).*\n?', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[\s\ufeff/;.\d°′″,NSEW-]+$', '', text, flags=re.MULTILINE)
        text = re.sub(r'\( "[^"]*"\)', '', text)
        return text

    def _truncate_terminal_sections(self, text: str) -> str:
        """Taglia il testo alla prima sezione terminale (note, references, ...)"""
        return self._TERMINAL_SECTIONS.split(text, maxsplit=1)[0]

    def _extract_title(self, url: str) -> str:
        path = urlparse(url).path
        return path.split("/wiki/")[-1].replace("_", " ")