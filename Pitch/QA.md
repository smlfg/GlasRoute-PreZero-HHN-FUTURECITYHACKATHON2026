# Jury-Q&A — die 12 härtesten Fragen an GlasRoute

Stand: 15.11.2026 · Jede Antwort: 2 Sätze, ehrlich, mit Beleg. **OPEN** = können wir nicht ehrlich beantworten.

**Hinweis zur Quelle:** Die Demo-Zahlen sind in `Projek-Management/proof/demo_day_numbers.json` gepinnt (geprüft mit
`Projek-Management/proof/verify_pitch_numbers.py`, Beleg `A3_pitch_zahlen.txt`: „ALL MATCH“); die lesbare Kurzfassung
steht in `Pitch/demo_facts.txt`. Alle Zahlen unten stammen von dort, aus `docs/BENCHMARK.md` oder `docs/BACKTEST.md`.

| # | Thema | Status |
|---|---|---|
| 1 | Ist die Route optimal? | beantwortet |
| 2 | Warum 81 %, wenn die Standorte erfunden sind? | beantwortet (Zahl zurückgezogen) |
| 3 | Was, wenn der Fahrer falsch schätzt? | **teilweise OPEN** |
| 4 | Ist der Füllstand überhaupt vorhersagbar? | beantwortet |
| 5 | Skaliert es auf andere Städte? | beantwortet |
| 6 | Skaliert es auf andere Abfallarten? | beantwortet |
| 7 | Was spart es pro Tag in Euro? | **teilweise OPEN** |
| 8 | Warum fährt die Jahressimulation mehr km? | beantwortet |
| 9 | Warum vergleicht ihr gegen B1 statt B0? | beantwortet |
| 10 | Wie viele Überläufe verpasst euer Timer? | beantwortet |
| 11 | Wie verlässlich sind eure Betriebsannahmen? | beantwortet |
| 12 | Wie lange läuft es und was kostet der Betrieb? | **OPEN** |

---

## 1. Ist die Route optimal?

**Nein, und wir behaupten es nicht.** B4 nutzt OR-Tools mit hartem Abbruch nach 25 Lösungen (`scripts/benchmark.py:129-182`, `solution_limit`), liefert also eine reproduzierbare Heuristik ohne Optimalitätsbeweis; in 2 von 12 Fällen war der Solver schlechter als Nearest Neighbor und NN wurde behalten (`docs/BENCHMARK.md`, `nn_kept_cases` = 2 bei B4, 4 bei B3).
Der Routing-Effekt ist mit 9,7 % (Spanne 2,3–14,1 %) bewusst der kleinere Hebel; der größere ist die Auswahl, welche Container überhaupt angefahren werden (29,9 %).

## 2. Warum „81 %“, wenn die Standorte erfunden sind?

**Die 81 % gibt es nicht mehr.** „24,1 / 70,7 / 81 %“ beruhten auf Dauersensor-Annahme und festem Saisonfaktor und sind ausdrücklich ungültig (`docs/STAKEHOLDER.md:138`); die verwandte Zahl „102“ in `Pitch/demo_facts.txt` meint 102 *fällige Standorte, die das 25-Stopp-Limit offenlässt*, keine Ersparnis.
Auch die 83,4 % auf der Karte vergleichen nur eine Teil-Tour (25 von 127 Standorten) mit „alles leeren“ und sind laut `Pitch/NOTES.md` keine Pitch-Zahl; belastbar sind die Verhältnisse 29,9 % / 9,7 % / 36,7 %, nicht absolute km.

## 3. Was, wenn der Fahrer falsch schätzt? — **teilweise OPEN**

**Er schätzt ohnehin nur grob:** Die Rohdaten kommen zu 100 % in 10-%-Stufen (`docs/STAKEHOLDER.md:34-42`), das Formular erzwingt das (`src/prezero/ui.py:2246`, Validierung `:4868`), und der Backtest-Fehler von 19,9 pp liegt bei etwa zwei Schätzstufen (`docs/BACKTEST.md`).
**OPEN:** Eine gezielte Sensitivitätsanalyse „Schätzfehler ±10/±20 pp → Routenänderung“ haben wir nicht gebaut (`scripts/benchmark.py` variiert nur die Standort-Zuordnung, nicht die Füllstände); was wir sagen können, ist nur, dass jeder Besuch den Timer neu setzt und Fehler sich nicht aufschaukeln, bewiesen ist das nicht.

## 4. Ist der Füllstand überhaupt vorhersagbar, oder ist alles Zufall?

**Besser als Zufall, aber nicht präzise.** Walk-forward über 9.059 Besuche: Timer-Modell 19,9 pp Fehler gegen 22,3 pp für „Durchschnitt bisher“ (`docs/BACKTEST.md`, `backtest_summary.json`), Precision für „voll“ 75,0 % gegen 64,9 % Basis.
Der Abstand ist moderat (2,4 pp) und wir sagen nie „x % genauer als Ihr System“ (`docs/STAKEHOLDER.md:141`); unter etwa 10 pp ist die Auflösung der Daten ohnehin nicht erreichbar.

## 5. Skaliert es auf andere Städte?

**Technisch ja, empirisch ungetestet.** Alle Betriebsvariablen stehen in `prezero_config.json` und `OperationalConfig` (`src/prezero/routing.py:22-46`), Standorte werden über `Location_id,lat,lon` ausgetauscht (`scripts/refresh_locations.py --real`), und ein Lauf mit 112 Stopps dauert 0,31 s (`docs/BENCHMARK.md`).
Wir haben nur Heilbronn gerechnet, das Raster der Standortplanung hängt an der fest verdrahteten `HEILBRONN_BBOX` (`docs/STANDORTPLANUNG.md`), und ob Nearest Neighbor + 25-Lösungen-Solver bei tausenden Stopps noch brauchbar bleibt, haben wir nicht gemessen.

## 6. Skaliert es auf andere Abfallarten?

**Die Pipeline ja, die Evidenz nein.** `WasteStream` kapselt Dichte, Volumen und Saison je Fraktion (`src/prezero/model.py:41-58`, `prezero_config.json` → `streams`), und `--stream paper|bio|gastro|plastik` läuft end-to-end (`docs/ABFALLARTEN.md` §4).
Aber nur Altglas ist echt: 11.701 Messungen; Papier, Bio, Gastro und Plastik sind **synthetisch** erzeugt (`scripts/generate_synthetic_streams.py:117-118`), beweisen also nur, dass der Code läuft, nicht dass das Modell dort stimmt.

## 7. Was spart es pro Tag in Euro? — **teilweise OPEN**

**Wir haben ein Modell, aber keine PreZero-Preise.** Das Kostenmodell (500 €/Fahrzeugtag + 64 €/h Crew + 0,65 €/km) ergibt in der Q3-Simulation 4.132 € oder 5,0 % Ersparnis (≈ 16.500 €/Jahr, `Mathe/KOSTEN_UND_STRESSTEST_ANALYSE.md:98`), im Wesentlichen aus 5 eingesparten Fahrzeugtagen.
**OPEN:** Die Sätze sind unsere Annahmen ohne Quelle, und `data/dispatch_experiment.json`/`dispatch_policy.py`, aus denen die Q3-Zahl stammt, liegen nicht in diesem Repo, die Zahl ist hier nicht reproduzierbar; eine „€ pro Tag“-Zahl nennen wir daher nicht.

## 8. Warum fährt die Jahressimulation *mehr* Kilometer als der Status quo?

**Weil sie mehr Glas abholt, nicht weil sie schlechter ist.** Optimiert: 28.497,8 km und 9.451 t gegen 20.538,5 km und 7.719 t Status quo (`docs/KOSTENMODELL.md` §1), dafür Ø-Füllstand bei Leerung 83,5 % statt 66,0 % und 0 statt 1.192 Überfüllungen.
Das ist ein Schwachpunkt: Die Tonnen sind nicht gleich, der Vergleich ist kein „gleiche Arbeit, weniger km“, und die 0 Überläufe folgen teils aus der Regel „bei drohenden ≥ 110 % einplanen“ (§2.2) und sind kein unabhängiger Befund; die km-Ersparnis belegt nur der Stichtags-Benchmark (B1→B4).

## 9. Warum vergleicht ihr gegen B1 (optimierter Status quo) und nicht gegen die Papierliste?

**Weil B1 die härtere, fairere Baseline ist.** B1 leert alle 121 Standorte mit optimierter Reihenfolge und denselben Regeln (11 t, 26 m³, 8 h) wie unsere Varianten (`scripts/benchmark.py:270-274`), die Papierliste B0 wäre mit 41,4 % schmeichelhafter (`docs/BENCHMARK.md`).
Gegen B1 ergibt sich 29,9 % Bedarfs- plus 9,7 % Routing-Effekt = 36,7 %, über 12 Fälle 32,9–70,7 %; der Status quo „Gebiet für Gebiet“ selbst ist aber nur aus Messreihen rekonstruiert, nicht aus Tourprotokollen (`docs/STAKEHOLDER.md:52-67`).

## 10. Wie viele Überläufe verpasst euer Timer?

**Viele, denn der Recall beträgt nur 59,4 %.** Von den tatsächlich vollen (≥ 80 %) Besuchen erkennt das Modell 59,4 % (`docs/BACKTEST.md`), bei Braunglas sogar nur 40,2 %; 11,2 % aller Besuche fanden den Container übervoll.
Der Schwellenwert 80 % ist eine Annahme „von PreZero zu ersetzen“ (`src/prezero/features.py:40`); wer weniger Überläufe will, senkt ihn und fährt mehr, den Trade-off haben wir nicht als Kurve ausgewertet.

## 11. Wie verlässlich sind eure Betriebsannahmen und Standorte?

**Sie sind Annahmen, und wir markieren sie.** Alle 11 Betriebsvariablen tragen im Code `# Annahme, von PreZero zu ersetzen` (`src/prezero/routing.py:22-46`); bei Dichte 300 statt 400 kg/m³ und Umwegfaktor 1,2 bleibt die Flotte bei 3 Fahrzeugen und die Strecke sinkt von 227 auf 197 km (`Pitch/NOTES.md`), die Ergebnisse sind also sensibel.
Alle 449 Standorte sind echte OSM-Punkte, aber die Zuordnung zu den anonymen IDs ist simuliert (`src/prezero/locations.py:230-238`, `simulated_mapping`), jeder Punkt wird bis zu 9× vergeben, und das Banner sagt „Ortsdaten erfunden, nicht von PreZero“; absolute km, Fahrzeuge und Schichten sind deshalb Illustration, belastbar sind nur die Verhältnisse.

## 12. Wie lange läuft es, und was kostet der Betrieb? — **OPEN**

**Rechenzeit ist belegt, Betriebskosten nicht.** Eine Tourberechnung dauert 0,12–0,31 s (`docs/BENCHMARK.md`, `runtime_s`), das System ist ein lokales Python-CLI ohne Cloud-Zwang (`pyproject.toml`: pandas, OR-Tools, folium), und der Copilot rechnet laut `src/prezero/copilot.py:5` nie selbst, der LLM-Teil ist optional (`use_llm=False` als Default, `:2490`).
**OPEN:** Eine Zahl für Betrieb, Integration, Fahrer-Schulung (Tablet/Formular, `tour_feedback_<datum>.csv`) oder Wartung haben wir nicht; ob Disponenten das Freigabe-Workflow (`src/prezero/approval.py`) im Alltag nutzen würden, ist ungetestet.

---

## Was wir *nicht* sagen (Kurzliste für die Bühne)

- „81 % / 70,7 % / 24,1 % gespart“, „Echtzeit-Füllstand“, „126 echte Standorte“, „wir kennen Ihren Leerungsplan“ (`docs/STAKEHOLDER.md:133-141`).
- Eine einzelne Ersparnis-Zahl ohne Aufteilung in Bedarfs- und Routing-Effekt.
- Eine Euro-Zahl pro Tag.

## Offene Punkte vor Sonntag 13:00 (aus den OPEN-Fragen)

1. Sensitivität Schätzfehler → Route (Frage 3) — ein Lauf mit ±10/±20 pp Rauschen auf `fill_level_numeric`; 
2. `dispatch_experiment.json` ins Repo oder Q3-Zahl streichen (Frage 7).
3. Von PreZero vor Ort erfragen: Tagessatz, Crew-Kosten, Dichte (Fragenliste in `Pitch/NOTES.md`, „Der stärkste Live-Impuls“).
