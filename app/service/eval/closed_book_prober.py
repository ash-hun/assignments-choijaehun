"""데이터셋 선정 실험의 closed-book 검증. 문서 없이 모델에 물어 사전 지식으로 답하는 정도를 잰다."""
import asyncio

from app.schema.selection_schema import ClosedBookAnswer, ClosedBookQuestion
from app.client.llm_client import ChatMessage, LlmClient
from app.common.logger import get_logger

SYSTEM_PROMPT = (
    "You are a technical assistant. Answer the question concisely in 1-3 sentences, "
    "in the same language as the question. If you are not sure, say you don't know instead of guessing."
)
# 추론 토큰도 이 한도에 포함되는 모델이 있어 답변 길이(1~3문장)보다 넉넉하게 둔다.
MAX_COMPLETION_TOKENS = 1000

logger = get_logger(__name__)


class ClosedBookProber:
    """같은 모델, 같은 프롬프트, 같은 seed 목록으로 모든 후보의 문항에 답을 받는다."""

    def __init__(self, llm: LlmClient, seeds: list[int], concurrency: int, temperature: float | None = None) -> None:
        self._llm = llm
        self._seeds = seeds
        self._temperature = temperature
        self._semaphore = asyncio.Semaphore(concurrency)

    async def probe(self, corpus: str, questions: list[ClosedBookQuestion]) -> list[ClosedBookAnswer]:
        """문항 순서, seed 순서대로 답변을 돌려준다. 문항당 seed 개수만큼 답이 나온다."""
        jobs = [self._ask(corpus, q, s) for q in questions for s in self._seeds]
        return list(await asyncio.gather(*jobs))

    async def _ask(self, corpus: str, question: ClosedBookQuestion, seed: int) -> ClosedBookAnswer:
        async with self._semaphore:
            completion = await self._llm.complete(
                [ChatMessage(role="system", content=SYSTEM_PROMPT), ChatMessage(role="user", content=question.question)],
                seed=seed,
                max_completion_tokens=MAX_COMPLETION_TOKENS,
                temperature=self._temperature,
            )
        logger.info("closed_book_answered", corpus=corpus, id=question.id, seed=seed)
        return ClosedBookAnswer(
            id=question.id,
            corpus=corpus,
            category=question.category,
            model=completion.model,
            seed=seed,
            answer=completion.text,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
        )
