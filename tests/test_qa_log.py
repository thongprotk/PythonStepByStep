import app.db.qa_log as qa_log_module
from app.db.qa_log import log_qa_session


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeTable:
    def __init__(self, sink):
        self._sink = sink

    def insert(self, payload):
        self._sink.append(payload)
        return self

    def execute(self):
        return _FakeResponse(self._sink)


class _FakeClient:
    def __init__(self, sink):
        self._sink = sink

    def table(self, name):
        assert name == "qa_logs"
        return _FakeTable(self._sink)


def test_log_qa_session_inserts_into_supabase(monkeypatch):
    sink: list[dict] = []
    monkeypatch.setattr(qa_log_module, "get_supabase", lambda: _FakeClient(sink))

    log_qa_session("/chat", "hello", "hi there", extra={"confidence": 0.9})

    assert sink == [
        {
            "endpoint": "/chat",
            "user_message": "hello",
            "answer": "hi there",
            "extra": {"confidence": 0.9},
        }
    ]


def test_log_qa_session_defaults_extra_to_empty_dict(monkeypatch):
    sink: list[dict] = []
    monkeypatch.setattr(qa_log_module, "get_supabase", lambda: _FakeClient(sink))

    log_qa_session("/chat", "hello", "hi there")

    assert sink[0]["extra"] == {}


def test_log_qa_session_falls_back_to_error_log_on_failure(monkeypatch):
    def raise_error():
        raise RuntimeError("SUPABASE_URL / SUPABASE_KEY is not configured")

    monkeypatch.setattr(qa_log_module, "get_supabase", raise_error)

    captured = {}
    monkeypatch.setattr(
        qa_log_module,
        "log_error",
        lambda source, error, context: captured.update(
            source=source, error=error, context=context
        ),
    )

    log_qa_session("/chat", "hello", "hi there")

    assert captured["source"] == "qa_log:/chat"
    assert "not configured" in captured["error"]
    assert captured["context"] == {"user_message": "hello"}


def test_log_qa_session_never_raises_on_upstream_error(monkeypatch):
    class BrokenClient:
        def table(self, name):
            raise RuntimeError("connection reset")

    monkeypatch.setattr(qa_log_module, "get_supabase", lambda: BrokenClient())
    monkeypatch.setattr(qa_log_module, "log_error", lambda *a, **k: None)

    # Must not raise.
    log_qa_session("/mida-assistant", "hello", "hi there")
