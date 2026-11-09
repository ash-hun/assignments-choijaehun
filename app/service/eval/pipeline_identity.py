"""질의 파이프라인 구성의 식별자. Gold Set 평가와 실시간 질의가 같은 함수로 계산해 같은 구성이면 같은 config_id를 쓴다."""
import json
import hashlib

from app.service.query.prompt_builder import build_messages
from app.common.settings import Settings


def answer_prompt_hash() -> str:
    """답변 프롬프트 템플릿의 해시 앞 12자리."""
    prompt = json.dumps([m.model_dump() for m in build_messages("{question}", [])], ensure_ascii=False)
    return hashlib.sha256(prompt.encode()).hexdigest()[:12]


def pipeline_config_id(settings: Settings, top_k: int) -> str:
    """인덱스 계약, 답변 모델, 답변 프롬프트, 거절 임계값, 근거 수, 검색 방식의 해시 앞 12자리.

    dense는 검색 방식을 해시에 넣지 않는다. 검색 방식을 설정으로 만들기 전의 기준선과 같은 config_id를 유지한다.
    """
    pipeline: dict[str, object] = {
        "index_contract": settings.index_contract().model_dump(), "answer_model": settings.answer_llm_model,
        "prompt_hash": answer_prompt_hash(), "refusal_threshold": settings.refusal_threshold, "top_k": top_k,
    }
    if settings.retrieval_mode != "dense":
        retrieval: dict[str, object] = {"mode": settings.retrieval_mode}
        if settings.retrieval_mode in ("rrf", "cc"):
            retrieval["pool"] = settings.fusion_pool
        if settings.retrieval_mode == "rrf":
            retrieval["rrf_k"] = settings.rrf_k
        if settings.retrieval_mode == "cc":
            retrieval["cc_alpha"] = settings.cc_alpha
        pipeline["retrieval"] = retrieval
    return hashlib.sha256(json.dumps(pipeline, sort_keys=True).encode()).hexdigest()[:12]
