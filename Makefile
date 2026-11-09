.PHONY: build corpus ingest serve stop eval validity fusion label-sheet agreement profile closed-book closed-book-report gold-draft gold-translate gold-check db-bench embed-bench embed-check refusal-calib llm-bench tok-bench chunk-bench test typecheck

# --build: 코드를 고친 뒤 이미지를 다시 빌드하지 않아 예전 코드로 도는 일을 막는다. 캐시를 써서 빠르다.
BATCH = docker compose run --rm --build batch
DEV = docker compose run --rm --build dev
SPLIT ?= dev
LANG_CODE ?= en

build:
	docker compose --profile batch --profile dev build

corpus:
	$(BATCH) app.cli.corpus_cli fetch

# 운영 Qdrant를 띄우고 확정 구성으로 색인한다. 같은 원문과 설정이면 다시 돌려도 같은 상태가 된다(CPU에서 약 5분).
ingest:
	docker compose up -d qdrant
	$(BATCH) app.cli.ingest_cli

# API 서버(http://localhost:8000). 색인과 설정의 인덱스 계약이 다르면 기동하지 않는다.
serve:
	docker compose up -d --build api
	@echo "대시보드: http://localhost:8000/dashboard"

stop:
	docker compose stop api qdrant evaldb

# Gold Set 평가. 같은 설정, 데이터, 인덱스면 같은 run_id라 기록된 문항은 다시 부르지 않는다(비용 0).
CONFIG ?= configs/baseline.toml
# 예: EVAL_ARGS="--judge-limit 10"(파일럿)
EVAL_ARGS ?=
GIT_COMMIT = $(shell git rev-parse --short HEAD)$(shell git diff --quiet HEAD -- app configs || echo -dirty)
eval:
	docker compose up -d --wait qdrant evaldb
	docker compose run --rm --build -e GIT_COMMIT=$(GIT_COMMIT) batch app.cli.eval_run_cli --config $(CONFIG) $(EVAL_ARGS)

# 지표 타당성 검증: 망가뜨린 변형 5종을 평가하고 기준선과 비교한다(research/artifacts/judge_validity).
validity:
	$(MAKE) eval CONFIG=configs/validity_random_chunks.toml || true
	$(MAKE) eval CONFIG=configs/validity_no_refusal.toml || true
	$(MAKE) eval CONFIG=configs/validity_shuffled_citations.toml || true
	$(MAKE) eval CONFIG=configs/validity_swapped_context.toml || true
	$(MAKE) eval CONFIG=configs/validity_stripped_citations.toml || true
	$(BATCH) app.cli.judge_check_cli validity

# 사람 라벨 시트(data/gold/human_labels_sheet.md)와 채울 라벨 파일. 라벨 파일이 있으면 덮어쓰지 않는다.
# Part C 검색 융합 비교: BM25 단독, RRF, CC를 평가하고 기준선(dense)과 짝지어 판정한 뒤, 채택한 언어별 선택(routed)을 dev set 검색 지표와 test set으로 확인한다.
fusion:
	$(MAKE) eval CONFIG=configs/fusion_bm25.toml || true
	$(MAKE) eval CONFIG=configs/fusion_rrf.toml || true
	$(MAKE) eval CONFIG=configs/fusion_cc.toml || true
	$(BATCH) app.cli.fusion_compare_cli compare
	$(BATCH) app.cli.fusion_compare_cli dev-check
	$(MAKE) eval CONFIG=configs/fusion_routed.toml || true
	$(BATCH) app.cli.fusion_compare_cli routed-check

label-sheet:
	docker compose up -d --wait qdrant evaldb
	$(BATCH) app.cli.judge_check_cli label-sheet

# 사람 라벨 대비 Judge 일치율과 Cohen's kappa(research/artifacts/judge_agreement).
agreement:
	docker compose up -d --wait evaldb
	$(BATCH) app.cli.judge_check_cli agreement

profile:
	$(BATCH) app.cli.corpus_cli profile

closed-book:
	$(BATCH) app.cli.selection_cli closed-book

closed-book-report:
	$(BATCH) app.cli.selection_cli closed-book-report

gold-draft:
	$(BATCH) app.cli.eval_cli gold-draft --split $(SPLIT)

gold-translate:
	$(BATCH) app.cli.eval_cli gold-translate --split $(SPLIT) --lang ko

gold-check:
	$(BATCH) app.cli.eval_cli gold-check --split $(SPLIT) --lang $(LANG_CODE)

DBS = qdrant pgvector chroma
DB_ARTIFACTS = research/artifacts/database
DB_STATS = docker stats --no-stream --format '{{json .}}' $$(docker compose --profile dbbench ps -q $(DBS))

# 후보 DB를 띄우고, 적재 전 메모리, 측정, 적재 후 메모리를 기록한 뒤 DB를 멈춘다.
db-bench:
	mkdir -p $(DB_ARTIFACTS)
	docker compose --profile dbbench up -d $(DBS)
	sleep 5
	$(DB_STATS) > $(DB_ARTIFACTS)/docker_stats_idle.jsonl
	$(BATCH) app.cli.database_selection_cli
	$(DB_STATS) > $(DB_ARTIFACTS)/docker_stats_loaded.jsonl
	docker compose --profile dbbench stop $(DBS)

# 선정된 Qdrant만 띄워 후보 임베딩 모델을 비교한다. 모델 파일은 .cache/models에 받아 재사용한다.
embed-bench:
	docker compose --profile dbbench up -d qdrant
	$(BATCH) app.cli.embedding_selection_cli
	docker compose --profile dbbench stop qdrant

# 확정한 Chunking(structure-512-77)으로 Embedding 상위 두 모델을 다시 잰다(선정 실험 7단계). CPU에서 약 10분.
embed-check:
	docker compose --profile dbbench up -d qdrant
	$(BATCH) app.cli.embedding_crosscheck_cli
	docker compose --profile dbbench stop qdrant

# 확정 구성으로 dev set 전 문항의 dense 최고 점수를 재고 거절 임계값을 고른다(선정 실험 8단계). CPU에서 약 6분.
refusal-calib:
	docker compose --profile dbbench up -d qdrant
	$(BATCH) app.cli.refusal_calibration_cli
	docker compose --profile dbbench stop qdrant

# 확정 검색 구성의 근거로 LLM 후보마다 dev set 답을 받는다(선정 실험 9단계). 엘리스 ML API를 호출해 비용이 든다.
# 응답은 research/artifacts/llm_selection/responses.jsonl에 캐시돼 다시 돌리면 API를 부르지 않는다.
llm-bench:
	docker compose --profile dbbench up -d qdrant
	$(BATCH) app.cli.llm_selection_cli
	docker compose --profile dbbench stop qdrant

tok-bench:
	docker compose --profile dbbench up -d qdrant
	docker compose run --rm --build batch-korean app.cli.tokenizer_selection_cli
	docker compose --profile dbbench stop qdrant

# 선정 임베딩(Qwen3)으로 분할 설정마다 다시 색인한다. CPU에서 설정 하나에 약 5분.
# 2단계 방식은 1단계 규칙의 선택(재귀) 대신 문서 구조로 정했다. 근거는 research/chunking_selection.md.
CHUNK_METHOD ?= structure
chunk-bench:
	docker compose --profile dbbench up -d qdrant
	$(BATCH) app.cli.chunking_selection_cli --method $(CHUNK_METHOD)
	docker compose --profile dbbench stop qdrant

test:
	$(DEV) pytest -q -p no:cacheprovider

typecheck:
	$(DEV) mypy --cache-dir=/dev/null
