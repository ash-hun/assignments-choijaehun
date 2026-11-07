.PHONY: build corpus profile closed-book closed-book-report gold-draft gold-translate gold-check test typecheck

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

test:
	$(DEV) pytest -q -p no:cacheprovider

typecheck:
	$(DEV) mypy --cache-dir=/dev/null
