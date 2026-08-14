from backend.src.db import schema, seed


class FakeCursor:
    def __init__(self):
        self.executed = []
        self.executed_many = []

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def executemany(self, query, params):
        self.executed_many.append((query, list(params)))

    def close(self):
        pass


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.commits = 0
        self.rollbacks = 0

    def cursor(self, **kwargs):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


def test_initialize_schema_creates_parent_tables_first(monkeypatch):
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
