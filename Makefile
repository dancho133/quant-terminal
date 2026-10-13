.PHONY: demo test lint format
demo:
	uv run --locked quant-terminal-demo
test:
	uv run --locked python -m unittest discover -s tests -v
lint:
	uv run --locked ruff check .
	uv run --locked ruff format --check .
format:
	uv run --locked ruff format .
