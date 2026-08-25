"""Salva e legge i risultati del Judge"""

from typing import TypedDict

import mariadb

from ..database import get_connection


class PersistedJudgeResult(TypedDict):
    """Descrive un giudizio pronto per MariaDB"""
    url: str
    model_name: str
    judge_score: int
    judge_feedback: str
    extra_noise: str
    prompt_version: str


def upsert(result: PersistedJudgeResult) -> None:
    """Inserisce o aggiorna il giudizio corrente di un GS"""

    upsert_many([result])


def upsert_many(results: list[PersistedJudgeResult]) -> None:
    """Inserisce o aggiorna più giudizi in una sola transazione"""

    if not results:
        return

    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.executemany(
            """
            INSERT INTO judge_results (
                url,
                model_name,
                judge_score,
                judge_feedback,
                extra_noise,
                prompt_version
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON DUPLICATE KEY UPDATE
                model_name = VALUES(model_name),
                judge_score = VALUES(judge_score),
                judge_feedback = VALUES(judge_feedback),
                extra_noise = VALUES(extra_noise),
                prompt_version = VALUES(prompt_version)
            """,
            [
                (
                    item["url"],
                    item["model_name"],
                    item["judge_score"],
                    item["judge_feedback"],
                    item["extra_noise"],
                    item["prompt_version"],
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


def get_by_url(url: str) -> PersistedJudgeResult | None:
    """Restituisce il giudizio persistito per URL"""

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT
                url,
                model_name,
                judge_score,
                judge_feedback,
                extra_noise,
                prompt_version
            FROM judge_results
            WHERE url = ?
            """,
            (url,),
        )
        return cursor.fetchone()
    finally:
        cursor.close()
        connection.close()


def averages_by_domain() -> dict[str, dict[str, float | int]]:
    """Aggrega i punteggi Judge persistiti per dominio"""

    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT
                wr.domain,
                AVG(jr.judge_score),
                COUNT(*)
            FROM judge_results AS jr
            INNER JOIN web_resources AS wr
                ON wr.url = jr.url
            GROUP BY wr.domain
            ORDER BY wr.domain
            """
        )
        return {
            domain: {
                "judge_score": round(float(score), 4),
                "n_evaluated": int(count),
            }
            for domain, score, count in cursor.fetchall()
        }
    finally:
        cursor.close()
        connection.close()
