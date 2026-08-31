"""
Shared pytest fixtures. Sets BRIGHTWAY2_DIR to an isolated temp directory
BEFORE any bw2data import happens (including via ecoinvent_regionalizer.config),
so the test suite never touches the developer's real brightway projects or
any licensed ecoinvent data -- it only ever operates on small synthetic
in-memory-scale fixtures defined here.
"""
from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

_TEST_BW_DIR = Path(tempfile.mkdtemp(prefix="ecoinvent_regionalizer_test_bw_"))
os.environ["BRIGHTWAY2_DIR"] = str(_TEST_BW_DIR)

import bw2data as bd  # noqa: E402
import pytest  # noqa: E402

from ecoinvent_regionalizer import config  # noqa: E402,F401


@pytest.fixture
def bw_project():
    """Fresh, isolated brightway project per test, torn down afterward."""
    name = f"test-{uuid.uuid4().hex[:12]}"
    bd.projects.set_current(name)
    yield name
    if name in [p.name for p in bd.projects]:
        bd.projects.delete_project(name, delete_dir=True)


@pytest.fixture
def basic_papercup(bw_project):
    """
    One-level fixture: paper cup (RER) depends on electricity (RER/RoW/US)
    and kraft pulp (RER/RoW). Electricity has no RoW->US path collision;
    this is the baseline scenario used to validate direct-substitution
    correctness.
    """
    DB, BIO = "test-db", "test-biosphere"
    bio = bd.Database(BIO)
    bio.write({
        (BIO, "co2"): {"name": "Carbon dioxide", "unit": "kg", "type": "emission", "categories": ("air",)},
    })
    db = bd.Database(DB)
    db.write({
        (DB, "electricity_RER"): {"name": "electricity, medium voltage", "reference product": "electricity, medium voltage", "unit": "kWh", "location": "RER", "exchanges": [
            {"input": (DB, "electricity_RER"), "amount": 1, "type": "production"},
            {"input": (BIO, "co2"), "amount": 0.4, "type": "biosphere"},
        ]},
        (DB, "electricity_US"): {"name": "electricity, medium voltage", "reference product": "electricity, medium voltage", "unit": "kWh", "location": "US", "exchanges": [
            {"input": (DB, "electricity_US"), "amount": 1, "type": "production"},
            {"input": (BIO, "co2"), "amount": 0.6, "type": "biosphere"},
        ]},
        (DB, "electricity_RoW"): {"name": "electricity, medium voltage", "reference product": "electricity, medium voltage", "unit": "kWh", "location": "RoW", "exchanges": [
            {"input": (DB, "electricity_RoW"), "amount": 1, "type": "production"},
            {"input": (BIO, "co2"), "amount": 0.5, "type": "biosphere"},
        ]},
        (DB, "pulp_RER"): {"name": "kraft pulp", "reference product": "kraft pulp", "unit": "kg", "location": "RER", "exchanges": [
            {"input": (DB, "pulp_RER"), "amount": 1, "type": "production"},
            {"input": (BIO, "co2"), "amount": 1.2, "type": "biosphere"},
        ]},
        (DB, "pulp_RoW"): {"name": "kraft pulp", "reference product": "kraft pulp", "unit": "kg", "location": "RoW", "exchanges": [
            {"input": (DB, "pulp_RoW"), "amount": 1, "type": "production"},
            {"input": (BIO, "co2"), "amount": 1.5, "type": "biosphere"},
        ]},
        (DB, "papercup_RER"): {"name": "paper cup", "reference product": "paper cup", "unit": "unit", "location": "RER", "exchanges": [
            {"input": (DB, "papercup_RER"), "amount": 1, "type": "production"},
            {"input": (DB, "electricity_RER"), "amount": 0.01, "type": "technosphere"},
            {"input": (DB, "pulp_RER"), "amount": 0.02, "type": "technosphere"},
            {"input": (BIO, "co2"), "amount": 0.05, "type": "biosphere"},
        ]},
    })
    method = ("test", "GWP")
    bd.Method(method).write([((BIO, "co2"), 1.0)])
    return {"db": DB, "bio": BIO, "root_key": (DB, "papercup_RER"), "method": method}


@pytest.fixture
def nested_papercup(bw_project):
    """
    Two-level fixture: paper cup -> electricity (RER/US/RoW) -> steel (RER/US),
    plus pulp (RER/RoW). Used to validate depth>1 resolution: at depth 2 the
    tool should explore the CHOSEN electricity's own steel input, not the
    original RER electricity's.
    """
    DB, BIO = "test-db", "test-biosphere"
    bio = bd.Database(BIO)
    bio.write({
        (BIO, "co2"): {"name": "Carbon dioxide", "unit": "kg", "type": "emission", "categories": ("air",)},
    })
    db = bd.Database(DB)
    db.write({
        (DB, "steel_RER"): {"name": "steel", "reference product": "steel", "unit": "kg", "location": "RER", "exchanges": [
            {"input": (DB, "steel_RER"), "amount": 1, "type": "production"},
            {"input": (BIO, "co2"), "amount": 2.0, "type": "biosphere"},
        ]},
        (DB, "steel_US"): {"name": "steel", "reference product": "steel", "unit": "kg", "location": "US", "exchanges": [
            {"input": (DB, "steel_US"), "amount": 1, "type": "production"},
            {"input": (BIO, "co2"), "amount": 2.5, "type": "biosphere"},
        ]},
        (DB, "electricity_RER"): {"name": "electricity, medium voltage", "reference product": "electricity, medium voltage", "unit": "kWh", "location": "RER", "exchanges": [
            {"input": (DB, "electricity_RER"), "amount": 1, "type": "production"},
            {"input": (DB, "steel_RER"), "amount": 0.1, "type": "technosphere"},
            {"input": (BIO, "co2"), "amount": 0.4, "type": "biosphere"},
        ]},
        (DB, "electricity_US"): {"name": "electricity, medium voltage", "reference product": "electricity, medium voltage", "unit": "kWh", "location": "US", "exchanges": [
            {"input": (DB, "electricity_US"), "amount": 1, "type": "production"},
            {"input": (DB, "steel_RER"), "amount": 0.1, "type": "technosphere"},
            {"input": (BIO, "co2"), "amount": 0.6, "type": "biosphere"},
        ]},
        (DB, "electricity_RoW"): {"name": "electricity, medium voltage", "reference product": "electricity, medium voltage", "unit": "kWh", "location": "RoW", "exchanges": [
            {"input": (DB, "electricity_RoW"), "amount": 1, "type": "production"},
            {"input": (BIO, "co2"), "amount": 0.5, "type": "biosphere"},
        ]},
        (DB, "pulp_RER"): {"name": "kraft pulp", "reference product": "kraft pulp", "unit": "kg", "location": "RER", "exchanges": [
            {"input": (DB, "pulp_RER"), "amount": 1, "type": "production"},
            {"input": (BIO, "co2"), "amount": 1.2, "type": "biosphere"},
        ]},
        (DB, "pulp_RoW"): {"name": "kraft pulp", "reference product": "kraft pulp", "unit": "kg", "location": "RoW", "exchanges": [
            {"input": (DB, "pulp_RoW"), "amount": 1, "type": "production"},
            {"input": (BIO, "co2"), "amount": 1.5, "type": "biosphere"},
        ]},
        (DB, "papercup_RER"): {"name": "paper cup", "reference product": "paper cup", "unit": "unit", "location": "RER", "exchanges": [
            {"input": (DB, "papercup_RER"), "amount": 1, "type": "production"},
            {"input": (DB, "electricity_RER"), "amount": 0.01, "type": "technosphere"},
            {"input": (DB, "pulp_RER"), "amount": 0.02, "type": "technosphere"},
            {"input": (BIO, "co2"), "amount": 0.05, "type": "biosphere"},
        ]},
    })
    method = ("test", "GWP")
    bd.Method(method).write([((BIO, "co2"), 1.0)])
    return {"db": DB, "bio": BIO, "root_key": (DB, "papercup_RER"), "method": method}


@pytest.fixture
def cyclic_papercup(bw_project):
    """
    Cyclic fixture: electricity depends on heat, heat depends on electricity
    (a classic cogeneration-style loop, common in real ecoinvent). Used to
    validate that depth-walking and the regionalized-activity builder both
    terminate instead of recursing forever.
    """
    DB, BIO = "test-db", "test-biosphere"
    bio = bd.Database(BIO)
    bio.write({
        (BIO, "co2"): {"name": "Carbon dioxide", "unit": "kg", "type": "emission", "categories": ("air",)},
    })
    db = bd.Database(DB)
    db.write({
        (DB, "electricity_RER"): {"name": "electricity", "reference product": "electricity", "unit": "kWh", "location": "RER", "exchanges": [
            {"input": (DB, "electricity_RER"), "amount": 1, "type": "production"},
            {"input": (DB, "heat_RER"), "amount": 0.1, "type": "technosphere"},
            {"input": (BIO, "co2"), "amount": 0.4, "type": "biosphere"},
        ]},
        (DB, "heat_RER"): {"name": "heat", "reference product": "heat", "unit": "MJ", "location": "RER", "exchanges": [
            {"input": (DB, "heat_RER"), "amount": 1, "type": "production"},
            {"input": (DB, "electricity_RER"), "amount": 0.05, "type": "technosphere"},
            {"input": (BIO, "co2"), "amount": 0.2, "type": "biosphere"},
        ]},
        (DB, "papercup_RER"): {"name": "paper cup", "reference product": "paper cup", "unit": "unit", "location": "RER", "exchanges": [
            {"input": (DB, "papercup_RER"), "amount": 1, "type": "production"},
            {"input": (DB, "electricity_RER"), "amount": 0.01, "type": "technosphere"},
            {"input": (BIO, "co2"), "amount": 0.05, "type": "biosphere"},
        ]},
    })
    method = ("test", "GWP")
    bd.Method(method).write([((BIO, "co2"), 1.0)])
    return {"db": DB, "bio": BIO, "root_key": (DB, "papercup_RER"), "method": method}
