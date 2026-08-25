"""Gestisce il pool di connessioni MariaDB"""

import logging
import mariadb

from ..config import (
    DATABASE_HOST,
    DATABASE_NAME,
    DATABASE_PASSWORD,
    DATABASE_POOL_SIZE,
    DATABASE_PORT,
    DATABASE_USER,
)


logger = logging.getLogger("minerva-parser.database")
_pool: mariadb.ConnectionPool | None = None


def create_pool() -> None:
    """Crea il pool di connessioni al database"""

    global _pool

    if _pool is not None:
        return

    try:
        _pool = mariadb.ConnectionPool(
            pool_name="minerva_pool",
            pool_size=DATABASE_POOL_SIZE,
            pool_reset_connection=True,
            host=DATABASE_HOST,
            port=DATABASE_PORT,
            database=DATABASE_NAME,
            user=DATABASE_USER,
            password=DATABASE_PASSWORD,
            connect_timeout=5,
        )

        logger.info(
            "Pool MariaDB creato con %s connessioni",
            DATABASE_POOL_SIZE
        )

    except mariadb.Error:
        logger.exception("Creazione pool di connessioni fallita")
        raise


def get_connection() -> mariadb.Connection:
    """Preleva una connessione dal pool"""

    if _pool is None:
        raise RuntimeError("Database pool non inizializzato")

    try:
        return _pool.get_connection()

    except mariadb.PoolError:
        logger.exception("Nessuna connessione disponibile nel pool")
        raise

def ping_database() -> bool:
    """Verifica il database con query banale"""

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("SELECT 1")
        row = cursor.fetchone()
        return row == (1,)

    finally:
        cursor.close()
        connection.close()
    

def close_pool() -> None:
    """Chiude il pool durante lo shutdown del backend"""

    global _pool

    if _pool is None:
        return

    try:
        _pool.close()
        logger.info("Pool di connessioni chiuso")

    finally:
        _pool = None