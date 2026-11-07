.PHONY: build corpus profile closed-book closed-book-report test typecheck

BATCH = docker compose run --rm batch
DEV = docker compose run --rm dev

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

test:
	$(DEV) pytest -q -p no:cacheprovider

typecheck:
	$(DEV) mypy --cache-dir=/dev/null
