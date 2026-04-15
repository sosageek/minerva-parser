import re
from urllib.parse import urlparse
from crawl4ai import AsyncWebCrawler
from .parser import Parser

class WikipediaParser(Parser):

    def __init__(self):
        super().__init__(
            excluded_selector=".mw-navigation, #mw-head, #mw-panel, .navbox, .sidebar, .toc, .hatnote, .ambox, .infobox, .mw-page-description, .geo-dec, .geo-dms, .coordinates, #coordinates",
            target_elements=["#mw-content-text"]
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
        lines = text.split('\n')
        if lines and not lines[0].strip().endswith('.'):
            lines = lines[1:]
        text = '\n'.join(lines)

        text = re.sub(r'\[(\[[^\]]*\])\]\([^)]*Help:IPA[^)]*\)', lambda m: '/' + m.group(1).strip('[]') + '/', text)
        text = re.sub(r'\[\[[^\]]*\]\]\([^)]*\)', '', text)
        text = self._clean_markdown_common(text)
        text = re.sub(r'\(https?://(?:[^\s)\\]|\\.)+\)(?=\S)[^\n]*', '', text)
        text = re.sub(r'\(https?://(?:[^\s)\\]|\\.)+\)', '', text)
        text = re.sub(r'https?://(?:[^\s)\\]|\\.)+', '', text)
        text = re.sub(r'^Disambiguation\s*[–—-][^\n]*\n?', '', text, flags=re.MULTILINE)
        text = re.sub(r'^.*(?:WikiMiniAtlas|\d+°\d+[′\']\d+[″"][NSEW]).*\n?', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[\s\ufeff/;.\d°′″,NSEW-]+$', '', text, flags=re.MULTILINE)
        text = re.sub(r'\( "[^"]*"\)', '', text)
        text = re.split(
            r'^#{1,6}\s+(?:Notes|References|Bibliography|See also|Further reading|External links|Categories|Career statistics|Honours|Honors|Awards|Discography|Filmography|Selected works|Publications)\s*$',
            text, maxsplit=1, flags=re.MULTILINE
        )[0]
        return text.strip()

    def _extract_title(self, url: str) -> str:
        path = urlparse(url).path
        return path.split("/wiki/")[-1].replace("_", " ")