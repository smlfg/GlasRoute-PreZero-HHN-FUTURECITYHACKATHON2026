# Pitch – PreZero Route

Dauer: ca. 3 Minuten.

## 1. Problem

Glascontainer in Heilbronn werden nach festem Plan geleert. Laster fahren zu halbleeren Containern, während andere überlaufen.

## 2. Warum lösen?

Jede unnötige Fahrt kostet Sprit, Zeit und CO₂. Überfüllte Container ärgern Bürger und verschmutzen die Stadt.

## 3. Gewinn (Zahlen aus den Daten)

- 11.701 Messungen, 449 Container, 1.192 `overfull`-Ereignisse.
- Weißglas füllt sich schneller als braun/grün.
- Saisonaler Peak Januar–April, Einbruch Juni/Sommer.
- Mit unserem Tool fährt das Entsorgungsfahrzeug nur noch die Container an, die wirklich geleert werden müssen.

## 4. So funktioniert es

1. Füllstände einlesen.
2. Muster erkennen (Material, Standort, Saison).
3. Kritikalitäts-Score berechnen.
4. Agent schlägt Route vor.
5. Disponent gibt Freigabe.

## 5. Umsetzung

- Baut auf den vorhandenen Fillinq-Daten auf.
- Startet mit einem Fahrzeug.
- CLI-basiert, modular, skalierbar.
- Platzhalter-Koordinaten sind gegen echte austauschbar.

## Demo-Szenario

> „Heute, 15.04.2026: 12 Container sind kritisch. Statt einer festen Tour über 40 Container schlägt der Agent 12 Stopps vor. Hier ist die Karte, hier die Reihenfolge, hier die Freigabe."
o
