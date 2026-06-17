#!/usr/bin/env python3
"""Build analysis-ready FOWCUS tables from the upstream workbook."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/raw/FOWCUS_dataset_Coudard_June_2025_Scientific_Data_v2.xlsx"
DEFAULT_OUTPUT = ROOT / "data/processed"

DATA_SHEETS = [
    "livestock",
    "seafood",
    "eggs",
    "sugar",
    "cereals",
    "vegetable_oils",
    "vegetables",
    "root_vegetables",
    "legumes_pulses",
    "fruits",
    "nuts",
    "stimulants",
]

EXPECTED_COLUMNS = [
    "group",
    "item_code",
    "item",
    "part",
    "mass_fraction",
    "accounted_in_fao",
    "avoidability",
    "references",
    "notes",
    "data_manipulation",
    "reference_link",
]

AVOIDABILITY_MAP = {
    "Avoidable": "avoidable",
    "Potentially Avoidable": "potentially_avoidable",
    "Unavoidable": "unavoidable",
}


def clean_text(value: Any) -> str | None:
    """Return stripped text with internal whitespace normalized."""
    if pd.isna(value):
        return None
    text = str(value).replace("\u00a0", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text or None


def format_item_code(value: Any) -> str:
    """Preserve Excel commodity codes as stable strings."""
    if pd.isna(value):
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return format(Decimal(str(value)).normalize(), "f").rstrip("0").rstrip(".")
    return str(value).strip()


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "unknown"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def short_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]


def reference_id(reference_text: str | None, reference_link: str | None) -> str:
    payload = json.dumps(
        {"reference_text": reference_text or "", "reference_link": reference_link or ""},
        sort_keys=True,
        ensure_ascii=False,
    )
    return "ref_" + hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def item_code_kind(item_code: str) -> str:
    if item_code.lower() == "aggregation":
        return "aggregation"
    return "commodity_code"


def read_composition(input_path: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for sheet in DATA_SHEETS:
        df = pd.read_excel(input_path, sheet_name=sheet, dtype=object)
        df = df.dropna(how="all").copy()
        if list(df.columns) != EXPECTED_COLUMNS:
            raise ValueError(f"{sheet} columns differ from expected schema: {list(df.columns)}")

        df["source_sheet"] = sheet
        df["source_row_number"] = df.index.astype(int) + 2
        frames.append(df)

    raw = pd.concat(frames, ignore_index=True)

    text_columns = [
        "group",
        "item",
        "part",
        "accounted_in_fao",
        "avoidability",
        "references",
        "notes",
        "data_manipulation",
        "reference_link",
        "source_sheet",
    ]
    for column in text_columns:
        raw[column] = raw[column].map(clean_text)

    raw["item_code"] = raw["item_code"].map(format_item_code)
    raw["item_code_kind"] = raw["item_code"].map(item_code_kind)
    raw["mass_fraction"] = pd.to_numeric(raw["mass_fraction"], errors="raise").astype(float)
    raw["mass_percent"] = raw["mass_fraction"] * 100.0

    accounted_values = set(raw["accounted_in_fao"].dropna())
    if accounted_values - {"yes", "no"}:
        raise ValueError(f"Unexpected accounted_in_fao values: {sorted(accounted_values)}")
    raw["accounted_in_fao"] = raw["accounted_in_fao"].map({"yes": True, "no": False}).astype("boolean")

    avoidability_values = set(raw["avoidability"].dropna())
    if avoidability_values - set(AVOIDABILITY_MAP):
        raise ValueError(f"Unexpected avoidability values: {sorted(avoidability_values)}")
    raw["avoidability"] = raw["avoidability"].map(AVOIDABILITY_MAP)

    raw = raw.rename(
        columns={
            "group": "source_group",
            "references": "reference_text",
            "reference_link": "reference_url",
        }
    )
    raw["food_group"] = raw["source_sheet"]

    raw["_commodity_key"] = (
        raw["food_group"]
        + "|"
        + raw["item_code"].fillna("")
        + "|"
        + raw["item"].fillna("")
    )
    raw["commodity_id"] = [
        "fowcus_"
        + slugify(food_group)
        + "_"
        + slugify(item_code or "no-code")
        + "_"
        + slugify(item or "no-item")
        + "_"
        + short_hash(key)
        for food_group, item_code, item, key in zip(
            raw["food_group"], raw["item_code"], raw["item"], raw["_commodity_key"]
        )
    ]
    if raw.groupby(raw["_commodity_key"])["commodity_id"].nunique().max() != 1:
        raise ValueError("Commodity identifiers are not stable for repeated commodity keys.")
    if raw[["_commodity_key", "commodity_id"]].drop_duplicates()["commodity_id"].duplicated().any():
        raise ValueError("Commodity identifier collision detected.")

    raw["reference_id"] = [
        reference_id(text, url) for text, url in zip(raw["reference_text"], raw["reference_url"])
    ]
    raw["record_id"] = [f"fowcus_part_{idx:05d}" for idx in range(1, len(raw) + 1)]

    columns = [
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
    ]
    return raw[columns + ["reference_text", "reference_url"]]


def build_references(composition: pd.DataFrame) -> pd.DataFrame:
    references = (
        composition[["reference_id", "reference_text", "reference_url"]]
        .drop_duplicates()
        .sort_values("reference_id")
        .reset_index(drop=True)
    )
    counts = composition.groupby("reference_id", as_index=False).size().rename(columns={"size": "n_records"})
    return references.merge(counts, on="reference_id", how="left")[
        ["reference_id", "reference_text", "reference_url", "n_records"]
    ]


def build_commodities(composition: pd.DataFrame) -> pd.DataFrame:
    pieces = composition.copy()
    pieces["avoidable_mass_fraction"] = pieces["mass_fraction"].where(
        pieces["avoidability"] == "avoidable", 0.0
    )
    pieces["potentially_avoidable_mass_fraction"] = pieces["mass_fraction"].where(
        pieces["avoidability"] == "potentially_avoidable", 0.0
    )
    pieces["unavoidable_mass_fraction"] = pieces["mass_fraction"].where(
        pieces["avoidability"] == "unavoidable", 0.0
    )
    accounted_mask = pieces["accounted_in_fao"].eq(True)
    non_fao_mask = pieces["accounted_in_fao"].eq(False)
    unknown_fao_mask = pieces["accounted_in_fao"].isna()
    pieces["accounted_mass_fraction"] = pieces["mass_fraction"].where(accounted_mask, 0.0)
    pieces["non_fao_mass_fraction"] = pieces["mass_fraction"].where(non_fao_mask, 0.0)
    pieces["unknown_fao_accounting_mass_fraction"] = pieces["mass_fraction"].where(unknown_fao_mask, 0.0)

    commodities = (
        pieces.groupby(["commodity_id", "food_group", "item_code", "item_code_kind", "item"], as_index=False)
        .agg(
            n_parts=("record_id", "count"),
            mass_fraction_sum=("mass_fraction", "sum"),
            accounted_mass_fraction_sum=("accounted_mass_fraction", "sum"),
            non_fao_mass_fraction_sum=("non_fao_mass_fraction", "sum"),
            unknown_fao_accounting_mass_fraction_sum=("unknown_fao_accounting_mass_fraction", "sum"),
            avoidable_mass_fraction=("avoidable_mass_fraction", "sum"),
            potentially_avoidable_mass_fraction=("potentially_avoidable_mass_fraction", "sum"),
            unavoidable_mass_fraction=("unavoidable_mass_fraction", "sum"),
            source_sheets=("source_sheet", lambda values: ";".join(sorted(set(values)))),
        )
        .sort_values(["food_group", "item", "item_code"])
        .reset_index(drop=True)
    )
    commodities["mass_balance_error"] = commodities["mass_fraction_sum"] - 1.0
    commodities["mass_balance_status"] = commodities["mass_balance_error"].abs().map(
        lambda value: "pass" if value <= 1e-6 else "review"
    )
    return commodities[
        [
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
        ]
    ]


def build_quality_flags(composition: pd.DataFrame, commodities: pd.DataFrame) -> pd.DataFrame:
    flags: list[dict[str, Any]] = []

    mass_review = commodities.loc[commodities["mass_balance_status"] != "pass"]
    for row in mass_review.itertuples(index=False):
        severity = "warning" if abs(row.mass_balance_error) > 0.02 else "info"
        flags.append(
            {
                "scope": "commodity",
                "severity": severity,
                "check": "mass_balance",
                "record_id": None,
                "commodity_id": row.commodity_id,
                "message": (
                    f"Commodity parts sum to {row.mass_fraction_sum:.6f}; "
                    f"expected 1.000000 for a closed mass balance."
                ),
            }
        )

    duplicate_parts = composition.loc[
        composition.duplicated(subset=["commodity_id", "part"], keep=False),
        ["record_id", "commodity_id", "part"],
    ].sort_values(["commodity_id", "part", "record_id"])
    for row in duplicate_parts.itertuples(index=False):
        flags.append(
            {
                "scope": "part",
                "severity": "warning",
                "check": "duplicate_part_label_within_commodity",
                "record_id": row.record_id,
                "commodity_id": row.commodity_id,
                "message": f"Part label {row.part!r} appears more than once for this commodity.",
            }
        )

    missing_accounting = composition.loc[
        composition["accounted_in_fao"].isna(),
        ["record_id", "commodity_id", "part"],
    ]
    for row in missing_accounting.itertuples(index=False):
        flags.append(
            {
                "scope": "part",
                "severity": "warning",
                "check": "missing_accounted_in_fao",
                "record_id": row.record_id,
                "commodity_id": row.commodity_id,
                "message": f"Part {row.part!r} has no accounted_in_fao value in the source workbook.",
            }
        )

    missing_manipulation = composition.loc[
        composition["data_manipulation"].isna(),
        ["record_id", "commodity_id", "part"],
    ]
    for row in missing_manipulation.itertuples(index=False):
        flags.append(
            {
                "scope": "part",
                "severity": "info",
                "check": "missing_data_manipulation",
                "record_id": row.record_id,
                "commodity_id": row.commodity_id,
                "message": f"Part {row.part!r} has no data_manipulation note in the source workbook.",
            }
        )

    item_case = (
        composition[["food_group", "item_code", "item", "commodity_id"]]
        .drop_duplicates()
        .assign(item_casefold=lambda frame: frame["item"].str.casefold())
    )
    case_collisions = item_case.groupby(["food_group", "item_code", "item_casefold"]).filter(
        lambda group: group["item"].nunique() > 1
    )
    for row in case_collisions.itertuples(index=False):
        flags.append(
            {
                "scope": "commodity",
                "severity": "warning",
                "check": "case_only_item_label_collision",
                "record_id": None,
                "commodity_id": row.commodity_id,
                "message": "Commodity item label differs from another item only by letter case.",
            }
        )

    item_codes = (
        composition[["food_group", "item", "item_code", "commodity_id"]]
        .drop_duplicates()
        .assign(item_casefold=lambda frame: frame["item"].str.casefold())
    )
    multi_code_items = item_codes.groupby(["food_group", "item_casefold"]).filter(
        lambda group: group["item_code"].nunique() > 1
    )
    for row in multi_code_items.itertuples(index=False):
        flags.append(
            {
                "scope": "commodity",
                "severity": "info",
                "check": "item_label_has_multiple_codes",
                "record_id": None,
                "commodity_id": row.commodity_id,
                "message": "The same item label appears with multiple source item_code values.",
            }
        )

    quality = pd.DataFrame(
        flags,
        columns=["flag_id", "scope", "severity", "check", "record_id", "commodity_id", "message"],
    )
    if quality.empty:
        return quality
    quality["flag_id"] = [f"quality_flag_{idx:04d}" for idx in range(1, len(quality) + 1)]
    return quality


def build_classification_notes(input_path: Path) -> pd.DataFrame:
    notes = pd.read_excel(input_path, sheet_name="classification_notes", dtype=object)
    notes = notes.rename(
        columns={
            "Food Group": "food_group",
            "Infomation": "classification_note",
            "Item": "item",
        }
    )
    notes = notes.dropna(how="all").copy()
    notes["food_group"] = notes["food_group"].ffill().map(clean_text)
    notes["classification_note"] = notes["classification_note"].ffill().map(clean_text)
    notes["item"] = notes["item"].map(clean_text)
    notes = notes.dropna(subset=["item"]).reset_index(drop=True)
    notes["classification_note_id"] = [f"classification_note_{idx:04d}" for idx in range(1, len(notes) + 1)]
    return notes[["classification_note_id", "food_group", "classification_note", "item"]]


def write_table(df: pd.DataFrame, output_dir: Path, name: str) -> None:
    csv_dir = output_dir / "csv"
    parquet_dir = output_dir / "parquet"
    csv_dir.mkdir(parents=True, exist_ok=True)
    parquet_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_dir / f"{name}.csv", index=False)
    df.to_parquet(parquet_dir / f"{name}.parquet", index=False)


def build_summary(
    input_path: Path,
    composition: pd.DataFrame,
    commodities: pd.DataFrame,
    references: pd.DataFrame,
    classification_notes: pd.DataFrame,
    quality_flags: pd.DataFrame,
) -> dict[str, Any]:
    by_group = (
        commodities.groupby("food_group")
        .agg(n_commodities=("commodity_id", "count"), n_parts=("n_parts", "sum"))
        .reset_index()
        .to_dict(orient="records")
    )
    return {
        "title": "FOWCUS analysis-ready derived tables",
        "upstream_workbook": str(input_path.relative_to(ROOT) if input_path.is_relative_to(ROOT) else input_path),
        "upstream_workbook_sha256": sha256(input_path),
        "upstream_article_doi": "10.1038/s41597-025-05629-x",
        "upstream_dataset_doi": "10.6084/m9.figshare.27203688.v1",
        "n_part_records": int(len(composition)),
        "n_commodities": int(commodities["commodity_id"].nunique()),
        "n_food_groups": int(commodities["food_group"].nunique()),
        "n_references": int(len(references)),
        "n_classification_note_items": int(len(classification_notes)),
        "n_quality_flags": int(len(quality_flags)),
        "mass_balance_review_commodities": int((commodities["mass_balance_status"] != "pass").sum()),
        "food_groups": by_group,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Path to upstream FOWCUS workbook.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output directory for derived tables.")
    args = parser.parse_args()

    input_path = args.input.resolve()
    output_dir = args.output.resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input workbook not found: {input_path}")

    composition_with_refs = read_composition(input_path)
    references = build_references(composition_with_refs)
    composition = composition_with_refs.drop(columns=["reference_text", "reference_url"])
    commodities = build_commodities(composition)
    quality_flags = build_quality_flags(composition, commodities)
    classification_notes = build_classification_notes(input_path)

    write_table(composition, output_dir, "fowcus_parts")
    write_table(commodities, output_dir, "fowcus_commodities")
    write_table(references, output_dir, "fowcus_references")
    write_table(classification_notes, output_dir, "fowcus_classification_notes")
    write_table(quality_flags, output_dir, "fowcus_quality_flags")

    summary = build_summary(input_path, composition, commodities, references, classification_notes, quality_flags)
    metadata_dir = ROOT / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "dataset_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
