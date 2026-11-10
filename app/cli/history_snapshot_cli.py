"""질의 내역 스냅샷 내보내기 명령. 평가 기록 저장소의 실시간 기록과 대시보드 기준선을 data/seed/evaldb_seed.jsonl로 쓴다."""
import sys
import asyncio
import argparse
from psycopg import AsyncConnection

from app.repository.eval_record_repository import EvalRecordRepository
from app.service.eval.pipeline_identity import pipeline_config_id
from app.service.live.history_snapshot import HistorySnapshot
from app.service.eval.judge_prompt import prompt_version
from app.common.settings import Settings, get_settings
from app.schema.judge_schema import JUDGE_KINDS
from app.common.logger import get_logger

logger = get_logger(__name__)


async def export(settings: Settings, allow_unjudged: bool) -> int:
    """채점이 끝나지 않은 실시간 기록이 있으면 내보내지 않는다. 받은 사람의 API가 그 기록을 자기 크레딧으로 채점하게 되기 때문이다."""
    if settings.eval_db_password is None:
        raise SystemExit("EVAL_DB_PASSWORD must be set")
    versions = [prompt_version(kind) for kind in JUDGE_KINDS]
    async with await AsyncConnection.connect(
        host=settings.eval_db_host, port=settings.eval_db_port, dbname=settings.eval_db_name, user=settings.eval_db_user,
        password=settings.eval_db_password.get_secret_value(), autocommit=True, connect_timeout=10,
    ) as conn:
        repository = EvalRecordRepository(conn)
        await repository.ensure_schema()
        live = await repository.history_records([])
        configs = sorted({item.record.config_id for item in live})
        pending = sum([len(await repository.unjudged_live(c, versions, 10_000)) for c in configs])
        if pending and not allow_unjudged:
            logger.error("history_export_blocked", unjudged=pending,
                         hint="API를 띄워 둔 채 채점이 끝나기를 기다린 뒤 다시 내보낸다. 그래도 내보내려면 --allow-unjudged")
            return 1
        counts = await HistorySnapshot(repository).export(settings.history_seed_path,
                                                          [pipeline_config_id(settings, settings.default_top_k)])
    logger.info("history_exported", path=str(settings.history_seed_path), unjudged=pending, **counts.model_dump())
    return 0


def main(argv: list[str] | None = None) -> int:
    """같은 저장소 내용이면 같은 파일을 쓴다."""
    parser = argparse.ArgumentParser(prog="history-snapshot")
    parser.add_argument("command", choices=["export"])
    parser.add_argument("--allow-unjudged", action="store_true", help="채점이 끝나지 않은 실시간 기록이 있어도 내보낸다")
    args = parser.parse_args(argv)
    return asyncio.run(export(get_settings(), args.allow_unjudged))


if __name__ == "__main__":
    sys.exit(main())
