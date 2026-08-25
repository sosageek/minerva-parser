"""Salva e legge le metriche deterministiche"""

from typing import Any, TypedDict

import mariadb

from ..database import get_connection


class EvaluationResult(TypedDict):
    """Descrive una evaluation pronta per MariaDB"""
    url: str
    parsed_text: str
    precision: float
    recall: float
    f1: float
    chrf: float
    noise_ratio: float
    rouge_1_precision: float
    rouge_1_recall: float
    rouge_1_f1: float


def upsert(result: EvaluationResult) -> None:
    """Inserisce o aggiorna le metriche deterministiche di un GS"""

    upsert_many([result])


def upsert_many(results: list[EvaluationResult]) -> None:
    """Inserisce o aggiorna più evaluation in una sola transazione"""

    if not results:
        return

    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.executemany(
            """
            INSERT INTO evaluation_results (
                url,
                parsed_text,
                token_precision,
                recall_score,
                f1,
                chrf,
                noise_ratio,
                rouge_1_precision,
                rouge_1_recall,
                rouge_1_f1
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON DUPLICATE KEY UPDATE
                parsed_text = VALUES(parsed_text),
                token_precision = VALUES(token_precision),
                recall_score = VALUES(recall_score),
                f1 = VALUES(f1),
                chrf = VALUES(chrf),
                noise_ratio = VALUES(noise_ratio),
                rouge_1_precision = VALUES(rouge_1_precision),
                rouge_1_recall = VALUES(rouge_1_recall),
                rouge_1_f1 = VALUES(rouge_1_f1)
            """,
            [
                (
                    item["url"],
                    item["parsed_text"],
                    item["precision"],
                    item["recall"],
                    item["f1"],
                    item["chrf"],
                    item["noise_ratio"],
                    item["rouge_1_precision"],
                    item["rouge_1_recall"],
                    item["rouge_1_f1"],
                )
                for item in results
            ],
        )
        connection.commit()
    except mariadb.Error:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def get_by_url(url: str) -> EvaluationResult | None:
    """Restituisce l'ultima evaluation persistita per URL"""

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT
                url,
                parsed_text,
                token_precision AS `precision`,
                recall_score AS recall,
                f1,
                chrf,
                noise_ratio,
                rouge_1_precision,
                rouge_1_recall,
                rouge_1_f1
            FROM evaluation_results
            WHERE url = ?
            """,
            (url,),
        )
        return cursor.fetchone()
    finally:
        cursor.close()
        connection.close()


def averages_by_domain() -> dict[str, dict[str, Any]]:
    """Aggrega le metriche persistite per dominio"""

    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT
                wr.domain,
                AVG(ev.token_precision),
                AVG(ev.recall_score),
                AVG(ev.f1),
                AVG(ev.chrf),
                AVG(ev.noise_ratio),
                AVG(ev.rouge_1_precision),
                AVG(ev.rouge_1_recall),
                AVG(ev.rouge_1_f1),
                COUNT(*)
            FROM evaluation_results AS ev
            INNER JOIN web_resources AS wr
                ON wr.url = ev.url
            GROUP BY wr.domain
            ORDER BY wr.domain
            """
        )
        return {
            domain: {
                "token_level_eval": {
                    "precision": round(float(precision), 4),
                    "recall": round(float(recall), 4),
                    "f1": round(float(f1), 4),
                },
                "x_eval": {
                    "chrf": round(float(chrf), 4),
                    "noise_ratio": round(float(noise_ratio), 4),
                    "rouge_1": {
                        "precision": round(float(rouge_precision), 4),
                        "recall": round(float(rouge_recall), 4),
                        "f1": round(float(rouge_f1), 4),
                    },
                    "n_evaluated": int(count),
                },
            }
            for (
                domain,
                precision,
                recall,
                f1,
                chrf,
                noise_ratio,
                rouge_precision,
                rouge_recall,
                rouge_f1,
                count,
            ) in cursor.fetchall()
        }
    finally:
        cursor.close()
        connection.close()
