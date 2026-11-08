.PHONY: build corpus profile closed-book closed-book-report gold-draft gold-translate gold-check db-bench embed-bench embed-check refusal-calib tok-bench chunk-bench test typecheck

# --build: 코드를 고친 뒤 이미지를 다시 빌드하지 않아 예전 코드로 도는 일을 막는다. 캐시를 써서 빠르다.
BATCH = docker compose run --rm --build batch
DEV = docker compose run --rm --build dev
SPLIT ?= dev
LANG_CODE ?= en

build:
	docker compose --profile batch --profile dev build

corpus:
	$(BATCH) app.cli.corpus_cli fetch

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
