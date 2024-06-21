PROJECT_NAME=jj_spec_validator

.PHONY: update-requirements
update-requirements:
	@pip-compile --upgrade -o requirements.txt requirements.in

.PHONY: sync-requirements
sync-requirements:
	@pip-sync requirements.txt

.PHONY: check-requirements
check-requirements:
	@pip-sync requirements.txt --dry-run

.PHONY: check-types
check-types:
	python3 -m mypy ${PROJECT_NAME} --strict

.PHONY: check-imports
check-imports:
	python3 -m isort ${PROJECT_NAME} tests --check-only

.PHONY: sort-imports
sort-imports:
	python3 -m isort ${PROJECT_NAME} tests

.PHONY: check-style
check-style:
	python3 -m flake8 ${PROJECT_NAME} tests

.PHONY: lint
lint: check-types check-style check-imports
