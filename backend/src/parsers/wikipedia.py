import re
from urllib.parse import urlparse
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from .base import BaseParser

class WikipediaParser(BaseParser):

    async def parse(self, url: str) -> dict:
        browser_cfg = BrowserConfig(headless=True)
        crawler_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
        
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url=url, config=crawler_cfg)

        #TODO: risolvere bottleneck di AsyncWebCrawler che apre e chiude chromium a ogni chiamata di parse
        
        if not result.success:
            raise ValueError(f"errore: impossibile raggiungere {url}")
        
        return {
            "url": url,
            "domain": urlparse(url).netloc,
            "title": self._extract_title(result.markdown),
            "html_text": result.cleaned_html,
            "parsed_text": self.clean_markdown(result.markdown)
        }

    def clean_markdown(self, text: str) -> str:
        text = re.sub(r'\[\d+\]', '', text)
        text = re.sub(r'^\s*\[.*?\]\(.*?\)\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _extract_title(self, markdown: str) -> str:
        match = re.search(r'^#\s+(.+)$', markdown, flags=re.MULTILINE)
        return match.group(1).strip() if match else ""