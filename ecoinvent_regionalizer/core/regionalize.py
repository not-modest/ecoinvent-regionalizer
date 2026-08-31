"""
Core regionalization engine.

Scope (matches the manual Excel workflow this replaces, extended with an
optional depth): given one root activity (e.g. a paper cup dataset that
only exists for RER), look at its DIRECT technosphere exchanges (inputs)
and, for each one, try to swap the linked input activity for an equivalent
activity (same name + reference product + unit) available in a geography
closer to the user's target, using a user-ranked priority list of
locations. With depth > 1, each resolved (chosen-geography) input's own
technosphere exchanges are walked the same way for the next level, and so
on -- so deeper levels explore the CHOSEN geography's supply chain, not the
original one, since that's the graph the regionalized result will actually
use. Biosphere exchanges and each activity's own process content are left
untouched -- only technosphere inputs are re-pointed.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import bw2data as bd

from ecoinvent_regionalizer import config

MAX_SUBSTITUTION_NODES = 4000


@dataclass
class FlowCandidate:
    location: str
    activity_key: tuple  # (database, code)
    activity_name: str


@dataclass
class FlowSubstitution:
    exchange_id: tuple  # (input_key, output_key, type) - stable id within this activity's exchanges
    flow_name: str
    reference_product: str
    unit: str
    amount: float
    original_location: str
    original_key: tuple
    candidates: dict[str, FlowCandidate]  # location -> candidate
    depth: int = 1
    parent_key: tuple | None = None  # key of the (already-resolved) activity this exchange belongs to
    chosen_location: str | None = None
    manual_override: bool = False

    @property
    def available_locations(self) -> list[str]:
        return sorted(self.candidates.keys())

    @property
    def chosen_key(self) -> tuple:
        if self.chosen_location and self.chosen_location in self.candidates:
            return self.candidates[self.chosen_location].activity_key
        return self.original_key


def search_activities(db_name: str, term: str, limit: int = 50) -> list[bd.backends.proxies.Activity]:
    db = bd.Database(db_name)
    term_lower = term.lower()
    results = [
        act for act in db
        if term_lower in (act.get("name") or "").lower()
        or term_lower in (act.get("reference product") or "").lower()
    ]
    results.sort(key=lambda a: (a.get("name") or "", a.get("location") or ""))
    return results[:limit]


def get_all_locations(db_name: str) -> list[str]:
    db = bd.Database(db_name)
    locations = {act.get("location") for act in db if act.get("location")}
    return sorted(locations)


def get_direct_technosphere_exchanges(activity: bd.backends.proxies.Activity) -> list:
    return [exc for exc in activity.technosphere()]


def _flow_signature(activity: bd.backends.proxies.Activity) -> tuple:
    return (
        (activity.get("name") or "").strip().lower(),
        (activity.get("reference product") or "").strip().lower(),
        (activity.get("unit") or "").strip().lower(),
    )


def build_flow_signature_index(db_name: str) -> dict[tuple, list]:
    """
    One pass over the database building {(name, ref_product, unit): [activities]}
    so that finding geography siblings for many flows is O(1) lookups instead
    of a full-database scan per flow.
    """
    db = bd.Database(db_name)
    index: dict[tuple, list] = {}
    for act in db:
        index.setdefault(_flow_signature(act), []).append(act)
    return index


def get_location_options_for_input(
    input_activity: bd.backends.proxies.Activity,
    signature_index: dict[tuple, list],
) -> dict[str, FlowCandidate]:
    sig = _flow_signature(input_activity)
    siblings = signature_index.get(sig, [])
    options: dict[str, FlowCandidate] = {}
    for act in siblings:
        loc = act.get("location")
        if not loc:
            continue
        options[loc] = FlowCandidate(
            location=loc,
            activity_key=act.key,
            activity_name=act.get("name", ""),
        )
    return options


def resolve_priority(options: dict[str, FlowCandidate], priority_list: list[str], original_location: str) -> str | None:
    for loc in priority_list:
        if loc in options:
            return loc
    if original_location in options:
        return original_location
    return None


def _substitutions_for_activity(
    activity: bd.backends.proxies.Activity,
    priority_list: list[str],
    signature_index: dict[tuple, list],
    depth: int,
) -> list[FlowSubstitution]:
    subs = []
    for exc in get_direct_technosphere_exchanges(activity):
        input_act = exc.input
        options = get_location_options_for_input(input_act, signature_index)
        original_location = input_act.get("location", "")
        chosen = resolve_priority(options, priority_list, original_location)
        subs.append(FlowSubstitution(
            exchange_id=(exc.input.key, exc.output.key, exc.get("type", "technosphere")),
            flow_name=input_act.get("name", ""),
            reference_product=input_act.get("reference product", ""),
            unit=input_act.get("unit", ""),
            amount=exc.get("amount", 0.0),
            original_location=original_location,
            original_key=input_act.key,
            candidates=options,
            depth=depth,
            parent_key=activity.key,
            chosen_location=chosen,
        ))
    return subs


def build_substitutions(
    root_activity: bd.backends.proxies.Activity,
    priority_list: list[str],
    signature_index: dict[tuple, list],
    max_depth: int = 1,
    max_nodes: int = MAX_SUBSTITUTION_NODES,
) -> tuple[list[FlowSubstitution], bool]:
    """
    Walks depth 1..max_depth, breadth-first. Depth 1 is root_activity's own
    direct technosphere exchanges (as before). Each subsequent depth walks
    the CHOSEN (already-geography-resolved) activity from the previous
    level, not the original one -- since that's the actual graph the
    regionalized result will use, digging further should explore what that
    chosen substitute itself depends on.

    A shared-subgraph guard (`visited`) avoids re-walking the same resolved
    activity twice if multiple branches happen to depend on it. A hard cap
    (`max_nodes`) protects against combinatorial blowup at higher depths on
    real ecoinvent data, where a single activity can have dozens of direct
    inputs. Returns (substitutions, truncated) so the UI can warn the user
    if the cap was hit.
    """
    all_subs: list[FlowSubstitution] = []
    frontier = [root_activity]
    visited = {root_activity.key}
    truncated = False

    for depth in range(1, max_depth + 1):
        next_frontier = []
        for activity in frontier:
            if len(all_subs) >= max_nodes:
                truncated = True
                break
            level_subs = _substitutions_for_activity(activity, priority_list, signature_index, depth)
            all_subs.extend(level_subs)
            for sub in level_subs:
                chosen_key = sub.chosen_key
                if chosen_key in visited:
                    continue
                visited.add(chosen_key)
                try:
                    next_frontier.append(bd.get_activity(chosen_key))
                except Exception:
                    pass
        if truncated:
            break
        frontier = next_frontier
        if not frontier:
            break

    return all_subs, truncated


def build_regionalized_activity(
    root_activity: bd.backends.proxies.Activity,
    substitutions: list[FlowSubstitution],
    new_name: str,
    regionalized_db_name: str = config.REGIONALIZED_DB,
) -> bd.backends.proxies.Activity:
    """
    Recursively writes (or overwrites) a scenario activity tree in the
    scratch `regionalized_db_name` database. The root always gets a fresh
    copy. A descendant only gets a copy of its own if something about it
    (or something beneath it) actually changed -- otherwise the chosen
    activity is referenced as-is, so a depth-1 scenario behaves exactly as
    before and deeper scenarios don't create needless duplicate nodes.

    Memoized by activity key: since `substitutions` groups children purely
    by the parent activity's key (not by which branch reached it), the same
    shared input (e.g. two different flows both depending on "electricity,
    US") is only rebuilt once and reused, matching how the real graph
    shares nodes.
    """
    if regionalized_db_name not in bd.databases:
        bd.Database(regionalized_db_name).register()
    scratch_db = bd.Database(regionalized_db_name)
    existing_codes = {a["code"] for a in scratch_db}

    subs_by_parent: dict[tuple, list[FlowSubstitution]] = defaultdict(list)
    for s in substitutions:
        subs_by_parent[s.parent_key].append(s)

    cache: dict[tuple, tuple] = {}
    building: set[tuple] = set()  # cycle guard: keys currently mid-construction

    def make_copy(activity, children, name_override=None):
        code = f"regionalized_{activity['code']}"
        if code in existing_codes:
            scratch_db.get(code).delete()

        new_act = scratch_db.new_activity(
            code=code,
            name=name_override or f"{activity.get('name')} [regionalized]",
            unit=activity.get("unit"),
            location=f"{activity.get('location')}->custom",
        )
        new_act["reference product"] = activity.get("reference product", "")
        new_act.save()
        new_act.new_exchange(input=new_act.key, amount=1.0, type="production").save()

        sub_by_input_key = {s.original_key: s for s in children}
        for exc in activity.exchanges():
            exc_type = exc.get("type")
            if exc_type == "production":
                continue
            if exc_type == "technosphere" and exc.input.key in sub_by_input_key:
                sub = sub_by_input_key[exc.input.key]
                child_key = build_node(sub.chosen_key)
                new_act.new_exchange(
                    input=child_key, amount=exc.get("amount", 0.0),
                    type="technosphere", unit=exc.get("unit"),
                ).save()
            else:
                new_act.new_exchange(
                    input=exc.input.key, amount=exc.get("amount", 0.0),
                    type=exc_type, unit=exc.get("unit"),
                ).save()

        return new_act.key

    def build_node(activity_key: tuple, name_override: str | None = None) -> tuple:
        if activity_key in cache:
            return cache[activity_key]
        if activity_key in building:
            # Cycle in the technosphere graph (real ecoinvent data has these --
            # e.g. cogeneration/recycling loops). Break it by pointing this
            # specific edge at the original, unmodified activity instead of
            # recursing forever; every other edge into this node still gets
            # properly regionalized once its build completes.
            return activity_key
        children = subs_by_parent.get(activity_key, [])
        if not children and name_override is None:
            cache[activity_key] = activity_key
            return activity_key
        building.add(activity_key)
        activity = bd.get_activity(activity_key)
        new_key = make_copy(activity, children, name_override=name_override)
        building.discard(activity_key)
        cache[activity_key] = new_key
        return new_key

    root_key = build_node(root_activity.key, name_override=new_name)
    return bd.get_activity(root_key)
