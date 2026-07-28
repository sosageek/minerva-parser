import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# configurazione path
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env")

_gs_data_dir = Path(os.environ.get("GS_DATA_DIR", "gs_data"))
GS_DATA_DIR: Path = (
    _gs_data_dir
    if _gs_data_dir.is_absolute()
    else _PROJECT_ROOT / _gs_data_dir
)

# configurazione logging
LOGGER_NAME: str = "minerva-parser"
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FORMAT: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

# configurazione crawl4ai
CRAWLER_HEADLESS: bool = os.environ.get("CRAWLER_HEADLESS", "true").lower() == "true"
# il default di crawl4ai dovrebbe essere true quindi non c'era bisogno di esplicitare fallback
# spero di non sbagliarmi (gabriele)

# configurazione servizi esterni
DATABASE_HOST: str = os.environ.get("DATABASE_HOST", "database")
DATABASE_PORT: int = int(os.environ.get("DATABASE_PORT", "3306"))
DATABASE_NAME: str = os.environ.get("DATABASE_NAME", "parser_db")
DATABASE_USER: str = os.environ.get("DATABASE_USER", "minerva")
DATABASE_PASSWORD: str = os.environ.get("DATABASE_PASSWORD", "minerva_password")
DATABASE_POOL_SIZE: int = int(os.environ.get("DATABASE_POOL_SIZE", "5"))
OLLAMA_URL: str = os.environ.get("OLLAMA_URL", "http://ollama:11434")
STATUS_CHECK_TIMEOUT: float = float(os.environ.get("STATUS_CHECK_TIMEOUT", "1.0"))


def configure_logging() -> None:
    """Inizializza logger con formato e livello coerenti

    ``force=True`` sovrascrive eventuali configurazioni precedenti
    """
    logging.basicConfig(
        level=LOG_LEVEL,
        format=LOG_FORMAT,
        force=True,
    )
