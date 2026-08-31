"""Pure CSV-writing functions, factored out of the Qt widgets so they can be
unit tested without a running GUI."""
from __future__ import annotations

import csv

import bw2data as bd

from ecoinvent_regionalizer.core.regionalize import FlowSubstitution


def substitutions_to_rows(
    ordered_substitutions: list[FlowSubstitution],
) -> list[list]:
    """Builds the row data for the Analysis tab's flow-substitution export.
    Kept separate from the file-writing so tests can check row contents
    without touching the filesystem."""
    rows: list[list] = [[
        "Depth", "Parent flow", "Flow", "Reference product", "Amount", "Unit",
        "Original geography", "Resolved geography", "Manually overridden",
        "Available geographies",
    ]]
    for sub in ordered_substitutions:
        parent_act = bd.get_activity(sub.parent_key)
        rows.append([
            sub.depth,
            parent_act.get("name", ""),
            sub.flow_name,
            sub.reference_product,
            sub.amount,
            sub.unit,
            sub.original_location,
            sub.chosen_location or "",
            "yes" if sub.manual_override else "no",
            "; ".join(sub.available_locations),
        ])
    return rows


def export_substitutions_csv(ordered_substitutions: list[FlowSubstitution], path: str) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(substitutions_to_rows(ordered_substitutions))


def breakdowns_to_rows(
    methods: list[tuple],
    original_breakdowns: dict[tuple, dict[str, float]],
    new_breakdowns: dict[tuple, dict[str, float]],
) -> list[list]:
    """Builds the row data for the Results tab's impact-breakdown export."""
    rows: list[list] = [["Method", "Bar", "Geography", "Contribution"]]
    for m in methods:
        method_label = " / ".join(m)
        for bar_label, breakdown in [
            ("Original", original_breakdowns[m]),
            ("Regionalized", new_breakdowns[m]),
        ]:
            for loc, value in sorted(breakdown.items()):
                rows.append([method_label, bar_label, loc, value])
            rows.append([method_label, bar_label, "TOTAL", sum(breakdown.values())])
    return rows


def export_results_csv(
    methods: list[tuple],
    original_breakdowns: dict[tuple, dict[str, float]],
    new_breakdowns: dict[tuple, dict[str, float]],
    path: str,
) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(breakdowns_to_rows(methods, original_breakdowns, new_breakdowns))
