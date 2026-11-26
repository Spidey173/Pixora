.PHONY: run test lint format

run:
	./run.sh

test:
	pytest -q

lint:
	ruff check .

format:
	ruff format .
