# FOWCUS Analysis-Ready Dataset

[![Validate dataset](https://github.com/ezefranca/FOWCUS/actions/workflows/validate.yml/badge.svg)](https://github.com/ezefranca/FOWCUS/actions/workflows/validate.yml)
[![Data license: CC BY 4.0](https://img.shields.io/badge/data%20license-CC%20BY%204.0-blue.svg)](LICENSE-DATA.md)
[![Code license: MIT](https://img.shields.io/badge/code%20license-MIT-green.svg)](LICENSE)
[![Formats: CSV and Parquet](https://img.shields.io/badge/formats-CSV%20%7C%20Parquet-informational.svg)](docs/data_dictionary.md)

This repository repackages the upstream FOWCUS workbook into analysis-ready, versionable tables for food-waste quantification and by-product valorization research.

The upstream workbook contains mass composition records for 276 food commodities across 12 groups. This repository preserves the original workbook in `data/raw/`, then derives normalized CSV and Parquet tables with stable identifiers, separated references, commodity summaries, classification notes, and explicit quality flags for source rows that need review.

## What This Adds

- Reproducible conversion from the upstream `.xlsx` into flat research tables.
- CSV and Parquet outputs for Python, R, DuckDB, GIS, and workflow engines.
- Stable `record_id`, `commodity_id`, and `reference_id` fields.
- Nullable booleans and normalized categorical values instead of spreadsheet-only labels.
- Machine-readable metadata in `datapackage.json`, `codemeta.json`, and `metadata/dataset_summary.json`.
- Quality flags that preserve source anomalies instead of silently editing them.
- Documentation for citation, provenance, schema, and usage.

## Data Products

| Table | CSV | Parquet | Rows | Description |
| --- | --- | --- | ---: | --- |
| Parts | `data/processed/csv/fowcus_parts.csv` | `data/processed/parquet/fowcus_parts.parquet` | 1,159 | One row per commodity part. |
| Commodities | `data/processed/csv/fowcus_commodities.csv` | `data/processed/parquet/fowcus_commodities.parquet` | 276 | One row per commodity-code/item combination with mass-balance summaries. |
| References | `data/processed/csv/fowcus_references.csv` | `data/processed/parquet/fowcus_references.parquet` | 266 | Deduplicated source references and URLs. |
| Classification notes | `data/processed/csv/fowcus_classification_notes.csv` | `data/processed/parquet/fowcus_classification_notes.parquet` | 2,973 | Normalized notes from the workbook classification sheet. |
| Quality flags | `data/processed/csv/fowcus_quality_flags.csv` | `data/processed/parquet/fowcus_quality_flags.parquet` | 82 | Source-data checks requiring review or caution. |

## Quick Start

```bash
python3 -m pip install -r requirements.txt
python3 scripts/build_dataset.py
python3 scripts/validate_dataset.py
```

Or:

```bash
make all
```

The default build reads `data/raw/FOWCUS_dataset_Coudard_June_2025_Scientific_Data_v2.xlsx` and rewrites `data/processed/` plus `metadata/dataset_summary.json`.

## Citation

This repository is derived from the original FOWCUS publication and Figshare dataset. Cite the upstream sources when using these tables:

Coudard, A., Szabo-Hemmings, T., Honorine Delval, M. et al. The FOod Commodity composition for Waste qUantification and valorization opportunitieS (FOWCUS) Dataset. *Scientific Data* 12, 1553 (2025). https://doi.org/10.1038/s41597-025-05629-x

Coudard, Antoine; Szabo-Hemmings, Tom; Delval, Mona Honorine; Marriyapillai Ravisandiran, Sowmya; Mogollon, Jose M (2025). The FOod Commodity composition for Waste qUantification and valorization opportunitieS (FOWCUS) Dataset. figshare. Dataset. https://doi.org/10.6084/m9.figshare.27203688.v1

After this repository receives its own DOI, cite that DOI in addition to the upstream article and dataset.

## Documentation

- `docs/data_dictionary.md` describes every derived table and field.
- `docs/provenance.md` documents sources, transformation decisions, checksums, and licensing.
- `docs/usage.md` gives Python, R, DuckDB, and FAOSTAT-style usage examples.

## Validation Notes

The validator checks table schemas, expected row counts, identifier uniqueness, category values, CSV/Parquet row parity, and metadata consistency. It does not erase source anomalies. Instead, known issues are recorded in `fowcus_quality_flags`, including mass-balance deviations, duplicate part labels for sheep/lamb source variants, blank source accounting fields, and item labels that differ only by case.

## License

The upstream Figshare record is listed as CC BY. The derived data in `data/processed/` should be used with attribution to the upstream FOWCUS authors and DOI. See `LICENSE-DATA.md` for data-license notes. Code in `scripts/` follows the repository software license in `LICENSE`.
