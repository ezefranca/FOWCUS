# Usage Notes

## Python

```python
import pandas as pd

parts = pd.read_parquet("data/processed/parquet/fowcus_parts.parquet")
commodities = pd.read_parquet("data/processed/parquet/fowcus_commodities.parquet")

avoidable_by_group = (
    commodities
    .groupby("food_group", as_index=False)["avoidable_mass_fraction"]
    .mean()
    .sort_values("avoidable_mass_fraction", ascending=False)
)

print(avoidable_by_group)
```

## R

```r
library(readr)
library(dplyr)

parts <- read_csv("data/processed/csv/fowcus_parts.csv", show_col_types = FALSE)

parts %>%
  count(food_group, avoidability, wt = mass_fraction, name = "mass_fraction_sum")
```

## DuckDB

```sql
SELECT
  food_group,
  avoidability,
  SUM(mass_fraction) AS mass_fraction_sum
FROM read_parquet('data/processed/parquet/fowcus_parts.parquet')
GROUP BY food_group, avoidability
ORDER BY food_group, avoidability;
```

## Joining To Production Data

The original FOWCUS article describes using the source item codes with FAOSTAT and FishStat production data. A typical analysis joins production quantities to `fowcus_parts` by source commodity code and then computes part masses:

```python
production = pd.read_csv("faostat_production.csv")
parts = pd.read_csv("data/processed/csv/fowcus_parts.csv")

merged = production.merge(
    parts,
    left_on="item_code",
    right_on="item_code",
    how="inner",
)

merged["part_mass_tonnes"] = merged["production_tonnes"] * merged["mass_fraction"]
```

For commodities where `accounted_in_fao` is false, analysts may need to adjust production volumes to include parts outside FAO production accounting. Review `fowcus_commodities` and `fowcus_quality_flags` before applying national or regional production estimates.

## Rebuild Workflow

```bash
python3 scripts/build_dataset.py
python3 scripts/validate_dataset.py
```

Use `--input` to transform a different upstream workbook:

```bash
python3 scripts/build_dataset.py --input path/to/FOWCUS.xlsx
```
