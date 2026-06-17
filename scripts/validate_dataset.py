#!/usr/bin/env python3
"""Validate the derived FOWCUS tables."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / "data/processed"
DEFAULT_METADATA = ROOT / "metadata/dataset_summary.json"

EXPECTED_COUNTS = {
    "fowcus_parts": 1159,
    "fowcus_commodities": 276,
}

EXPECTED_COLUMNS = {
    "fowcus_parts": [
        "record_id",
        "commodity_id",
        "food_group",
        "source_group",
        "item_code",
        "item_code_kind",
        "item",
        "part",
        "mass_fraction",
        "mass_percent",
        "accounted_in_fao",
        "avoidability",
        "reference_id",
        "notes",
        "data_manipulation",
        "source_sheet",
        "source_row_number",
    ],
    "fowcus_commodities": [
        "commodity_id",
        "food_group",
        "item_code",
        "item_code_kind",
        "item",
        "n_parts",
        "mass_fraction_sum",
        "mass_balance_error",
        "mass_balance_status",
        "accounted_mass_fraction_sum",
        "non_fao_mass_fraction_sum",
        "unknown_fao_accounting_mass_fraction_sum",
        "avoidable_mass_fraction",
        "potentially_avoidable_mass_fraction",
        "unavoidable_mass_fraction",
        "source_sheets",
    ],
    "fowcus_references": [
        "reference_id",
        "reference_text",
        "reference_url",
        "n_records",
    ],
    "fowcus_classification_notes": [
        "classification_note_id",
        "food_group",
        "classification_note",
        "item",
    ],
    "fowcus_quality_flags": [
        "flag_id",
        "scope",
        "severity",
        "check",
        "record_id",
        "commodity_id",
        "message",
    ],
}

REQUIRED_NON_NULL = {
    "fowcus_parts": [
        "record_id",
        "commodity_id",
        "food_group",
        "source_group",
        "item_code",
        "item",
        "part",
        "mass_fraction",
        "mass_percent",
        "avoidability",
        "reference_id",
        "source_sheet",
        "source_row_number",
    ],
    "fowcus_commodities": [
        "commodity_id",
        "food_group",
        "item_code",
        "item",
        "n_parts",
        "mass_fraction_sum",
        "mass_balance_status",
    ],
    "fowcus_references": ["reference_id", "reference_text", "n_records"],
    "fowcus_classification_notes": [
        "classification_note_id",
        "food_group",
        "classification_note",
        "item",
    ],
    "fowcus_quality_flags": [
        "flag_id",
        "scope",
        "severity",
        "check",
        "commodity_id",
        "message",
    ],
}


def load_table(data_dir: Path, name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    csv_path = data_dir / "csv" / f"{name}.csv"
    parquet_path = data_dir / "parquet" / f"{name}.parquet"
    if not csv_path.exists():
        raise AssertionError(f"Missing CSV table: {csv_path}")
    if not parquet_path.exists():
        raise AssertionError(f"Missing Parquet table: {parquet_path}")
    csv_df = pd.read_csv(csv_path, keep_default_na=False)
    parquet_df = pd.read_parquet(parquet_path)
    if len(csv_df) != len(parquet_df):
        raise AssertionError(f"{name}: CSV and Parquet row counts differ")
    return csv_df, parquet_df


def assert_columns(name: str, df: pd.DataFrame) -> None:
    expected = EXPECTED_COLUMNS[name]
    actual = list(df.columns)
    if actual != expected:
        raise AssertionError(f"{name}: expected columns {expected}, found {actual}")


def assert_non_null(name: str, df: pd.DataFrame) -> None:
    for column in REQUIRED_NON_NULL[name]:
        missing = df[column].isna() | (df[column].astype(str).str.len() == 0)
        if missing.any():
            raise AssertionError(f"{name}: {column} has {int(missing.sum())} missing values")


def validate(data_dir: Path, metadata_path: Path) -> list[str]:
    tables: dict[str, pd.DataFrame] = {}
    messages: list[str] = []
    for name in EXPECTED_COLUMNS:
        csv_df, parquet_df = load_table(data_dir, name)
        assert_columns(name, csv_df)
        assert_columns(name, parquet_df)
        assert_non_null(name, csv_df)
        tables[name] = csv_df

    for name, expected_count in EXPECTED_COUNTS.items():
        actual_count = len(tables[name])
        if actual_count != expected_count:
            raise AssertionError(f"{name}: expected {expected_count} rows, found {actual_count}")

    parts = tables["fowcus_parts"]
    commodities = tables["fowcus_commodities"]
    references = tables["fowcus_references"]

    if parts["record_id"].duplicated().any():
        raise AssertionError("fowcus_parts: duplicate record_id values")
    if commodities["commodity_id"].duplicated().any():
        raise AssertionError("fowcus_commodities: duplicate commodity_id values")
    if references["reference_id"].duplicated().any():
        raise AssertionError("fowcus_references: duplicate reference_id values")

    missing_commodities = set(parts["commodity_id"]) - set(commodities["commodity_id"])
    if missing_commodities:
        raise AssertionError(f"Parts reference missing commodity_id values: {sorted(missing_commodities)[:5]}")
    missing_references = set(parts["reference_id"]) - set(references["reference_id"])
    if missing_references:
        raise AssertionError(f"Parts reference missing reference_id values: {sorted(missing_references)[:5]}")

    allowed_avoidability = {"avoidable", "potentially_avoidable", "unavoidable"}
    actual_avoidability = set(parts["avoidability"])
    if actual_avoidability - allowed_avoidability:
        raise AssertionError(f"Unexpected avoidability values: {sorted(actual_avoidability)}")

    allowed_accounted = {"True", "False", ""}
    actual_accounted = set(parts["accounted_in_fao"].astype(str))
    if actual_accounted - allowed_accounted:
        raise AssertionError(f"Unexpected accounted_in_fao values: {sorted(actual_accounted)}")

    if not parts["mass_fraction"].between(0, 1).all():
        bad = parts.loc[~parts["mass_fraction"].between(0, 1), ["record_id", "mass_fraction"]]
        raise AssertionError(f"mass_fraction outside [0,1]: {bad.head().to_dict(orient='records')}")

    if not metadata_path.exists():
        raise AssertionError(f"Missing metadata summary: {metadata_path}")
    summary = json.loads(metadata_path.read_text(encoding="utf-8"))
    if summary["n_part_records"] != len(parts):
        raise AssertionError("Metadata n_part_records does not match fowcus_parts")
    if summary["n_commodities"] != len(commodities):
        raise AssertionError("Metadata n_commodities does not match fowcus_commodities")
    if summary["n_quality_flags"] != len(tables["fowcus_quality_flags"]):
        raise AssertionError("Metadata n_quality_flags does not match fowcus_quality_flags")

    messages.append(f"Validated {len(parts)} part records.")
    messages.append(f"Validated {len(commodities)} commodities across {parts['food_group'].nunique()} food groups.")
    messages.append(f"Validated {len(references)} unique reference entries.")
    messages.append(f"Recorded {len(tables['fowcus_quality_flags'])} source-data quality flags.")
    return messages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    args = parser.parse_args()

    try:
        messages = validate(args.data_dir.resolve(), args.metadata.resolve())
    except Exception as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 1

    for message in messages:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
