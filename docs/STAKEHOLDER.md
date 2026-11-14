# Stakeholder-Regeln (PreZero / Mentor)

Stand: 14.11.2026 · Quellen: `20261113_Readme Challenge PZ.docx`, `PreZero.pptx`,
Mentor-Gespräche (in `Pitch/NOTES.md` festgehalten).

**Diese sechs Sätze sind fixierte Regeln, keine Meinungen.** Wer eine Zahl, eine Formulierung oder
ein Modul ändert, prüft zuerst gegen diese Liste. Jede Regel nennt die Stelle im Code, an der sie
umgesetzt ist — und was daraus für Aussagen im Pitch folgt.

---

## R1 — Der Fahrer schätzt den Füllstand und leert sofort

> „these algorithms cannot deliver true efficiency without real-time fill-level intelligence"

Jede Messung ist ein **Besuch**: der Fahrer sieht den Stand, schätzt ihn, und leert den Container.
Der Container startet danach bei ~0 %.

**Umsetzung**
- `src/prezero/features.py:1-12` — Modul-Docstring: measure-and-empty als Datenvertrag.
- `src/prezero/features.py:56` `fill_rates_after_emptying` — Füllrate eines Intervalls =
  vorgefundener Stand ÷ Tage seit dem letzten Besuch (Intervall startet leer).
- `src/prezero/features.py:75` `estimate_fill` — geschätzter Stand heute = Rate × Tage seit Leerung.
- `scripts/backtest.py:1-15` — derselbe Vertrag im Walk-forward-Backtest.

**Konsequenz für Aussagen**
- „Stand heute“ ist **geschätzt**, nicht gemessen. Immer so sagen.
- `last_fill_level` ist der Stand *beim Besuch*, nicht der Stand *jetzt*. Nicht verwechseln.

---

## R2 — Schätzungen kommen in 10-%-Schritten

Der Fahrer schätzt am Container in Zehnerschritten; feiner gibt es die Daten nicht.

**Umsetzung**
- Rohdaten: 10.509 nicht-übervolle Messungen, **100 % durch 10 teilbar** (0, 10, …, 100).
- `src/prezero/features.py:43` `MAX_FILL_PCT = 110.0` — `overfull` wird als 110 % kodiert
  (`src/prezero/ingest.py:42`), die echte Höhe ist unbekannt.
- Fahrer-Formular: `src/prezero/ui.py:1911` und `:3377` — `step="10"`, `min=0`, `max=110`;
  `src/prezero/ui.py:3819` weist andere Werte ab. Rückmeldung als `tour_feedback_<datum>.csv`
  (`src/prezero/ui.py:3836`), Wiedereinspielung über `prezero-route run --input <csv>`.

**Konsequenz für Aussagen**
- Keine Genauigkeit unterhalb eines Schritts behaupten. Der Backtest-Fehler von **19,9 pp**
  (`docs/BACKTEST.md`) sind rund **zwei Schätzschritte** — das ist die Auflösungsgrenze.
- 80 % als Fälligkeitsschwelle (`src/prezero/features.py:40`) ist selbst eine Annahme und im Code
  als „Annahme, von PreZero zu ersetzen“ markiert.

---

## R3 — Bei PreZero ist nichts digitalisiert

Es gibt keine Tourprotokolle, keine Leerungsliste, keine Zeitstempel je Fahrt. Nur Füllstände.

**Umsetzung**
- `scripts/backtest.py` rekonstruiert Besuche ausschließlich aus Messreihen (kein externer Fahrplan).
- Leerungsrhythmus (`docs/BACKTEST.md`) = Median der Abstände zwischen Besuchen, nicht aus
  Betriebsdaten gelesen.
- Der harte Saisonfaktor wurde deshalb verworfen (`src/prezero/features.py:8-10`); `season_factor`
  existiert nur noch als Informationsspalte.

**Konsequenz für Aussagen**
- Rhythmus-Zahlen sind **Rekonstruktionen**, keine PreZero-Protokolle. „Aus den Daten
  rekonstruiert“ sagen, nicht „Ihr Leerungsplan war“.
- Kein Feature bauen, das eine existierende digitale Quelle voraussetzt (Schnittstelle, iCal,
  Tourenhistorie).

---

## R4 — Erst auswählen, dann sortieren

Einsparung entsteht in zwei getrennten Schritten: **welche** Container (Timer abgelaufen) und
**in welcher Reihenfolge** (Routing). Beides wird getrennt gemessen.

**Umsetzung**
- Auswahl: `src/prezero/scoring.py:38` `critical = est_fill_level >= 80` —
  Timer je Container (`src/prezero/features.py:150-161`: `due_date`, `days_until_due`).
- Reihenfolge: `src/prezero/routing.py` (Nearest Neighbor, Kapazität/Schicht/Umschlag).
- Getrennte Messung: `scripts/benchmark.py:270-274` B0–B4 —
  B0/B1 = alle Standorte (Status quo), B2 = nur fällige, B3/B4 = gleiche Stopps, bessere Ordnung.
  Effekte in `scripts/benchmark.py:318-320`: **Bedarfs-Effekt B1→B2**, **Routing-Effekt B2→B4**.

**Konsequenz für Aussagen**
- Nie eine einzige „X % gespart“-Zahl nennen. Immer Bedarfs-Effekt **und** Routing-Effekt getrennt
  (15.04.2026: 29,9 % / 9,7 % / gesamt 36,7 %). Beleg: `Projek-Management/proof/A3_pitch_zahlen.txt`.
- Wenn der Solver nicht besser ist als Nearest Neighbor, bleibt NN (`nn_kept` in
  `benchmark_results.csv`). Das wird berichtet, nicht versteckt.

---

## R5 — Von PreZero kommen keine Standorte

Die Challenge enthält **keine** Adresse, keine Koordinate, keinen Orts-Schlüssel — nur anonyme IDs.

**Umsetzung**
- `src/prezero/locations.py:230-238` — alle 449 IDs liegen auf echten OSM-Punkten,
  `source=osm_assigned`, `confidence=simulated_mapping`; die Zuordnung ist simuliert
  (Punkte werden wiederverwendet).
- `src/prezero/locations.py:89-94` — der Vertrag wird validiert; andere Confidence-Werte sind
  ein Fehler, kein stiller Fallback.
- `src/prezero/ui.py:1238` — Banner auf der Website: „Ortsdaten erfunden, nicht von PreZero“.
- Austauschpfad: `data/external/locations_real.csv` (`Location_id,lat,lon`) +
  `scripts/refresh_locations.py --real`, ohne Codeänderung.

**Konsequenz für Aussagen**
- Nie „126 echte, 323 Platzhalter“ (veraltet) und nie „wir wissen, wo die Container stehen“.
- Absolute km, Fahrzeugzahl, Schichtstunden hängen an dieser Geografie → **Illustration**.
  Belastbar sind die **Verhältnisse** (Bedarfs- vs. Routing-Effekt).

---

## R6 — Der Status quo leert Gebiet für Gebiet

> „Emptying these containers usually takes place area by area. Then all containers in the area are
> emptied, regardless of the actual fill level ('you'll drive past there anyway')."

Das ist die Baseline, gegen die wir argumentieren — nicht eine erfundene Vergleichsroute.

**Umsetzung**
- `scripts/benchmark.py:270-271` — B0 (Papierlisten-Reihenfolge) und B1 (alle 121 Standorte,
  optimierte Reihenfolge) sind der Status quo.
- 15.04.2026: 509 von 1.269 Containern fällig — deshalb ist der Bedarfs-Effekt an diesem Tag klein
  (29,9 %), über vier Stichtage 28,6–67,1 %.

**Konsequenz für Aussagen**
- Die Kernaussage ist der **Rhythmus**, nicht die Tageskilometer: Braunglas ideal 95 Tage, heute
  42 Tage, 89 % zu oft geleert; Weißglas teils zu selten (16 %). Beleg: `docs/BACKTEST.md`.
- „Mitte April spart Weglassen ein Drittel, über das Jahr 30–67 %“ — so und nicht anders.

---

## Was daraus nie im Pitch steht

| Nicht sagen | Warum | Stattdessen |
|---|---|---|
| „126 echte Standorte, 323 Platzhalter“ | veraltet seit `d12331f` | „alle 449 auf echten OSM-Punkten, Zuordnung simuliert“ |
| „24,1 % / 70,7 % / 81 % gespart“ | ungültig: alte Sensor-/Saisonannahmen | 29,9 % / 9,7 % / 36,7 % (`A3`) |
| „Echtzeit-Füllstand“ | Daten sind Besuchsschätzungen | „geschätzter Stand heute aus Fahrer-Schätzung“ |
| „Wir kennen Ihren Leerungsplan“ | nichts ist digitalisiert | „aus den Messreihen rekonstruiert“ |
| „x % genauer als Ihr System“ | Auflösung ist 10 pp | „Fehler 19,9 pp ≈ zwei Schätzschritte“ |
