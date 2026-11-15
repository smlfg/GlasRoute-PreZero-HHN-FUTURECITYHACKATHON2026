# MODEL_SPEC — GlasRoute Rechenmodell (Szenario-Vergleich)

Stand 15.11.2026. Gilt für `scripts/simulate_daily.py` und alle Szenario-Läufe.
Quellen-Label: **Daten** = `data/processed/cleaned_readings.csv` (11.701 Leerungen, 449 Standorte),
**Mentor 15.11.** = PreZero-Mentor-Gespräch, **Config** = `prezero_config.json`, **Annahme** = von uns gesetzt.

## 0. Kernmodell (hat Vorrang vor allem Folgenden)

Erzeuger-Verbraucher-Problem **pro Container**, kein Routing-Problem.

- **Erzeuger:** Haushalte füllen Container c mit nahezu konstanter Rate r_c (kg/Tag), geschätzt aus
  Füllstand bei Leerung / Tage seit der letzten Leerung (jeder Besuch = messen + auf 0 setzen).
- **Verbraucher:** Leerungstakt T_c (Tage) je Container.
- **Ziel:** T_c an r_c anpassen: `T_c = (Kapazität − Sicherheitspuffer) / r_c`, nach jeder neuen Messung neu.
- **Glasmenge pro Jahr = Σ_c r_c × 365** — in jedem Szenario identisch. Ein Szenario, das mehr sammelt, ist falsch.
- **Routing/Flotte** ist nachgelagert: bündelt fällige Container zu Gebietstouren. Es ändert nie,
  welches Glas existiert, nur wie effizient es geholt wird.
- **Primäre Kennzahlen** (bei gleicher Tonnage): Ø Füllstand bei Leerung, Überläufe, eingesparte
  Leerungen (Stopps). km/Flotte sind sekundär.

## 1. Grundsatz: ein Weltmodell, viele Politiken

Jedes Szenario läuft gegen **dieselbe Welt** (Nachfrage = Glasanfall pro Container und Tag).
Szenarien unterscheiden sich nur in der **Entscheidungsregel** (wann wird geleert) und in der Tourbildung.
Die Welt kennt die wahre Rate, die Politik nur Schätzungen aus der Vergangenheit (Walk-Forward, kein Look-Ahead).

Daraus folgt die Pflicht-Invariante (Massenerhaltung, Mentor 15.11.):

    produziert(c) = Σ_d r_c                       (identisch in allen Szenarien)
    gesammelt(S) + Endbestand(S) = Anfangsbestand + produziert      (pro Szenario exakt)
    |gesammelt(A) − gesammelt(B)| / gesammelt(A) ≤ 2 %               (Test: tests/test_mass_balance.py)

Überlaufenes Glas verschwindet nicht: es steht neben dem Container und wird bei der nächsten Leerung
mitgenommen. Der Füllstand wird daher **intern nicht bei 110 % gekappt**; 110 % ist nur die Schwelle,
ab der ein **Überlauf-Ereignis** gezählt wird.

## 2. Ursache des Tonnage-Bugs (9.451 t vs 7.719 t)

Gemessen mit den Daten (Faktor 0,01 t pro %-Punkt = 2,5 m³ × 400 kg/m³ / 100):

| Posten | t | Wirkung |
|---|---:|---|
| Summe aller Messungen (historisch gezählt) | 7.719,2 | Status-quo-Zeile |
| davon erste Messung je Container (Glas aus der Zeit **vor** dem Fenster) | 775,7 | nur historisch gezählt, Simulation startet bei 0 % |
| in-Fenster gemessen (Messung 2…n) | 6.943,5 | vergleichbare Basis |
| Produktion mit **Mittel der Quotienten** `mean(level_i/Δt_i)` × aktive Tage | 8.697,7 | so rechnet die Simulation |
| Produktion mit **Quotient der Summen** `Σlevel_i/ΣΔt_i` × aktive Tage | 7.529,6 | erwartungstreu für konstante Rate |

Ursachen in der Simulation (`simulate_optimized_daily`):
1. **Wahrheit = Schätzung:** Der Glasanfall der Simulation wird aus den Walk-Forward-Schätzraten erzeugt,
   statt aus einer festen Welt. Die Schätzung `mean(level/Δt)` ist durch kurze Intervalle nach oben verzerrt
   (+15,5 % ggü. Quotient der Summen) und schwankt in den ersten Wochen stark (wenige Messungen).
2. **Phantom-Masse:** Nach jeder Leerung startet der Container bei `uniform(0, 5) %` → ≈ 2,5 pp × 11.321
   Leerungen ≈ 283 t Glas, das nie produziert wurde.
3. **Unterschiedliche Bilanzgrenzen:** Historisch zählt den Anfangsbestand (erste Messung, 776 t) mit,
   die Simulation nicht; die Simulation lässt Endbestand stehen, historisch nicht.
4. **Kappung bei 110 %** auf beiden Seiten verschluckt Überlauf-Glas (1.192 Messungen „overfull“).

Fix-Richtung (W1): eine Nachfragefunktion `r_c = Σ level_i / Σ Δt_i` (Intervalle ab 2. Messung) als
Welt für **beide** Seiten; Status quo = Replay der realen Leerungstage gegen diese Welt
(reproduziert die gemessene In-Fenster-Masse per Konstruktion); gleicher Anfangsbestand,
Endbestand ausgewiesen; Reset auf exakt 0 %; keine Kappung der Masse.

**Gemessen nach dem Fix (W1, `PYTHONPATH=src python3 scripts/simulate_daily.py`, 349 Tage):**

| Kennzahl | Status quo | Timer-Modell |
|---|---:|---:|
| Produziert (`produced_total`, Σ r_c × aktive Tage) | 7.613,95 t | 7.613,95 t |
| Gesammelt im Fenster | 6.943,50 t | 7.157,52 t |
| Endbestand 30.09.2026 | 670,45 t | 456,43 t |
| Gesammelt + Endbestand | 7.613,95 t | 7.613,95 t |
| Leerungen | 10.363 | 10.954 |
| Ø wahrer Füllstand bei Leerung (ungekappt) | 67,0 % | 65,3 % |
| Überfüllte Leerungen (≥ 110 %) | 1.196 | 214 |
| Überlauf-Containertage (≥ 110 %) | 19.047 | 1.484 |
| km / Fahrzeugtage / Stunden | 19.007,6 / 317 / 1.593,3 | 25.684,6 / 339 / 2.026,2 |

Entscheidungen: erste Messung = Start der Systemgrenze auf beiden Seiten (keine Leerung, keine Masse;
11.701 − 1.338 Container = 10.363 Leerungen im Status quo). Ø Füllstand ungekappt. Die In-Fenster-Tonnage
unterscheidet sich um +3,1 %, genau um die Endbestands-Differenz (214 t); der ±2-%-Test vergleicht daher
für beide Seiten gleich „gesammelt + Endbestand“. Das Timer-Modell leert **nicht voller** als der Status quo,
weil die Walk-Forward-Schätzung über der wahren Rate liegt und die Regel deshalb zu früh leert.

## 3. Entscheidungsvariablen

| Symbol | Bedeutung | Einheit |
|---|---|---|
| x_{c,d} ∈ {0,1} | Container c wird am Tag d geleert | – |
| y_{v,d} ∈ {0,1} | Fahrzeug v ist am Tag d im Einsatz | – |
| Reihenfolge der Stopps je Fahrzeug/Tag | Tour (Nearest-Neighbour-Heuristik, `routing._simulate_constrained_routes`) | – |

## 4. Zustand und Dynamik

    f_{c,d} = f_{c,d−1} + r_c                 (vor der Entscheidung, in % von 2,5 m³)
    f_{c,d} := 0          falls x_{c,d} = 1    (Masse f·0,01 t wird gesammelt)
    Überlauf-Ereignis      falls f_{c,d} ≥ 110 % (gezählt pro Container-Tag)

## 5. Ziele (je Szenario eines; Vergleich über alle Kennzahlen)

| Szenario | Ziel / Regel |
|---|---|
| (a) 0 % Überlauf | min Überlauf-Ereignisse, Leerung sobald Prognose bis nächster Betriebstag ≥ Schwelle |
| (b) min km | min Σ km, Leerung so spät wie möglich |
| (c) max Fahrzeugfüllung | max Ø Füllstand bei Leerung / Last je Tour |
| (d) Status quo | reale Leerungstage (jeder Container wie historisch) |
| (e) Mentor-Politik | Container mit Prognose ≤ 20 % → 14-Tage-Rhythmus; frei werdende Zeit an kritische Standorte; Sicherheitspuffer (nicht erst an der Kante leeren) |

## 6. Nebenbedingungen

| Nebenbedingung | Wert | Quelle |
|---|---|---|
| Gesammelte Tonnage A == B (±2 %) | – | Mentor 15.11. |
| Glasanfall pro Container konstant über das Jahr | r_c | Mentor 15.11. / Daten |
| Fahrzeug-Nutzlast | 11 t | Mentor 15.11. / Config |
| Fahrzeug-Volumen | 26 m³ | Mentor 15.11. / Config |
| volle Container → mehr Entladefahrten | Entladen bei Kapazität | Mentor 15.11. |
| Schichtlänge | 8 h | Config (Annahme) |
| Betriebstage | Mo–Fr ohne BW-Feiertage | Daten (Feiertage ohne Leerung) |
| feste Gebiete statt tageweisem Kreuz und Quer | Gebietsplanung | Mentor 15.11. |
| Sicherheitspuffer | Leerung vor 100 % | Mentor 15.11. |

## 7. Parameter

| Parameter | Wert | Einheit | Quelle |
|---|---:|---|---|
| Behältervolumen | 2,5 | m³ | Config (Annahme) |
| Schüttdichte Glas | 400 | kg/m³ | Config (Annahme) |
| Fällig-Schwelle (Timer) | 80 | % | Annahme (`features.DUE_FILL_PCT`) |
| Überlauf-Schwelle | 110 | % | Daten („overfull“ = 110) |
| Servicezeit je Stopp | 5 | min | Mentor 15.11. (unabhängig vom Füllstand) |
| Fahrzeit zwischen Stopps, städtisch (Heilbronn) | 7 | min | Mentor 15.11. |
| Fahrzeit zwischen Stopps, ländlich (Flein, Lauffen) | 15 | min | Mentor 15.11. |
| Depot-Rückfahrt / Entladen | 20 | min | Config (Annahme) |
| Geschwindigkeit (nur km-Modell) | 25 | km/h | Config (Annahme) |
| Umwegfaktor | 1,35 | – | Config (Annahme) |
| Skip-Schwelle Mentor-Politik | 20 | % | Mentor 15.11. |
| Skip-Rhythmus | 14 | Tage | Mentor 15.11. |
| Kosten Fahrzeugtag | 500 | € | Annahme |
| Kosten Crew | 64 | €/h | Annahme (2 × 32 €/h) |
| Kosten Strecke | 0,65 | €/km | Annahme |

Kostenformel (Annahme): `Kosten = Fahrzeugtage × 500 € + Crew-h × 64 € + km × 0,65 €`.

## 8. Kennzahlen je Szenario

Tonnage (muss gleich sein), Überlauf-Ereignisse, Ø Füllstand bei Leerung, Stopps, Fahrzeugtage,
Stunden, km, Kosten. Jede Zahl stammt aus einer Skriptausgabe; Quelle wird im Vergleich zitiert.

## 9. Entscheidungen 15.11. (Owner)

1. **Tonnage-Vergleich:** „gesammelt + Endbestand“ (= produziert) muss gleich sein. In der
   Vergleichstabelle stehen **beide** Spalten offen: gesammelt im Fenster und Endbestand.
2. **Schätzer überall:** Walk-Forward-Rate = Σ Füllstand / Σ Tage (Quotient der Summen) aus Messungen
   mit Datum < d. `mean(level/Δt)` ist verboten (Bias, §2).
3. **Neue Frage km-Delta (+35 % km bei +6 % Leerungen):** zerlegen in (1) zusätzliche Leerungen,
   (2) gestreute Tages-Fälligkeiten statt fester Gebiete, (3) zusätzliche Fahrzeuge inkl. Depot hin/zurück,
   (4) zusätzliche Entlade-/Depotfahrten, (5) Aufspaltung der Glasfarben eines Standorts
   (gemessen: Status quo 2,79 Container je Standortbesuch, Timer 1,35; 3.714 vs 8.092 Standortbesuche).
4. **Politik (f) „feste Gebiete“:** jeder Container gehört zu genau einem Gebiet (geografisches Clustering),
   jedes Gebiet hat feste Wochentage; ein fälliger Container wird am nächsten Gebietstag geleert,
   der Puffer muss Überläufe bis dahin verhindern.
5. **Standort-Bündelung (Parameter):** ist ein Container eines Standorts fällig, werden die anderen
   Farben mitgeleert, wenn ihr geschätzter Füllstand ≥ Mitnahme-Schwelle (Standard 50 %, Annahme).
6. **Kein Merge nach master/main vor 16:00** (Pitch 15:00 läuft auf eingefrorenem Stand).

## 10. Datenmodell: Container, Standort, Halt

| Begriff | Definition | Anzahl |
|---|---|---|
| **Container** | (Location_id, material_type ∈ {white, green, brown}); Füllrate r, Takt T und Fälligkeit gelten **pro Container** | 1.338 |
| **Standort** | eine Location_id = bis zu 3 Container (eine je Farbe) | 449 (441 mit 3 Farben, 7 mit 2, 1 mit 1) |
| **Halt** | ein physischer Punkt (lat/lon); der LKW hält einmal und leert alles, was an diesem Punkt geleert wird | 121 Punkte |

**Warum 449 IDs auf nur 121 Punkten liegen (kein Geocoding-Fehler, sondern Absicht):**
`data/external/locations.csv` hat für alle 449 IDs `source=osm_assigned`, `confidence=simulated_mapping`,
`match_reason="real OSM site, ID assignment simulated"`. PreZero hat die IDs anonymisiert und keine Koordinaten
geliefert. `locations.assign_osm_sites` (src/prezero/locations.py:215) verteilt jede ID **zufällig mit Zurücklegen**
(`rng.randrange`, fester Seed) auf eine der 121 echten OSM-Glascontainer-Punkte in Heilbronn. Ergebnis:
nur 11 Punkte haben genau 1 ID, 438 IDs teilen sich einen Punkt mit anderen (bis zu 9 IDs = 27 Container je Punkt).
**Folge:** Halte bündeln in der Simulation mehr Container als in der Realität; absolute km/Halte sind illustrativ.
Mit PreZeros echter Standortliste ändert sich nur `locations.csv`.

**Heutiges Verhalten:** Nur **fällige** Container eines Halts werden geleert
(Demo-Tour: `routing.py:292-293`, nur `crit_mass_kg`/`crit_volume_m3` geladen; Jahressimulation:
`scripts/simulate_daily.py` ~Z. 529-571, nur `due`-Container in `site_dict`). Nicht fällige Farben am selben
Halt bleiben stehen und werden Tage später erneut angefahren.

**Offene Frage (Annahme, Parameter `truck_mode`):**
- `multi_chamber` (Standard-Annahme): ein LKW nimmt alle 3 Farben in einem Halt mit (Mehrkammer).
- `per_colour`: ein LKW je Farbe; jede Farbe eines Halts ist ein eigener Halt einer eigenen Tour.
Ob PreZero Mehrkammer-Fahrzeuge einsetzt, ist **unbekannt** → beide Varianten werden gerechnet.

**Szenario (g) „co-empty“:** wird ein Halt angefahren, werden auch die anderen Container dort mit
geschätztem Füllstand ≥ X % geleert (Parameter, Standard X = 50 %, Annahme). Berichtet: zusätzliche
Leerungen vs. eingesparte spätere Halte, km, Stunden, Ø Füllstand, Überläufe — bei gleicher Tonnage.
In `per_colour` ist co-empty nur innerhalb derselben Farbe möglich (mehrere IDs derselben Farbe am selben Punkt).
