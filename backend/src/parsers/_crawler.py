import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig

_crawler: AsyncWebCrawler | None = None
_lock = asyncio.Lock()


async def get_crawler() -> AsyncWebCrawler:
    """Ritorna istanza condivisa del crawler
    Returns:
        oggetto ``AsyncWebCrawler`` avviato e pronto a ricevere ``arun()``
    """
    global _crawler
    async with _lock:
        if _crawler is None:
            crawler = AsyncWebCrawler(config=BrowserConfig(headless=True))
            await crawler.start()
            _crawler = crawler
    return _crawler


async def close_crawler() -> None:
    """Chiude l'istanza condivisa del crawler se presente
    
    se non chiamata rimarrà processo zombie di Chromium attivo
    """
    global _crawler
    async with _lock:
        if _crawler is not None:
            try:
                await _crawler.close()
            finally:
                _crawler = None
