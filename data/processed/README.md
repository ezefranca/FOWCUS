# Processed Data

This directory contains generated analysis-ready tables. Do not edit these files manually.

Regenerate them with:

```bash
python3 scripts/build_dataset.py
python3 scripts/validate_dataset.py
```

The CSV files are portable and reviewable in version control. The Parquet files preserve efficient typed storage for analysis engines.
