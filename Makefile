.PHONY: install test lint render policy
install:
	pip install -e ".[dev]"
test:
	pytest
lint:
	ruff check src tests
render:
	helm template demo charts/llm-stack -f charts/llm-stack/values-airgap.yaml > rendered-airgap.yaml
policy: render
	airgap lint rendered-airgap.yaml --profile airgap --registry registry.plant.internal:5000
