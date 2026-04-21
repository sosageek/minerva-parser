from __future__ import annotations

import json
import os
from pathlib import Path

from ..parsers import MeteoAmParser, NpsParser, WikipediaParser
from ..parsers.parser import Parser


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
GS_DATA_DIR = Path(os.environ.get("GS_DATA_DIR", _PROJECT_ROOT / "gs_data")) # ovveridable con var d'ambiente del container

PARSERS: dict[str, Parser] = {
    "www.meteoam.it": MeteoAmParser(),
    "en.wikipedia.org": WikipediaParser(),
    "www.nps.gov": NpsParser(),
}

GS_FILES: dict[str, Path] = {
    "www.meteoam.it": GS_DATA_DIR / "meteoam.it.json",
    "en.wikipedia.org": GS_DATA_DIR / "en.wikipedia.org_gs.json",
    "www.nps.gov": GS_DATA_DIR / "nps.gov_gs.json",
}


def supported_domains() -> list[str]:
    """
    Returns:
        lista ordinata dei domini registrati in ``PARSERS``
    """
    return sorted(PARSERS.keys())


def get_parser(domain: str) -> Parser | None:
    """Ritorna il parser associato al dominio o ``None`` se non supportato

    Args:
        domain: netloc del dominio

    Returns:
        istanza di ``Parser`` o ``None``
    """
    return PARSERS.get(domain)


def get_gs_file(domain: str) -> Path | None:
    """Ritorna il path del file GS associato al dominio o ``None`` se non registrato"""
    return GS_FILES.get(domain)


def load_gold_standards() -> dict[str, list[dict]]:
    """Carica in memoria tutti i GS all'avvio del server

    nota: utile finché i json dei GS sono piccoli

    Returns:
        mappa ``dominio -> lista di entry del GS``

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
