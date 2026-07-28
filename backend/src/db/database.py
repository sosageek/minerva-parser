import mariadb

from ..config import (
    DATABASE_HOST,
    DATABASE_NAME,
    DATABASE_PASSWORD,
    DATABASE_POOL_SIZE,
    DATABASE_PORT,
    DATABASE_USER,
)


_pool: mariadb.ConnectionPool | None = None


def create_pool() -> None:
    """Crea il pool di connessioni al database"""

    global _pool

    if _pool is not None:
        return

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


def get_connection() -> mariadb.Connection:
    """Preleva una connessione dal pool

        è un wrapper di `_pool.get_connection()` con controllo
        sull'esistenza del pool
    """

    if _pool is None:
        raise RuntimeError("Database pool non inizializzato")

    return _pool.get_connection()


def close_pool() -> None:
    """Chiude il pool durante lo shutdown del backend"""

    global _pool

    if _pool is not None:
        _pool.close()
        _pool = None