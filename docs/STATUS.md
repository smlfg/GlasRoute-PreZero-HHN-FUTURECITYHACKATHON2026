# Status — GlasRoute (PreZero Challenge, Future City Hackathon 2026)

**Stand:** So 15.11.2026, 09:40 · **Feature-Freeze:** So 15.11. 11:00 · **Abgabe:** So 15.11. 13:00
**Code-Stand der Zahlen unten:** `611178b` (Pitch-Zahlen) · zuletzt verifiziert auf `fb980e8`

## In 30 Sekunden

Ein CLI-Prototyp, der Füllstandsdaten von 449 Heilbronner Glascontainern in eine **priorisierte,
freigabepflichtige Tagesroute** übersetzt. Kernbefund: **Braunglas wird doppelt so oft geleert, wie
es nötig wäre**, Weißglas läuft teils über. Deshalb bekommt jeder Container einen **eigenen Timer**
statt eines Gebietsrhythmus.

## Was läuft (nachprüfbar)

```bash
pip install -e ".[test]"                       # Installation (bs4 nur für die Website-Tests)

prezero-route run --date 2026-04-15            # Pipeline + Website
prezero-route propose                          # Vorschlag (nichts wird ohne Freigabe dispatcht)
prezero-route approve --by "Disponentin"       # Freigabe + Beleg data/processed/approval_<datum>.json
prezero-route ui --date 2026-04-15             # ui_2026-04-15.html (11 Tabs, offline nutzbar*)
prezero-route forecast --date 2026-04-15       # Prognose +7/+14/+21 Tage, forecast_16.html
python scripts/backtest.py && python scripts/benchmark.py   # Rhythmus + fairer Vergleich (~2 min)
PYTHONPATH=src pytest -q                        # 151 grün, 2 bekannte Fehler (Copilot-Änderung, noch nicht committed)
PYTHONPATH=src python Projek-Management/proof/verify_pitch_numbers.py   # "RESULT: ALL MATCH"
```

**Teststand (gemessen am 15.11.2026, 09:40):** 151 von 153 Tests grün. Die 2 roten Tests sind
`tests/test_copilot.py::test_approve_tour_is_forbidden_as_chat_tool` und
`tests/test_copilot.py::test_copilot_all_ten_intents_return_structured_output_with_stand_and_sources` —
beide erwarten noch die alte Tool-Liste (12 Einträge) gegen die laufende, noch nicht committete
Copilot-Änderung (13 Einträge). Sie gehören zum Copilot-Thread, nicht zu diesem Dokumentationsstand.

Erwartete Ausgabe von `run`:
`106 critical physical sites (276 critical IDs, 509 containers) · 249.9 km planned (25 stops) vs 1202.24 km full round`

\* Kartenkacheln kommen von OpenStreetMap — **ohne Internet bleiben die Karten leer**, Tabellen und
Kennzahlen funktionieren. Vor dem Pitch einmal offline prüfen.

## Pitch-Zahlen (Stand `611178b`, Beleg `Projek-Management/proof/A3_pitch_zahlen.txt`)

| Kennzahl | Wert | Spanne |
|---|---|---|
| Bedarfs-Effekt (B1→B2: nur fällige Container) | **29,9 %** | 28,6–67,1 % (4 Stichtage × 3 Seeds) |
| Routing-Effekt (B2→B4: gleiche Stopps, bessere Reihenfolge) | **9,7 %** | 2,3–14,1 % |
| Gesamt vs. Status quo B1 | **36,7 %** | 32,9–70,7 % |
| Rhythmus Braunglas | ideal **95 Tage**, heute **42 Tage**, **89 %** zu oft geleert | – |
| Rhythmus Weißglas | 16 % zu selten geleert (läuft über) | – |
| Fahrten, die zu früh kamen (<50 % voll) | 30 % | – |
| Prognosefehler (Walk-forward) | 19,9 pp gegen 22,3 pp Baseline | – |
| Datenbasis | 11.701 Messungen · 449 Container · 1.192 `overfull` | – |

Tages-Tour 15.04.2026: 25 von 106 fälligen Standorten, 249,9 km, 4 Fahrzeuge, 19 Runden,
142,8 t, längste Schicht 7,58 h (Limit 8 h). Die **79,2 %** auf der Website sind diese Teil-Tour gegen
„alles leeren“ — **keine Pitch-Zahl**.

## Was simuliert ist

| Teil | Status |
|---|---|
| Füllstände | **echt** (PreZero-CSV), aber Fahrer-**Schätzungen in 10-%-Schritten** |
| Standorte | 449 **echte OSM-Punkte**, Zuordnung der anonymen IDs **simuliert** (`osm_assigned` / `simulated_mapping`) |
| Stand heute | **geschätzt**: Füllrate × Tage seit der letzten Leerung (nicht gemessen) |
| Leerungsrhythmus | **rekonstruiert** aus Messreihen — bei PreZero ist nichts digitalisiert |
| Distanzen | Haversine × Umwegfaktor 1,35, **kein Straßenrouting** |
| Betriebsvariablen | 11 Annahmen (Dichte, Fahrzeuglast, Zeiten, Depots) in `prezero_config.json` |

Daraus folgt: **absolute** km/Fahrzeuge/Stunden sind Illustration, belastbar sind die **Verhältnisse**.

## Was offen ist

Siehe [`TODO.md`](TODO.md). Kurz: echte PreZero-Koordinaten, Straßenrouting, Flottenoptimum,
Wochenauswahl auf der Prognosekarte. Regeln für alle Aussagen: [`STAKEHOLDER.md`](STAKEHOLDER.md).
Dokumentenlage: [`INDEX.md`](INDEX.md).
