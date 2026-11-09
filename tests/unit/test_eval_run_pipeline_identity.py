"""eval_run 기능의 파이프라인 식별자(pipeline_identity) 단위 테스트."""
from app.service.eval.pipeline_identity import pipeline_config_id
from app.common.settings import Settings


def test_dense_config_id_ignores_fusion_settings_so_the_baseline_keeps_its_id() -> None:
    plain = Settings(_env_file=None, retrieval_mode="dense")
    tuned = Settings(_env_file=None, retrieval_mode="dense", fusion_pool=10, rrf_k=1, cc_alpha=0.9)

    assert pipeline_config_id(plain, 5) == pipeline_config_id(tuned, 5)


def test_each_retrieval_mode_and_its_own_parameter_change_the_config_id() -> None:
    ids = {mode: pipeline_config_id(Settings(_env_file=None, retrieval_mode=mode), 5) for mode in ("dense", "bm25", "rrf", "cc", "routed")}

    assert len(set(ids.values())) == 5
    assert pipeline_config_id(Settings(_env_file=None, retrieval_mode="cc", cc_alpha=0.3), 5) != ids["cc"]
    assert pipeline_config_id(Settings(_env_file=None, retrieval_mode="bm25", rrf_k=1), 5) == ids["bm25"]
