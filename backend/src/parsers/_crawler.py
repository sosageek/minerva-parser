import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig

from ..config import CRAWLER_HEADLESS

_crawler: AsyncWebCrawler | None = None
_lock = asyncio.Lock()

async def get_crawler() -> AsyncWebCrawler:
    """Ritorna istanza condivisa del crawler

    Returns:
        ``AsyncWebCrawler`` avviato e pronto a ricevere ``arun()``
    """
    global _crawler
    async with _lock:
        if _crawler is None:
            crawler = AsyncWebCrawler(config=BrowserConfig(headless=CRAWLER_HEADLESS))
            await crawler.start()
            _crawler = crawler
    return _crawler


async def close_crawler() -> None:
    """Chiude l'istanza condivisa del crawler se presente
    
    nota: se non chiamata rimarrà processo zombie attivo
    """
    global _crawler
    async with _lock:
        if _crawler is not None:
            try:
                await _crawler.close()
            finally:
                _crawler = None
