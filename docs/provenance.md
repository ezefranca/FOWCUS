# Provenance

## Upstream Sources

This repository is derived from the FOWCUS workbook distributed with:

- Coudard, A., Szabo-Hemmings, T., Honorine Delval, M. et al. The FOod Commodity composition for Waste qUantification and valorization opportunitieS (FOWCUS) Dataset. *Scientific Data* 12, 1553 (2025). https://doi.org/10.1038/s41597-025-05629-x
- Coudard, Antoine; Szabo-Hemmings, Tom; Delval, Mona Honorine; Marriyapillai Ravisandiran, Sowmya; Mogollon, Jose M (2025). The FOod Commodity composition for Waste qUantification and valorization opportunitieS (FOWCUS) Dataset. figshare. Dataset. https://doi.org/10.6084/m9.figshare.27203688.v1

The Figshare record lists the upstream dataset under CC BY. The raw workbook is preserved at `data/raw/FOWCUS_dataset_Coudard_June_2025_Scientific_Data_v2.xlsx`.

## Raw-File Integrity

- Raw workbook SHA-256: `0ec5937847e2670bf46dcf92252887777ba593840d21f0e572168a3006edc24d`
- Source workbook size: 652.2 kB
- Workbook commodity sheets transformed: `livestock`, `seafood`, `eggs`, `sugar`, `cereals`, `vegetable_oils`, `vegetables`, `root_vegetables`, `legumes_pulses`, `fruits`, `nuts`, `stimulants`
- Non-commodity sheets transformed separately: `classification_notes`
- Workbook metadata sheet preserved only in the raw workbook: `general_information`

## Transformation Decisions

- Commodity sheets are concatenated into a long part-level table.
- Source item codes are stored as strings to avoid losing decimal codes and large seafood identifiers.
- Source `yes`/`no` values in `accounted_in_fao` are converted to nullable booleans.
- Avoidability labels are normalized to snake case.
- References are deduplicated into a separate table and linked by `reference_id`.
- Classification notes are normalized by filling down food-group and note headings.
- CSV and Parquet outputs are generated from the same in-memory tables.
- Source anomalies are not corrected without authority; they are recorded in `fowcus_quality_flags`.

## Quality Checks

`scripts/validate_dataset.py` checks:

- Expected row counts for the current upstream workbook.
- CSV/Parquet row-count parity.
- Exact table schemas.
- Required identifiers and category values.
- Unique `record_id`, `commodity_id`, and `reference_id` values.
- Foreign-key consistency from parts to commodities and references.
- Metadata summary consistency.

The generated quality flags currently include:

- 48 commodity mass-balance reviews.
- Duplicate part labels for sheep/lamb source variants under `Sheeps`.
- Two blank upstream `accounted_in_fao` values.
- Two blank upstream `data_manipulation` values.
- Item labels that differ only by case.
- Item labels that appear with multiple source item codes.

These flags are part of the dataset, not validation failures.
