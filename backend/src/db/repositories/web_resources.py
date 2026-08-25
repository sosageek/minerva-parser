"""Salva e legge le risorse web"""

from typing import TypedDict
import mariadb
from ..database import get_connection


class WebResource(TypedDict):
    """Definizione di una web resource"""

    url: str
    domain: str
    title: str
    html_text: str


def get_by_url(url: str) -> WebResource | None:
    """Restituisce una web resource oppure None"""

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                url,
                domain,
                title,
                html_text
            FROM web_resources
            WHERE url = ?
            """,
            (url,),
        )

        return cursor.fetchone()

    finally:
        cursor.close()
        connection.close()


def upsert(url: str, domain: str, title: str, html_text: str) -> None:
    """Inserisce o aggiorna una web resource"""

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
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
            """,
            (
                url,
                domain,
                title,
                html_text,
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
    """Cancella una web resource"""

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            DELETE FROM web_resources
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
    """Restituisce il numero totale di web resources"""

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM web_resources
            """
        )

        row = cursor.fetchone()
        return int(row[0])

    finally:
        cursor.close()
        connection.close()


def count_by_domain() -> dict[str, int]:
    """Restituisce il numero di risorse per dominio"""

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                domain,
                COUNT(*)
            FROM web_resources
            GROUP BY domain
            ORDER BY domain
            """
        )

        return {
            domain: int(resource_count)
            for domain, resource_count in cursor.fetchall()
        }

    finally:
        cursor.close()
        connection.close()