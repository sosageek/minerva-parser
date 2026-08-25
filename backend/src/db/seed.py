"""Valida e carica i dati iniziali del progetto"""

import json
import logging
from pathlib import Path
from typing import Any

from ..config import GS_DATA_DIR, OLLAMA_MODEL, PRECOMPUTED_RESULTS_FILE
from ..judge.models import PROMPT_VERSION
from .database import get_connection
from .repositories import evaluation_results, judge_results


logger = logging.getLogger("minerva-parser.database")


_REQUIRED_FIELDS = {
    "url",
    "domain",
    "title",
    "html_text",
    "gold_text",
}

_REQUIRED_PRECOMPUTED_FIELDS = {
    "url",
    "parsed_text",
    "token_level_eval",
    "x_eval",
    "judge",
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
    """Legge e valida le entry contenute nei file Gold Standard"""

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


def _require_number(value: Any, field: str, index: int) -> float:
    """Valida e converte una metrica numerica compresa tra zero e uno"""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Entry precomputata {index}: '{field}' non numerico")
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"Entry precomputata {index}: '{field}' fuori range")
    return number


def _load_precomputed_results() -> tuple[
    list[evaluation_results.EvaluationResult],
    list[judge_results.PersistedJudgeResult],
]:
    """Legge e valida metriche e giudizi precalcolati delle 41 entry GS"""

    raw_entries = _read_json_file(PRECOMPUTED_RESULTS_FILE)
    expected_urls = {entry["url"] for entry in _load_seed_entries()}
    seen_urls: set[str] = set()
    evaluations: list[evaluation_results.EvaluationResult] = []
    judges: list[judge_results.PersistedJudgeResult] = []

    for index, entry in enumerate(raw_entries):
        if not isinstance(entry, dict):
            raise ValueError(f"Entry precomputata {index} non è un oggetto JSON")
        missing = _REQUIRED_PRECOMPUTED_FIELDS - entry.keys()
        if missing:
            raise ValueError(
                f"Entry precomputata {index}: campi mancanti {sorted(missing)}"
            )

        url = entry["url"]
        if not isinstance(url, str) or not url:
            raise ValueError(f"Entry precomputata {index}: URL non valida")
        if url in seen_urls:
            raise ValueError(f"URL precomputata duplicata: {url}")
        seen_urls.add(url)

        parsed_text = entry["parsed_text"]
        token_eval = entry["token_level_eval"]
        x_eval = entry["x_eval"]
        judge = entry["judge"]
        if not isinstance(parsed_text, str):
            raise ValueError(f"Entry precomputata {index}: parsed_text non stringa")
        if not all(isinstance(item, dict) for item in (token_eval, x_eval, judge)):
            raise ValueError(f"Entry precomputata {index}: struttura annidata non valida")

        rouge = x_eval.get("rouge_1")
        if not isinstance(rouge, dict):
            raise ValueError(f"Entry precomputata {index}: rouge_1 non valido")

        score = judge.get("judge_score")
        if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 5:
            raise ValueError(f"Entry precomputata {index}: judge_score fuori range")
        for field in ("model_name", "judge_feedback", "extra_noise", "prompt_version"):
            if not isinstance(judge.get(field), str):
                raise ValueError(f"Entry precomputata {index}: '{field}' non stringa")
        if judge["model_name"] != OLLAMA_MODEL:
            raise ValueError(
                f"Entry precomputata {index}: modello {judge['model_name']!r}, "
                f"atteso {OLLAMA_MODEL!r}"
            )
        if judge["prompt_version"] != PROMPT_VERSION:
            raise ValueError(
                f"Entry precomputata {index}: prompt {judge['prompt_version']!r}, "
                f"atteso {PROMPT_VERSION!r}"
            )

        evaluations.append(
            {
                "url": url,
                "parsed_text": parsed_text,
                "precision": _require_number(token_eval.get("precision"), "precision", index),
                "recall": _require_number(token_eval.get("recall"), "recall", index),
                "f1": _require_number(token_eval.get("f1"), "f1", index),
                "chrf": _require_number(x_eval.get("chrf"), "chrf", index),
                "noise_ratio": _require_number(
                    x_eval.get("noise_ratio"), "noise_ratio", index
                ),
                "rouge_1_precision": _require_number(
                    rouge.get("precision"), "rouge_1.precision", index
                ),
                "rouge_1_recall": _require_number(
                    rouge.get("recall"), "rouge_1.recall", index
                ),
                "rouge_1_f1": _require_number(
                    rouge.get("f1"), "rouge_1.f1", index
                ),
            }
        )
        judges.append(
            {
                "url": url,
                "model_name": judge["model_name"],
                "judge_score": score,
                "judge_feedback": judge["judge_feedback"][:500],
                "extra_noise": judge["extra_noise"][:300],
                "prompt_version": judge["prompt_version"],
            }
        )

    if seen_urls != expected_urls:
        missing_urls = sorted(expected_urls - seen_urls)
        extra_urls = sorted(seen_urls - expected_urls)
        raise ValueError(
            "Le entry precomputate non corrispondono al GS: "
            f"mancanti={missing_urls}, extra={extra_urls}"
        )

    return evaluations, judges


def seed_precomputed_results() -> None:
    """Popola metriche e Judge reali senza invocare Ollama durante le API"""

    evaluations, judges = _load_precomputed_results()
    evaluation_results.upsert_many(evaluations)
    judge_results.upsert_many(judges)
    logger.info("Seed risultati precalcolati completato: %s risorse", len(evaluations))
