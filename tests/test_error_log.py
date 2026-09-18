import json

from app.core.error_log import log_error, search_errors


def test_log_error_appends_jsonl_entry(tmp_path):
    log_path = tmp_path / "errors.jsonl"
    log_error("qa_log:/chat", "connection reset", {"user_message": "hi"}, log_path)

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["source"] == "qa_log:/chat"
    assert entry["error"] == "connection reset"
    assert entry["context"] == {"user_message": "hi"}
    assert "timestamp" in entry


def test_log_error_appends_multiple_entries(tmp_path):
    log_path = tmp_path / "errors.jsonl"
    log_error("a", "first", {}, log_path)
    log_error("b", "second", {}, log_path)
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 2


def test_search_errors_matches_keyword_case_insensitive(tmp_path):
    log_path = tmp_path / "errors.jsonl"
    log_error("qa_log:/chat", "Connection Reset by peer", {}, log_path)
    log_error("qa_log:/mida-assistant", "timeout", {}, log_path)

    matches = search_errors("connection reset", log_path=log_path)
    assert len(matches) == 1
    assert matches[0]["source"] == "qa_log:/chat"


def test_search_errors_no_match_returns_empty(tmp_path):
    log_path = tmp_path / "errors.jsonl"
    log_error("a", "first", {}, log_path)
    assert search_errors("nonexistent", log_path=log_path) == []


def test_search_errors_missing_file_returns_empty(tmp_path):
    assert search_errors("anything", log_path=tmp_path / "does-not-exist.jsonl") == []


def test_search_errors_respects_limit(tmp_path):
    log_path = tmp_path / "errors.jsonl"
    for i in range(5):
        log_error("qa_log:/chat", f"error {i}", {}, log_path)
    matches = search_errors("error", limit=2, log_path=log_path)
    assert len(matches) == 2
    # keeps the most recent ones
    assert matches[-1]["error"] == "error 4"
