"""Definisce il comportamento comune dei parser"""

from abc import ABC, abstractmethod
from crawl4ai import CrawlerRunConfig, CacheMode
from .schema import ParsedDocument
from ._crawler import get_crawler

class CrawlError(Exception):
    """Errore di fetch di una pagina web"""

    def __init__(self, url: str, status_code: int | None = None, error_message: str | None = None):
        """Prepara la configurazione Crawl4AI del parser"""
        self.url = url
        self.status_code = status_code
        self.error_message = error_message
        detail = f"status={status_code}" if status_code is not None else "no status"
        msg = f"crawl fallito per {url} ({detail})"
        if error_message:
            msg += f": {error_message}"
        super().__init__(msg)


class Parser(ABC):
    """Classe astratta per parser di pagine che producono markdown pulito"""

# ---------------------------------- CONFIG CRAWL4AI ----------------------------------

    def __init__(self, excluded_selector: str = "", target_elements: list[str] | None = None):
        """Inizializza la configurazione della run di crawling"""

        self.crawler_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            excluded_tags=["nav", "header", "footer", "aside"],
            word_count_threshold=10,
            remove_forms=True,
            excluded_selector=excluded_selector,
            target_elements=target_elements or [],
        )


    async def _fetch(self, url: str, raw_html: str | None = None, config: CrawlerRunConfig | None = None):
        """Acquisisce una pagina usando il crawler condiviso"""

        crawler = await get_crawler()
        fetch_target = f"raw:{raw_html}" if raw_html is not None else url
        result = await crawler.arun(url=fetch_target, config=config or self.crawler_config)
        # nota: con raw_html non c'è fetch di rete, lo status code è None / 200 fittizio.
        # Lo controlliamo solo quando abbiamo davvero scaricato una pagina (gabriele)
        status = getattr(result, "status_code", None)
        if not result.success or (raw_html is None and status is not None and status >= 400):
            raise CrawlError(
                url=url,
                status_code=status,
                error_message=getattr(result, "error_message", None),
            )
        return result
    
# ---------------------------------- METODI ASTRATTI ----------------------------------

    @abstractmethod
    async def parse(self, url: str, raw_html: str | None = None) -> ParsedDocument:
        """Acquisisce la pagina e ne estrae il markdown pulito"""
        pass

    @abstractmethod
    def normalize(self, text: str) -> str:
        """Applica pipeline di pulizia specifica rispetto al dominio"""
        pass
