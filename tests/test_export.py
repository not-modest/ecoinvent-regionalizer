from __future__ import annotations

import csv

import bw2data as bd

from ecoinvent_regionalizer.core import export, lcia, regionalize


def test_substitutions_csv_export(basic_papercup, tmp_path):
    root = bd.get_activity(basic_papercup["root_key"])
    sig_index = regionalize.build_flow_signature_index(basic_papercup["db"])
    subs, _ = regionalize.build_substitutions(root, ["US", "RoW", "RER"], sig_index, max_depth=1)

    out = tmp_path / "flows.csv"
    export.export_substitutions_csv(subs, str(out))

    with open(out) as f:
        rows = list(csv.reader(f))
    assert rows[0] == [
        "Depth", "Parent flow", "Flow", "Reference product", "Amount", "Unit",
        "Original geography", "Resolved geography", "Manually overridden",
        "Available geographies",
    ]
    assert len(rows) == 3  # header + 2 flows
    flow_names = {row[2] for row in rows[1:]}
    assert flow_names == {"electricity, medium voltage", "kraft pulp"}


def test_results_csv_export_includes_totals(basic_papercup, tmp_path):
    method = basic_papercup["method"]
    breakdown = lcia.contribution_by_location_for_methods(basic_papercup["root_key"], 1.0, [method])

    out = tmp_path / "results.csv"
    export.export_results_csv([method], breakdown, breakdown, str(out))

    with open(out) as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["Method", "Bar", "Geography", "Contribution"]
    total_rows = [r for r in rows[1:] if r[2] == "TOTAL"]
    assert len(total_rows) == 2  # one per bar (Original, Regionalized)
    for row in total_rows:
        assert abs(float(row[3]) - 0.078) < 1e-6
