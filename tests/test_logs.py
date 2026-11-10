import json
from datetime import datetime, timedelta, timezone

from src.logs import RunLog, Status


def test_record_appends_jsonl_entry(tmp_path):
    log = RunLog(tmp_path / "results.jsonl")

    entry = log.record("João Silva", "5511999999999", "Olá!", Status.SENT)

    assert entry.status == Status.SENT
    entries = log.read_all()
    assert len(entries) == 1
    assert entries[0].phone == "5511999999999"


def test_already_processed_phones_only_counts_terminal_statuses(tmp_path):
    log = RunLog(tmp_path / "results.jsonl")

    log.record("João Silva", "5511999999999", "Olá!", Status.PENDING)
    log.record("João Silva", "5511999999999", "Olá!", Status.SENT)
    log.record("Maria Souza", "5511988888888", "Olá!", Status.FAILED, reason="timeout")
    log.record("Pedro Santos", "5511977777777", "Olá!", Status.SKIPPED, reason="not approved")

    processed = log.already_processed_phones()

    assert processed == {"5511999999999", "5511977777777"}


def test_record_with_reason_persists_it(tmp_path):
    log = RunLog(tmp_path / "results.jsonl")

    log.record("João Silva", "5511999999999", "Olá!", Status.FAILED, reason="invalid number")

    entries = log.read_all()
    assert entries[0].reason == "invalid number"


def test_already_processed_phones_expires_after_cooldown(tmp_path):
    path = tmp_path / "results.jsonl"
    log = RunLog(path)
    old_timestamp = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    stale_entry = {
        "name": "João Silva",
        "phone": "5511999999999",
        "timestamp": old_timestamp,
        "message": "Olá!",
        "status": "SENT",
        "reason": None,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(stale_entry) + "\n")

    assert log.already_processed_phones() == set()
