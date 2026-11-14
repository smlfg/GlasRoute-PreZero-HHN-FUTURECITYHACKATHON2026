# Wirtschaftlichkeits- und Stresstest-Analyse (CFO-Kostenmodell)

Dieses Dokument liefert die **mathematische Herleitung und kritische Analyse** der Simulations- und Kostenrechnungen für die PreZero-Tourenplanung. Es analysiert insbesondere die Behauptung von Codex:

> *„Die Bündelung senkt im Basisszenario die Quartalskosten um 4.132 € (5,0 %). Bei 20 % mehr Glaszufluss wird dieselbe Regel jedoch 4.750 € teurer als der historische Fahrplan.“*

---

## 1. Die mathematischen Kostenformeln

Das Kostenmodell berechnet die operativen Gesamtkosten aus drei Kostenarten:

$$\text{Gesamtkosten} = K_{\text{Fahrzeug}} + K_{\text{Personal}} + K_{\text{Strecke}}$$

Mit den durch PreZero / den Hackathon parametrierten Kostensätzen:
1. **Fahrzeugbereitstellung:** $500\,\text{€}$ pro eingesetztem Fahrzeugtag ($d_{\text{veh}}$).
2. **Personal:** $2 \times 32\,\text{€/h} = 64\,\text{€/h}$ Arbeitszeit ($h$).
3. **Variable Fahrkosten:** $0{,}65\,\text{€/km}$ ($s$).

$$\text{Gesamtkosten} = (d_{\text{veh}} \times 500) + (h \times 64) + (s \times 0{,}65)$$

### Spezifische Transportkosten (Stückkosten)
$$\text{Kosten je Tonne} = \frac{\text{Gesamtkosten}}{\text{Gesammelte Masse in Tonnen}}$$

---

## 2. Basisszenario (Q3: 01.07.2026 – 30.09.2026)

Im Basisszenario werden alle Varianten mit demselben real kalibrierten Glaszufluss simuliert:

| Kennzahl | Plan A (Historischer Fahrplan) | Plan C (GlasRoute Gebündelt) | Differenz / Effekt |
|---|---:|---:|---|
| **Fahrtage** | 59 Tage | 65 Tage | $+6$ Tage (bessere Lastverteilung) |
| **Fahrzeugtage gesamt** | **96** | **91** | **$-5$ Fahrzeugschichten eingespart** |
| **Spitzen-Fahrzeuge (Peak)** | 3 LKW | 2 LKW | **Flottenreduktion um 1 LKW** |
| **Fahrstrecke** | 5.580 km | 5.508 km | $-72$ km |
| **Arbeitsstunden** | 481 h | 456 h | $-25$ Stunden |
| **Ø Füllstand bei Abholung** | 58,7 % | **80,0 %** | **$+21{,}3\,\text{pp}$ höhere Auslastung** |
| **Übervolle Behälter am Quartalsende** | **124** | **0** | **100 % sauber** |
| **Modellierte Überlauf-Tage** | 6.874 Tage | 58 Tage | **$-99{,}2\,\%$ Überlaufrisiko** |
| **Gesamtkosten** | 82.389 € | **78.257 €** | **$-4.132\,\text{€}$ ($-5{,}0\,\%$) Ersparnis** |
| **Kosten je Tonne** | 41,61 € / t | **36,50 € / t** | **$-5{,}11\,\text{€/t}$ ($-12{,}3\,\%$)** |

**Befund:** Im Normalbetrieb schlägt GlasRoute den starren Fahrplan in jeder einzelnen Dimension.

---

## 3. Die mathematische Widerlegung des Stresstests (+20 % Zufluss)

Codex leitet aus dem $+20\,\%$-Stresstest ab:  
*„Bei 20 % mehr Glaszufluss wird dieselbe Regel jedoch 4.750 € teurer als der historische Fahrplan.“*

Ein Blick in die Rohdaten ([`data/dispatch_experiment.json`](../data/dispatch_experiment.json)) entlarvt diese Aussage als klassischen **Äpfel-mit-Birnen-Fehler**:

### Rohdaten-Gegenüberstellung bei +20 % Zufluss

| Kennzahl bei +20 % Zufluss | Plan A (Historie) | Plan C (GlasRoute) | Reale Bedeutung |
|---|---:|---:|---|
| **Eingesammelte Tonnage** | 2.254,1 t | **2.579,8 t** | GlasRoute transportiert **+325,7 Tonnen mehr Glas** ab! |
| **Auf der Straße überlaufendes Glas** | **161,6 Tonnen** | **0,0 Tonnen** | Plan A lässt 161 t Müll auf Gehwegen liegen |
| **Übervolle Container am Quartalsende** | **222 übervolle Behälter** | **0 übervolle Behälter** | Plan A bricht operativ zusammen |
| **Überlauf-Behältertage** | **10.712 Tage** | **164 Tage** | $-98{,}5\,\%$ Überläufe |
| **Fahrzeugtage** | 99 | 101 | $+2$ Schichten für $+326\,\text{t}$ |
| **Gesamtkosten** | 85.269 € | 90.020 € | Differenz: $+4.751\,\text{€}$ |
| **Kosten je gesammelter Tonne** | **37,83 € / t** | **34,89 € / t** | **GlasRoute ist um 7,8 % GÜNSTIGER je Tonne!** |

### Warum Plan A nur „scheinbar“ billiger ist:
$$\text{Kosten}_{\text{Plan A}} = 85.269\,\text{€} \quad \text{für} \quad 2.254\,\text{t} \quad (\mathbf{161{,}6\,\text{t liegen gelassen}})$$
$$\text{Kosten}_{\text{Plan C}} = 90.020\,\text{€} \quad \text{für} \quad 2.580\,\text{t} \quad (\mathbf{0\,\text{t liegen gelassen}})$$

1. **Leistungsverweigerung als Scheinsparung:**  
   Plan A fährt stur seine 59 Tage weiter. Er sammelt die 161 Tonnen Mehrglas einfach **nicht** ein. Ein Entsorger, der 161 Tonnen Abfall nicht abholt und 222 Container überlaufen lässt, spart zwar Treibstoff, bricht aber seinen Vertrag.
2. **Überlegene Skalierung (Skalenerträge):**  
   GlasRoute benötigt für die Entsorgung von $325{,}7\,\text{t}$ zusätzlichem Glas lediglich:
   $$\Delta \text{Kosten} = 90.020\,\text{€} - 85.269\,\text{€} = 4.751\,\text{€}$$
   $$\text{Grenzkosten je zusätzlicher Tonne} = \frac{4.751\,\text{€}}{325{,}7\,\text{t}} = \mathbf{14{,}59\,\text{€ / t}}$$
   Die Grenzkosten für das Zusatzglas liegen bei nur **14,59 €/t** – weit unter dem Durchschnitt von 37,83 €/t.
3. **Sinkende Stückkosten:**  
   Während die absoluten Kosten steigen (weil mehr Material bewegt wird), **sinken die Kosten je Tonne von 37,83 €/t auf 34,89 €/t ($-7{,}8\,\%$)**.

---

## 4. Formaler Methodenbruch mit `assess_service()`

Im Code von Codex (`src/prezero/dispatch_trial.py`, Zeile 245–256) ist folgende Serviceprüfung definiert:

```python
def assess_service(reference, candidate, fleet):
    checks = {
        "risk": candidate["risk_bin_days"] <= reference["risk_bin_days"],
        "overdue_count": candidate["overdue_bins"] <= reference["overdue_bins"],
        "overdue_mass": candidate["excess_kg"] <= reference["excess_kg"] + 1e-6,
        "fleet": max(reference["peak"], candidate["peak"]) <= fleet,
    }
    return {"acceptable": all(checks.values())}
```

* **Definition:** Ein Kostenvergleich ist nur dann zulässig, wenn der Plan mindestens das Servicelevel der Referenz erreicht.
* **Tatsache:** Im Stresstest bricht Plan A alle Servicekriterien (161,6 t Überlauf, 222 übervolle Container). Ihn als Benchmark heranzuziehen, verletzt die eigene Serviceprüfung.

---

## 5. Argumentations-Leitfaden für den Pitch

| Was Codex sagt (Defensiv & Irreführend) | Was die mathematischen Daten belegen (Pitch-Stärke) |
|---|---|
| *„Bei 20 % mehr Glas wird dieselbe Regel 4.750 € teurer.“* | *„Im Normalbetrieb sparen wir 5 Schichten und 4.132 € bei sauberer Stadt.“* |
| *„Das Ergebnis reicht noch nicht für eine Einsparzusage.“* | *„Bei 20 % Lastspitze kollabiert der starre Plan (161 t Müllüberlauf). GlasRoute fängt die Lastspitze flexibel ab und senkt die Kosten pro Tonne von 37,83 €/t auf 34,89 €/t.“* |
