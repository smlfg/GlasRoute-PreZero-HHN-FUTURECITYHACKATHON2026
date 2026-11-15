"""JavaScript of the cadence UI (static, offline, no framework).

The script is embedded into the generated HTML. It only *reads* the
precomputed payload — there is no live computation in the browser.
"""

from __future__ import annotations

JS = r"""
(function () {
  "use strict";

  function readPayload(id) {
    var node = document.getElementById(id);
    if (!node) { return null; }
    try {
      return JSON.parse(node.textContent);
    } catch (err) {
      return null;
    }
  }

  var detailPayload = readPayload("cadence-detail-payload") || [];

  function de(value, digits) {
    if (value === null || value === undefined || value === "") { return "-"; }
    var number = Number(value);
    if (!isFinite(number)) { return String(value); }
    return number.toLocaleString("de-DE", {
      minimumFractionDigits: digits === undefined ? 1 : digits,
      maximumFractionDigits: digits === undefined ? 1 : digits
    });
  }

  function esc(value) {
    return String(value === null || value === undefined ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function dateDe(value) {
    if (!value) { return "–"; }
    var parts = String(value).split("-");
    if (parts.length !== 3) { return String(value); }
    return parts[2] + "." + parts[1] + "." + parts[0];
  }

  // --- filter the container list ---------------------------------------------------------

  var filterButtons = document.querySelectorAll(".cadence-filter-btn");
  var tableBody = document.getElementById("cadence-table-body");

  var activeFilter = "all";
  var searchBox = document.getElementById("cadence-search");

  function applyFilter(filter) {
    if (!tableBody) { return; }
    activeFilter = filter;
    var needle = searchBox ? searchBox.value.trim().toLowerCase() : "";
    var rows = tableBody.querySelectorAll("tr.cadence-row");
    var shown = 0;
    rows.forEach(function (row) {
      var status = row.getAttribute("data-status");
      var visible = (filter === "all" || status === filter) &&
        (!needle || row.textContent.toLowerCase().indexOf(needle) !== -1 ||
         (row.getAttribute("data-location") || "").toLowerCase().indexOf(needle) !== -1);
      row.style.display = visible ? "" : "none";
      if (visible) { shown += 1; }
    });
    var countNode = document.getElementById("cadence-filter-count");
    if (countNode) { countNode.textContent = shown + " von " + rows.length + " Containern"; }
  }

  if (searchBox) {
    searchBox.addEventListener("input", function () { applyFilter(activeFilter); });
  }

  filterButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      filterButtons.forEach(function (other) { other.classList.remove("active"); });
      btn.classList.add("active");
      applyFilter(btn.getAttribute("data-filter"));
    });
  });

  // --- approvals (Disponentin) ----------------------------------------------------------

  var statusNode = document.getElementById("cadence-approval-status");
  var approved = {};

  function setStatus(text, done) {
    if (!statusNode) { return; }
    statusNode.textContent = text;
    statusNode.classList.toggle("pending", !done);
    statusNode.classList.toggle("ok", !!done);
  }

  function markApproved(btn) {
    btn.classList.add("approved");
    btn.textContent = "Freigegeben";
    btn.disabled = true;
  }

  document.addEventListener("click", function (evt) {
    var btn = evt.target && evt.target.closest ? evt.target.closest(".cadence-approve-btn") : null;
    if (!btn) { return; }
    var key = btn.getAttribute("data-location") + "|" + btn.getAttribute("data-material");
    approved[key] = true;
    markApproved(btn);
    setStatus("Status: " + Object.keys(approved).length + " Taktänderung(en) freigegeben", true);
  });

  var approveAll = document.getElementById("cadence-approve-all-btn");
  if (approveAll) {
    approveAll.addEventListener("click", function () {
      var rows = document.querySelectorAll("tr.cadence-row");
      var count = 0;
      rows.forEach(function (row) {
        if (row.style.display === "none") { return; }
        var btn = row.querySelector(".cadence-approve-btn");
        if (btn && !btn.disabled) {
          btn.classList.add("approved");
          btn.textContent = "Freigegeben";
          btn.disabled = true;
          approved[btn.getAttribute("data-location") + "|" + btn.getAttribute("data-material")] = true;
          count += 1;
        }
      });
      setStatus("Status: " + count + " Taktänderung(en) freigegeben", true);
    });
  }

  // --- container detail ------------------------------------------------------------------

  var select = document.getElementById("cadence-detail-select");
  var body = document.getElementById("cadence-detail-body");

  function findRow(location, material) {
    for (var i = 0; i < detailPayload.length; i += 1) {
      if (detailPayload[i].location_id === location &&
          detailPayload[i].material === material) {
        return detailPayload[i];
      }
    }
    return null;
  }

  function sawtoothSvg(row) {
    var history = row.history || [];
    if (!history.length) {
      return '<div class="empty-note">Keine Messungen für diesen Container.</div>';
    }
    var width = 900, height = 260;
    var padLeft = 46, padRight = 16, padTop = 16, padBottom = 34;
    var plotW = width - padLeft - padRight;
    var plotH = height - padTop - padBottom;
    var first = new Date(history[0][0] + "T00:00:00");
    var last = new Date(history[history.length - 1][0] + "T00:00:00");
    var spanDays = Math.max(1, Math.round((last - first) / 86400000));

    function xOf(ts) {
      var t = new Date(ts + "T00:00:00");
      return padLeft + ((t - first) / 86400000) / spanDays * plotW;
    }
    function yOf(level) {
      var clamped = Math.max(0, Math.min(110, Number(level) || 0));
      return padTop + (1 - clamped / 110) * plotH;
    }

    var parts = [];
    var dots = [];
    var grid = [];
    [0, 50, 80, 110].forEach(function (level) {
      var y = yOf(level);
      grid.push('<line x1="' + padLeft + '" y1="' + y.toFixed(1) + '" x2="' +
        (width - padRight) + '" y2="' + y.toFixed(1) + '" class="saw-grid"/>');
      grid.push('<text x="' + (padLeft - 6) + '" y="' + (y + 4).toFixed(1) +
        '" class="saw-axis" text-anchor="end">' + de(level, 0) + " %</text>");
    });

    for (var i = 0; i < history.length; i += 1) {
      var ts = history[i][0];
      var level = history[i][1];
      var x = xOf(ts);
      var y = yOf(level);
      if (i === 0) {
        parts.push("M " + x.toFixed(1) + " " + y.toFixed(1));
        parts.push("L " + x.toFixed(1) + " " + (padTop + plotH).toFixed(1));
      } else {
        var px = xOf(history[i - 1][0]);
        var py = yOf(history[i - 1][1]);
        parts.push("M " + px.toFixed(1) + " " + (padTop + plotH).toFixed(1));
        parts.push("L " + px.toFixed(1) + " " + py.toFixed(1));
        parts.push("L " + x.toFixed(1) + " " + y.toFixed(1));
      }
      dots.push('<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) +
        '" r="3" class="saw-dot"/>');
    }

    function axisDate(ts) {
      var p = String(ts).split("-");
      return p.length === 3 ? p[2] + "." + p[1] + "." + p[0] : String(ts);
    }

    return '<svg class="saw-chart" viewBox="0 0 ' + width + " " + height +
      '" role="img" aria-label="Füllstandverlauf: Anstieg zwischen den Leerungen, Sprung auf 0 % bei jeder Leerung">' +
      grid.join("") +
      '<path class="saw-path" d="' + parts.join(" ") + '"/>' + dots.join("") +
      '<text x="' + padLeft + '" y="' + (height - 10) + '" class="saw-axis">' +
      esc(axisDate(history[0][0])) + "</text>" +
      '<text x="' + (width - padRight) + '" y="' + (height - 10) +
      '" class="saw-axis" text-anchor="end">' +
      esc(axisDate(history[history.length - 1][0])) + "</text>" +
      "</svg>";
  }

  function renderDetail(row) {
    if (!row) {
      body.innerHTML = '<p class="muted">Container wählen, um den Verlauf zu sehen.</p>';
      return;
    }
    var current = row.current_cadence_days;
    var proposed = row.proposed_cadence_days;
    var currentTxt = current === null || current === undefined ? "–" : de(current, 0) + " Tage";
    var proposedTxt = de(proposed, 0) + " Tage";

    body.innerHTML =
      '<div class="cadence-detail-title">' +
        "<h3>" + esc(row.site_title) + "</h3>" +
        '<span class="status-pill status-' + esc(row.status) + '">' +
        esc(row.status_label) + "</span>" +
      "</div>" +
      '<p class="muted">' + esc(row.area_label) + " · " + esc(row.material_label) +
        " · Füllrate " + de(row.rate_pct_per_day, 1) + " %/Tag" +
        " · " + de(row.emptyings_status_quo, 0) + " Leerungen im Status quo" +
        " · " + (row.skip_14d > 0 ? "im Mentor-Takt übersprungen" : "im Mentor-Takt nicht übersprungen") + "</p>" +
      '<p class="cadence-explain">' + esc(row.explanation) + "</p>" +
      '<div class="kpi-grid">' +
        '<div class="card"><div class="label">Takt heute</div><div class="value">' +
          currentTxt + '</div></div>' +
        '<div class="card"><div class="label">Takt neu</div><div class="value">' +
          proposedTxt + '</div></div>' +
        '<div class="card"><div class="label">Ø Füllstand (Status quo)</div><div class="value">' +
          de(row.avg_fill_status_quo_pct, 1) + " %</div></div>" +
        '<div class="card"><div class="label">Ø Füllstand (Mentor)</div><div class="value">' +
          de(row.avg_fill_mentor_pct, 1) + " %</div></div>" +
      "</div>" +
      sawtoothSvg(row);
  }

  function populateSelect() {
    if (!select) { return; }
    var options = [];
    detailPayload.forEach(function (row, index) {
      options.push('<option value="' + index + '">' + esc(row.site_title) +
        " · " + esc(row.status_label) + "</option>");
    });
    select.innerHTML = options.join("");
  }

  if (select) {
    populateSelect();
    select.addEventListener("change", function () {
      var row = detailPayload[Number(select.value)];
      renderDetail(row);
    });
    if (detailPayload.length) {
      renderDetail(detailPayload[0]);
    }
  }

  // --- link from the list to the detail --------------------------------------------------

  document.addEventListener("click", function (evt) {
    var link = evt.target && evt.target.closest ? evt.target.closest(".cadence-detail-link") : null;
    if (!link) { return; }
    evt.preventDefault();
    var location = link.getAttribute("data-location");
    var material = link.getAttribute("data-material");
    var row = findRow(location, material);
    if (!row || !select) { return; }
    for (var i = 0; i < detailPayload.length; i += 1) {
      if (detailPayload[i].location_id === location &&
          detailPayload[i].material === material) {
        select.value = String(i);
        break;
      }
    }
    renderDetail(row);
    if (window.activateTab) { window.activateTab("view-cadence-detail"); }
    var target = document.getElementById("view-cadence-detail");
    if (target && target.scrollIntoView) { target.scrollIntoView({ block: "start" }); }
  });
})();
"""
