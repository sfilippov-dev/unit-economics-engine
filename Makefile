.PHONY: install demo report check abc summary test lint clean

install:
	pip install -e ".[dev]"

demo:
	python -m unit_economics.cli demo --out data/demo

report: demo
	python -m unit_economics.cli report --data data/demo \
		--html docs/report.html --fixed-costs 1500000 \
		--title "Юнит-экономика: демонстрационные данные"

check:
	python -m unit_economics.cli check --data data/demo

abc:
	python -m unit_economics.cli abc --data data/demo --by net_profit

summary:
	python -m unit_economics.cli summary --data data/demo

test:
	python -m pytest

lint:
	ruff check unit_economics tests

clean:
	rm -rf data/demo docs/report.html .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -exec rm -rf {} +
