# Backtest: Ist der Füllstand vorhersagbar?

Frage des Stakeholders: „es kann auch sein, dass alle Werte wirklich komplett random ist“.

**Vorgehen (walk-forward, ohne Blick in die Zukunft):** Für jeden Besuch eines Containers
(Standort × Glasfarbe), vor dem es schon mindestens ein Intervall gab, wird der Füllstand, den
der Fahrer vorfinden wird, **nur aus den Besuchen davor** vorhergesagt und mit der echten
Messung verglichen. 9059 Besuche in 1257 Containern.
46.3 % der Besuche fanden den Container ≥ 80 % voll vor.

## Kurzantwort

**Nicht zufällig.** Das Timer-Modell sagt den vorgefundenen Füllstand mit 19.9 pp Fehler voraus, „Durchschnitt bisher“ mit 22.3 pp. Wenn das Modell „voll“ sagt, stimmt es in 75.0 % der Fälle (Basis 64.9 %). Die Zeit seit der letzten Leerung trägt also Information.

## Ergebnis

| Methode | Fehler Ø (Prozentpunkte) | Treffer ±20 pp | „voll“ korrekt vorhergesagt (Precision) | volle erkannt (Recall) | Rangkorrelation |
|---|---|---|---|---|---|
| Timer-Modell (Füllrate x Tage) | 19.9 | 63.7 % | 75.0 % | 59.4 % | 0.599 |
| Timer mit altem Saisonfaktor | 26.5 | 47.4 % | 78.7 % | 34.0 % | 0.613 |
| Basis: Durchschnitt bisher | 22.3 | 55.5 % | 64.9 % | 60.8 % | 0.479 |
| Basis: wie letztes Mal | 26.1 | 57.3 % | 60.1 % | 61.8 % | 0.375 |

„voll“ = ≥ 80 %. Die Messwerte sind Schätzungen des Fahrers in 10-%-Stufen;
`overfull` ist als 110 % kodiert (wahre Höhe unbekannt). Ein Fehler unter ca. 10 pp ist deshalb
nicht erreichbar.

## Je Glasfarbe (Fehler Ø in pp)

| Glasfarbe | Timer-Modell | Durchschnitt bisher | wie letztes Mal | volle erkannt (Modell) |
|---|---|---|---|---|
| brown | 21.9 | 22.9 | 26.0 | 40.2 % |
| green | 20.8 | 23.9 | 27.7 | 57.7 % |
| white | 17.9 | 20.3 | 24.7 | 63.7 % |

**Streuung über Container:** Fehler Ø des Modells je Container, Quartile 25 / 50 / 75 %:
13.1 / 19.4 / 27.0 pp. Manche Container sind gut vorhersagbar, andere kaum.


## Passt der heutige Leerungsrhythmus?

Je Container: idealer Abstand = 80 % ÷ Füllrate; tatsächlicher Abstand = Median der Tage zwischen
zwei Besuchen. „zu oft“ = tatsächlich < 0,8 × ideal, „zu selten“ = > 1,2 × ideal.

| Glasfarbe | idealer Abstand (Tage) | tatsächlich (Tage) | zu oft geleert | zu selten geleert |
|---|---|---|---|---|
| Braunglas | 95.4 | 42.0 | 89.1 % | 2.1 % |
| Grünglas | 42.3 | 34.0 | 45.1 % | 6.6 % |
| Weißglas | 32.5 | 33.0 | 12.2 % | 15.8 % |
| **alle** | 48.2 | 35.0 | 48.2 % | 8.3 % |

Bei 30.1 % aller 10363 Besuche war der Container unter 50 % voll (Fahrt zu früh),
bei 11.2 % lief er über. **Braunglas wird viel zu oft geleert**, Weißglas teils zu selten.

## Einordnung

- Ist das Modell besser als „Durchschnitt bisher“, steckt in der Füllrate (Zeit seit der letzten
  Leerung) echte Information. Ist es nicht besser, reicht für die Planung der Mittelwert.
- Ein ML-Modell (z. B. Gradient Boosting mit Wochentag, Ferien, Standortgruppe) ist der nächste
  Schritt, aber erst sinnvoll, wenn diese Basis steht. Bewusst nicht im Hackathon-Scope.

Erzeugt mit `python scripts/backtest.py` aus `data/processed/cleaned_readings.csv`.
