"""selection_run 기능의 LLM 선정 판정(품질 하한, 최저 비용) 단위 테스트."""
from app.service.eval.llm_benchmark import LlmRun, pick_llm


def run(model: str, language: str, format_compliance: float, false_refusal: float, cost: float) -> LlmRun:
    return LlmRun(model=model, language=language, generated=30, format_compliance=format_compliance, dropped_citation_rate=0.0,
                  answerable_false_refusal=false_refusal, unanswerable_refusal=0.5, cost_krw_per_item=cost,
                  latency_ms_mean=1.0, latency_ms_p95=1.0)


def test_cheapest_model_that_passes_the_floor_in_every_language_is_chosen() -> None:
    runs = [
        run("cheap-bad", "en", 0.99, 0.0, 0.1), run("cheap-bad", "ko", 0.90, 0.0, 0.1),
        run("mid", "en", 0.97, 0.05, 0.5), run("mid", "ko", 0.96, 0.10, 0.5),
        run("pricey", "en", 1.0, 0.0, 2.0), run("pricey", "ko", 1.0, 0.0, 2.0),
    ]

    verdict = pick_llm(runs)

    assert (verdict.passed, verdict.chosen) == (["mid", "pricey"], "mid")


def test_no_model_passing_the_floor_means_no_choice() -> None:
    assert pick_llm([run("a", "en", 0.5, 0.0, 1.0)]).chosen is None
