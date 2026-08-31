"""
Brightway project lifecycle: create the project, seed it with biosphere
flows + LCIA methods (bw2io's standard background data, NOT ecoinvent data),
and import a local ecospold2 dataset export into it.

No network calls to ecoinvent itself happen here. `bw2setup()` pulls
brightway's own generic biosphere/LCIA-method data package (needed for any
brightway project to compute impacts at all) -- this is a one-time,
non-ecoinvent-specific step.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import bw2data as bd
import bw2io as bi

from ecoinvent_regionalizer import config


def _load_fixed_lcia_data() -> list[dict]:
    """
    Loads bw2io's bundled default LCIA method data (lcia_39_ecoinvent.zip)
    and fixes a bug in installed bw2io (0.9.17): each characterization
    factor's biosphere flow key is stored as a JSON list (e.g.
    ['biosphere3', '<uuid>']). bw2io's own "shortcut" loader
    (create_default_lcia_methods(shortcut=True)) only converts
    `method["name"]` to a tuple and forgets to convert each exchange's
    `input` key, so bw2data.Method.write() rejects every CF with "Can't
    understand elementary flow identifier [...]" (list, not tuple). The
    non-shortcut path (shortcut=False) avoids this but needs an external
    Excel file bw2io doesn't bundle, so isn't usable standalone. This
    reproduces the shortcut path with the missing conversion added.
    """
    import json
    import zipfile

    fp = Path(bi.__file__).parent / "data" / "lcia" / "lcia_39_ecoinvent.zip"
    with zipfile.ZipFile(fp, mode="r") as archive:
        data = json.load(archive.open("data.json"))

    for method in data:
        method["name"] = tuple(method["name"])
        for exc in method["exchanges"]:
            if isinstance(exc.get("input"), list):
                exc["input"] = tuple(exc["input"])

    return data


def _create_default_lcia_methods_fixed(overwrite: bool = False) -> None:
    from bw2io.importers.base_lcia import LCIAImporter

    data = _load_fixed_lcia_data()
    ei = LCIAImporter("lcia_39_ecoinvent.zip")
    ei.data = data
    ei.write_methods(overwrite=overwrite)


def ensure_project(
    project_name: str = config.DEFAULT_BW_PROJECT,
    log: Callable[[str], None] = print,
) -> None:
    """
    Idempotent, resumable setup: checks biosphere3 and LCIA methods
    independently and completely, since a prior run can fail partway
    through -- e.g. Method.register() runs before Method.write() for each
    method in bw2io's write loop, so a crash on method N leaves methods
    0..N-1 (or, on the very first bad flow, exactly 1 method) registered
    but incomplete. A naive `len(bd.methods) == 0` check misses that
    partial state entirely, so this compares against the actual expected
    count instead.
    """
    bd.projects.set_current(project_name)
    if "biosphere3" not in bd.databases:
        log("Setting up biosphere flow database (one-time, ~4700 flows)...")
        bi.create_default_biosphere3()

    expected_method_count = len(_load_fixed_lcia_data())
    if len(bd.methods) < expected_method_count:
        log(f"Setting up default LCIA methods (one-time, {expected_method_count} methods)...")
        _create_default_lcia_methods_fixed(overwrite=True)

    log("Setting up core data migrations...")
    bi.create_core_migrations()


def list_projects() -> list[str]:
    return sorted(p.name for p in bd.projects)


def delete_project(project_name: str) -> bool:
    """Deletes a brightway project entirely (all its databases, methods,
    everything) so import can be redone from scratch. Returns False if the
    project doesn't exist."""
    if project_name not in [p.name for p in bd.projects]:
        return False
    if bd.projects.current == project_name:
        bd.projects.set_current("default")
    bd.projects.delete_project(project_name, delete_dir=True)
    return True


def list_databases(project_name: str = config.DEFAULT_BW_PROJECT) -> list[str]:
    bd.projects.set_current(project_name)
    return sorted(bd.databases)


def find_ecospold_dir(root: Path) -> Path:
    """
    ecoinvent's ecospold2 export is usually a zip that extracts to a folder
    containing a `datasets` subfolder full of .spold files. Walk `root`
    looking for that, falling back to `root` itself if .spold files are
    directly inside it.
    """
    if any(root.glob("*.spold")):
        return root
    for candidate in root.rglob("datasets"):
        if candidate.is_dir() and any(candidate.glob("*.spold")):
            return candidate
    for candidate in root.rglob("*.spold"):
        return candidate.parent
    raise FileNotFoundError(
        f"No .spold files found under {root}. Point to the folder that "
        f"contains the extracted ecospold2 dataset export."
    )


def import_ecoinvent(
    source_dir: Path,
    db_name: str = config.DEFAULT_ECOINVENT_DB,
    project_name: str = config.DEFAULT_BW_PROJECT,
    log: Callable[[str], None] = print,
) -> None:
    ensure_project(project_name, log=log)

    if db_name in bd.databases:
        log(f"Database '{db_name}' already exists in project '{project_name}'. Skipping import.")
        return

    spold_dir = find_ecospold_dir(Path(source_dir))
    log(f"Found ecospold2 files in: {spold_dir}")

    log("Extracting ecospold2 datasets (this reads every .spold file)...")
    importer = bi.SingleOutputEcospold2Importer(str(spold_dir), db_name)
    log("Applying import strategies (linking exchanges, matching biosphere flows)...")
    importer.apply_strategies()

    stats = importer.statistics()
    log(f"Import statistics: {stats}")

    unlinked = list(importer.unlinked)
    if unlinked:
        log(f"WARNING: {len(unlinked)} exchanges could not be linked "
            f"(likely biosphere flows newer than this bw2io install's "
            f"bundled flow list). Dropping them so the database doesn't "
            f"contain dangling references -- write_database() does not "
            f"raise on unlinked exchanges by default, so leaving them in "
            f"would silently under-count impacts for any activity that "
            f"uses one of these flows.")
        importer.drop_unlinked(i_am_reckless=True)
        remaining = len(list(importer.unlinked))
        log(f"After dropping: {remaining} unlinked exchanges remain.")

    log("Writing database (this can take several minutes for the full ecoinvent DB)...")
    importer.write_database()
    log(f"Done. Database '{db_name}' now has {len(bd.Database(db_name))} activities.")
