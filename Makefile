.PHONY: build corpus profile closed-book closed-book-report gold-draft gold-translate gold-check db-bench test typecheck

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

test:
	$(DEV) pytest -q -p no:cacheprovider

typecheck:
	$(DEV) mypy --cache-dir=/dev/null
