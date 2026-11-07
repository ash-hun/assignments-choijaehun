"""PostgreSQL + pgvector에 청크와 dense, sparse 벡터를 저장하고 검색한다. 데이터베이스 선정 실험의 후보 구현이다."""
import json
import numpy as np
from pgvector import SparseVector
from psycopg import sql, AsyncConnection
from pgvector.psycopg import register_vector_async

from app.schema.vector_schema import SPARSE_DIM, SparseTerms, IndexContract
from app.schema.chunk_schema import Chunk

RRF_K = 60


class PgvectorChunkRepository:
    """테이블 하나가 인덱스 하나다. 인덱스 계약은 별도 테이블에 컬렉션 이름을 키로 둔다. SQL은 모두 바인딩과 식별자 조합으로 만든다."""

    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    async def ensure_collection(self, name: str, dim: int, contract: IndexContract) -> None:
        """확장, 계약 테이블, 청크 테이블, HNSW 인덱스를 없으면 만든다."""
        table = sql.Identifier(name)
        async with self._conn.transaction():
            await self._conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await register_vector_async(self._conn)
            await self._conn.execute("CREATE TABLE IF NOT EXISTS index_contract (collection text PRIMARY KEY, contract jsonb NOT NULL)")
            await self._conn.execute(sql.SQL(
                "CREATE TABLE IF NOT EXISTS {} (chunk_id text PRIMARY KEY, doc_id text NOT NULL, ordinal int NOT NULL, "
                "text text NOT NULL, dense vector({}) NOT NULL, sparse sparsevec({}) NOT NULL)"
            ).format(table, sql.Literal(dim), sql.Literal(SPARSE_DIM)))
            await self._conn.execute(sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} USING hnsw (dense vector_cosine_ops)").format(
                sql.Identifier(f"{name}_dense_hnsw"), table))
            await self._conn.execute(sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} (doc_id)").format(sql.Identifier(f"{name}_doc_id"), table))
            await self._conn.execute(
                "INSERT INTO index_contract (collection, contract) VALUES (%s, %s) ON CONFLICT (collection) DO NOTHING",
                (name, json.dumps(contract.model_dump())),
            )

    async def drop_collection(self, name: str) -> None:
        """실험용 초기화. 운영 경로에서는 부르지 않는다."""
        async with self._conn.transaction():
            await self._conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(name)))
            await self._conn.execute("CREATE TABLE IF NOT EXISTS index_contract (collection text PRIMARY KEY, contract jsonb NOT NULL)")
            await self._conn.execute("DELETE FROM index_contract WHERE collection = %s", (name,))

    async def read_contract(self, name: str) -> IndexContract | None:
        """계약 테이블에서 읽는다."""
        cur = await self._conn.execute("SELECT contract FROM index_contract WHERE collection = %s", (name,))
        row = await cur.fetchone()
        return IndexContract.model_validate(row[0]) if row else None

    async def upsert(self, name: str, chunks: list[Chunk], dense: np.ndarray, sparse: list[SparseTerms]) -> None:
        """chunk_id 기본 키로 덮어쓴다."""
        query = sql.SQL(
            "INSERT INTO {} (chunk_id, doc_id, ordinal, text, dense, sparse) VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (chunk_id) DO UPDATE SET doc_id = EXCLUDED.doc_id, ordinal = EXCLUDED.ordinal, "
            "text = EXCLUDED.text, dense = EXCLUDED.dense, sparse = EXCLUDED.sparse"
        ).format(sql.Identifier(name))
        rows = [
            (c.chunk_id, c.doc_id, c.ordinal, c.text, dense[i], _to_sparsevec(sparse[i]))
            for i, c in enumerate(chunks)
        ]
        async with self._conn.transaction():
            async with self._conn.cursor() as cur:
                await cur.executemany(query, rows)

    async def count(self, name: str) -> int:
        """저장된 청크 수."""
        cur = await self._conn.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(name)))
        row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def search_dense(self, name: str, vector: np.ndarray, k: int, exact: bool = False, doc_id: str | None = None) -> list[str]:
        """코사인 거리 상위 k개 chunk_id. exact면 인덱스 스캔을 꺼서 전수 비교한다."""
        where = sql.SQL("WHERE doc_id = %s") if doc_id else sql.SQL("")
        query = sql.SQL("SELECT chunk_id FROM {} {} ORDER BY dense <=> %s LIMIT %s").format(sql.Identifier(name), where)
        params = ((doc_id,) if doc_id else ()) + (vector, k)
        async with self._conn.transaction():
            if exact:
                await self._conn.execute("SET LOCAL enable_indexscan = off")
            cur = await self._conn.execute(query, params)
            return [r[0] for r in await cur.fetchall()]

    async def search_sparse(self, name: str, sparse: SparseTerms, k: int) -> list[str]:
        """sparse 내적 상위 k개 chunk_id. pgvector에는 IDF 가중이 없어 값을 그대로 곱한다."""
        query = sql.SQL("SELECT chunk_id FROM {} ORDER BY sparse <#> %s LIMIT %s").format(sql.Identifier(name))
        cur = await self._conn.execute(query, (_to_sparsevec(sparse), k))
        return [r[0] for r in await cur.fetchall()]

    async def search_hybrid(self, name: str, vector: np.ndarray, sparse: SparseTerms, k: int) -> list[str]:
        """dense와 sparse 순위를 SQL 안에서 RRF로 합친다. pgvector에는 내장 결합 검색이 없다."""
        query = sql.SQL(
            "WITH d AS (SELECT chunk_id, row_number() OVER (ORDER BY dense <=> %s) AS r FROM {t} ORDER BY dense <=> %s LIMIT %s), "
            "s AS (SELECT chunk_id, row_number() OVER (ORDER BY sparse <#> %s) AS r FROM {t} ORDER BY sparse <#> %s LIMIT %s) "
            "SELECT chunk_id, sum(1.0 / (%s + r)) AS score FROM (SELECT * FROM d UNION ALL SELECT * FROM s) u "
            "GROUP BY chunk_id ORDER BY score DESC, chunk_id LIMIT %s"
        ).format(t=sql.Identifier(name))
        sv = _to_sparsevec(sparse)
        cur = await self._conn.execute(query, (vector, vector, k * 4, sv, sv, k * 4, RRF_K, k))
        return [r[0] for r in await cur.fetchall()]


def _to_sparsevec(terms: SparseTerms) -> SparseVector:
    return SparseVector(dict(zip(terms.indices, terms.values)), SPARSE_DIM)
