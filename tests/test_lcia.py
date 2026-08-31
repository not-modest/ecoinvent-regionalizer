from __future__ import annotations

import bw2data as bd
import pytest

from ecoinvent_regionalizer.core import lcia, regionalize


def test_compute_lcia_matches_hand_calculation(basic_papercup):
    method = basic_papercup["method"]
    score = lcia.compute_lcia(basic_papercup["root_key"], 1.0, [method])[method]
    assert score == pytest.approx(0.05 + 0.01 * 0.4 + 0.02 * 1.2)


def test_compute_lcia_multiple_methods_share_one_lca_object(basic_papercup):
    BIO = basic_papercup["bio"]
    bd.Method(("test", "GWP2")).write([((BIO, "co2"), 2.0)])
    scores = lcia.compute_lcia(
        basic_papercup["root_key"], 1.0, [basic_papercup["method"], ("test", "GWP2")],
    )
    assert scores[("test", "GWP2")] == pytest.approx(scores[basic_papercup["method"]] * 2)


def test_contribution_by_location_sums_to_total(basic_papercup):
    method = basic_papercup["method"]
    breakdowns = lcia.contribution_by_location_for_methods(
        basic_papercup["root_key"], 1.0, [method],
    )
    breakdown = breakdowns[method]
    total = sum(breakdown.values())
    expected_total = lcia.compute_lcia(basic_papercup["root_key"], 1.0, [method])[method]
    assert total == pytest.approx(expected_total)


def test_contribution_by_location_groups_correctly(basic_papercup):
    method = basic_papercup["method"]
    breakdown = lcia.contribution_by_location_for_methods(
        basic_papercup["root_key"], 1.0, [method],
    )[method]

    # electricity_RER (RER, 0.01 kWh * 0.4) + pulp_RER (RER, 0.02 kg * 1.2)
    assert breakdown["RER"] == pytest.approx(0.01 * 0.4 + 0.02 * 1.2)
    # the paper cup's own direct biosphere exchange
    assert breakdown["direct (this process)"] == pytest.approx(0.05)


def test_contribution_by_location_after_regionalization(basic_papercup):
    root = bd.get_activity(basic_papercup["root_key"])
    sig_index = regionalize.build_flow_signature_index(basic_papercup["db"])
    subs, _ = regionalize.build_substitutions(root, ["US", "RoW", "RER"], sig_index, max_depth=1)
    new_act = regionalize.build_regionalized_activity(root, subs, "papercup [test]")

    method = basic_papercup["method"]
    breakdown = lcia.contribution_by_location_for_methods(new_act.key, 1.0, [method])[method]

    assert breakdown["US"] == pytest.approx(0.01 * 0.6)  # electricity now US
    assert breakdown["RoW"] == pytest.approx(0.02 * 1.5)  # pulp now RoW
    assert breakdown["direct (this process)"] == pytest.approx(0.05)


def test_contribution_by_flow_keeps_flows_separate_and_sorted(basic_papercup):
    method = basic_papercup["method"]
    rows = lcia.contribution_by_flow_for_methods(basic_papercup["root_key"], 1.0, [method])[method]

    names = {name for name, _loc, _val in rows}
    assert names == {"electricity, medium voltage", "kraft pulp", "(direct emissions of this process)"}

    # sorted by |contribution| descending
    values = [abs(val) for _n, _l, val in rows]
    assert values == sorted(values, reverse=True)

    by_name = {name: (loc, val) for name, loc, val in rows}
    assert by_name["electricity, medium voltage"] == ("RER", pytest.approx(0.01 * 0.4))
    assert by_name["kraft pulp"] == ("RER", pytest.approx(0.02 * 1.2))
    assert by_name["(direct emissions of this process)"][0] == lcia.DIRECT_LABEL
    assert by_name["(direct emissions of this process)"][1] == pytest.approx(0.05)


def test_contribution_by_flow_and_by_location_are_consistent(basic_papercup):
    """contribution_by_location_for_methods aggregates
    contribution_by_flow_for_methods -- the two must always agree."""
    method = basic_papercup["method"]
    flow_rows = lcia.contribution_by_flow_for_methods(basic_papercup["root_key"], 1.0, [method])[method]
    location_breakdown = lcia.contribution_by_location_for_methods(
        basic_papercup["root_key"], 1.0, [method],
    )[method]

    manual_agg: dict[str, float] = {}
    for _name, loc, val in flow_rows:
        manual_agg[loc] = manual_agg.get(loc, 0.0) + val

    assert manual_agg.keys() == location_breakdown.keys()
    for loc in manual_agg:
        assert manual_agg[loc] == pytest.approx(location_breakdown[loc])
