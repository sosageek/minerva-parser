"""Verifica schema seed e repository senza un database reale"""

from backend.src.db import schema, seed


class FakeCursor:
    """Registra le query senza usare MariaDB"""
    def __init__(self):
        """Prepara gli elenchi delle query registrate"""
        self.executed = []
        self.executed_many = []

    def execute(self, query, params=None):
        """Registra una query singola e i suoi parametri"""
        self.executed.append((query, params))

    def executemany(self, query, params):
        """Registra una query eseguita con più parametri"""
        self.executed_many.append((query, list(params)))

    def close(self):
        """Imita la chiusura del cursore senza fare nulla"""
        pass


class FakeConnection:
    """Registra commit e rollback senza usare MariaDB"""
    def __init__(self):
        """Prepara il cursore e i contatori della transazione"""
        self.cursor_instance = FakeCursor()
        self.commits = 0
        self.rollbacks = 0

    def cursor(self, **kwargs):
        """Restituisce sempre lo stesso cursore finto"""
        return self.cursor_instance

    def commit(self):
        """Conta i commit richiesti dal codice sotto test"""
        self.commits += 1

    def rollback(self):
        """Conta i rollback richiesti dal codice sotto test"""
        self.rollbacks += 1

    def close(self):
        """Imita la chiusura della connessione senza fare nulla"""
        pass


def test_initialize_schema_creates_parent_tables_first(monkeypatch):
    """Crea le tabelle padre prima delle tabelle collegate"""
    connection = FakeConnection()
    monkeypatch.setattr(schema, "get_connection", lambda: connection)

    schema.initialize_schema()

    statements = [query for query, _ in connection.cursor_instance.executed]
    assert "CREATE TABLE IF NOT EXISTS web_resources" in statements[0]
    assert "CREATE TABLE IF NOT EXISTS gold_standard" in statements[1]
    assert "CREATE TABLE IF NOT EXISTS evaluation_results" in statements[2]
    assert "CREATE TABLE IF NOT EXISTS judge_results" in statements[3]
    assert connection.commits == 1


def test_gold_standard_seed_uses_idempotent_upserts(monkeypatch):
    """Usa upsert idempotenti per caricare il Gold Standard"""
    connection = FakeConnection()
    monkeypatch.setattr(seed, "get_connection", lambda: connection)
    monkeypatch.setattr(
        seed,
        "_load_seed_entries",
        lambda: [
            {
                "url": "https://example.test/page",
                "domain": "example.test",
                "title": "Title",
                "html_text": "<main>Text</main>",
                "gold_text": "Text",
            }
        ],
    )

    seed.seed_gold_standards()

    queries = [query for query, _ in connection.cursor_instance.executed_many]
    assert all("ON DUPLICATE KEY UPDATE" in query for query in queries)
    assert connection.commits == 1


def test_precomputed_seed_requires_exact_gold_standard_urls(monkeypatch):
    """Rifiuta risultati che non coprono tutti gli URL del Gold Standard"""
    monkeypatch.setattr(
        seed,
        "_load_seed_entries",
        lambda: [{"url": "https://example.test/expected"}],
    )
    monkeypatch.setattr(seed, "_read_json_file", lambda path: [])

    try:
        seed._load_precomputed_results()
    except ValueError as error:
        assert "non corrispondono al GS" in str(error)
    else:
        raise AssertionError("Il seed incompleto deve essere rifiutato")
