.PHONY: all build visualize validate clean

all: build visualize validate

build:
	python3 scripts/build_dataset.py

visualize:
	python3 scripts/build_visualization.py

validate:
	python3 scripts/validate_dataset.py

clean:
	rm -rf data/processed/csv data/processed/parquet metadata/dataset_summary.json docs/assets/fowcus_explainer.svg
