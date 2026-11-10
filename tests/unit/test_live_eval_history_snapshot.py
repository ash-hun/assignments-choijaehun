"""live_eval 기능의 질의 내역 스냅샷(history_snapshot) 단위 테스트."""
import pytest
import asyncio
from pathlib import Path

from tests.integ.memory_backend import MemoryEvalRecordRepository
from app.service.live.history_snapshot import HistorySnapshot


def test_malformed_line_inserts_nothing_and_raises(tmp_path: Path) -> None:
    seed = tmp_path / "seed.jsonl"
    seed.write_text('{"kind": "run", "run_id": "r", "config_id": "c", "manifest": {}}\n{"kind": "unknown"}\n', encoding="utf-8")
    repository = MemoryEvalRecordRepository()

    with pytest.raises(ValueError, match="seed.jsonl:2"):
        asyncio.run(HistorySnapshot(repository).load(seed))
    assert repository.runs == {}


def test_empty_store_exports_an_empty_file(tmp_path: Path) -> None:
    seed = tmp_path / "out" / "seed.jsonl"

    counts = asyncio.run(HistorySnapshot(MemoryEvalRecordRepository()).export(seed, ["c"]))

    assert (counts.runs, counts.records, counts.judgments) == (0, 0, 0) and seed.read_text() == ""
