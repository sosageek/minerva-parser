"""Gestisce il browser condiviso dai parser"""

import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig

from ..config import CRAWLER_HEADLESS

_crawler: AsyncWebCrawler | None = None
_lock = asyncio.Lock()

async def get_crawler() -> AsyncWebCrawler:
    """Ritorna istanza condivisa del crawler"""
    global _crawler
    async with _lock:
        if _crawler is None:
            crawler = AsyncWebCrawler(config=BrowserConfig(headless=CRAWLER_HEADLESS))
            await crawler.start()
            _crawler = crawler
    return _crawler


async def close_crawler() -> None:
    """Chiude l'istanza condivisa del crawler se presente"""
    global _crawler
    async with _lock:
        if _crawler is not None:
            try:
                await _crawler.close()
            finally:
                _crawler = None
