// Standalone operational price, before comparisons of service quality.
function collectionCost(s, a, days) {
  const vehicle = s.vehicle_days * a.vehicle_day;
  const crewHours = s.hours * a.crew;
  const labor = crewHours * a.wage;
  const drive = s.km * a.km_cost;
  const total = vehicle + labor + drive;
  const daily = total / days;
  const tonnes = s.inventory.collected_kg / 1000;
  return {vehicle, crewHours, labor, drive, total, daily, annual: daily * a.annual_days,
          perTonne: tonnes ? total / tonnes : null};
}

// Shared by the static dashboard and the reproducible pitch calculation (Node).
function economics(r, p, threshold = r.threshold_pct) {
  const opt = +threshold === r.threshold_pct ? r.optimized : r.threshold_options[threshold];
  function scenario(s, a) {
    return collectionCost(s, a, r.calendar_days ?? r.operating_days);
  }
  const h = scenario(r.historical, p), o = scenario(opt, p);
  const difference = h.total-o.total;
  const sensitivity = {};
  for (const k of Object.keys(p)) {
    sensitivity[k] = [0.8,1.2].map(factor => {
      const a = {...p, [k]: p[k]*factor};
      return scenario(r.historical,a).annual - scenario(opt,a).annual;
    });
  }
  return {historical:h, optimized:o, difference, percent:h.total ? 100*difference/h.total : null,
    variableDifference:h.labor+h.drive-o.labor-o.drive, sensitivity,
    // Break-even incremental value of extra glass recovered, excluding any resale revenue.
    breakEvenPerExtraTonne: opt.inventory.collected_kg > r.historical.inventory.collected_kg ?
      -difference / ((opt.inventory.collected_kg-r.historical.inventory.collected_kg)/1000) : null};
}
if (typeof module !== 'undefined') module.exports = economics;
if (typeof module !== 'undefined') module.exports.collectionCost = collectionCost;
