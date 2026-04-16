from abc import ABC, abstractmethod
from crawl4ai import BrowserConfig, CrawlerRunConfig, CacheMode
from .schema import ParsedDocument


class Parser(ABC):
    """Classe astratta per parser di pagine che producono markdown pulito

    le sottoclassi devono implementare ``parse`` e ``clean_markdown``
    Per pulizia generica usare le funzioni del modulo ``cleaning``

    Attributes:
        browser_config: configurazione del browser usata da ``crawl4ai``
        crawler_config: configurazione della run di crawling
    """

    def __init__(self, excluded_selector: str = "", target_elements: list[str] | None = None):
        """Inizializza la configurazione di browser e crawler

        Args:
            excluded_selector: selettore CSS con gli elementi da escludere
            target_elements: lista di selettori CSS su cui restringere l'estrazione
        """
        self.browser_config = BrowserConfig(headless=True)
        self.crawler_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            excluded_tags=["nav", "header", "footer", "aside"],
            word_count_threshold=10,
            remove_forms=True,
            excluded_selector=excluded_selector,
            target_elements=target_elements or [],
        )

    @abstractmethod
    async def parse(self, url: str) -> ParsedDocument:
        """Scarica la pagina e ne estrae il markdown pulito

        Args:
            url: URL assoluto della pagina da acquisire

        Returns:
            un ``ParsedDocument`` con ``url``, ``domain``, ``title``,
            ``html_text`` e ``parsed_text``

        Raises:
            ValueError: se il fetch della pagina fallisce
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
