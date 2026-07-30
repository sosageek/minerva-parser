from typing import TypedDict
import mariadb
from ..database import get_connection


class GoldStandardEntry(TypedDict):
    """Definizione GS completo della relativa web resource"""

    url: str
    domain: str
    title: str
    html_text: str
    gold_text: str


def get_by_url(url: str) -> GoldStandardEntry | None:
    """Restituisce il GS completo oppure None"""

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                wr.url,
                wr.domain,
                wr.title,
                wr.html_text,
                gs.gold_text
            FROM gold_standard AS gs
            INNER JOIN web_resources AS wr
                ON wr.url = gs.url
            WHERE gs.url = ?
            """,
            (url,),
        )

        return cursor.fetchone()

    finally:
        cursor.close()
        connection.close()


def list_urls(domain: str | None = None) -> list[str]:
    """Restituisce tutti gli URL che possiedono un GS

    Se domain è valorizzato, filtra gli URL per dominio
    """

    connection = get_connection()
    cursor = connection.cursor()   

    try:
        if domain is None:
            cursor.execute(
                """
                SELECT url
                FROM gold_standard
                ORDER BY url
                """
            )
        else:
            cursor.execute(
                """
                SELECT gs.url
                FROM gold_standard AS gs
                INNER JOIN web_resources AS wr
                    ON wr.url = gs.url
                WHERE wr.domain = ?
                ORDER BY gs.url
                """,
                (domain,),
            )

        return [
            url
            for (url,) in cursor.fetchall()
        ]

    finally:
        cursor.close()
        connection.close()


def list_by_domain(domain: str) -> list[GoldStandardEntry]:
    """Restituisce tutte le entry complete di un dominio"""

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                wr.url,
                wr.domain,
                wr.title,
                wr.html_text,
                gs.gold_text
            FROM gold_standard AS gs
            INNER JOIN web_resources AS wr
                ON wr.url = gs.url
            WHERE wr.domain = ?
            ORDER BY wr.url
            """,
            (domain,),
        )

        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()


def upsert(url: str, gold_text: str) -> None:
    """Inserisce o aggiorna un GS

    Nota: la web resource deve già esistere
    """

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO gold_standard (
                url,
                gold_text
            )
            VALUES (?, ?)
            ON DUPLICATE KEY UPDATE
                gold_text = VALUES(gold_text)
            """,
            (
                url,
                gold_text,
            ),
        )

        connection.commit()

    except mariadb.Error:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


def delete_by_url(url: str) -> bool:
    """Cancella un GS senza cancellare la web resource"""

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            DELETE FROM gold_standard
            WHERE url = ?
            """,
            (url,),
        )

        deleted = cursor.rowcount > 0
        connection.commit()
        return deleted

    except mariadb.Error:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


def count() -> int:
    """Restituisce il numero totale di GS"""

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM gold_standard
            """
        )

        row = cursor.fetchone()
        return int(row[0])

    finally:
        cursor.close()
        connection.close()


def count_by_domain() -> dict[str, int]:
    """Restituisce il numero di GS per dominio"""

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                wr.domain,
                COUNT(*)
            FROM gold_standard AS gs
            INNER JOIN web_resources AS wr
                ON wr.url = gs.url
            GROUP BY wr.domain
            ORDER BY wr.domain
            """
        )

        return {
            domain: int(entry_count)
            for domain, entry_count in cursor.fetchall()
        }

    finally:
        cursor.close()
        connection.close()