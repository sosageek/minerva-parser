from ..database import get_connection


_REQUIRED_TABLES = (
    "web_resources",
    "gold_standard",
    "evaluation_results",
    "judge_results",
)


def get_schema() -> dict[str, dict[str, str]]:
    """Restituisce colonne e vincoli delle tabelle obbligatorie"""

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                TABLE_NAME,
                COLUMN_NAME,
                REFERENCED_TABLE_NAME,
                REFERENCED_COLUMN_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
                AND REFERENCED_TABLE_NAME IS NOT NULL
                AND TABLE_NAME IN (?, ?, ?, ?)
            """,
            _REQUIRED_TABLES,
        )

        foreign_keys = {
            (table_name, column_name): (
                f"{referenced_table}.{referenced_column}"
            )
            for (
                table_name,
                column_name,
                referenced_table,
                referenced_column,
            ) in cursor.fetchall()
        }

        cursor.execute(
            """
            SELECT
                TABLE_NAME,
                COLUMN_NAME,
                COLUMN_TYPE,
                COLUMN_KEY
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME IN (?, ?, ?, ?)
            ORDER BY
                TABLE_NAME,
                ORDINAL_POSITION
            """,
            _REQUIRED_TABLES,
        )

        schema = {
            table_name: {}
            for table_name in _REQUIRED_TABLES
        }

        for table_name, column_name, column_type, column_key in cursor.fetchall():
            details = [column_type.lower()]

            if column_key == "PRI":
                details.append("PK")

            foreign_key = foreign_keys.get(
                (table_name, column_name)
            )

            if foreign_key is not None:
                details.append(f"FK({foreign_key})")

            schema[table_name][column_name] = ", ".join(details)

        return schema

    finally:
        cursor.close()
        connection.close()
