"""평가 기록 저장소(PostgreSQL). Gold Set 평가 실행과 질의별 기록을 남기고, 같은 키로 다시 쓰면 덮어쓴다."""
from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from app.schema.eval_schema import EvalRecord, EvalManifest
from app.schema.judge_schema import JudgeResult

# 스키마는 코드가 맞춘다. 몇 번 실행해도 같은 테이블과 인덱스가 된다.
SCHEMA = """
CREATE TABLE IF NOT EXISTS eval_run (
    run_id text PRIMARY KEY,
    config_id text NOT NULL,
    manifest jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS eval_record (
    record_id text PRIMARY KEY,
    run_id text REFERENCES eval_run (run_id) ON DELETE CASCADE,
    source text NOT NULL CHECK (source IN ('gold', 'live')),
    config_id text NOT NULL,
    item_id text,
    status text NOT NULL,
    body jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS eval_record_source_config ON eval_record (source, config_id, created_at);
CREATE INDEX IF NOT EXISTS eval_record_run ON eval_record (run_id);
CREATE TABLE IF NOT EXISTS judge_result (
    record_id text NOT NULL REFERENCES eval_record (record_id) ON DELETE CASCADE,
    kind text NOT NULL CHECK (kind IN ('citation', 'rubric')),
    sample integer NOT NULL,
    judge_model text NOT NULL,
    prompt_version text NOT NULL,
    ok boolean NOT NULL,
    body jsonb NOT NULL,
    PRIMARY KEY (record_id, kind, sample, judge_model, prompt_version)
);
"""


class EvalRecordRepository:
    """autocommit 연결 하나를 받는다. 문장 하나가 곧 트랜잭션 하나라, 중간에 죽어도 이미 쓴 기록은 남고 재실행이 이어서 쓴다."""

    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def ensure_schema(self) -> None:
        """테이블과 인덱스가 없으면 만든다."""
        await self._conn.execute(SCHEMA)

    async def upsert_run(self, run_id: str, manifest: EvalManifest) -> None:
        """실행 하나를 기록한다. 같은 run_id면 manifest(git commit 포함)를 최신으로 바꾼다."""
        await self._conn.execute(
            "INSERT INTO eval_run (run_id, config_id, manifest) VALUES (%s, %s, %s) "
            "ON CONFLICT (run_id) DO UPDATE SET manifest = EXCLUDED.manifest, updated_at = now()",
            (run_id, manifest.config_id, Jsonb(manifest.model_dump(mode="json"))),
        )

    async def records(self, run_id: str) -> list[EvalRecord]:
        """실행 하나의 기록 전부를 record_id 순으로."""
        cursor = await self._conn.execute("SELECT body FROM eval_record WHERE run_id = %s ORDER BY record_id", (run_id,))
        return [EvalRecord.model_validate(row[0]) for row in await cursor.fetchall()]

    async def upsert_record(self, record: EvalRecord) -> None:
        """record_id가 같으면 덮어쓴다. 같은 요청을 다시 보내거나 같은 실행을 다시 돌려도 행이 늘지 않는다."""
        await self._conn.execute(
            "INSERT INTO eval_record (record_id, run_id, source, config_id, item_id, status, body) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (record_id) DO UPDATE SET status = EXCLUDED.status, body = EXCLUDED.body",
            (record.record_id, record.run_id, record.source, record.config_id, record.item_id, record.status,
             Jsonb(record.model_dump(mode="json"))),
        )

    async def upsert_judgment(self, result: JudgeResult) -> None:
        """(기록, 종류, 표본, Judge 모델, 프롬프트 버전)이 같으면 덮어쓴다."""
        await self._conn.execute(
            "INSERT INTO judge_result (record_id, kind, sample, judge_model, prompt_version, ok, body) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (record_id, kind, sample, judge_model, prompt_version) DO UPDATE SET ok = EXCLUDED.ok, body = EXCLUDED.body",
            (result.record_id, result.kind, result.sample, result.judge_model, result.prompt_version, result.ok,
             Jsonb(result.model_dump(mode="json"))),
        )

    async def judgments(self, run_id: str) -> list[JudgeResult]:
        """실행 하나의 판정 전부. 기록, 종류, 표본 순."""
        cursor = await self._conn.execute(
            "SELECT j.body FROM judge_result j JOIN eval_record r ON r.record_id = j.record_id "
            "WHERE r.run_id = %s ORDER BY j.record_id, j.kind, j.sample, j.prompt_version",
            (run_id,),
        )
        return [JudgeResult.model_validate(row[0]) for row in await cursor.fetchall()]
