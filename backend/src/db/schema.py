import logging

import mariadb

from .database import get_connection


logger = logging.getLogger("minerva-parser.database")


_CREATE_WEB_RESOURCES = """
CREATE TABLE IF NOT EXISTS web_resources (
    url VARCHAR(768) NOT NULL,
    domain VARCHAR(255) NOT NULL,
    title TEXT NOT NULL,
    html_text LONGTEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (url)
)
ENGINE=InnoDB
DEFAULT CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci
"""

_CREATE_GOLD_STANDARD = """
CREATE TABLE IF NOT EXISTS gold_standard (
    url VARCHAR(768) NOT NULL,
    gold_text LONGTEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (url),

    CONSTRAINT fk_gold_standard_web_resource
        FOREIGN KEY (url)
        REFERENCES web_resources(url)
        ON UPDATE CASCADE
        ON DELETE CASCADE
)
ENGINE=InnoDB
DEFAULT CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci
"""

def initialize_schema() -> None:
    """Crea le tabelle obbligatorie se non esistono"""

    connection = get_connection()
    cursor = connection.cursor()

    try: 
        cursor.execute(_CREATE_WEB_RESOURCES)
        cursor.execute(_CREATE_GOLD_STANDARD)
        # NON INVERTIRE: prima la tabella principale, poi quella con la foreign key

        connection.commit()
        logger.info("Schema MariaDB inizializzato")

    except mariadb.Error:
        connection.rollback()
        logger.exception("Inizializzazione schema MariaDB fallita")
        raise

    finally:
        cursor.close()
        connection.close()