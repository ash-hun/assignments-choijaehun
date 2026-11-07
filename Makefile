.PHONY: corpus profile closed-book closed-book-report test typecheck

corpus:
	uv run python -m app.cli.corpus_cli fetch

profile:
	uv run python -m app.cli.corpus_cli profile

closed-book:
	uv run python -m app.cli.selection_cli closed-book

closed-book-report:
	uv run python -m app.cli.selection_cli closed-book-report

test:
	uv run pytest -q

typecheck:
	uv run mypy
