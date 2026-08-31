from __future__ import annotations

import bw2data as bd
import matplotlib.patches as mpatches
import mplcursors
from matplotlib.backends.backend_qtagg import (
    FigureCanvasQTAgg,
    NavigationToolbar2QT,
)
from matplotlib.figure import Figure
from matplotlib.path import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ecoinvent_regionalizer.core import export, lcia, regionalize
from ecoinvent_regionalizer.ui.style import COLORBLIND_PALETTE

DIAGRAM_STACKED = "Stacked bars (by geography)"
DIAGRAM_HOTSPOT = "Top contributors (hotspot ranking)"
DIAGRAM_SANKEY = "Geography substitution flow (Sankey)"


class ResultsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.root_activity = None
        self.substitutions = []
        self.priority_list: list[str] = []
        self._last_methods: list[tuple] = []
        self._last_original_flows: dict = {}   # method -> [(flow_name, location, value), ...]
        self._last_new_flows: dict = {}
        self._last_original_breakdowns: dict = {}  # method -> {location: value}
        self._last_new_breakdowns: dict = {}
        self._computed_signature = None
        self._cursor = None
        self._build_ui()

    def _current_signature(self):
        if self.root_activity is None:
            return None
        return (
            self.root_activity.key,
            tuple(sorted((s.original_key, s.chosen_location) for s in self.substitutions)),
            tuple(self.priority_list),
        )

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(10, 10, 10, 10)

        method_box = QGroupBox("Impact assessment methods")
        method_layout = QVBoxLayout(method_box)
        self.method_list = QListWidget()
        self.method_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.method_list.setMaximumHeight(140)
        method_layout.addWidget(self.method_list)
        btn_row = QHBoxLayout()
        self.compute_btn = QPushButton("Compute && compare (original vs regionalized)")
        self.compute_btn.clicked.connect(self._compute)
        btn_row.addWidget(self.compute_btn)
        self.export_btn = QPushButton("Export to CSV")
        self.export_btn.clicked.connect(self._export_csv)
        btn_row.addWidget(self.export_btn)
        method_layout.addLayout(btn_row)
        layout.addWidget(method_box, 0)

        self.stale_label = QLabel(
            "⚠ Scenario changed since these results were computed — click "
            "\"Compute & compare\" to refresh."
        )
        self.stale_label.setStyleSheet(
            "background: #fff3cd; color: #7a5b00; padding: 6px 10px; "
            "border: 1px solid #e0c46c; border-radius: 4px; font-weight: 600;"
        )
        self.stale_label.setVisible(False)
        layout.addWidget(self.stale_label, 0)

        view_row = QHBoxLayout()
        view_row.addWidget(QLabel("Method:"))
        self.view_combo = QComboBox()
        self.view_combo.addItem("All selected methods (compact)")
        self.view_combo.currentIndexChanged.connect(self._on_view_changed)
        view_row.addWidget(self.view_combo)
        view_row.addWidget(QLabel("Diagram:"))
        self.diagram_combo = QComboBox()
        self.diagram_combo.addItems([DIAGRAM_STACKED, DIAGRAM_HOTSPOT, DIAGRAM_SANKEY])
        self.diagram_combo.currentIndexChanged.connect(self._on_view_changed)
        view_row.addWidget(self.diagram_combo)
        self.percent_checkbox = QCheckBox("Show as % of total (stacked bars only)")
        self.percent_checkbox.toggled.connect(self._on_view_changed)
        view_row.addWidget(self.percent_checkbox)
        view_row.addStretch()
        layout.addLayout(view_row)

        self.figure = Figure(figsize=(10, 5.5), dpi=150, constrained_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.canvas.setMinimumHeight(400)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        layout.addWidget(self.toolbar, 0)
        layout.addWidget(self.canvas, 4)

        self.summary_table = QTableWidget(0, 4)
        self.summary_table.setHorizontalHeaderLabels(
            ["Method", "Original score", "Regionalized score", "% change"]
        )
        self.summary_table.horizontalHeader().setStretchLastSection(True)
        self.summary_table.setAlternatingRowColors(True)
        self.summary_table.setMaximumHeight(160)
        layout.addWidget(self.summary_table, 0)

    def set_project(self, project_name: str):
        bd.projects.set_current(project_name)
        self.method_list.clear()
        for method in lcia.list_methods():
            item = QListWidgetItem(" / ".join(method))
            item.setData(Qt.ItemDataRole.UserRole, method)
            self.method_list.addItem(item)

    def set_scenario(self, root_activity, substitutions, priority_list):
        self.root_activity = root_activity
        self.substitutions = substitutions
        self.priority_list = priority_list
        if self._computed_signature is not None:
            self.stale_label.setVisible(self._current_signature() != self._computed_signature)

    def _selected_methods(self) -> list[tuple]:
        return [item.data(Qt.ItemDataRole.UserRole) for item in self.method_list.selectedItems()]

    def _compute(self):
        if self.root_activity is None or not self.substitutions:
            QMessageBox.warning(self, "No scenario", "Build a scenario in the Analysis tab first.")
            return
        methods = self._selected_methods()
        if not methods:
            QMessageBox.warning(self, "No method", "Select at least one impact method.")
            return

        new_act = regionalize.build_regionalized_activity(
            self.root_activity,
            self.substitutions,
            new_name=f"{self.root_activity.get('name')} [regionalized: {'>'.join(self.priority_list)}]",
        )

        original_flows = lcia.contribution_by_flow_for_methods(self.root_activity.key, 1.0, methods)
        new_flows = lcia.contribution_by_flow_for_methods(new_act.key, 1.0, methods)

        def aggregate(rows):
            out: dict[str, float] = {}
            for _name, loc, val in rows:
                out[loc] = out.get(loc, 0.0) + val
            return out

        original_breakdowns = {m: aggregate(original_flows[m]) for m in methods}
        new_breakdowns = {m: aggregate(new_flows[m]) for m in methods}
        original_scores = {m: sum(original_breakdowns[m].values()) for m in methods}
        new_scores = {m: sum(new_breakdowns[m].values()) for m in methods}

        self._last_methods = methods
        self._last_original_flows = original_flows
        self._last_new_flows = new_flows
        self._last_original_breakdowns = original_breakdowns
        self._last_new_breakdowns = new_breakdowns
        self._computed_signature = self._current_signature()
        self.stale_label.setVisible(False)

        self.view_combo.blockSignals(True)
        self.view_combo.clear()
        self.view_combo.addItem("All selected methods (compact)")
        for m in methods:
            self.view_combo.addItem(" / ".join(m))
        self.view_combo.blockSignals(False)

        self._render_current_view()
        self._render_table(methods, original_scores, new_scores)

    def _on_view_changed(self, *_args):
        if self._last_methods:
            self._render_current_view()

    def _focused_method(self) -> tuple:
        """The single method hotspot/Sankey views operate on -- the chosen
        method if one is selected, otherwise the first computed method."""
        idx = self.view_combo.currentIndex()
        if idx > 0:
            return self._last_methods[idx - 1]
        return self._last_methods[0]

    def _render_current_view(self):
        diagram = self.diagram_combo.currentText()
        if diagram == DIAGRAM_HOTSPOT:
            self._render_hotspot_chart(self._focused_method())
            return
        if diagram == DIAGRAM_SANKEY:
            self._render_sankey_chart(self._focused_method())
            return

        idx = self.view_combo.currentIndex()
        methods_to_show = self._last_methods if idx <= 0 else [self._last_methods[idx - 1]]
        normalize = self.percent_checkbox.isChecked()
        self._render_stacked_chart(
            methods_to_show, self._last_original_breakdowns, self._last_new_breakdowns, normalize,
        )

    @staticmethod
    def _normalize(breakdown: dict[str, float]) -> dict[str, float]:
        total = sum(breakdown.values())
        if not total:
            return breakdown
        return {k: v / total * 100 for k, v in breakdown.items()}

    def _set_hover(self, artist_label_pairs: list[tuple]):
        """Attaches (or replaces) a hover tooltip cursor over the given
        (artist, label) pairs. Must be called after the artists are added
        to the axes and before/around canvas.draw()."""
        if self._cursor is not None:
            self._cursor.remove()
            self._cursor = None
        if not artist_label_pairs:
            return
        artists = [a for a, _ in artist_label_pairs]
        label_by_id = {id(a): label for a, label in artist_label_pairs}
        self._cursor = mplcursors.cursor(artists, hover=True)

        @self._cursor.connect("add")
        def _on_add(sel):
            sel.annotation.set_text(label_by_id.get(id(sel.artist), ""))
            sel.annotation.get_bbox_patch().set(fc="#ffffe0", alpha=0.95)

    def _render_stacked_chart(self, methods, original_breakdowns, new_breakdowns, normalize: bool = False):
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        if normalize:
            original_breakdowns = {m: self._normalize(original_breakdowns[m]) for m in methods}
            new_breakdowns = {m: self._normalize(new_breakdowns[m]) for m in methods}

        direct_label = lcia.DIRECT_LABEL
        all_locations = set()
        for m in methods:
            all_locations.update(original_breakdowns[m].keys())
            all_locations.update(new_breakdowns[m].keys())
        geo_locations = sorted(loc for loc in all_locations if loc != direct_label)
        ordered_locations = geo_locations + ([direct_label] if direct_label in all_locations else [])

        color_map = {loc: COLORBLIND_PALETTE[i % len(COLORBLIND_PALETTE)] for i, loc in enumerate(geo_locations)}
        color_map[direct_label] = "#888888"

        width = 0.6 if len(methods) == 1 else 0.35
        hover_pairs = []
        for i, m in enumerate(methods):
            bottom_orig = 0.0
            bottom_new = 0.0
            for loc in ordered_locations:
                v_orig = original_breakdowns[m].get(loc, 0.0)
                if v_orig:
                    bars = ax.bar(i - width / 2, v_orig, width, bottom=bottom_orig, color=color_map[loc])
                    hover_pairs.append((bars[0], f"{loc}\nOriginal: {v_orig:.4g}"))
                    bottom_orig += v_orig
                v_new = new_breakdowns[m].get(loc, 0.0)
                if v_new:
                    bars = ax.bar(i + width / 2, v_new, width, bottom=bottom_new, color=color_map[loc])
                    hover_pairs.append((bars[0], f"{loc}\nRegionalized: {v_new:.4g}"))
                    bottom_new += v_new

        labels = [m[-1] if len(m) else str(m) for m in methods]
        ax.set_xticks(list(range(len(methods))))
        ax.set_xticklabels(labels, rotation=20, ha="right")
        ax.set_ylabel("% of total impact" if normalize else "Impact score")
        title = "Original (left bar) vs Regionalized (right bar), stacked by geography"
        if normalize:
            title += " — normalized to 100% per bar"
        ax.set_title(title)

        handles = [mpatches.Patch(color=color_map[loc], label=loc) for loc in ordered_locations]
        ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1), fontsize=8)
        self._set_hover(hover_pairs)
        self.canvas.draw()

    def _render_hotspot_chart(self, method: tuple, top_n: int = 12):
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        orig_rows = self._last_original_flows.get(method, [])
        new_rows = self._last_new_flows.get(method, [])
        orig_by_name = {name: val for name, _loc, val in orig_rows}
        new_by_name = {name: val for name, _loc, val in new_rows}
        loc_by_name = {name: loc for name, loc, _val in new_rows}
        loc_by_name.update({name: loc for name, loc, _val in orig_rows if name not in loc_by_name})

        all_names = sorted(
            set(orig_by_name) | set(new_by_name),
            key=lambda n: -max(abs(orig_by_name.get(n, 0.0)), abs(new_by_name.get(n, 0.0))),
        )[:top_n]

        if not all_names:
            ax.text(0.5, 0.5, "No flow data to show.", ha="center", va="center", transform=ax.transAxes)
            self.canvas.draw()
            return

        y = list(range(len(all_names)))
        orig_vals = [orig_by_name.get(n, 0.0) for n in all_names]
        new_vals = [new_by_name.get(n, 0.0) for n in all_names]

        height = 0.35
        hover_pairs = []
        bars_orig = ax.barh([i + height / 2 for i in y], orig_vals, height,
                             label="Original", color=COLORBLIND_PALETTE[0])
        bars_new = ax.barh([i - height / 2 for i in y], new_vals, height,
                            label="Regionalized", color=COLORBLIND_PALETTE[1])
        for bar, name, val in zip(bars_orig, all_names, orig_vals):
            hover_pairs.append((bar, f"{name}\n({loc_by_name.get(name, '?')})\nOriginal: {val:.4g}"))
        for bar, name, val in zip(bars_new, all_names, new_vals):
            hover_pairs.append((bar, f"{name}\n({loc_by_name.get(name, '?')})\nRegionalized: {val:.4g}"))

        ax.set_yticks(y)
        ax.set_yticklabels(all_names, fontsize=9)
        ax.invert_yaxis()
        ax.set_xlabel("Impact score")
        ax.set_title(f"Top contributing flows — {' / '.join(method)}")
        ax.legend()
        self._set_hover(hover_pairs)
        self.canvas.draw()

    def _render_sankey_chart(self, method: tuple):
        """
        A hand-drawn Sankey-style ribbon diagram showing original geography
        -> resolved geography per direct (depth-1) input flow, with ribbon
        width proportional to that flow's contribution to the regionalized
        activity's total impact for `method`.

        Scoped to depth-1 flows only, matching what the stacked-bar chart
        already shows directly: deeper (depth 2+) substitutions are folded
        into their parent's contribution rather than broken out separately
        here. Ribbon weight is matched to flows by name, which is a
        reasonable approximation for typical activities but can merge
        distinct same-named flows.
        """
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.axis("off")

        depth1_subs = [s for s in self.substitutions if s.depth == 1]
        if not depth1_subs:
            ax.text(0.5, 0.5, "No direct flows to show.", ha="center", va="center", transform=ax.transAxes)
            self.canvas.draw()
            return

        contrib_by_name: dict[str, float] = {}
        for name, _loc, val in self._last_new_flows.get(method, []):
            contrib_by_name[name] = contrib_by_name.get(name, 0.0) + abs(val)

        links = []
        for s in depth1_subs:
            chosen = s.chosen_location or s.original_location
            weight = contrib_by_name.get(s.flow_name, 0.0)
            links.append((s.original_location, chosen, weight, s.flow_name))

        total_weight = sum(w for *_r, w, _n in links) or 1.0
        min_weight = total_weight * 0.01
        links = [(o, c, max(w, min_weight), n) for o, c, w, n in links]

        left_totals: dict[str, float] = {}
        right_totals: dict[str, float] = {}
        for orig, chosen, w, _n in links:
            left_totals[orig] = left_totals.get(orig, 0.0) + w
            right_totals[chosen] = right_totals.get(chosen, 0.0) + w

        gap = 0.08 * sum(left_totals.values())

        def stack(totals):
            positions, y = {}, 0.0
            for loc in sorted(totals):
                positions[loc] = (y, y + totals[loc])
                y += totals[loc] + gap
            return positions, y

        left_pos, left_max = stack(left_totals)
        right_pos, right_max = stack(right_totals)
        y_max = max(left_max, right_max)

        all_locs = sorted(set(left_totals) | set(right_totals))
        color_map = {loc: COLORBLIND_PALETTE[i % len(COLORBLIND_PALETTE)] for i, loc in enumerate(all_locs)}

        node_width = 0.04
        x0, x1, mid = node_width, 1 - node_width, 0.5
        for loc, (y0, y1) in left_pos.items():
            ax.add_patch(mpatches.Rectangle((0, y0), node_width, y1 - y0, color=color_map[loc]))
            ax.text(-0.015, (y0 + y1) / 2, loc, ha="right", va="center", fontsize=9)
        for loc, (y0, y1) in right_pos.items():
            ax.add_patch(mpatches.Rectangle((x1, y0), node_width, y1 - y0, color=color_map[loc]))
            ax.text(1.015, (y0 + y1) / 2, loc, ha="left", va="center", fontsize=9)

        left_cursor = {loc: left_pos[loc][0] for loc in left_pos}
        right_cursor = {loc: right_pos[loc][0] for loc in right_pos}
        hover_pairs = []

        for orig, chosen, w, name in sorted(links, key=lambda link: -link[2]):
            y0a = left_cursor[orig]
            y1a = y0a + w
            left_cursor[orig] = y1a
            y0b = right_cursor[chosen]
            y1b = y0b + w
            right_cursor[chosen] = y1b

            verts = [
                (x0, y0a),
                (mid, y0a), (mid, y0b), (x1, y0b),
                (x1, y1b),
                (mid, y1b), (mid, y1a), (x0, y1a),
                (x0, y0a),
            ]
            codes = [
                Path.MOVETO,
                Path.CURVE4, Path.CURVE4, Path.CURVE4,
                Path.LINETO,
                Path.CURVE4, Path.CURVE4, Path.CURVE4,
                Path.CLOSEPOLY,
            ]
            patch = mpatches.PathPatch(Path(verts, codes), facecolor=color_map[orig], alpha=0.55, edgecolor="none")
            ax.add_patch(patch)
            hover_pairs.append((patch, f"{name}\n{orig} → {chosen}"))

        ax.set_xlim(-0.3, 1.3)
        ax.set_ylim(-0.02 * y_max, y_max * 1.02)
        ax.set_title(
            f"Geography substitution flow — {' / '.join(method)}\n"
            f"(ribbon width ∝ contribution to regionalized impact; direct-flow level only)"
        )
        self._set_hover(hover_pairs)
        self.canvas.draw()

    def _export_csv(self):
        if not self._last_methods:
            QMessageBox.warning(self, "Nothing to export", "Compute results first.")
            return
        default_name = f"{(self.root_activity.get('name') or 'results').replace(' ', '_')}_impact_breakdown.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Export results to CSV", default_name, "CSV files (*.csv)")
        if not path:
            return
        try:
            export.export_results_csv(
                self._last_methods, self._last_original_breakdowns,
                self._last_new_breakdowns, path,
            )
            QMessageBox.information(self, "Exported", f"Saved to {path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export failed", str(exc))

    def _render_table(self, methods, original_scores, new_scores):
        self.summary_table.setRowCount(len(methods))
        for row, m in enumerate(methods):
            orig = original_scores[m]
            new = new_scores[m]
            pct = ((new - orig) / orig * 100) if orig else float("nan")
            self.summary_table.setItem(row, 0, QTableWidgetItem(" / ".join(m)))
            self.summary_table.setItem(row, 1, QTableWidgetItem(f"{orig:.6g}"))
            self.summary_table.setItem(row, 2, QTableWidgetItem(f"{new:.6g}"))
            self.summary_table.setItem(row, 3, QTableWidgetItem(f"{pct:+.2f}%"))
