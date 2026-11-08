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

    async def judgments_for(self, record_ids: list[str]) -> list[JudgeResult]:
        """기록 id 목록의 판정 전부. 기록, 종류, 표본 순."""
        if not record_ids:
            return []
        cursor = await self._conn.execute(
            "SELECT body FROM judge_result WHERE record_id = ANY(%s) ORDER BY record_id, kind, sample, prompt_version",
            (record_ids,),
        )
        return [JudgeResult.model_validate(row[0]) for row in await cursor.fetchall()]

    async def live_records(self, config_id: str, limit: int) -> list[EvalRecord]:
        """구성 하나의 실시간 기록 중 최근 limit개를 오래된 것부터."""
        cursor = await self._conn.execute(
            "SELECT body FROM (SELECT body, created_at, record_id FROM eval_record WHERE source = 'live' AND config_id = %s "
            "ORDER BY created_at DESC, record_id DESC LIMIT %s) recent ORDER BY created_at, record_id",
            (config_id, limit),
        )
        return [EvalRecord.model_validate(row[0]) for row in await cursor.fetchall()]

    async def unjudged_live(self, config_id: str, versions: list[str], limit: int) -> list[EvalRecord]:
        """답했지만 주어진 프롬프트 버전들의 판정이 모두 있지는 않은 실시간 기록. 재시작 뒤 이어서 채점할 대상이다."""
        cursor = await self._conn.execute(
            "SELECT r.body FROM eval_record r WHERE r.source = 'live' AND r.config_id = %s AND r.status = 'answered' "
            "AND (SELECT count(DISTINCT j.prompt_version) FROM judge_result j WHERE j.record_id = r.record_id AND j.ok "
            "AND j.prompt_version = ANY(%s)) < cardinality(%s::text[]) ORDER BY r.created_at LIMIT %s",
            (config_id, versions, versions, limit),
        )
        return [EvalRecord.model_validate(row[0]) for row in await cursor.fetchall()]

    async def live_judge_tokens(self) -> tuple[int, int]:
        """실시간 기록에 쓴 Judge 입력, 출력 토큰 합. 예산 상한을 재시작 뒤에도 이어서 센다."""
        cursor = await self._conn.execute(
            "SELECT coalesce(sum((j.body->>'input_tokens')::bigint), 0), coalesce(sum((j.body->>'output_tokens')::bigint), 0) "
            "FROM judge_result j JOIN eval_record r ON r.record_id = j.record_id WHERE r.source = 'live'"
        )
        row = await cursor.fetchone()
        return (int(row[0]), int(row[1])) if row else (0, 0)

    async def latest_gold_run(self, config_id: str) -> str | None:
        """같은 구성의 변형 없는 Gold Set 실행 중 가장 최근 것. 대시보드 기준선으로 쓴다."""
        cursor = await self._conn.execute(
            "SELECT run_id FROM eval_run WHERE config_id = %s AND coalesce(manifest->'config'->>'variant', 'none') = 'none' "
            "ORDER BY updated_at DESC LIMIT 1",
            (config_id,),
        )
        row = await cursor.fetchone()
        return str(row[0]) if row else None
