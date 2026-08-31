"""LCIA helpers built on bw2calc (brightway 2.5 matrix backend)."""
from __future__ import annotations

import bw2calc as bc
import bw2data as bd


def list_methods() -> list[tuple]:
    return sorted(bd.methods)


def compute_lcia(activity_key: tuple, amount: float, methods: list[tuple]) -> dict[tuple, float]:
    results: dict[tuple, float] = {}
    if not methods:
        return results

    lca = bc.LCA({activity_key: amount}, methods[0])
    lca.lci()
    lca.lcia()
    results[methods[0]] = lca.score

    for method in methods[1:]:
        lca.switch_method(method)
        lca.lcia()
        results[method] = lca.score

    return results


DIRECT_LABEL = "direct (this process)"


def contribution_by_flow_for_methods(
    activity_key: tuple, amount: float, methods: list[tuple]
) -> dict[tuple, list[tuple[str, str, float]]]:
    """
    For each method, decomposes the activity's total LCIA score into a
    per-flow contribution list: one (flow_name, location, contribution)
    tuple per direct technosphere input, plus a "direct (this process)"
    entry for everything not attributable to an input (the activity's own
    direct biosphere exchanges). Sorted by |contribution| descending
    (hotspot order).

    This is the shared low-level computation behind both
    contribution_by_location_for_methods (aggregated by geography) and
    anything that needs per-flow detail (hotspot rankings, the geography
    substitution Sankey diagram). Factorizes the technosphere matrix
    exactly once for this activity and reuses it across every sub-solve AND
    every method, since factorization only depends on technosphere
    structure, not the impact method or which sub-demand is being solved.
    """
    activity = bd.get_activity(activity_key)
    exchanges = [
        (exc.input, exc.get("amount", 0.0) * amount)
        for exc in activity.technosphere()
    ]

    lca = bc.LCA({activity_key: amount}, methods[0])
    lca.lci(factorize=True)

    results: dict[tuple, list[tuple[str, str, float]]] = {}
    for method in methods:
        lca.switch_method(method)
        lca.lcia({activity.id: amount})
        total = lca.score

        rows: list[tuple[str, str, float]] = []
        residual = total
        for input_act, exc_amount in exchanges:
            if exc_amount == 0:
                continue
            lca.lcia({input_act.id: exc_amount})
            contribution = lca.score
            loc = input_act.get("location") or "unknown"
            rows.append((input_act.get("name", ""), loc, contribution))
            residual -= contribution

        rows.append(("(direct emissions of this process)", DIRECT_LABEL, residual))
        rows.sort(key=lambda r: abs(r[2]), reverse=True)
        results[method] = rows

    return results


def contribution_by_location_for_methods(
    activity_key: tuple, amount: float, methods: list[tuple]
) -> dict[tuple, dict[str, float]]:
    """
    Same as contribution_by_flow_for_methods, but aggregated by geography
    (summing all flows that share a location) instead of kept per-flow.
    """
    flow_data = contribution_by_flow_for_methods(activity_key, amount, methods)
    results: dict[tuple, dict[str, float]] = {}
    for method, rows in flow_data.items():
        breakdown: dict[str, float] = {}
        for _flow_name, loc, contribution in rows:
            breakdown[loc] = breakdown.get(loc, 0.0) + contribution
        results[method] = breakdown
    return results
