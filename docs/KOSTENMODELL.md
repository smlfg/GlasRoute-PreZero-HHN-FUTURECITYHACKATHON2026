# Kostenmodell & Jahressimulation: Status quo vs. Timer-Modell

Dieses Dokument vergleicht den **Status quo** (die realen Leerungstage aus den 11.701 Messungen, nachgespielt gegen ein festes Weltmodell) mit der **Walk-Forward-Simulation** des Timer-Modells über denselben Zeitraum (**17.10.2025 bis 30.09.2026**, 349 Kalendertage). Generiert von `scripts/simulate_daily.py`; Rechenmodell: [`docs/MODEL_SPEC.md`](MODEL_SPEC.md).

Die Rohdaten liegen als CSVs vor:
- [`data/outputs/historical_daily.csv`](../data/outputs/historical_daily.csv) (Status quo, `source=real`)
- [`data/outputs/optimized_daily.csv`](../data/outputs/optimized_daily.csv) (Timer-Modell, `source=simulated`)

## 1. Massenbilanz (eine Welt, zwei Politiken)

| Posten | Status quo | Timer-Modell |
|---|---:|---:|
| Produziert (Welt, Σ r_c × aktive Tage) | 7.613,9 t | 7.613,9 t |
| Gesammelt im Fenster (`tonnage_t`) | 6.943,5 t | 7.157,5 t |
| Endbestand am 30.09.2026 (steht noch im Container) | 670,4 t | 456,4 t |
| **Gesammelt + Endbestand** | **7.613,9 t** | **7.613,9 t** |

Beide Seiten gehen auf dieselbe produzierte Menge auf (Test: `tests/test_mass_balance.py`). Die im Fenster gesammelte Tonnage unterscheidet sich nur um den Endbestand: Der Status quo lässt am Stichtag mehr Glas im Container stehen. Routing erzeugt kein Glas.

## 2. Jahres-Kennzahlen im Vergleich

| Kennzahl | Status quo | Timer-Modell | Delta |
|---|---|---|---|
| Ø Füllstand bei Leerung (wahrer Füllstand, ungekappt) | **67,0 %** | **65,3 %** | -1,7 pp |
| Leerungen | **10.363** | **10.954** | +5,7 % |
| Überfüllte Leerungen (≥ 110 % bei Leerung) | **1.196** | **214** | -82,1 % |
| Überlauf-Containertage (≥ 110 %, ungeleert) | **19.047** | **1.484** | -92,2 % |
| Fahrstrecke (est. km) | **19.007,6** | **25.684,6** | +35,1 % |
| Fahrzeug-Einsatztage | **317** | **339** | +6,9 % |
| Fahrerstunden | **1.593,3 h** | **2.026,2 h** | +27,2 % |

Ehrlich gelesen: Das Timer-Modell senkt Überläufe stark, leert aber **nicht voller** als heute. Die Walk-Forward-Schätzung `mean(level/Δt)` liegt im Mittel über der wahren Rate, darum leert die Regel zu früh. Mehr Strecke und Stunden sind der Preis für fast keine Überläufe.

## 3. Methodik & Regeln

1. **Welt (Wahrheit):** Jeder Container hat eine feste Glasrate `r_c = Σ level_i / Σ Δt_i` (Intervalle ab der 2. Messung, Quotient der Summen; unter 2 Messungen: Median des Materials). Sie erzeugt das Glas in **beiden** Szenarien, ab dem Tag nach der ersten Messung, Startbestand 0 %.
2. **Systemgrenze:** Die erste Messung je Container ist der Start des Fensters (Glas davor, 775,7 t, zählt auf keiner Seite). Darum zählt der Status quo 11.701 − 1.338 = 10.363 Leerungen. Endbestand am letzten Tag wird ausgewiesen, nicht verschwiegen.
3. **Status quo:** An jedem realen Leerungstag wird der Modell-Füllstand gesammelt und auf exakt 0 % gesetzt. Damit reproduziert der Status quo die gemessene In-Fenster-Masse (Messungen 2…n) exakt.
4. **Timer-Modell, strikter Walk-Forward ohne Look-Ahead:** Die Regel kennt nur Raten aus Messungen mit $\text{Datum} < d$ und den daraus geschätzten Füllstand seit der letzten Leerung. Eingeplant wird bei Schätzung $\ge 80\,\%$ oder wenn bis zum nächsten Betriebstag $\ge 110\,\%$ drohen. Der LKW nimmt den **wahren** Füllstand mit; Reset auf exakt 0 % (kein Zufallsrest mehr).
5. **Keine Kappung:** Der Füllstand wird intern nicht bei 110 % gekappt (übergelaufenes Glas steht neben dem Container und wird mitgenommen). 110 % zählt nur als Überlauf-Ereignis. Ø Füllstand bei Leerung ist daher **ungekappt** und kann über 100 % liegen.
6. **Betriebsrestriktionen (OperationalConfig):**
   Beide Modelle unterliegen exakt denselben Annahmen aus `prezero_config.json`:
   - LKW-Nutzlast: 11.000 kg, Ladevolumen: 26,0 m³, Dichte: 400 kg/m³, Behälter: 2,5 m³
   - Max. Schichtdauer: 8,0 h, Rüstzeit: 2,0 min, Hubzeit: 3,0 min/Behälter, Entladezeit: 20,0 min
   - Umwegfaktor: 1,35 auf Haversine, Geschwindigkeit: 25 km/h
   - Feste Depots: Betriebshof (49.1427, 9.2109), Entladestelle (49.1780, 9.2085)
7. **Geodaten-Transparenz:**
   Routing auf simulierten Zuordnungen (`source=osm_assigned`, `confidence=simulated_mapping`).
