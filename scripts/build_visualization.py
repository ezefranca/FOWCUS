#!/usr/bin/env python3
"""Build a simple visual explainer for the FOWCUS dataset."""

from __future__ import annotations

import html
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CSV_DIR = ROOT / "data/processed/csv"
OUTPUT = ROOT / "docs/assets/fowcus_explainer.svg"

COLORS = {
    "avoidable": "#2f7d46",
    "potentially_avoidable": "#d99000",
    "unavoidable": "#51606d",
    "ink": "#1f2933",
    "muted": "#52606d",
    "line": "#d9e2ec",
    "paper": "#fbfaf7",
    "panel": "#ffffff",
    "blue": "#2f6690",
}


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def kg(value: float) -> str:
    return f"{value * 100:.1f} kg"


def wrap_lines(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word])
        if current and len(candidate) > max_chars:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def text_block(
    x: float,
    y: float,
    text: str,
    *,
    size: int = 18,
    color: str = COLORS["ink"],
    weight: int = 400,
    max_chars: int = 70,
    line_gap: int = 24,
) -> str:
    lines = wrap_lines(text, max_chars)
    spans = []
    for idx, line in enumerate(lines):
        dy = 0 if idx == 0 else line_gap
        spans.append(f'<tspan x="{x}" dy="{dy}">{esc(line)}</tspan>')
    return (
        f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
        f'font-weight="{weight}">{"".join(spans)}</text>'
    )


def rounded_rect(x: float, y: float, w: float, h: float, fill: str, stroke: str = "none") -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" '
        f'fill="{fill}" stroke="{stroke}"/>'
    )


def stacked_bar(
    x: float,
    y: float,
    w: float,
    h: float,
    values: list[tuple[str, float]],
    *,
    label_inside: bool = True,
) -> str:
    parts: list[str] = []
    cursor = x
    total = sum(value for _, value in values) or 1.0
    for name, value in values:
        width = w * value / total
        if width <= 0:
            continue
        color = COLORS[name]
        parts.append(f'<rect x="{cursor:.2f}" y="{y}" width="{width:.2f}" height="{h}" fill="{color}"/>')
        if label_inside and width > 160:
            label = name.replace("_", " ")
            parts.append(
                f'<text x="{cursor + width / 2:.2f}" y="{y + h / 2 + 6:.2f}" '
                f'font-size="15" text-anchor="middle" fill="white" font-weight="700">'
                f'{esc(label)} {pct(value / total)}</text>'
            )
        cursor += width
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="{COLORS["line"]}"/>')
    return "\n".join(parts)


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    parts = pd.read_csv(CSV_DIR / "fowcus_parts.csv")
    commodities = pd.read_csv(CSV_DIR / "fowcus_commodities.csv")
    quality = pd.read_csv(CSV_DIR / "fowcus_quality_flags.csv")
    return parts, commodities, quality


def build_group_summary(commodities: pd.DataFrame) -> pd.DataFrame:
    working = commodities.copy()
    denominator = working["mass_fraction_sum"].replace(0, pd.NA)
    for column in [
        "avoidable_mass_fraction",
        "potentially_avoidable_mass_fraction",
        "unavoidable_mass_fraction",
    ]:
        working[column.replace("_mass_fraction", "_share")] = working[column] / denominator

    return (
        working.groupby("food_group", as_index=False)
        .agg(
            n_commodities=("commodity_id", "count"),
            avoidable_share=("avoidable_share", "mean"),
            potentially_avoidable_share=("potentially_avoidable_share", "mean"),
            unavoidable_share=("unavoidable_share", "mean"),
        )
        .sort_values("unavoidable_share", ascending=False)
        .reset_index(drop=True)
    )


def build_svg() -> str:
    parts, commodities, quality = load_data()
    group_summary = build_group_summary(commodities)

    egg = parts.loc[parts["item"].eq("Hen eggs in shell, fresh")].copy()
    egg = egg.sort_values("mass_fraction", ascending=False)
    egg_values = [(row.avoidability, float(row.mass_fraction)) for row in egg.itertuples(index=False)]
    egg_labels = [
        (row.part.replace("_", " "), float(row.mass_fraction), row.avoidability)
        for row in egg.itertuples(index=False)
    ]

    group_counts = group_summary.sort_values("n_commodities", ascending=False)
    max_count = int(group_counts["n_commodities"].max())

    width = 1400
    height = 2050
    svg: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">'
        ),
        "<title id=\"title\">FOWCUS dataset visual explainer</title>",
        (
            "<desc id=\"desc\">A simple visualization explaining that FOWCUS breaks food commodities "
            "into mass fractions, avoidability categories, and source-accounting notes.</desc>"
        ),
        "<style>text{font-family:Inter,Arial,sans-serif}.small{font-size:15px}.mono{font-family:ui-monospace,Menlo,Consolas,monospace}</style>",
        rounded_rect(0, 0, width, height, COLORS["paper"], "none"),
    ]

    svg.append(text_block(70, 88, "FOWCUS in one picture", size=48, weight=800, max_chars=40))
    svg.append(
        text_block(
            72,
            136,
            "Like a 5-year-old: each food is a thing made of smaller pieces. FOWCUS tells us how big each piece is.",
            size=22,
            color=COLORS["muted"],
            max_chars=88,
            line_gap=30,
        )
    )

    stats = [
        ("commodities", f"{commodities['commodity_id'].nunique():,}"),
        ("food groups", f"{commodities['food_group'].nunique():,}"),
        ("part records", f"{len(parts):,}"),
        ("review flags", f"{len(quality):,}"),
    ]
    card_w = 285
    for idx, (label, value) in enumerate(stats):
        x = 72 + idx * (card_w + 18)
        svg.append(rounded_rect(x, 220, card_w, 116, COLORS["panel"], COLORS["line"]))
        svg.append(f'<text x="{x + 26}" y="270" font-size="36" font-weight="800" fill="{COLORS["ink"]}">{value}</text>')
        svg.append(f'<text x="{x + 26}" y="304" font-size="18" fill="{COLORS["muted"]}">{esc(label)}</text>')

    # Flow diagram.
    svg.append(text_block(72, 405, "What the dataset does", size=30, weight=800, max_chars=40))
    flow_y = 450
    boxes = [
        ("1. Pick a food", "Example: eggs, apples, fish, cattle."),
        ("2. Split it into parts", "Shell, meat, peel, seed, bone, pulp."),
        ("3. Label the parts", "Could eat, maybe eat, or normally cannot eat."),
        ("4. Use production", "100 tonnes of food times each fraction gives tonnes of each stream."),
    ]
    box_w = 295
    for idx, (heading, body) in enumerate(boxes):
        x = 72 + idx * 322
        svg.append(rounded_rect(x, flow_y, box_w, 170, COLORS["panel"], COLORS["line"]))
        svg.append(text_block(x + 24, flow_y + 44, heading, size=21, weight=800, max_chars=24))
        svg.append(text_block(x + 24, flow_y + 84, body, size=17, color=COLORS["muted"], max_chars=26, line_gap=22))
        if idx < len(boxes) - 1:
            ax = x + box_w + 10
            svg.append(f'<path d="M{ax} {flow_y + 85} H{ax + 28}" stroke="{COLORS["blue"]}" stroke-width="4"/>')
            svg.append(f'<path d="M{ax + 28} {flow_y + 85} l-10 -8 v16 z" fill="{COLORS["blue"]}"/>')

    # Egg example.
    svg.append(text_block(72, 705, "Tiny example: one 100 kg pile of fresh hen eggs", size=30, weight=800, max_chars=70))
    svg.append(
        text_block(
            72,
            746,
            "FOWCUS says that pile is mostly egg liquid and a smaller shell part. The math is just a recipe for splitting the pile.",
            size=18,
            color=COLORS["muted"],
            max_chars=92,
            line_gap=24,
        )
    )
    svg.append(stacked_bar(72, 805, 850, 72, egg_values))
    legend_x = 970
    legend_y = 800
    for idx, (part, value, avoidability) in enumerate(egg_labels):
        y = legend_y + idx * 48
        svg.append(f'<rect x="{legend_x}" y="{y}" width="24" height="24" fill="{COLORS[avoidability]}"/>')
        svg.append(
            f'<text x="{legend_x + 38}" y="{y + 19}" font-size="18" fill="{COLORS["ink"]}">'
            f'{esc(part)} = {kg(value)} ({esc(avoidability.replace("_", " "))})</text>'
        )
    svg.append(
        text_block(
            72,
            928,
            "So if a country reports 100 kg of this commodity, FOWCUS lets an analyst estimate about 89.5 kg egg liquid and 10.5 kg shell.",
            size=18,
            color=COLORS["muted"],
            max_chars=96,
            line_gap=24,
        )
    )

    # Category legend.
    svg.append(text_block(72, 1030, "The three simple labels", size=30, weight=800, max_chars=50))
    labels = [
        ("avoidable", "The part people can normally eat or use as food."),
        ("potentially_avoidable", "The part some people might eat or use, depending on place or habit."),
        ("unavoidable", "The part people normally do not eat, like shell, bones, or peel in many cases."),
    ]
    for idx, (name, body) in enumerate(labels):
        x = 72 + idx * 420
        svg.append(rounded_rect(x, 1075, 386, 136, COLORS["panel"], COLORS["line"]))
        svg.append(f'<rect x="{x + 24}" y="1104" width="28" height="28" fill="{COLORS[name]}"/>')
        svg.append(
            f'<text x="{x + 66}" y="1126" font-size="20" font-weight="800" fill="{COLORS["ink"]}">'
            f'{esc(name.replace("_", " "))}</text>'
        )
        svg.append(text_block(x + 24, 1166, body, size=16, color=COLORS["muted"], max_chars=36, line_gap=21))

    # Group composition chart.
    svg.append(text_block(72, 1290, "Average split by food group", size=30, weight=800, max_chars=50))
    svg.append(
        text_block(
            72,
            1328,
            "Each bar averages commodities in that food group. It shows what kind of pieces the group tends to contain.",
            size=17,
            color=COLORS["muted"],
            max_chars=92,
        )
    )
    chart_x = 300
    chart_y = 1370
    chart_w = 880
    row_h = 34
    for idx, row in enumerate(group_summary.itertuples(index=False)):
        y = chart_y + idx * row_h
        svg.append(
            f'<text x="72" y="{y + 21}" font-size="16" fill="{COLORS["ink"]}">'
            f'{esc(str(row.food_group).replace("_", " "))}</text>'
        )
        values = [
            ("avoidable", float(row.avoidable_share)),
            ("potentially_avoidable", float(row.potentially_avoidable_share)),
            ("unavoidable", float(row.unavoidable_share)),
        ]
        svg.append(stacked_bar(chart_x, y, chart_w, 24, values, label_inside=False))
        svg.append(
            f'<text x="{chart_x + chart_w + 18}" y="{y + 19}" font-size="15" fill="{COLORS["muted"]}">'
            f'{pct(float(row.unavoidable_share))} unavoidable</text>'
        )

    # Count chart.
    svg.append(text_block(72, 1810, "Most rows are seafood because it has many species", size=26, weight=800, max_chars=70))
    x0 = 72
    y0 = 1842
    count_w = 980
    for idx, row in enumerate(group_counts.head(5).itertuples(index=False)):
        y = y0 + idx * 38
        bar_w = count_w * int(row.n_commodities) / max_count
        svg.append(
            f'<text x="{x0}" y="{y + 19}" font-size="15" fill="{COLORS["ink"]}">'
            f'{esc(str(row.food_group).replace("_", " "))}</text>'
        )
        svg.append(f'<rect x="{x0 + 210}" y="{y}" width="{bar_w:.1f}" height="24" fill="{COLORS["blue"]}"/>')
        svg.append(
            f'<text x="{x0 + 220 + bar_w:.1f}" y="{y + 18}" font-size="15" fill="{COLORS["muted"]}">'
            f'{int(row.n_commodities)} commodities</text>'
        )

    svg.append("</svg>")
    return "\n".join(svg)


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(build_svg(), encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
