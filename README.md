# Ecoinvent Geography Regionalizer

[![CI](https://github.com/not-modest/ecoinvent-regionalizer/actions/workflows/ci.yml/badge.svg)](https://github.com/not-modest/ecoinvent-regionalizer/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A desktop app (PyQt6 + [Brightway 2.5](https://docs.brightway.dev/)) for
regionalizing a single-geography ecoinvent activity: it takes an activity
that's only available for one geography (commonly Europe/RER) and rebuilds
it with each input flow re-pointed to your preferred geography, using a
ranked fallback list you control (e.g. `USA -> RNA -> GLO -> RoW -> RER`).
It then computes and compares LCIA results for the original vs. the
regionalized version.

**Scope**: only the input flows of the selected activity are re-pointed to
alternate-geography versions of the same flow (same name, reference
product, unit) — optionally recursing to deeper levels of the supply chain.
The activity's own foreground process content and direct emissions are
never changed. See the app's "0. About" tab for the full methodology and
limitations.

## Installation

Requires **Python 3.11** (brightway's dependencies don't yet have prebuilt
wheels for newer Python versions on all platforms).

```bash
git clone https://github.com/not-modest/ecoinvent-regionalizer.git
cd ecoinvent-regionalizer
python3.11 -m venv .venv
source .venv/bin/activate          # .venv\Scripts\activate on Windows
pip install -e .
```

## Running the app

```bash
source .venv/bin/activate
ecoinvent-regionalizer
```

(or `python -m ecoinvent_regionalizer.main`, equivalently)

## Getting your ecoinvent data in

**This project does not include, bundle, or distribute any ecoinvent
data.** You need your own valid [ecoinvent](https://ecoinvent.org/) license.

1. Log into ecoinvent, download the **ecospold2 dataset export** for your
   ecoinvent version and system model (e.g. "ecoinvent 3.12 cutoff") — not
   the SimaPro CSV or the Excel matrices, the ecospold2 XML export.
2. Extract the archive. It should contain (or contain a subfolder with) a
   `datasets` folder full of `.spold` files.
3. Keep the extracted data **outside** this repository — anywhere on your
   machine you like (the app defaults to `~/ecoinvent_data/raw_export/` but
   lets you browse to any folder).
4. Launch the app → **Setup / Import** tab → Browse to that folder →
   Import. First-time import also does a one-time setup of brightway's own
   generic biosphere-flow and LCIA-method background data (not ecoinvent's
   data — this is the only network call the app makes). Importing the full
   ecoinvent database can take several minutes depending on your machine;
   the app shows a progress indicator and log throughout.

## Using it

1. **Setup / Import tab** — import once (or reconnect to an
   already-imported project/database with "Already imported — just
   connect"). "Clear project & start fresh" wipes a project if you need to
   redo the import.
2. **Analysis tab** — search for your root activity (e.g. "paper cup"),
   double-click to select it. Build your geography priority ranking on the
   right by adding locations (only ones that actually exist in your
   database are offered) and dragging to reorder. Set the **depth** (1 =
   direct inputs only; 2+ recurses into each resolved input's own inputs).
   Click "Load exchanges & resolve geography" to see the flow table with
   original vs. resolved geography per row — override any row manually via
   its dropdown. Export the table to CSV if you want a written record.
3. **Results tab** — select one or more LCIA methods, click "Compute &
   compare" to see a stacked bar chart (by geography) of original vs.
   regionalized impact scores, switch between a compact multi-method view
   or a single-method deep-dive, toggle percent-of-total normalization, and
   export the full breakdown to CSV.

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v          # test suite
ruff check .               # lint
mypy ecoinvent_regionalizer --ignore-missing-imports   # type check
```

The test suite uses small synthetic in-process fixtures (not real ecoinvent
data) and runs in CI on every push/PR via GitHub Actions.

## Licensing / data isolation

This software is licensed under the [MIT License](LICENSE). **ecoinvent
data is licensed separately by the ecoinvent Association**; you are
responsible for holding your own valid license, and this repository never
includes, bundles, or redistributes any ecoinvent data. Keep your extracted
ecoinvent export and any imported brightway project data outside this
repository (the default paths already do this) — this also matters if
you're using an AI coding assistant alongside this codebase, since
ecoinvent's terms prohibit sharing the data with third parties, which can
include AI tooling with filesystem access.

## Notes / limitations

- Flow matching is by exact `(name, reference product, unit)` — if
  ecoinvent names a flow differently across geographies, it won't be found
  as a candidate and the original is kept.
- This is an approximation technique for exploratory and comparative LCA
  work, not an ecoinvent-endorsed or peer-reviewed regionalization method.
  Validate results against your own domain knowledge.
- Built on [Brightway 2.5](https://docs.brightway.dev/) (`bw2data`,
  `bw2io`, `bw2calc`) and PyQt6.

## Contributing

Issues and PRs welcome. Please run `pytest` and `ruff check .` before
submitting.
