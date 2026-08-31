from __future__ import annotations

import bw2data as bd
import bw2io as bi

from ecoinvent_regionalizer.core import bw_setup


def test_fixed_lcia_data_has_tuple_flow_keys_not_lists():
    """
    Regression test: bw2io's bundled create_default_lcia_methods(shortcut=True)
    only converts method['name'] to a tuple and leaves each characterization
    factor's flow key as a JSON list, which bw2data.Method.write() rejects.
    Our fixed loader must convert those too.
    """
    data = bw_setup._load_fixed_lcia_data()
    assert len(data) > 0
    for method in data:
        assert isinstance(method["name"], tuple)
        for exc in method["exchanges"]:
            assert isinstance(exc["input"], tuple), (
                f"flow key not converted to tuple: {exc['input']!r}"
            )


def test_ensure_project_creates_biosphere_and_all_methods(bw_project):
    bw_setup.ensure_project(bw_project)
    assert "biosphere3" in bd.databases
    expected = len(bw_setup._load_fixed_lcia_data())
    assert len(bd.methods) == expected


def test_ensure_project_resumes_from_partial_method_state(bw_project):
    """
    Regression test for the exact failure mode a real user hit: the setup
    crashed after registering (but not writing) exactly one LCIA method,
    leaving `len(bd.methods) == 1`. A naive `== 0` check would treat that as
    "already done" and never repair it.
    """
    bi.create_default_biosphere3()
    data = bw_setup._load_fixed_lcia_data()
    first = data[0]
    m = bd.Method(first["name"])
    m.register(description=first["description"], filename=first["filename"], unit=first["unit"])
    assert len(bd.methods) == 1

    bw_setup.ensure_project(bw_project)
    assert len(bd.methods) == len(data)


def test_delete_project_removes_it(bw_project):
    assert bw_setup.delete_project(bw_project) is True
    assert bw_project not in [p.name for p in bd.projects]


def test_delete_nonexistent_project_returns_false():
    assert bw_setup.delete_project("definitely-does-not-exist-xyz") is False
