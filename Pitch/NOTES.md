# Pitch-Notizen für Sonntag 13:00

Stand: Samstag, 14.11.2026, 16:30 Uhr. Demo-Datum: **15.04.2026**.
Alle Zahlen sind gegen `data/raw/` und `data/processed/` geprüft (Beleg: `Projek-Management/proof/A3_pitch_zahlen.txt`).

---

## ⚠️ Drei Dinge, die du wissen musst

### 1. Standorte: 126 real, 323 Platzhalter

Von 449 `Location_id`s haben **126 einen echten OSM-Standort** in Heilbronn. Die übrigen **323 sind
benannte Platzhalter** (Seed 2026, BBox 49.09–49.23 N / 9.13–9.28 E).

Die Zuordnung ist **heuristisch**: `confidence=low`, `source=osm_heuristic`, `match_reason` mit
„UNVERIFIED“. Anonyme PreZero-IDs haben keinen Fremdschlüssel zu OSM-Objekten — eine Zuordnung über
Material ist keine Identität.

**So im Pitch sagen:**
> „Wir haben 126 echte Glascontainer-Standorte aus OpenStreetMap. Weil die Container-IDs anonymisiert
> sind, ist die Zuordnung eine Heuristik, keine Identität — wir markieren das als `low`/`UNVERIFIED`.
> Die restlichen 323 bekommen deterministische Platzhalter. Sobald PreZero die echte Zuordnungstabelle
> einspielt, übernimmt das System sie ohne Codeänderung."

Nicht sagen: „wir haben alle Standorte gefunden".

### 2. Die 24,1 %: was wird verglichen?

**Die Ersparnis ist eine Bedarfs-Ersparnis, keine Routing-Ersparnis.**

| Vergleich | Stopps | km |
|---|---|---|
| **Geplante Tour** (heute) | 25 | 119,75 |
| **Volle Runde** (Status quo) | 431 | 157,72 |
| **Ersparnis** | | **37,97 km = 24,1 %** |

Die volle Runde fährt **alle 431 Standorte mit Daten** ab — das ist der Status quo, den der
Stakeholder meint („heute fährt der Fahrer alle Container ab“). Es ist **nicht** „dieselben 25
Stopps, nur anders sortiert“. Eine reine Routing-Ersparnis wäre ein anderer Vergleich.

**Richtig formulieren:**
> „Heute fährt das Fahrzeug alle 431 Standorte mit Daten ab — 157,72 km. Unser Tool schlägt vor,
> die 25 kritischsten zuerst zu bedienen: 119,75 km, 24,1 % weniger Strecke, und die überlaufenden
> Container sind zuerst dran."

**Nicht behaupten:** „24 % Routing-Effizienz“ oder „bessere Reihenfolge spart 24 %“. Das wäre falsch.

### 3. Zwei Agenten haben gleichzeitig committet

Bis jetzt laufen zwei Agenten parallel ins Repo. **Ab jetzt nur einer zur Zeit.**
Konkret: `git log` vor jedem Commit prüfen (`git status` + `git log --oneline -3`), und wenn
schon jemand anderes committen will, warten bis dessen Commit durch ist.

---

## Pitch-Struktur (3 Minuten)

### 1. Problem (30 Sek.)
> „Glascontainer in Heilbronn werden nach festem Plan geleert. Laster fahren zu halbleeren
> Containern, während andere überlaufen."

Belegt: 11.701 Messungen, 449 Container, **1.192 `overfull`-Ereignisse**. Jeder vierte Überlauf-Fall
betrifft Weißglas (731 von 1.192).

### 2. Warum lösen (20 Sek.)
Jede unnötige Fahrt kostet Sprit, Zeit und CO₂. Überfüllte Container ärgern Bürger. Der Disponent
entscheidet heute aus dem Bauchgefühl, weil Füllstandsdaten nicht in Routen übersetzt werden.

### 3. Was wir sparen (60 Sek.) — Demo

| Kennzahl | Wert |
|---|---|
| Kritische Container heute | 169 |
| Tour: 25 Stopps | **119,75 km** |
| Volle Runde: 431 Stopps | 157,72 km |
| **Ersparte Strecke** | **37,97 km = 24,1 %** |
| Fahrzeuge | 2 |
| Schichtstunden | 8,52 h (Limit 8,0 h) |
| Sammelmenge | 41,8 t |

**Saisonalität** (Anteil `overfull` je Monat, aus den Rohdaten):

| Jan | Feb | **Mär** | Apr | Mai | Jun | Jul | Aug |
|---|---|---|---|---|---|---|---|
| 11,6 % | 12,9 % | **37,6 %** | 23,3 % | 22,7 % | 5,2 % | 5,0 % | 2,8 % |

→ Planung muss **material- und standortspezifisch** sein: Weißglas im Frühjahr, Sommer anders.

### 4. Wie funktioniert's (40 Sek.)
Ingest → Features (letzter Füllstand, Füllrate, Overfull-Quote, Saison) → Kritikalitäts-Score →
Routing (Nearest-Neighbor, Haversine, ein Fahrzeug, Kapazitäts-/Schicht-/Umschlaggrenzen) →
**Freigabe** → Export.

### 5. Umsetzung (30 Sek.)
- Läuft auf den vorhandenen Fillinq-Daten, ein Fahrzeug genügt.
- Python-CLI, modular, Betriebsvariablen in Config-Datei statt im Code.
- Austauschpfad: echte Koordinaten als `Location_id,lat,lon` → `scripts/refresh_locations.py --real`.
- **Human-Agent-Interface:** Der Agent *schlägt* vor, die Disponentin *gibt frei*. Ohne Freigabe wird
  nichts dispatcht. Jede Entscheidung wird als Beleg protokolliert.

---

## Live-Demo

```bash
prezero-route run --date 2026-04-15
prezero-route propose
prezero-route approve --by "Disponentin (Heilbronn)"
```

Erwartete Ausgabe:

```
Pipeline complete for 2026-04-15: 169 critical locations (213 pairs).
119.75 km planned (25 stops) vs. 157.72 km full round (431 stops)
```

```
Route proposal for 2026-04-15
  stops: 25 | planned: 119.75 km | saved: 37.97 km (24.1 %)
  vehicles: 2 | shift hours: 8.52 | collected: 41.8 t
Nothing is dispatched until a dispatcher approves it.

Route approved by Disponentin (Heilbronn)
Record written to data/processed/approval_2026-04-15.json
```

Artefakte: `route_2026-04-15.json`, `map_2026-04-15.html`, `trends.png`,
`data/processed/approval_2026-04-15.json`.

---

## Offene Punkte — aktiv ansprechen

| Punkt | Stand |
|---|---|
| Echte PreZero-Koordinaten | fehlen → 126 OSM-Standorte, Zuordnung `low`/`UNVERIFIED`, Rest Platzhalter |
| Route ist Luftlinien-Näherung | Umwegfaktor 1,35, kein Straßenrouting |
| 24,1 % | Bedarfs-Ersparnis vs. volle Runde, **keine** Routing-Effizienz |
| Flottenoptimum | gezeigt: 2 Fahrzeuge nötig und wie sie verteilt werden |

---

## Prognosekarte mit Wochenauswahl — offen

Der Stakeholder will eine **Prognosekarte mit Wochenauswahl** sehen. Frage an Samuel: soll Zed das
als Nächstes bauen?

**Einschätzung, bevor gebaut wird:**

- **Was es geben müsste:** Karte mit Container-Standorten, eingefärbt nach prognostiziertem Füllstand
  für einen gewählten Wochentag, plus eine Wochen-Auswahl (Mo–So).
- **Was die Daten hergeben:** `scored_<date>.csv` hat bereits `season_factor` und `avg_daily_increase`
  je Container. Eine Wochentags-Prognose ist also rechnerisch möglich — ohne neues ML.
- **Risiko:** Genau das ist der Bereich, in dem letzte Nacht Zeit versickert. Ein zweites
  Prognosemodell neben der Kernpipeline ist Scope-Creep.
- **Vorschlag:** Wenn ja, dann als **kleine Erweiterung der bestehenden Map** (ein Wochentags-Dropdown
  über der vorhandenen `map_<date>.html`), nicht als neue Visualisierung. Scope: ~1 h, kein neues
  Modul. Erst wenn der Kern-Pitch (Abschnitt 1–5) durch ist.

**Entscheidung: offen — wartet auf Samuel.**

