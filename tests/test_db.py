from fastapi.testclient import TestClient

import app.api.routes.db as db_route
from app.main import app

client = TestClient(app)


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeTable:
    def __init__(self, rows):
        self._rows = rows
        self._inserted = None

    def select(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def insert(self, payload):
        self._inserted = {"id": 1, **payload}
        return self

    def execute(self):
        if self._inserted is not None:
            return _FakeResponse([self._inserted])
        return _FakeResponse(self._rows)


class _FakeClient:
    def __init__(self, rows=None):
        self._rows = rows or []

    def table(self, name):
        assert name == "todos"
        return _FakeTable(self._rows)


def test_db_health_without_creds_returns_500(monkeypatch):
    def _raise():
        raise RuntimeError("SUPABASE_URL / SUPABASE_KEY is not configured")

    monkeypatch.setattr(db_route, "get_supabase", _raise)
    response = client.get("/db/health")
    assert response.status_code == 500


def test_list_todos_with_mock(monkeypatch):
    monkeypatch.setattr(
        db_route, "get_supabase", lambda: _FakeClient([{"id": 1, "name": "demo"}])
    )
    response = client.get("/db/todos")
    assert response.status_code == 200
    assert response.json() == [{"id": 1, "name": "demo"}]


def test_create_todo_with_mock(monkeypatch):
    monkeypatch.setattr(db_route, "get_supabase", lambda: _FakeClient())
    response = client.post("/db/todos", json={"name": "buy milk"})
    assert response.status_code == 201
    assert response.json() == {"id": 1, "name": "buy milk"}


def test_db_provider_error_returns_502(monkeypatch):
    class BrokenClient:
        def table(self, name):
            raise RuntimeError("connection reset")

    monkeypatch.setattr(db_route, "get_supabase", lambda: BrokenClient())
    response = client.get("/db/todos")
    assert response.status_code == 502
