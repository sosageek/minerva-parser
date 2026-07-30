import json
import logging
from pathlib import Path
from typing import Any

from ..config import GS_DATA_DIR
from .database import get_connection


logger = logging.getLogger("minerva-parser.database")


_REQUIRED_FIELDS = {
    "url",
    "domain",
    "title",
    "html_text",
    "gold_text",
}

# Una normale insert funzionerebbe solo la prima volta. Essendo l'url primary key il db non aggiornerebbe la entry in quanto duplicata -> upsert è la way-to-go

# Upsert sarebbe: insert -> duplicato? -> update

_UPSERT_WEB_RESOURCE = """
INSERT INTO web_resources (
    url,
    domain,
    title,
    html_text
)
VALUES (?, ?, ?, ?)
ON DUPLICATE KEY UPDATE
    domain = VALUES(domain),
    title = VALUES(title),
    html_text = VALUES(html_text)
""" 

_UPSERT_GOLD_STANDARD = """
INSERT INTO gold_standard (
    url,
    gold_text
)
VALUES (?, ?)
ON DUPLICATE KEY UPDATE
    gold_text = VALUES(gold_text)
"""

def _load_seed_entries() -> list[dict[str, str]]:
    """Legge e valida le entry contenute nei file Gold Standard
    
        Controlla se la struttura è corretta ed eventuali duplicati nei GS
    """

    json_files = sorted(GS_DATA_DIR.glob("*_gs.json"))

    if not json_files:
        raise FileNotFoundError(
            f"Nessun file Gold Standard trovato in {GS_DATA_DIR}"
        )

    entries: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for json_file in json_files:
        file_entries = _read_json_file(json_file)

        for index, entry in enumerate(file_entries):
            _validate_entry(
                entry=entry,
                json_file=json_file,
                index=index,
            )

            url = entry["url"]

            if url in seen_urls:
                raise ValueError(
                    f"URL duplicata nei file Gold Standard: {url}"
                )

            seen_urls.add(url)
            entries.append(entry)

    logger.info(
        "Caricate %s entry seed da %s file JSON",
        len(entries),
        len(json_files),
    )

    return entries

def _validate_entry(entry: Any, json_file: Path, index: int) -> None:
    """Verifica struttura e campi obbligatori di una entry"""

    if not isinstance(entry, dict):
        raise ValueError(
            f"Entry {index} di {json_file} non è un oggetto JSON"
        )

    missing_fields = _REQUIRED_FIELDS - entry.keys()

    if missing_fields:
        raise ValueError(
            f"Entry {index} di {json_file}: "
            f"campi mancanti {sorted(missing_fields)}"
        )

    for field in _REQUIRED_FIELDS:
        if not isinstance(entry[field], str):
            raise ValueError(
                f"Entry {index} di {json_file}: "
                f"il campo '{field}' deve essere una stringa"
            )

def _read_json_file(json_file: Path) -> list[Any]:
    """Legge un singolo file JSON"""

    with json_file.open(encoding="utf-8") as file:
        content = json.load(file)

    if not isinstance(content, list):
        raise ValueError(
            f"Il file {json_file} deve contenere una lista JSON"
        )

    return content

def seed_gold_standards() -> None:
    """Inserisce o aggiorna web resource e GS"""

    entries = _load_seed_entries()

    web_resources = [
        (
            entry["url"],
            entry["domain"],
            entry["title"],
            entry["html_text"],
        )
        for entry in entries
    ]

    gold_standards = [
        (
            entry["url"],
            entry["gold_text"],
        )
        for entry in entries
    ]

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.executemany(
            _UPSERT_WEB_RESOURCE,
            web_resources,
        )

        cursor.executemany(
            _UPSERT_GOLD_STANDARD,
            gold_standards,
        )

        connection.commit()

        logger.info(
            "Seed completato: %s risorse",
            len(entries),
        )

    except Exception:
        connection.rollback()
        logger.exception("Seed fallito")
        raise

    finally:
        cursor.close()
        connection.close()