import logging
import os
from pathlib import Path

# configurazione path
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
GS_DATA_DIR: Path = Path(
    os.environ.get("GS_DATA_DIR", _PROJECT_ROOT / "gs_data") # path dei gold standards json overridable con variabile d ambiente
)

# configurazione logging
LOGGER_NAME: str = "minerva-parser"
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FORMAT: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

# configurazione crawl4ai
CRAWLER_HEADLESS: bool = os.environ.get("CRAWLER_HEADLESS", "true").lower() == "true"
# il default di crawl4ai dovrebbe essere true quindi non c'era bisogno di esplicitare fallback
# spero di non sbagliarmi (gabriele)


def configure_logging() -> None:
    """Inizializza logger con formato e livello coerenti

    ``force=True`` sovrascrive eventuali configurazioni precedenti
    """
    logging.basicConfig(
        level=LOG_LEVEL,
        format=LOG_FORMAT,
        force=True,
    )
