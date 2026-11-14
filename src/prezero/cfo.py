"""Self-contained analysis tab, driven by the paired replay (independent of demo date)."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def panel():
    report = ROOT / "data/replay_comparison.json"
    config = ROOT / "prezero_config.json"
    if not report.exists() or not config.exists():
        return "<p>Kein Replay verfügbar. Bitte scripts/replay.py ausführen.</p>"
    r = json.loads(report.read_text())
    params = json.loads(config.read_text())["economics"]
    labels = dict(
        vehicle_day="Fahrzeug €/Einsatztag",
        crew="Personen/Fahrzeug",
        wage="€/Personenstunde",
        km_cost="Variable €/km",
        annual_days="Betriebstage/Jahr",
    )
    controls = []
    for k, label in labels.items():
        if k == "crew":
            choices = sorted({2, 3, params[k]})
            control = (
                '<select id="cost-crew">'
                + "".join(
                    f"<option {'selected' if v == params[k] else ''}>{v}</option>"
                    for v in choices
                )
                + "</select>"
            )
        else:
            control = f'<input id="cost-{k}" type="number" value="{float(params[k])}" min="{1 if k == "annual_days" else 0}" step="any">'
        controls.append(f"<label>{label} {control}</label>")
    choices = sorted({r["threshold_pct"], *map(float, r["threshold_options"])})
    options = "".join(
        f"<option {'selected' if v == r['threshold_pct'] else ''}>{v:g}</option>"
        for v in choices
    )
    payload = json.dumps([r, params, labels], ensure_ascii=False).replace(
        "<", "\\u003c"
    )
    return (
        f"""<h2>Kosten &amp; Nutzen</h2><h3>Szenario unter Annahmen</h3>
    <p>Gesamtzeitraum {r["start"]} bis {r["end"]} · {r["operating_days"]} gemeinsame Betriebstage.
    Orte simuliert, Besuchstage aus Daten. Rekonstruierte Touren, keine GPS-Spuren.</p>
    <p>Gemessen: Ø {r["observed"]["mean_fill_pct"]:.1f} % bei {r["observed"]["emptyings"]} Leerungen;
    {r["observed"]["overfull"]} Übervoll-Beobachtungen. Timer-Fehler im Walk-forward: {r["walk_forward"]["model"]} Prozentpunkte.
    Die Tabelle vergleicht zwei Simulationen mit identischem Glaszufluss.</p>
    <fieldset id="cost-controls"><legend>Annahmen, keine PreZero-Kostendaten</legend>{" ".join(controls)}
    <label>Leerungsschwelle (%) <select id="cost-threshold">{options}</select></label></fieldset>
    <p id="cost-headline" aria-live="polite"></p><div id="cost-results"></div>
    <p>Fahrzeugtag ohne Lohn und Kilometerkosten. Fixkosten einer eigenen Flotte sinken dadurch nicht automatisch.
    Keine Erlöse, Software-, Umstellungs- oder Überlaufkosten eingerechnet. Jahreswerte = Periodenwert / Betriebstage × angenommene Jahrestage.</p>
    <script>{(Path(__file__).with_name("economics.js")).read_text()}
    (()=>{{const [r, defaults, labels]={payload};"""
        + """
    const $=id=>document.getElementById('cost-'+id);
    const fmt=n=>n==null?'–':n.toLocaleString('de-DE',{maximumFractionDigits:2});
    function render(){
      const p=Object.fromEntries(Object.keys(defaults).map(k=>[k,Number($(k).value)]));
      if(![...$('controls').querySelectorAll('input')].every(e=>e.value!=='' && e.validity.valid)){
        $('headline').textContent='Bitte gültige Annahmen eingeben.';$('results').textContent='';return;}
      const t=+$('threshold').value, o=t===r.threshold_pct?r.optimized:r.threshold_options[t], h=r.historical;
      const c=economics(r,p,t), rows=[];
      function row(label,a,b){rows.push('<tr><th>'+label+'</th><td>'+fmt(a)+'</td><td>'+fmt(b)+'</td><td>'+fmt(a==null||b==null?null:b-a)+'</td></tr>')}
      for(const [k,name] of Object.entries({mean_fill_pct:'Füllung bei Leerung (%)',emptyings:'Leerungen',km:'Kilometer',rounds:'Runden',
        vehicle_days:'Fahrzeugtage',hours:'Fahrzeugstunden',peak:'Spitze: Fahrzeuge pro Tag',overflow_bin_days:'Übervolle Behältertage',due_backlog:'Fällige Behälter am Ende'}))row(name,h[k],o[k]);
      for(const [k,name] of Object.entries({collected_kg:'Gesammelt',ending_kg:'Restbestand',spill_kg:'Überlauf'}))row(name+' (t)',h.inventory[k]/1000,o.inventory[k]/1000);
      for(const [k,name] of Object.entries({crewHours:'Personenstunden',vehicle:'Fahrzeuge (€)',labor:'Personal (€)',drive:'Fahrleistung (€)',total:'Periode (€)',daily:'€/Betriebstag',annual:'€/Jahr (hochgerechnet)',perTonne:'€/gesammelte Tonne'}))row(name,c.historical[k],c.optimized[k]);
      $('headline').textContent='Modellierte '+(c.difference<0?'Mehrkosten: ':'Minderkosten: ')+fmt(Math.abs(c.difference)/r.operating_days)+' €/Betriebstag ('+fmt(Math.abs(c.percent))+' %).';
      $('results').innerHTML='<table><thead><tr><th>Kennzahl</th><th>Historische Besuchstage</th><th>GlasRoute</th><th>Δ GlasRoute − Historie</th></tr></thead><tbody>'+rows.join('')+'</tbody></table>'+
        '<p>Kostendifferenz (Historie − GlasRoute): '+fmt(c.difference)+' €; davon Personal und Kilometer: '+fmt(c.variableDifference)+' €. Break-even je zusätzlich gesammelter Tonne: '+fmt(c.breakEvenPerExtraTonne)+' €/t.</p>'+
        '<h3>Sensitivität: Jahresdifferenz (€), jeweils ein Parameter</h3><table><tr><th>Annahme</th><th>−20 %</th><th>+20 %</th></tr>'+
        Object.entries(c.sensitivity).map(([k,v])=>'<tr><th>'+labels[k]+'</th><td>'+fmt(v[0])+'</td><td>'+fmt(v[1])+'</td></tr>').join('')+'</table><p>Crew-Sensitivität in rechnerischen Vollzeitäquivalenten; für den Einsatz oben zwei oder drei Personen wählen.</p>';
    }
    $('controls').addEventListener('input',render);render();})();</script>"""
    )
