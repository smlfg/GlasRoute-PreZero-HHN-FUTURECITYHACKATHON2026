# Pitch-Fallback — die Tour offline zeigen, ohne laufenden Rechner

**Wofür:** Wenn im Pitch der Laptop streikt, das WLAN weg ist oder die Pipeline nicht startet,
zeigen wir die **fertige Demo-Tour des 15.04.2026** aus diesem Ordner. Alles hier ist ein
Standbild aus dem Lauf `prezero-route run --date 2026-04-15`.
Beleg: `Projek-Management/proof/demo_day_numbers.json` und `Projek-Management/proof/A3_pitch_zahlen.txt`
(`RESULT: ALL MATCH`).

## Was hier liegt

| Datei | Inhalt |
|---|---|
| `route_2026-04-15.json` | Die Tour vollständig maschinenlesbar: alle Stops in Reihenfolge, je Fahrzeug und Runde, Entladungen, km, Lasten, Schichten und **alle 11 Annahmen** unter `assumptions` |
| `stops_2026-04-15.csv` | Dieselbe Tour als Tabelle: 38 Datenzeilen (39 mit Kopfzeile) — 25 Sammelstopps (`collection`) + 13 Entladungen (`unload`). Zum Öffnen in Excel, Numbers, LibreOffice oder einem Texteditor |

**Kernzahlen des Standbilds:** 25 Stopps · **227,2 km** · **3 Fahrzeuge** · 16 Runden ·
19,9 h Fahrzeugstunden gesamt · längste Schicht **7,96 h** (Limit 8 h) · **116,2 t** —
von 127 fälligen Standorten, 102 bleiben offen (Stopp-Limit 25).

## So zeigen wir die Tour offline

1. **Reihenfolge zeigen** — `stops_2026-04-15.csv` in Excel/Numbers/LibreOffice öffnen.
   Spalte `order` = die Fahrreihenfolge, `vehicle` = welches Fahrzeug, `round` = welche Runde.
   Die Runden je Fahrzeug: Fahrzeug 1 → 7, 2 → 6, 3 → 3 (zusammen 16).
   Nach `order` sortieren, das ist die Abfahrtsreihenfolge.
2. **Standorte zeigen** — Spalten `lat` / `lon` (z. B. `49.13366` / `9.217192`) sind die
   Koordinaten jedes Stopps. Für die Karte brauchen wir **Internet** (siehe unten); ohne Karte
   zeigen wir die Koordinaten und die Reihenfolge direkt aus der Tabelle.
3. **Was mitgenommen wird** — `primary_material` (braun / grün), `critical_bins` (Anzahl
   Container je Standort), `est_fill_level` (geschätzter Füllstand in %), `mass_kg` (Tonnen
   je Stopp), `load_kg` (aktuelle Fahrzeuglast), `leg_km` und `cumulative_km` (Strecke).
4. **Grenzen ehrlich benennen** — `source` / `confidence`: alle Standorte sind echte
   OSM-Glascontainer in Heilbronn, aber die **Zuordnung zu den anonymisierten IDs ist simuliert**
   (`osm_assigned` / `simulated_mapping`). Die angefahrenen Punkte sind also keine von PreZero
   bestätigten Containerplätze.

## Die Website

Im Repo-Root liegt `index.html` (Symlink auf `ui_2026-04-15.html`) — **ein Doppelklick genügt**,
kein Server, kein Netzwerk für die Seite selbst. Die Website läuft offline mit allen Tabs,
Tabellen und Kennzahlen.

**Nur die Kartenkacheln brauchen Internet:** Sie kommen von OpenStreetMap. Ohne Internet
bleiben die Karten leer, **alle Zahlen und Tabellen bleiben da**. Deshalb im Pitch den Tab
„Route & Freigabe“ und „Fairer Vergleich“ zeigen und die Karte nur ergänzen, wenn das WLAN steht.

## Noch von Hand zu ergänzen: Screenshots der 11 Tabs (1 Bild pro Tab)

> **Platzhalter — hier fehlen noch Bilder.** Für **jeden** Tab der Website ein Screenshot in
> diesen Ordner legen (PNG oder JPG), dazu eine einzeilige Bildunterschrift, die die im Bild
> sichtbare Kernaussage nennt. In dieser Session war kein Browser-Tool verfügbar, deshalb sind
> **bewusst keine Bilddateien und keine Platzhalter-Bilder erzeugt worden** — nichts zu erfinden.
>
> **Tab-Reihenfolge der Website (Stand 15.11.2026, `ui_2026-04-15.html`):** Die Website hat
> **11 Tabs** (Copilot- und Standortplanungs-Tab kamen später hinzu). Pro Tab ein Bild, also
> 11 Bilder:
> 1. Daten · 2. Forecast-Timeline · 3. Heatmap · 4. Route & Freigabe · 5. Copilot ·
> 6. Variablen · 7. Fairer Vergleich · 8. Datencheck · 9. Upload · 10. Standortplanung ·
> 11. Bisher vs. Optimiert.
>
> Für die Bilder reicht ein normales Browserfenster (Screenshot-Tool des Systems) — die Tabs
> lassen sich ohne Pipeline durchklicken. Was je Tab zu zeigen ist, steht in `Pitch/NOTES.md`
> (Abschnitt „Live-Demo“) und in `docs/UI_PLAN.md`.
