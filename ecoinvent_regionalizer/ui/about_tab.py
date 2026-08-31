from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

ABOUT_HTML = """
<h1 style="margin-bottom:0;">Ecoinvent Geography Regionalizer</h1>
<p style="color:#666; margin-top:2px;">Created by Prasham Mehta</p>

<h3>What this is</h3>
<p>
ecoinvent often publishes only one geography for a given product or process
(commonly Europe/RER), even when you need results for a different region.
This tool takes an activity that exists for only one geography and rebuilds
it with each input flow re-pointed to your preferred geography, using a
ranked fallback list you control (e.g. <b>USA &rarr; RNA &rarr; GLO &rarr; RoW &rarr; RER</b>).
It then computes and compares LCIA results for the original vs. the
regionalized version, so you can see exactly how much the substitution
changed your results and why.
</p>

<h3>How it works</h3>
<p>
For your chosen activity, the tool walks its direct input flows (optionally
recursing to deeper levels) and, for each one, looks for an equivalent
activity &mdash; same name, reference product, and unit &mdash; available in a
geography closer to your target. Your priority list decides which
geography wins when more than one option exists; if none of your preferred
geographies are available for a flow, the original is kept. A new
"regionalized" copy of the activity is built with only those swaps applied
&mdash; the process's own foreground content and direct emissions are left
untouched.
</p>

<h3>Scope &amp; limitations</h3>
<ul>
<li>Only technosphere input flows are substituted; the activity's own
process content (yields, technology, direct emissions) is not changed.</li>
<li>Flow matching is by exact (name, reference product, unit) &mdash; if
ecoinvent names a flow differently across geographies, it won't be found
as a candidate.</li>
<li>This is an approximation technique for exploratory and comparative use,
not an ecoinvent-endorsed or peer-reviewed regionalization method. Treat
results as directional, and validate against your own domain knowledge.</li>
</ul>

<h3>Data &amp; licensing</h3>
<p>
This application does not include, bundle, or redistribute any ecoinvent
data. You must have your own valid ecoinvent license and supply your own
ecospold2 export; all ecoinvent-derived data stays local to your machine.
</p>
<p>
Built on <a href="https://docs.brightway.dev/">Brightway 2.5</a>
(<code>bw2data</code>, <code>bw2io</code>, <code>bw2calc</code>) and PyQt6.
</p>
"""


class AboutTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)

        label = QLabel(ABOUT_HTML)
        label.setWordWrap(True)
        label.setOpenExternalLinks(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(label)
        layout.addStretch()
