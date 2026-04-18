from abc import ABC, abstractmethod
from crawl4ai import CrawlerRunConfig, CacheMode
from .schema import ParsedDocument
from ._crawler import get_crawler


class CrawlError(Exception):
    """Errore di fetch di una pagina web

    Portiamo dietro ``status_code`` e ``error_message`` così chi ci sta sopra
    (ad esempio il server FastAPI) può mappare l'errore a una risposta HTTP
    coerente senza dover parsare stringhe.

    Attributes:
        url: URL richiesto
        status_code: status HTTP restituito dal server, se disponibile
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

    Le sottoclassi devono implementare ``parse`` e ``clean_markdown``.
    Per pulizia generica usare le funzioni del modulo ``cleaning``.

    Il browser è condiviso tra tutti i parser tramite ``_crawler.get_crawler()``:
    ogni parser ha solo la propria configurazione di run, non il proprio browser.

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

    async def _fetch(self, url: str):
        """Scarica una pagina usando il crawler condiviso

        Args:
            url: URL assoluto della pagina

        Returns:
            un ``CrawlResult`` di crawl4ai con ``success=True``

        Raises:
            CrawlError: se il crawler ritorna ``success=False``
        """
        crawler = await get_crawler()
        result = await crawler.arun(url=url, config=self.crawler_config)
        if not result.success:
            raise CrawlError(
                url=url,
                status_code=getattr(result, "status_code", None),
                error_message=getattr(result, "error_message", None),
            )
        return result

    @abstractmethod
    async def parse(self, url: str) -> ParsedDocument:
        """Scarica la pagina e ne estrae il markdown pulito

        Args:
            url: URL assoluto della pagina da acquisire

        Returns:
            un ``ParsedDocument`` con ``url``, ``domain``, ``title``,
            ``html_text`` e ``parsed_text``

        Raises:
            CrawlError: se il fetch della pagina fallisce
        """
        pass

    @abstractmethod
    def clean_markdown(self, text: str) -> str:
        """Applica pipeline di pulizia specifica rispetto al dominio

        Args:
            text: testo MD grezzo estratto dalla pagina

        Returns:
            testo MD pulito
        """
        pass
