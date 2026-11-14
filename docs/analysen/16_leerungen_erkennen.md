# 16 – Mögliche Leerungen identifizieren

> Von 10.363 Messübergängen sind 936 (9,0 %) negative Sprünge ≥ 40 pp mit Zielwert ≤ 40 % — arbeitsdefinitorisch Leerungen; sie treffen 712 der 1.338 Zeitreihen, der Median-Abstand zwischen zwei rekonstruierten Leerungen derselben Reihe beträgt 81 Tage.

## Frage

Welche negativen Sprünge sind hinreichend groß, um als Leerung (oder Sensorreset) zu gelten? Wie viele Leerungen lassen sich daraus rekonstruieren, wie verteilen sie sich auf Material, Monat und Zeitreihe — und welcher Leerungstakt folgt daraus?

## Vorgehen

- Datenbasis: `../glass_fill_levels_anonymized_f.csv`, 11.701 Messungen, 1.338 Standort-/Material-Zeitreihen; `overfull` als 110 % kodiert (tatsächliche Höhe unbekannt).
- Je Zeitreihe nach Datum sortiert; **Übergang** = zwei aufeinanderfolgende Messungen derselben Reihe → 10.363 Übergänge. **Sprung** = Füllstand neu − Füllstand alt. 4.266 Übergänge (41,2 %) sind negativ.
- **Schwellenvergleich:** negative Sprünge ≤ −20, −30, −40, −50, −60 pp. Je Schwelle: Ereignisse, Anteil aller Übergänge, betroffene Zeitreihen, Zielwertverteilung (Füllstand direkt nach dem Sprung).
- **Plausibilitätsprüfung −30 pp:** Anteil Ereignisse mit Zielwert < 30 % (echte Leerung) gegen Anteil mit Zielwert > 50 % (eher Teilentleerung, Sensorreset oder Messfehler).
- **Arbeitsdefinition:** Sprung ≤ −40 pp **und** Zielwert ≤ 40 %. Begründung: −30 lässt ein Drittel der Fälle halbvoll stehen, −50 verwirft Sprünge von 60 % auf 20 %.
- Kennzahlen: Ereignisse gesamt, je Material, je Monat (Messdatum, normalisiert auf 100 Messungen), je Zeitreihe, Exposition in Zeitreihen-Jahren (Summe der Beobachtungsfenster = 1.011).
- **Abstände** zwischen zwei rekonstruierten Leerungen derselben Reihe (nur Reihen mit ≥ 2 Ereignissen). Zusätzlich Bündelung auf Standort-Ebene (gleiches Datum, gleiche `Location_id`).

## Ergebnisse

**1. Schwellenvergleich** (Basis 10.363 Übergänge, 1.338 Zeitreihen):

| Schwelle | Ereignisse | Anteil Übergänge | betroffene Reihen | Anteil aller Reihen | Median Zielwert |
|---|---|---|---|---|---|
| ≤ −20 pp | 3.083 | 29,7 % | 1.180 | 88,2 % | 50 % |
| ≤ −30 pp | 2.148 | 20,7 % | 1.075 | 80,3 % | 40 % |
| ≤ −40 pp | 1.501 | 14,5 % | 933 | 69,7 % | 40 % |
| ≤ −50 pp | 983 | 9,5 % | 730 | 54,6 % | 30 % |
| ≤ −60 pp | 614 | 5,9 % | 521 | 38,9 % | 30 % |

Die Sprunghöhen selbst sind unten stark besetzt: −10 pp 1.183-mal, −20 pp 935-mal (zusammen 49,6 % aller negativen Sprünge), −40 pp 518-mal, −100 pp nur 11-mal.

**2. Plausibilität der Schwellen** (Zielwert direkt nach dem Sprung):

| Schwelle | Zielwert < 30 % | Zielwert ≤ 40 % | Zielwert > 50 % | Median |
|---|---|---|---|---|
| ≤ −20 pp | 19,0 % | 49,0 % | 39,8 % | 50 % |
| ≤ −30 pp | 19,5 % | 54,4 % | 32,3 % | 40 % |
| ≤ −40 pp | 22,4 % | 62,4 % | 23,2 % | 40 % |
| ≤ −50 pp | 27,0 % | 73,4 % | 10,8 % | 30 % |
| ≤ −60 pp | 35,5 % | 88,8 % | 0,0 % | 30 % |

Bei −30 pp landen 694 von 2.148 Ereignissen (32,3 %) über 50 % — ein Behälter, der von 80 % auf 60 % fällt, war nicht geleert. Nur 419 (19,5 %) enden unter 30 %. Bei −40 pp sinkt der unplausible Anteil auf 23,2 %, und 62,4 % enden bei ≤ 40 %.

**3. Sensitivität der Arbeitsdefinition** (Ereignisse / Zeitreihen):

| Definition | Ereignisse | Anteil | Reihen |
|---|---|---|---|
| ≤ −30 **und** ≤ 40 % | 1.168 | 11,3 % | 813 |
| **≤ −40 und ≤ 40 % (gewählt)** | **936** | **9,0 %** | **712** |
| ≤ −50 und ≤ 40 % | 722 | 7,0 % | 585 |
| ≤ −40 und ≤ 30 % | 638 | 6,2 % | 523 |
| nur ≤ −40 (ohne Zielwert) | 1.501 | 14,5 % | 933 |

**4. Rekonstruierte Leerungen: 936** (= 21,9 % aller negativen Sprünge), Median Sprunghöhe −60 pp, Mittel −60,1 pp. Verteilung der Sprunghöhen: −100 11 · −90 46 · −80 114 · −70 203 · −60 171 · −50 177 · −40 214.

| Material | Zeitreihen | Ereignisse | Anteil | je Zeitreihe | je Zeitreihe·Jahr |
|---|---|---|---|---|---|
| braun | 442 | 316 | 33,8 % | 0,71 | 0,98 |
| grün | 448 | 370 | 39,5 % | 0,83 | 1,08 |
| weiß | 448 | 250 | 26,7 % | 0,56 | 0,72 |
| gesamt | 1.338 | 936 | 100 % | 0,70 | 0,93 |

Je Zeitreihe: 532 Reihen mit genau 1 Ereignis, 146 mit 2, 28 mit 3, 5 mit 4, 1 mit 8 (Median 1,0; Mittel 1,31 bei den 712 betroffenen). **626 Reihen (46,8 %) zeigen kein einziges Ereignis**, darunter auch gut beobachtete: von den 708 Reihen mit ≥ 8 Messungen bleiben 249 ohne Befund.

| Monat | Messungen | Leerungen | je 100 Messungen |
|---|---|---|---|
| 2025-10 | 741 | 2 | 0,3 |
| 2025-11 | 656 | 6 | 0,9 |
| 2025-12 | 1.357 | 45 | 3,3 |
| 2026-01 | 783 | 23 | 2,9 |
| 2026-02 | 657 | 27 | 4,1 |
| 2026-03 | 776 | 39 | 5,0 |
| 2026-04 | 896 | 46 | 5,1 |
| 2026-05 | 951 | 128 | 13,5 |
| 2026-06 | 1.501 | 316 | 21,1 |
| 2026-07 | 1.310 | 130 | 9,9 |
| 2026-08 | 1.215 | 121 | 10,0 |
| 2026-09 | 858 | 53 | 6,2 |

**5. Abstände zwischen zwei rekonstruierten Leerungen** (180 Reihen mit ≥ 2 Ereignissen, 224 Abstände):

| Kennzahl | Tage |
|---|---|
| Q1 | 52,8 |
| Median | 81 |
| Q3 | 117 |
| p90 | 153,7 |
| Max | 280 |

Verteilung: ≤ 30 d 15 · 31–45 d 25 · 46–60 d 31 · 61–90 d 63 · 91–120 d 40 · 121–180 d 37 · > 180 d 13. Je Material: braun Median 88 d (Q1 59 · Q3 136), grün 78 d (46 · 110), weiß 79 d (60 · 100). In den 34 Reihen mit ≥ 3 Ereignissen (78 Abstände) liegt der Median bei 70 d.

**6. Bündelung auf Standort-Ebene:** Die 936 Material-Ereignisse fallen auf 746 verschiedene Standort-Datum-Paare (587-mal ein Material, 128-mal zwei, 31-mal drei) in 370 der 449 Standorte. Bei gemeinsamer Anfahrt bleibt also ein Rest von **746 Terminen**, nicht 936.

**7. Zehn Beispiel-Zeitreihen** (IDs gekürzt):

| Reihe | Material | Datum | vorher → nachher | Sprung | Abstand zur Vormessung |
|---|---|---|---|---|---|
| `0004c095` | weiß | 2026-06-16 | 110 → 10 | −100 pp | 7 d |
| `734f7e77` | weiß | 2026-07-02 | 110 → 10 | −100 pp | 35 d |
| `1bb9643a` | weiß | 2025-12-24 | 90 → 40 | −50 pp | 26 d |
| `c7914b38` | grün | 2026-05-05 | 110 → 20 | −90 pp | 54 d |
| `62a30c59` | grün | 2026-03-11 | 110 → 40 | −70 pp | 15 d |
| `de821fab` | grün | 2026-09-30 | 90 → 40 | −50 pp | 42 d |
| `2f09e55b` | braun | 2026-07-13 | 110 → 10 | −100 pp | 119 d |
| `f944c52b` | braun | 2026-06-06 | 110 → 10 | −100 pp | 32 d |
| `2601fed9` | braun | 2026-07-29 | 90 → 20 | −70 pp | 100 d |
| `fd2c8a46` | braun | 2026-02-03 | 80 → 30 | −50 pp | 48 d |

## Interpretation

- **−30 pp ist zu weich.** Ein Drittel dieser Sprünge endet über 50 %; solche Behälter waren offensichtlich nicht geleert, sondern wurden teilentleert, umgestellt oder falsch gemessen. Die Schwelle markiert allein 2.148 Sprünge, davon 694 mit Zielwert über 50 %. Mit der Zielwertgrenze ≤ 40 % bleiben 1.168 — 232 mehr als bei −40 pp, überwiegend Sprünge von 40–60 % auf 0–20 %, die auch eine Teilentleerung sein können.
- **−60 pp ist zu hart**, weil sie nur Sprünge aus ≥ 70 % zulässt und damit kürzlich geleerte, niedrig gefüllte Behälter systematisch ausschließt (0 % Zielwerte über 50 % zeigt die Schieflage).
- **≤ −40 pp und Zielwert ≤ 40 %** ist der beste Kompromiss: 62,4 % der Treffer enden in einem Bereich, der zu einem geleerten Glascontainer passt, und die Fallzahl bleibt mit 936 groß genug für Gruppenvergleiche.
- **Der implizite Leerungstakt ist 81 Tage** — das ist rund dreimal der Median-Messabstand (28 Tage). Das ist kein Betriebstakt, sondern ein **Detektionstakt**: Zwischen zwei Messungen können mehrere Leerungen liegen, ohne Spuren zu hinterlassen.
- **0,93 Ereignisse je Zeitreihe und Jahr** ist für Glaskontainer deutlich zu niedrig. Realistische Sammelfrequenzen liegen im Bereich weniger Wochen; die Sensorreihe erfasst also nur die Leerungen, die zufällig zwischen zwei weit auseinanderliegenden Messungen als großer Sprung sichtbar werden.
- **Der Juni-2026-Gipfel (316 Ereignisse, 21,1 je 100 Messungen)** ist mit hoher Wahrscheinlichkeit ein Beobachtungsartefakt: In diesem Monat liegen auch die meisten Messungen (1.501), und viele Reihen treten erst im Frühjahr in die Beobachtung ein. Die Monatszahlen sind deshalb nur als messdichte-normierte Größe lesbar, nicht als echte Einsatzplanung.
- **Braun wird am seltensten als geleert erkannt** (0,72 je Reihe·Jahr), obwohl braunes Glas die niedrigsten Füllstände hat. Das passt dazu, dass kleine Behälter nach der Leerung rasch wieder niedrig stehen und der Sprung dann unter der Schwelle bleibt.
- **746 statt 936 Termine** auf Standort-Ebene: Ein Teil der Material-Ereignisse ist dieselbe Anfahrt. Wer Touren zählen will, muss auf Standort-Datum aggregieren.

## Grenzen

- **Leerungen sind nicht beobachtet.** Jede Zahl hier ist eine Rekonstruktion aus Sprüngen; die CSV enthält kein Leerungsprotokoll, keinen Sensor-Reset-Flag und keine Behältergröße. Kausalität ist nicht belegbar.
- **Zeitliche Auflösung begrenzt die Detektion.** Bei Median 28 Tagen zwischen zwei Messungen (Mittel der Reihen-Mediane 44,9 Tage) ist jede Leerung zwischen zwei Terminen unsichtbar. Die 936 Ereignisse sind eine **Untergrenze**, der 81-Tage-Takt eine Obergrenze des wahren Takts.
- **Kategoriale Skala:** 10-pp-Schritte, `overfull` nur als 110 codiert. Ein Sprung 110 → 40 ist als −70 pp verbucht, die tatsächliche Höhe (z. B. 120 %) ist unbekannt; Sprunghöhen sind also um bis zu 10 pp unscharf.
- **`Location_id` ist ein Standort, kein Container.** Ein Sprung kann einen Behältertausch, eine Umstellung oder einen Sensorreset abbilden; das ist von einer Leerung nicht unterscheidbar.
- **Monatsvergleich ist verzerrt:** Die gemessene Teilmenge schwankt stark (657 bis 1.501 Messungen je Monat), Reihen starten zu unterschiedlichen Zeitpunkten. Die Normierung auf 100 Messungen mildert, beseitigt das aber nicht.
- **626 Reihen ohne Ereignis** sind nicht gleichbedeutend mit „nie geleert": Bei 1–3 Messungen (179 Reihen) ist ein Sprung praktisch nicht beobachtbar.
- 936 Ereignisse bei 10.363 Übergängen heißt: 91,0 % der Übergänge tragen keine Leerungsinformation. Jede Takt-Aussage beruht auf den 9,0 % mit Signal.

## Nächster Schritt

Ein reales Leerungsprotokoll (Zeitstempel je Standort und Material, mindestens vier Wochen) beschaffen und gegen die 936 rekonstruierten Ereignisse matchen — daraus lässt sich die Trefferquote der −40-pp-Regel und der wahre Leerungstakt direkt messen, statt ihn zu schätzen.
