# Kostenmodell & Jahressimulation: Status quo vs. Timer-Modell

Dieses Dokument vergleicht die **historische Sammelleistung** (rekonstruiert aus den 11.701 realen Mess- und Leerungsereignissen) 1:1 mit der **bedarfsorientierten Jahressimulation** des PreZero-Timer-Modells über denselben Zeitraum (**17.10.2025 bis 30.09.2026**, 349 Kalendertage).

Die Rohdaten liegen als CSVs vor:
- [`data/outputs/historical_daily.csv`](../data/outputs/historical_daily.csv) (Status quo, `source=real`)
- [`data/outputs/optimized_daily.csv`](../data/outputs/optimized_daily.csv) (Timer-Modell, `source=simulated`)

## 1. Jahres-Kennzahlen im 1:1-Vergleich

| Kennzahl | Status quo (Historisch) | Timer-Modell (Optimiert) | Delta / Effekt |
|---|---|---|---|
| **Ø Füllstand bei Leerung** | **66.0 %** | **83.5 %** | **+17.5 pp** höhere Auslastung |
| **Gesamtzahl Leerungen** | **11,701** | **11,321** | **-3.2 %** Leerungsaufwand |
| **Überfüllungen bei Leerung (≥ 110 %)** | **1,192** | **0** | **-100.0 %** Überlauf-Risiko |
| **Tage mit unbedienten Überläufen** | *(nicht messbar)* | **0** | Nahezu 0 Überlauf-Tage |
| **Gesammelte Tonnage** | **7719.2 t** | **9451.0 t** | Massenerhaltung (aktive Pilotphase) |
| **Fahrstrecke gesamt (est. km)** | **20,538.5 km** | **28,497.8 km** | Kapazitäts- und schichtbeschränkt |
| **Fahrzeug-Einsatztage (vehicle-days)** | **345** | **381** | Glättung der Tageseinsätze |
| **Fahrerstunden gesamt** | **1,749.7 h** | **2,237.0 h** | Berechnet nach `prezero_config.json` |

## 2. Methodik & Regeln

1. **Strikter Walk-Forward ohne Look-Ahead:**
   Für jeden Tag $d$ lernt das Timer-Modell Container-Füllraten ausschließlich aus Messungen mit $\text{Datum} < d$. Zukünftige Messwerte fließen zu keinem Zeitpunkt in die Entscheidung ein.
2. **Bedarfsauslösung:**
   Ein Container wird eingeplant, sobald der geschätzte Füllstand $\ge 80\,\%$ erreicht oder bis zum nächsten regulären Betriebstag (Wochenende/Feiertag) $\ge 110\,\%$ überlaufen würde.
3. **Betriebsrestriktionen (OperationalConfig):**
   Beide Modelle unterliegen exakt denselben Annahmen aus `prezero_config.json`:
   - LKW-Nutzlast: 11.000 kg, Ladevolumen: 26,0 m³, Dichte: 400 kg/m³, Behälter: 2,5 m³
   - Max. Schichtdauer: 8,0 h, Rüstzeit: 2,0 min, Hubzeit: 3,0 min/Behälter, Entladezeit: 20,0 min
   - Umwegfaktor: 1,35 auf Haversine, Geschwindigkeit: 25 km/h
   - Feste Depots: Betriebshof (49.1427, 9.2109), Entladestelle (49.1780, 9.2085)
4. **Geodaten-Transparenz:**
   Routing auf simulierten Zuordnungen (`source=osm_assigned`, `confidence=simulated_mapping`).
