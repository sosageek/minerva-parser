import re
import html
from abc import ABC, abstractmethod
from crawl4ai import BrowserConfig, CrawlerRunConfig, CacheMode

class Parser(ABC):

    def __init__(self, excluded_selector: str = "", target_elements: list[str] | None = None):
        self.browser_config = BrowserConfig(headless=True)
        self.crawler_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            excluded_tags=["nav", "header", "footer", "aside"],
            word_count_threshold=10,
            remove_forms=True,
            excluded_selector=excluded_selector,
            target_elements = target_elements or []
        )

    @abstractmethod
    async def parse(self, url: str) -> dict:
        pass

    @abstractmethod
    def clean_markdown(self, text: str) -> str:
        pass

    def _clean_markdown_common(self, text: str) -> str:
        text = re.sub(r'!\[[^\]]*\]\((?:[^()]*|\([^()]*\))*\)', '', text)
        text = re.sub(r'\[([^\]]+)\]\((?:[^()]*|\([^()]*\))*\)', r'\1', text)
        text = re.sub(r'\[([^\]]+)\]\[[^\]]*\]', r'\1', text)
        text = re.sub(r'^\[[^\]]+\]:\s+\S+.*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'\[[^\]]{0,50}\]', '', text)
        text = re.sub(r'^\|.*\|$',   '', text, flags=re.MULTILINE)
        text = re.sub(r'^[|:\-\s]+$', '', text, flags=re.MULTILINE)
        text = re.sub(r'<[^>]+>', '', text)
        text = html.unescape(text)
        text = re.sub(r'(?<!\[)\]|\[(?!\])', '', text)
        text = re.sub(r'\s+([.,;:!?)\]])', r'\1', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()