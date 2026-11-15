"""CSS of the cadence UI (embedded into the generated HTML).

Contrast: every text/background pair below is >= 4.5:1.
Labels: no label is smaller than 12 px.
"""

from __future__ import annotations

CSS = r"""
:root {
  --cad-red-bg: #fee2e2;
  --cad-red-fg: #991b1b;
  --cad-yellow-bg: #fef3c7;
  --cad-yellow-fg: #92400e;
  --cad-ok-bg: #dcfce7;
  --cad-ok-fg: #166534;
  --cad-border: #cbd5e1;
  --cad-muted: #475569;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.cadence-view .muted,
.cadence-detail-view .muted,
.cadence-week-view .muted,
.cadence-scenarios-view .muted {
  font-size: 13px;
  color: var(--muted);
}

.cadence-kpi-grid > .card {
  flex: 1 1 180px;
}

.cadence-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 14px 0 10px;
}

.cadence-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.cadence-filter-btn {
  border: 1px solid var(--cad-border);
  background: #ffffff;
  color: var(--text);
  padding: 7px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
  font-size: 13px;
}

.cadence-filter-btn.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #ffffff;
}

.cadence-filter-btn:focus-visible,
.cadence-approve-btn:focus-visible,
.cadence-detail-link:focus-visible,
#cadence-detail-select:focus-visible,
.cadence-route-extra summary:focus-visible {
  outline: 3px solid #1d4ed8;
  outline-offset: 2px;
}

.cadence-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.table-scroll {
  overflow-x: auto;
  border: 1px solid var(--cad-border);
  border-radius: 8px;
  background: #ffffff;
}

.cadence-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  min-width: 760px;
}

.cadence-table th,
.cadence-table td {
  padding: 8px 10px;
  text-align: left;
  border-bottom: 1px solid #e2e8f0;
  vertical-align: top;
}

.cadence-table thead th {
  background: #f1f5f9;
  color: #334155;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
  position: sticky;
  top: 0;
}

.cadence-table td.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.cadence-table tbody tr:nth-child(even) {
  background: #f8fafc;
}

.cadence-row.status-red {
  box-shadow: inset 4px 0 0 #b91c1c;
}

.cadence-row.status-yellow {
  box-shadow: inset 4px 0 0 #b45309;
}

.cadence-site {
  min-width: 190px;
}

.cadence-detail-link {
  color: #1d4ed8;
  text-decoration: underline;
  font-weight: 600;
}

.cadence-id {
  display: block;
  font-size: 12px;
  color: var(--cad-muted);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.cadence-note {
  display: block;
  font-size: 12px;
  color: #92400e;
  font-weight: 600;
}

.status-pill {
  display: inline-block;
  padding: 2px 9px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.status-pill.status-red {
  background: var(--cad-red-bg);
  color: var(--cad-red-fg);
}

.status-pill.status-yellow {
  background: var(--cad-yellow-bg);
  color: var(--cad-yellow-fg);
}

.status-pill.status-ok {
  background: var(--cad-ok-bg);
  color: var(--cad-ok-fg);
}

.cadence-approve-btn {
  border: 1px solid #1d4ed8;
  background: #ffffff;
  color: #1d4ed8;
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
}

.cadence-approve-btn:hover {
  background: var(--accent-soft);
}

.cadence-approve-btn.approved {
  border-color: #15803d;
  color: #15803d;
  background: var(--cad-ok-bg);
}

.cadence-detail-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.cadence-detail-toolbar label {
  font-size: 13px;
  font-weight: 600;
}

#cadence-detail-select {
  font-size: 13px;
  padding: 6px 8px;
  border: 1px solid var(--cad-border);
  border-radius: 6px;
  background: #ffffff;
  color: var(--text);
  max-width: 100%;
}

.cadence-detail-body {
  border: 1px solid var(--cad-border);
  border-radius: 8px;
  background: #ffffff;
  padding: 16px;
}

.cadence-detail-title {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 4px;
}

.cadence-detail-title h3 {
  margin: 0;
  font-size: 17px;
}

.cadence-explain {
  margin: 12px 0 16px;
  padding: 11px 14px;
  border-left: 4px solid var(--accent);
  background: var(--accent-soft);
  font-size: 14px;
  color: var(--text);
}

.saw-chart {
  width: 100%;
  height: auto;
  display: block;
  max-width: 100%;
}

.saw-path {
  fill: none;
  stroke: #1d4ed8;
  stroke-width: 2;
  stroke-linejoin: round;
}

.saw-dot {
  fill: #b91c1c;
  stroke: #ffffff;
  stroke-width: 1.5;
}

.saw-grid {
  stroke: #e2e8f0;
  stroke-width: 1;
}

.saw-axis {
  font-size: 12px;
  fill: #475569;
}

.empty-note {
  font-size: 13px;
  color: var(--cad-muted);
  padding: 18px;
}

.week-group {
  margin-bottom: 18px;
}

.week-group h3 {
  font-size: 15px;
  margin: 0 0 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.week-table {
  min-width: 620px;
}

.cadence-route-extra {
  margin-top: 18px;
  border: 1px solid var(--cad-border);
  border-radius: 8px;
  background: #ffffff;
  padding: 12px 16px;
}

.cadence-route-extra summary {
  cursor: pointer;
  font-weight: 700;
  font-size: 14px;
  color: var(--text);
}

.cadence-route-extra[open] summary {
  margin-bottom: 12px;
}

.scenario-block {
  margin-bottom: 20px;
}

.scenario-block h3 {
  font-size: 15px;
  margin: 0 0 8px;
}

.scenario-table {
  min-width: 720px;
}

.scenario-table tr.scenario-best td {
  background: var(--cad-ok-bg);
}

@media (max-width: 800px) {
  .cadence-toolbar {
    flex-direction: column;
    align-items: flex-start;
  }

  .cadence-table {
    font-size: 13px;
  }
}
"""
