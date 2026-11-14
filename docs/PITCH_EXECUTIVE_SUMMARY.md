# Pitch Executive Summary

## Problem

Die Füllstände sind material- und saisonabhängig; ein einheitlicher Leerungsturnus behandelt daher ungleich belastete Standorte gleich. Gleichzeitig sind die Messungen unregelmäßig, Leerungsereignisse nicht markiert und Überfüllungen nur als `overfull` ohne tatsächliche Höhe erfasst.

## Datenbasis

Die CSV umfasst 11.701 Messungen von 449 anonymisierten Standorten in 1.338 Standort-/Material-Zeitreihen zwischen 17.10.2025 und 30.09.2026, mit 229 Messtagen und drei Materialtypen.

## Drei Kernaussagen

1. **Weißglas ist der Haupttreiber:** 66,4 % der Weißglas-Messungen liegen bei mindestens 80 %, gegenüber 14,7 % bei Braun.
2. **Die Belastung ist saisonal:** Das Gesamtmittel reicht von 52,4 % im Juni bis 84,6 % im März.
3. **Prognose ist möglich, aber begrenzt:** Der Material-Median erreicht 66,3 % der Vorhersagen innerhalb von ±20 Prozentpunkten (MAE 21,0 pp).

## Drei operative Hebel

- **Intervalle:** Material- und risikobasierte Intervalle statt eines festen Turnus; als Startpunkt nennt Analyse 07 80 % für Weiß, 70 % für Grün und 60 % für Braun.
- **Materialschwellen:** Weißglas priorisieren; 61,3 % aller `overfull`-Messungen entfallen auf Weißglas.
- **Kapazität:** Behältergrößen und Tourkapazität an der Materiallast ausrichten; 74,8 % der Standorte hatten mindestens eine `overfull`-Messung.

## Fehlende Daten: Blocker

- Welche dokumentierten Leerungsereignisse (Datum, Standort, Material, Menge) gab es je Messung?
- Welche realen Containerkapazitäten, Behältergrößen und Fahrzeugkapazitäten gelten?
- Welche echten Adressen/Koordinaten, Touren und Zeitfenster gelten für die Standorte?

## Kernaussage für den Pitch

> Die CSV zeigt das Verhalten. Standortdaten liefern den Kontext. Erst beides
> zusammen macht aus einer Füllstandsanalyse eine operative
> Tourenentscheidung.
