from __future__ import annotations

import bw2data as bd
import pytest

from ecoinvent_regionalizer.core import lcia, regionalize


def test_depth1_resolves_direct_flows(basic_papercup):
    root = bd.get_activity(basic_papercup["root_key"])
    sig_index = regionalize.build_flow_signature_index(basic_papercup["db"])
    subs, truncated = regionalize.build_substitutions(
        root, ["US", "RNA", "GLO", "RoW", "RER"], sig_index, max_depth=1,
    )
    assert not truncated
    assert len(subs) == 2
    by_flow = {s.flow_name: s for s in subs}
    assert by_flow["electricity, medium voltage"].chosen_location == "US"
    assert by_flow["kraft pulp"].chosen_location == "RoW"  # no US option exists


def test_priority_falls_back_to_original_when_nothing_matches(basic_papercup):
    root = bd.get_activity(basic_papercup["root_key"])
    sig_index = regionalize.build_flow_signature_index(basic_papercup["db"])
    subs, _ = regionalize.build_substitutions(
        root, ["ZZ-nonexistent"], sig_index, max_depth=1,
    )
    by_flow = {s.flow_name: s for s in subs}
    # neither flow has a "ZZ-nonexistent" option, so both keep their original
    assert by_flow["electricity, medium voltage"].chosen_location == "RER"
    assert by_flow["kraft pulp"].chosen_location == "RER"


def test_regionalized_activity_matches_hand_calculated_score(basic_papercup):
    root = bd.get_activity(basic_papercup["root_key"])
    sig_index = regionalize.build_flow_signature_index(basic_papercup["db"])
    subs, _ = regionalize.build_substitutions(
        root, ["US", "RoW", "RER"], sig_index, max_depth=1,
    )
    new_act = regionalize.build_regionalized_activity(root, subs, "papercup [test]")

    method = basic_papercup["method"]
    orig_score = lcia.compute_lcia(root.key, 1.0, [method])[method]
    new_score = lcia.compute_lcia(new_act.key, 1.0, [method])[method]

    assert orig_score == pytest.approx(0.05 + 0.01 * 0.4 + 0.02 * 1.2)
    assert new_score == pytest.approx(0.05 + 0.01 * 0.6 + 0.02 * 1.5)


def test_depth2_explores_the_chosen_activitys_own_inputs(nested_papercup):
    root = bd.get_activity(nested_papercup["root_key"])
    sig_index = regionalize.build_flow_signature_index(nested_papercup["db"])
    subs, truncated = regionalize.build_substitutions(
        root, ["US", "RNA", "GLO", "RoW", "RER"], sig_index, max_depth=2,
    )
    assert not truncated
    depth2 = [s for s in subs if s.depth == 2]
    assert len(depth2) == 1
    steel_sub = depth2[0]
    assert steel_sub.flow_name == "steel"
    # electricity resolved to US at depth 1, so depth 2 should explore
    # electricity_US's own inputs, not electricity_RER's
    assert steel_sub.parent_key == (nested_papercup["db"], "electricity_US")
    assert steel_sub.chosen_location == "US"


def test_depth2_regionalized_score_propagates_nested_substitution(nested_papercup):
    root = bd.get_activity(nested_papercup["root_key"])
    sig_index = regionalize.build_flow_signature_index(nested_papercup["db"])
    subs, _ = regionalize.build_substitutions(
        root, ["US", "RNA", "GLO", "RoW", "RER"], sig_index, max_depth=2,
    )
    new_act = regionalize.build_regionalized_activity(root, subs, "papercup [depth2]")

    method = nested_papercup["method"]
    new_score = lcia.compute_lcia(new_act.key, 1.0, [method])[method]
    expected = 0.05 + 0.01 * (0.6 + 0.1 * 2.5) + 0.02 * 1.5
    assert new_score == pytest.approx(expected)


def test_manual_override_is_respected_in_regionalized_activity(basic_papercup):
    root = bd.get_activity(basic_papercup["root_key"])
    sig_index = regionalize.build_flow_signature_index(basic_papercup["db"])
    subs, _ = regionalize.build_substitutions(
        root, ["US", "RoW", "RER"], sig_index, max_depth=1,
    )
    electricity_sub = next(s for s in subs if s.flow_name == "electricity, medium voltage")
    assert electricity_sub.chosen_location == "US"
    electricity_sub.chosen_location = "RoW"
    electricity_sub.manual_override = True

    new_act = regionalize.build_regionalized_activity(root, subs, "papercup [override]")
    method = basic_papercup["method"]
    new_score = lcia.compute_lcia(new_act.key, 1.0, [method])[method]
    assert new_score == pytest.approx(0.05 + 0.01 * 0.5 + 0.02 * 1.5)  # electricity_RoW's 0.5, not US's 0.6


def test_cyclic_graph_does_not_infinite_recurse(cyclic_papercup):
    """
    Regression test for a real bug: real ecoinvent has technosphere cycles
    (e.g. cogeneration where electricity depends on heat and vice versa).
    Both substitution building and regionalized-activity construction must
    terminate instead of recursing until RecursionError.
    """
    root = bd.get_activity(cyclic_papercup["root_key"])
    sig_index = regionalize.build_flow_signature_index(cyclic_papercup["db"])
    subs, truncated = regionalize.build_substitutions(
        root, ["RoW", "RER"], sig_index, max_depth=4,
    )
    assert not truncated
    assert len(subs) == 3  # electricity->heat->electricity, then cycle guard stops it

    new_act = regionalize.build_regionalized_activity(root, subs, "papercup [cyclic]")
    method = cyclic_papercup["method"]
    score = lcia.compute_lcia(new_act.key, 1.0, [method])[method]
    assert score > 0  # just needs to compute without raising/hanging


def test_shared_subgraph_is_only_built_once(nested_papercup):
    """
    If two different branches resolve to the same underlying activity, the
    regionalized-activity builder should reuse one copy of it rather than
    creating duplicates (memoization by activity key).
    """
    root = bd.get_activity(nested_papercup["root_key"])
    sig_index = regionalize.build_flow_signature_index(nested_papercup["db"])
    subs, _ = regionalize.build_substitutions(
        root, ["US", "RoW", "RER"], sig_index, max_depth=2,
    )
    regionalize.build_regionalized_activity(root, subs, "papercup [shared]")

    scratch_db = bd.Database(regionalize.config.REGIONALIZED_DB)
    codes = [a["code"] for a in scratch_db]
    assert len(codes) == len(set(codes))  # no duplicate codes were written
