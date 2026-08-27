"""Regression tests for examples/backend/fastapi/usage_proxy.py.

Covers:
- GET /balance is read-only (no provider call, no deduction, no usage record).
- Schema forward-migration adds missing columns without losing data, idempotently.
- Cost provenance: provider tokens vs local pricing; explicit monetary cost only.
- Overdraft protection: atomic charge, never negative, 402 on insufficient,
  no charged record written on rejection, concurrency-safe.
"""
import os
import sqlite3
import threading

import pytest


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    import examples.backend.fastapi.usage_proxy as proxy_mod

    def build(payload, balance="10.0", seed_old_schema=False):
        db = tmp_path / "usage_test.db"
        monkeypatch.setenv("CREDIT_DB_PATH", str(db))
        import sys
        import importlib
        sys.modules.pop(proxy_mod.__name__, None)
        import examples.backend.fastapi.usage_proxy as proxy
        importlib.reload(proxy)

        if seed_old_schema:
            conn = sqlite3.connect(str(db), isolation_level=None)
            conn.execute("DROP TABLE IF EXISTS usage_records")
            conn.execute(
                "CREATE TABLE usage_records ("
                "id TEXT PRIMARY KEY, project_id TEXT, ts TEXT, provider TEXT, model TEXT, "
                "prompt_tokens INTEGER, completion_tokens INTEGER, estimated_cost TEXT, "
                "provider_request_id TEXT, is_estimated INTEGER)"
            )
            conn.commit()
            conn.close()
            proxy.migrate_db(sqlite3.connect(str(db), isolation_level=None))

        conn = sqlite3.connect(str(db), isolation_level=None)
        conn.execute(
            "INSERT INTO projects (id,name,credit_balance) VALUES (?,?,?)",
            ("p1", "demo", str(balance)),
        )
        conn.commit()
        conn.close()

        class FakeResponse:
            def __init__(self, p):
                self._p = p
                self.status_code = 200

            def json(self):
                return self._p

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def post(self, url, json=None, headers=None):
                return FakeResponse(payload)

        proxy.httpx.AsyncClient = FakeAsyncClient
        from fastapi.testclient import TestClient
        return TestClient(proxy.app)

    return build


def _row(db):
    conn = sqlite3.connect(db, isolation_level=None)
    r = conn.execute(
        "SELECT is_estimated, cost_source, token_source, actual_cost "
        "FROM usage_records"
    ).fetchone()
    conn.close()
    return r


def _balance(db):
    conn = sqlite3.connect(db, isolation_level=None)
    b = conn.execute("SELECT credit_balance FROM projects WHERE id='p1'").fetchone()[0]
    conn.close()
    return b


def test_balance_get_is_read_only(make_client):
    calls = []
    payload = {"usage": {}}
    # capture provider calls via a wrapper
    import examples.backend.fastapi.usage_proxy as proxy

    class FakeResponse:
        def __init__(self, p):
            self._p = p
            self.status_code = 200

        def json(self):
            return self._p

    class FakeAsyncClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *e):
            return False

        async def post(self, url, json=None, headers=None):
            calls.append(url)
            return FakeResponse(payload)

    proxy.httpx.AsyncClient = FakeAsyncClient
    client = make_client(payload)
    r = client.get("/api/projects/p1/balance")
    assert r.status_code == 200
    assert r.json()["balance"] == "10.0"

    assert calls == []  # GET never calls provider

    db = os.environ["CREDIT_DB_PATH"]
    assert _balance(db) == "10.0"
    conn = sqlite3.connect(db, isolation_level=None)
    cnt = conn.execute("SELECT COUNT(*) FROM usage_records").fetchone()[0]
    conn.close()
    assert cnt == 0


def test_provider_tokens_without_monetary_stays_estimated(make_client):
    client = make_client({"id": "r1", "usage": {"prompt_tokens": 5, "completion_tokens": 3}})
    r = client.post("/api/agent/request", json={"project_id": "p1", "prompt": "hi", "model": "gpt-3.5-cheap"})
    assert r.status_code == 200
    data = r.json()["usage"]
    assert data["cost_source"] == "estimate"
    assert data["token_source"] == "provider"
    assert data["actual_cost"] is None
    row = _row(os.environ["CREDIT_DB_PATH"])
    assert row[0] == 1 and row[1] == "estimate" and row[2] == "provider" and row[3] is None


def test_provider_explicit_monetary_is_provider_confirmed(make_client):
    client = make_client({"id": "r2", "usage": {"prompt_tokens": 5, "completion_tokens": 3, "cost": 0.0017}})
    r = client.post("/api/agent/request", json={"project_id": "p1", "prompt": "hi", "model": "gpt-3.5-cheap"})
    assert r.status_code == 200
    data = r.json()["usage"]
    assert data["cost_source"] == "provider"
    assert data["actual_cost"] == "0.0017"
    row = _row(os.environ["CREDIT_DB_PATH"])
    assert row[0] == 0 and row[1] == "provider" and row[3] == "0.0017"


def test_zero_tokens_recognized_as_provider(make_client):
    client = make_client({"id": "r3", "usage": {"prompt_tokens": 0, "completion_tokens": 0}})
    r = client.post("/api/agent/request", json={"project_id": "p1", "prompt": "hi", "model": "gpt-3.5-cheap"})
    assert r.status_code == 200
    data = r.json()["usage"]
    assert data["token_source"] == "provider"
    assert data["prompt_tokens"] == 0
    assert data["completion_tokens"] == 0
    assert data["cost_source"] == "estimate"
    assert data["actual_cost"] is None
    row = _row(os.environ["CREDIT_DB_PATH"])
    assert row[2] == "provider" and row[1] == "estimate"


def test_migration_adds_columns_idempotent_preserves_rows(make_client, tmp_path, monkeypatch):
    db = tmp_path / "old.db"
    monkeypatch.setenv("CREDIT_DB_PATH", str(db))
    import sys
    import importlib
    import examples.backend.fastapi.usage_proxy as proxy
    sys.modules.pop(proxy.__name__, None)
    import examples.backend.fastapi.usage_proxy as proxy
    importlib.reload(proxy)
    conn = sqlite3.connect(str(db), isolation_level=None)
    conn.execute("DROP TABLE IF EXISTS usage_records")
    conn.execute(
        "CREATE TABLE usage_records ("
        "id TEXT PRIMARY KEY, project_id TEXT, ts TEXT, provider TEXT, model TEXT, "
        "prompt_tokens INTEGER, completion_tokens INTEGER, estimated_cost TEXT, "
        "provider_request_id TEXT, is_estimated INTEGER)"
    )
    conn.execute(
        "INSERT INTO usage_records (id, project_id, ts, provider, model, prompt_tokens, "
        "completion_tokens, estimated_cost, provider_request_id, is_estimated) "
        "VALUES ('old1','p1','now','manus','m',1,2,'0.001','r',0)"
    )
    conn.commit()
    conn.close()

    proxy.migrate_db(sqlite3.connect(str(db), isolation_level=None))
    c2 = sqlite3.connect(str(db), isolation_level=None)
    cols = {r[1] for r in c2.execute("PRAGMA table_info(usage_records)").fetchall()}
    for col in ("actual_cost", "cost_source", "token_source", "is_estimated"):
        assert col in cols
    row = c2.execute("SELECT id, project_id FROM usage_records WHERE id='old1'").fetchone()
    assert row[0] == "old1" and row[1] == "p1"
    proxy.migrate_db(c2)  # idempotent re-run
    c2.close()

    # POST works after migration.
    c3 = sqlite3.connect(str(db), isolation_level=None)
    c3.execute("INSERT INTO projects (id,name,credit_balance) VALUES ('p2','d','10.0')")
    c3.commit()
    c3.close()
    from fastapi.testclient import TestClient
    r = TestClient(proxy.app).post(
        "/api/agent/request", json={"project_id": "p2", "prompt": "hi", "model": "gpt-3.5-cheap"}
    )
    assert r.status_code == 200


def test_actual_cost_below_balance(make_client):
    client = make_client({"id": "r", "usage": {"prompt_tokens": 5, "completion_tokens": 3, "cost": 0.0017}}, balance="10.0")
    r = client.post("/api/agent/request", json={"project_id": "p1", "prompt": "hi", "model": "gpt-3.5-cheap"})
    assert r.status_code == 200
    assert float(_balance(os.environ["CREDIT_DB_PATH"])) > 0


def test_actual_cost_exactly_equal_to_balance(make_client):
    client = make_client({"id": "r", "usage": {"prompt_tokens": 5, "completion_tokens": 3, "cost": 0.005}}, balance="0.005")
    r = client.post("/api/agent/request", json={"project_id": "p1", "prompt": "hi", "model": "gpt-3.5-cheap"})
    assert r.status_code == 200
    assert float(_balance(os.environ["CREDIT_DB_PATH"])) == 0


def test_actual_cost_over_balance_returns_402_no_deduction(make_client):
    client = make_client({"id": "r", "usage": {"prompt_tokens": 5, "completion_tokens": 3, "cost": 0.005}}, balance="0.001")
    r = client.post("/api/agent/request", json={"project_id": "p1", "prompt": "hi", "model": "gpt-3.5-cheap"})
    assert r.status_code == 402
    # balance unchanged, no charged record written
    assert _balance(os.environ["CREDIT_DB_PATH"]) == "0.001"
    db = os.environ["CREDIT_DB_PATH"]
    conn = sqlite3.connect(db, isolation_level=None)
    cnt = conn.execute("SELECT COUNT(*) FROM usage_records").fetchone()[0]
    conn.close()
    assert cnt == 0


def test_concurrent_deductions_do_not_overdraw(tmp_path, monkeypatch):
    db = tmp_path / "cc.db"
    monkeypatch.setenv("CREDIT_DB_PATH", str(db))
    import sys
    import importlib
    import examples.backend.fastapi.usage_proxy as proxy
    sys.modules.pop(proxy.__name__, None)
    import examples.backend.fastapi.usage_proxy as proxy
    importlib.reload(proxy)
    conn = sqlite3.connect(str(db), isolation_level=None)
    conn.execute("INSERT INTO projects (id,name,credit_balance) VALUES ('p1','d','0.0017')")
    conn.commit()
    conn.close()

    charged = __import__("decimal").Decimal("0.0017")
    results = []

    def worker(rid):
        c = sqlite3.connect(str(db), timeout=30, isolation_level=None)
        params = (rid, "p1", "manus", "gpt-3.5-cheap", 5, 3, "0.000008", None, "estimate", "provider", "req1", 1)
        ok, _ = proxy.apply_charge(c, "p1", charged, params)
        results.append(ok)
        c.close()

    t1 = threading.Thread(target=worker, args=("a",))
    t2 = threading.Thread(target=worker, args=("b",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert results.count(True) == 1
    c = sqlite3.connect(str(db), isolation_level=None)
    bal = __import__("decimal").Decimal(c.execute("SELECT credit_balance FROM projects WHERE id='p1'").fetchone()[0])
    c.close()
    assert bal == __import__("decimal").Decimal("0")
