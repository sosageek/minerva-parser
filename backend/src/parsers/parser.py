from abc import ABC, abstractmethod
from crawl4ai import CrawlerRunConfig, CacheMode
from .schema import ParsedDocument
from ._crawler import get_crawler

class CrawlError(Exception):
    """Errore di fetch di una pagina web

    Attributes:
        url: URL richiesto
        status_code: status HTTP restituito dal server(se disponibile)
        error_message: messaggio di errore grezzo da crawl4ai
    """

    def __init__(self, url: str, status_code: int | None = None, error_message: str | None = None):
        self.url = url
        self.status_code = status_code
        self.error_message = error_message
        detail = f"status={status_code}" if status_code is not None else "no status"
        msg = f"crawl fallito per {url} ({detail})"
        if error_message:
            msg += f": {error_message}"
        super().__init__(msg)


class Parser(ABC):
    """Classe astratta per parser di pagine che producono markdown pulito

    Le sottoclassi devono implementare ``parse`` e ``clean_markdown``

    il browser è condiviso tra tutti i parser tramite ``_crawler.get_crawler()``

    Attributes:
        crawler_config: configurazione della run di crawling specifica del parser
    """

    def __init__(self, excluded_selector: str = "", target_elements: list[str] | None = None):
        """Inizializza la configurazione della run di crawling

        Args:
            excluded_selector: selettore CSS con gli elementi da escludere
            target_elements: lista di selettori CSS su cui restringere l'estrazione
        """
        self.crawler_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            excluded_tags=["nav", "header", "footer", "aside"],
            word_count_threshold=10,
            remove_forms=True,
            excluded_selector=excluded_selector,
            target_elements=target_elements or [],
        )

    async def _fetch(self, url: str, raw_html: str | None = None):
        """Acquisisce una pagina usando il crawler condiviso

        se ``raw_html`` è fornito non viene effettuata nessuna richiesta di rete: 
        crawl4ai processa direttamente l'HTML passato (prefisso ``raw:``)

        Args:
            url: URL assoluto della pagina (usato per logging e messaggi d'errore)
            raw_html: HTML già scaricato lato client

        Returns:
            un ``CrawlResult`` di crawl4ai con ``success=True``

        Raises:
            CrawlError: se il crawler ritorna ``success=False``
        """
        crawler = await get_crawler()
        fetch_target = f"raw:{raw_html}" if raw_html is not None else url
        result = await crawler.arun(url=fetch_target, config=self.crawler_config)
        if not result.success:
            raise CrawlError(
                url=url,
                status_code=getattr(result, "status_code", None),
                error_message=getattr(result, "error_message", None),
            )
        return result

    @abstractmethod
    async def parse(self, url: str, raw_html: str | None = None) -> ParsedDocument:
        """Acquisisce la pagina e ne estrae il markdown pulito

        Args:
            url: URL assoluto della pagina
            raw_html: se fornito, l'HTML viene processato senza crawl di rete

        Returns:
            un ``ParsedDocument`` con ``url``, ``domain``, ``title``, ``html_text`` e ``parsed_text``

        Raises:
            CrawlError: se il fetch della pagina fallisce
        """
        pass

    @abstractmethod
    def normalize(self, text: str) -> str:
        """Applica pipeline di pulizia specifica rispetto al dominio

        Args:
            text: testo MD grezzo estratto dalla pagina

        Returns:
            testo MD pulito
        """
        pass
