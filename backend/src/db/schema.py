"""Crea lo schema MariaDB del progetto"""

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
        ON DELETE CASCADE
)
ENGINE=InnoDB
DEFAULT CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci
"""

_CREATE_EVALUATION_RESULTS = """
CREATE TABLE IF NOT EXISTS evaluation_results (
    url VARCHAR(768) NOT NULL,
    parsed_text LONGTEXT NOT NULL,
    token_precision DOUBLE NOT NULL,
    recall_score DOUBLE NOT NULL,
    f1 DOUBLE NOT NULL,
    chrf DOUBLE NOT NULL,
    noise_ratio DOUBLE NOT NULL,
    rouge_1_precision DOUBLE NOT NULL,
    rouge_1_recall DOUBLE NOT NULL,
    rouge_1_f1 DOUBLE NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (url),

    CONSTRAINT fk_evaluation_results_gold_standard
        FOREIGN KEY (url)
        REFERENCES gold_standard(url)
        ON DELETE CASCADE,

    CONSTRAINT chk_evaluation_results_precision
        CHECK (token_precision BETWEEN 0 AND 1),
    CONSTRAINT chk_evaluation_results_recall
        CHECK (recall_score BETWEEN 0 AND 1),
    CONSTRAINT chk_evaluation_results_f1
        CHECK (f1 BETWEEN 0 AND 1)
)
ENGINE=InnoDB
DEFAULT CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci
"""

_CREATE_JUDGE_RESULTS = """
CREATE TABLE IF NOT EXISTS judge_results (
    url VARCHAR(768) NOT NULL,
    model_name VARCHAR(255) NOT NULL,
    judge_score TINYINT UNSIGNED NOT NULL,
    judge_feedback VARCHAR(500) NOT NULL,
    extra_noise VARCHAR(300) NOT NULL DEFAULT '',
    prompt_version VARCHAR(32) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (url),

    CONSTRAINT fk_judge_results_gold_standard
        FOREIGN KEY (url)
        REFERENCES gold_standard(url)
        ON DELETE CASCADE,

    CONSTRAINT chk_judge_results_score
        CHECK (judge_score BETWEEN 1 AND 5)
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
        cursor.execute(_CREATE_EVALUATION_RESULTS)
        cursor.execute(_CREATE_JUDGE_RESULTS)
        # NON INVERTIRE: le tabelle dipendenti vanno create dopo le rispettive FK

        connection.commit()
        logger.info("Schema inizializzato")

    except mariadb.Error:
        connection.rollback()
        logger.exception("Inizializzazione schema fallita")
        raise

    finally:
        cursor.close()
        connection.close()
