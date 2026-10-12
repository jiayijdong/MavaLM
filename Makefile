PYTHON ?= python3

.PHONY: install validate test check clean

install:
	$(PYTHON) -m pip install -e .

validate:
	$(PYTHON) scripts/validate_repository.py
	$(PYTHON) -m compileall -q mavalm scripts tests

test:
	$(PYTHON) -m unittest discover -s tests -v

check: validate test

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
