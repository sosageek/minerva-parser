import json
from pathlib import Path

from ..config import GS_DATA_DIR
from ..parsers import MeteoAmParser, NpsParser, WikipediaParser, BookerParser, Parser


PARSERS: dict[str, Parser] = {
    "www.meteoam.it": MeteoAmParser(),
    "en.wikipedia.org": WikipediaParser(),
    "www.nps.gov": NpsParser(),
    "thebookerprizes.com": BookerParser(),
}

GS_FILES: dict[str, Path] = {
    "www.meteoam.it": GS_DATA_DIR / "www.meteoam.it_gs.json",
    "en.wikipedia.org": GS_DATA_DIR / "en.wikipedia.org_gs.json",
    "www.nps.gov": GS_DATA_DIR / "www.nps.gov_gs.json",
    "thebookerprizes.com": GS_DATA_DIR / "thebookerprizes.com_gs.json"
}


def supported_domains() -> list[str]:
    """Ritorna lista ordinata dei domini per cui esiste un parser

    Returns:
        lista di stringhe ordinata dei domini registrati in ``PARSERS``
    """

    return sorted(PARSERS.keys())


def get_parser(domain: str) -> Parser | None:
    """Ritorna il parser associato al dominio o ``None`` se non supportato

    Args:
        domain(str): netloc del dominio

    Returns:
        istanza di ``Parser`` o ``None``
    """

    return PARSERS.get(domain)


def get_gs_file(domain: str) -> Path | None:
    """Ritorna il path del file GS associato al dominio o ``None`` se non registrato
    
    Args:
        domain(str): netloc del dominio

    Returns:
        ``Path`` del file GS associato al dominio o ``None``
    """

    return GS_FILES.get(domain)


def load_gold_standards() -> dict[str, list[dict]]:
    """Carica in memoria tutti i GS all'avvio del server

    nota: rimarrà utile finché i json dei GS sono pochi e di piccole dimensioni,
    qualora non dovesse essere più così converrebbe caricarli on demand

    Returns:
        dizionario che mappa ``dominio -> lista di entry del GS``

    Raises:
        FileNotFoundError: se un file GS dichiarato in ``GS_FILES`` manca
        RuntimeError: se un dominio in ``PARSERS`` non ha un GS associato
    """
    
    missing = [d for d in PARSERS if d not in GS_FILES]
    if missing:
        raise RuntimeError(
            f"Domini senza mapping GS in registry.GS_FILES: {missing}"
        )

    gs: dict[str, list[dict]] = {}
    for domain, path in GS_FILES.items():
        if not path.exists():
            raise FileNotFoundError(
                f"File GS mancante per '{domain}': {path}"
            )
        with path.open(encoding="utf-8") as fin:
            gs[domain] = json.load(fin)
    return gs
