# Mathematische & methodische Prüfung: Codex-Quartalsexperiment (`dispatch_experiment`)

**Geprüfte Quellen (Worktree `prezero-hero-worktree`):**
- `data/dispatch_experiment.json`
- `src/prezero/dispatch_policy.py`
- `src/prezero/dispatch_trial.py`
- `docs/KOSTENMODELL.md`

---

## 1. Rechnerische Prüfung

Alle von Codex genannten Kennzahlen und Commits (`685d702`, `ac0a144`, `4cba9ba`) stimmen exakt mit `data/dispatch_experiment.json` überein:

- **Basisfall (01.07.–30.09.2026):**
  - `A · Historischer Fahrplan`: 59 Fahrtage, 96 Fahrzeugtage, 5.579,7 km, 480,7 h, **1.980,0 t** gesammelt, **82.389,02 €** (`41,61 €/t`), Endbestand `662,3 t`, `124` überfällige Behälter (`100,3 t` Überhang), `6.874` Risiko-Behältertage.
  - `C · Gebündelt`: 65 Fahrtage, 91 Fahrzeugtage, 5.508,3 km, 455,9 h, **2.143,9 t** gesammelt, **78.256,72 €** (`36,50 €/t`), Endbestand `498,4 t`, `0` überfällige Behälter (`0,0 t` Überhang), `58` Risiko-Behältertage.
  - **Differenz (`A − C`):** `4.132,30 €` (`5,0 %`), davon `2.500 €` aus 5 eingesparten Fahrzeugtagen (`5 × 500 €`) und `1.632,30 €` aus Personal und Kilometern — obwohl `C` gleichzeitig **+163,9 t mehr Glas** abfährt.

---

## 2. Zentraler Denkfehler im Stresstest (+20 % Glaszufluss)

Codex' Hauptwarnung (*„Bei 20 % mehr Glaszufluss wird dieselbe Regel jedoch 4.750 € teurer als der historische Fahrplan“*) vergleicht **ungleiche Sammelleistungen**:

| Kennzahl (`inflow_plus_20_percent`) | A · Historischer Fahrplan | C · Gebündelt | Differenz (`C − A`) |
|---|---:|---:|---:|
| Fahrzeugtage | 99 | 101 | +2 |
| Gesammelte Masse | **2.254,1 t** | **2.579,8 t** | **+325,7 t (+14,4 %)** |
| Endbestand | 827,0 t | 501,3 t | −325,7 t |
| Überfällige Behälter am Ende | **222** (`161,6 t` Überhang) | **0** (`0,0 t` Überhang) | −222 |
| Risiko-Behältertage (`> 100 %`) | **10.712** | **164** | −98,5 % |
| Periodenkosten | 85.269,46 € | 90.019,69 € | **+4.750,23 € (+5,6 %)** |
| **Kosten je gesammelter Tonne** | **37,83 €/t** | **34,89 €/t** | **−2,94 €/t (−7,8 %)** |

**Mathematischer Befund:**
- `A` hält seinen starren Fahrplan (`3.373` Leerungen) bei und ignoriert das zusätzliche Volumen — dadurch bleiben **325,7 t mehr Glas** in `222` überlaufenden Behältern liegen.
- Weil die Kostenformel `0 €` Strafkosten für Überläufe ansetzt, erscheint `A` im Periodensummen-Vergleich künstlich billiger.
- **Normiert auf die tatsächlich geleistete Arbeit (`€/t`) bleibt `C` auch bei +20 % Zufluss um 7,8 % günstiger als `A`.**

---

## 3. Drei weitere Modellgrenzen im Code

1. **Nur ein 2-km-Anker pro Tag (`dispatch_policy.py:36–41`):**
   `manifest()` wählt einen einzigen `anchor` (knappste Restfrist), nimmt stadtweit alle `urgent`-Behälter (`stock + rates * gap > 100`) auf und bündelt `>= 60 %`-Nachbarn nur im 2-km-Radius um diesen *einen* Anker. Bei mehreren Hotspots fehlt die Bündelung um weitere Cluster; durch `[: fleet * 25]` (`75` Hebungen/Tag in `dispatch_trial.py:200`) können 60-%-Nachbarn des ersten Ankers zudem dringende Behälter in anderen Stadtteilen verdrängen.
2. **Perfekte Tages-Sensoren statt 10-%-Schätzung (`dispatch_trial.py:179–207`):**
   `B` und `C` beobachten täglich den exakten kontinuierlichen Modellbestand (`stock[s]`) ohne Messrauschen oder 10-%-Stufen, was die Trennschärfe der `> 100 %`-Auslöseschwelle im Vergleich zur Realität überschätzt.
3. **Konservativer Basisfall:**
   Da `C` bereits im Basisfall **163,9 t mehr** abfährt als `A` und dennoch `4.132 €` weniger kostet, ist der Kostenvorteil im Basisfall **konservativ** gerechnet.

---

## 4. Konsequenz für den Pitch

Die Aussage zum Stresstest darf nicht als *„Bündelung wird bei +20 % Zufluss teurer“* stehen bleiben, sondern korrekt:

> *„Im +20-%-Stresstest fährt die gebündelte Regel 325,7 t (+14,4 %) mehr Glas ab und hält Überläufe bei 0, während der starre Fahrplan 222 Behälter überlaufen lässt. Pro gesammelter Tonne bleibt die Bündelung auch unter Stress 7,8 % günstiger (34,89 €/t vs. 37,83 €/t).“*
