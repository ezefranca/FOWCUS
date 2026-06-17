.PHONY: all build validate clean

all: build validate

build:
	python3 scripts/build_dataset.py

validate:
	python3 scripts/validate_dataset.py

clean:
	rm -rf data/processed/csv data/processed/parquet metadata/dataset_summary.json
