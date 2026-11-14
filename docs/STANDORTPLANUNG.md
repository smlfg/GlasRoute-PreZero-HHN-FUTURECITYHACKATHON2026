# Standortplanung — What-if (Annahmen, keine Fakten)

Diese Seite dokumentiert die Annahmen hinter dem Tab **„10. Standortplanung“** in der
Analyse-Ansicht von `ui_<date>.html`.

## Was das Feature tut

Es schlägt bis zu fünf neue Glascontainer-Standorte vor und simuliert, wie sich die
Nachfrage in den ersten 12 Wochen auf die neuen Standorte und ihre Nachbarn verteilen
könnte.

## Simulationsbasis

- **Koordinaten sind simuliert.** Die aktuellen Standorte stammen aus OpenStreetMap
  (`source=osm_assigned`, `confidence=simulated_mapping`); die Zuordnung der anonymen
  PreZero-IDs zu diesen Punkten ist eine Heuristik. Die Vorschläge für neue Standorte
  bauen auf diesen simulierten Koordinaten auf.
- **Keine Aussage über reale Standorte.** Das Feature zeigt, welche Gebiete nach den
  vorliegenden Füllstandsdaten unterversorgt erscheinen könnten. Es ersetzt keine
  Standortuntersuchung vor Ort.

## Konfigurierbare Annahmen (`prezero_config.json`)

| Key | Default | Bedeutung |
|---|---|---|
| `location_planning_radius_m` | 500 m | Radius, innerhalb dessen ein neuer Standort Nachfrage von bestehenden Containern übernimmt |
| `location_planning_adoption_weeks` | 8 Wochen | Zeit, über die die Annahme des neuen Standorts von 0 % auf ~100 % steigt |
| `location_planning_logistic_steepness` | 1,0 | Steilheit der logistischen Adoptionskurve |

Diese Werte sind **Annahmen**, keine empirisch gemessenen Größen. Sie können über die
Konfigurationsdatei angepasst werden, ohne Code zu ändern.

## Methodik

1. **Raster über Heilbronn-BBox:** Das Modul legt ein regelmäßiges 40×40-Raster über
   den dokumentierten BBox `HEILBRONN_BBOX` (siehe `src/prezero/locations.py`).
2. **Zellen-Scoring:** Jede Zelle bekommt einen Score aus zwei Komponenten:
   - **Nachfrage-Score:** Summe der täglichen Füllraten (`avg_daily_increase`) der
     Container im Radius, gewichtet mit deren Übervoll-Häufigkeit und inverser Entfernung.
   - **Abstands-Score:** Entfernung zum nächsten bestehenden Standort, normiert auf den
     Radius. Zellen mit etwas Abstand zu bestehenden Standorten werden bevorzugt.
3. **Top-5-Auswahl:** Die besten Zellen werden gewählt, solange sie mindestens
   300 m voneinander entfernt liegen.
4. **Nachfrage-Umverteilung:** Container im Radius geben anteilig an den neuen Standort
   ab. Der Anteil ist entfernungsgewichtet; die Summe der Anteile pro Container wird auf
   100 % gekappt.
5. **Adoptionskurve:** Die Übernahme folgt einer logistischen Kurve
   `1 / (1 + exp(-k * (w - w0)))` mit `w0 = adoption_weeks / 2`.
6. **Timeline Woche 0–12:**
   - Neuer Container füllt sich mit der übernommenen Nachfrage × Adoptionsanteil.
   - Nachbarn sinken entsprechend.
   - Übervoll-Ereignisse (>= 110 %) und eine grobe NN-Tour-km-Schätzung werden vorher
     und nachher verglichen.

## Validierung

- **Nachfrageerhaltung:** Die Summe der täglichen Nachfrage bleibt konstant; sie wird
  nur umverteilt.
- **Monotonie:** Der Adoptionsanteil steigt von Woche zu Woche nie.
- **Begrenzung:** Füllstände werden auf 0–110 % gekappt.

## Nicht abgebildet

- Echte Geografie, Straßennetz, Genehmigungen, Lärm, Zugänglichkeit.
- Materialspezifische Container-Größen.
- Dynamische Anpassung der Leerungstouren; die Tour-km ist eine grobe
  Nearest-Neighbor-Schätzung über kritische Standorte.
