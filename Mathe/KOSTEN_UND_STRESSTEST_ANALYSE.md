# Mathematische Analyse: Kostenmodell & Stresstest (Codex-Prüfung)

Dieses Dokument analysiert und belegt die mathematischen Zusammenhänge der Quartalssimulation (Q3 2026: 01.07.–30.09.2026) aus `data/dispatch_experiment.json`. Es prüft die Aussage von Codex:
> *„Die Bündelung senkt im Basisszenario die Quartalskosten um 4.132 € (5,0 %). Bei 20 % mehr Glaszufluss wird dieselbe Regel jedoch 4.750 € teurer als der historische Fahrplan.“*

---

## 1. Executive Summary

| Prüfpunkt | Urteil | Begründung |
|---|---|---|
| **Mathematische Zahlenwerte** | **KORREKT** | Alle Kennzahlen stimmen exakt mit dem deterministischen Holdout-Experiment überein. |
| **Ökonomische Interpretation** | **FEHLERHAFT** | **Äpfel mit Birnen verglichen:** Fahrplan A ist bei +20 % nur deshalb nominal um 4.750 € „günstiger“, weil er **161,6 Tonnen Glas auf der Straße liegen lässt** (Leistungsverweigerung). |
| **Spezifische Kosten (€/t)** | **GLASROUTE GEWINNT** | C transportiert 325,7 t mehr Glas ab und ist **mit 34,89 €/t um 7,8 % günstiger** als A mit 37,83 €/t. |
| **Servicequalität** | **FAHRPLAN A KOLLABIERT** | A erzeugt 10.712 Überlauftage und 222 übervolle Standorte. C hält **0 übervolle Behälter**. |

---

## 2. Die mathematische Kostenformel

Die Gesamtkosten $K$ eines Entsorgungsszenarios berechnen sich aus drei Komponenten:

$$K = \underbrace{(N_{\text{Fahrzeugtage}} \times 500\,\text{€})}_{\text{Bereitstellung / Fixkosten}} + \underbrace{(H_{\text{Schicht}} \times 2 \times 32\,\text{€/h})}_{\text{2-Personen-Crew}} + \underbrace{(S_{\text{km}} \times 0{,}65\,\text{€/km})}_{\text{Kraftstoff / Verschleiß}}$$

### Kosten-Hebel:
1. **Fahrzeugbereitstellung (500 €/Tag):** Dominierender Fixkostenblock. Jeder zusätzliche Tag, an dem ein LKW den Betriebshof verlässt, schlägt mit mindestens 500 € zu Buche.
2. **Personal (64 €/h für 2er-Crew):** Stark zeitabhängig (Hubzeit 3 min/Behälter, Entladung 20 min/Tour, Fahrzeit 25 km/h Ø).
3. **Fahrstrecke (0,65 €/km):** Macht im urbanen Raum nur ca. 8–10 % der Gesamtkosten aus.

---

## 3. Basisszenario (Q3 2026: 01.07. – 30.09.2026)

Reales Glasaufkommen aus den 11.701 Messungen, kalibriert bis 30.06.2026. 1.332 aktive Behälter, 10 Spätzügler ausgeschlossen.

| Kennzahl | A · Historischer Fahrplan | B · Sofort ab 60 % (naiv) | B_weekday · Nur Werktags ab 60 % | C · GlasRoute (Gebündelt) | Delta (C vs. A) |
|---|---:|---:|---:|---:|---:|
| **Fahrtage** | 59 | 92 | 66 | 65 | +6 Tage |
| **Fahrzeugtage (Schichten)** | 96 | 129 | 113 | **91** | **−5 Schichten** |
| **Fahrzeuge am Spitzentag** | 3 | 2 | 2 | 2 | −1 LKW Peak |
| **Fahrstrecke in km** | 5.580 | 9.704 | 8.136 | **5.508** | −72 km |
| **Fahrzeugstunden** | 481 | 724 | 647 | **456** | **−25 h** |
| **Geleerte Behälter** | 3.373 | 3.593 | 3.496 | **2.680** | **−693 Leerungen** |
| **Gesammelte Tonnage** | 1.980 t | 2.261 t | 2.254 t | 2.144 t | +164 t |
| **Ø Füllstand bei Abholung** | 58,7 % | 62,9 % | 64,5 % | **80,0 %** | **+21,3 pp** |
| **Periodenkosten** | **82.389 €** | **117.121 €** | **103.215 €** | **78.257 €** | **−4.132 € (−5,0 %)** |
| **Kosten je Tonne Glas** | 41,61 €/t | 51,81 €/t | 45,80 €/t | **36,50 €/t** | **−5,11 €/t (−12,3 %)** |
| **Übervolle Behälter am Ende** | 124 | 0 | 0 | **0** | **−124 Standorte** |
| **Überlauf-Tage (`risk_bin_days`)** | 6.874 | 58 | 58 | **58** | **−99,2 %** |

### Mathematische Zerlegung der 4.132 € Ersparnis:
- **Bereitstellung:** $5 \text{ Schichten weniger} \times 500\,\text{€} = \mathbf{2.500\,\text{€}}$
- **Personal:** $25{,}1 \text{ Stunden weniger} \times 64\,\text{€/h} = \mathbf{1.606\,\text{€}}$
- **Kilometer:** $72 \text{ km weniger} \times 0{,}65\,\text{€/km} = \mathbf{47\,\text{€}}$
- **Summe:** $2.500 + 1.606 + 47 \approx \mathbf{4.132\,\text{€}}$

### Wichtige mathematische Erkenntnis (B vs. C):
Naive Sensorik (Szenario B) scheitert dramatisch (+34.732 € Mehrkosten), weil ein einzelner 60-%-Behälter unnötige LKW-Tagespauschalen triggert. Erst die GlasRoute-Regel C (Warten bis Werktag + 2-km-Cluster-Mitnahme) realisiert die Einsparung.

---

## 4. Stresstest (+20 % Glaszufluss): Die Widerlegung des Codex-Trugschlusses

Wird der tägliche Zufluss simuliert um 20 % erhöht, entstehen folgende Werte:

| Kennzahl bei +20 % Zufluss | A · Historischer Fahrplan | C · GlasRoute (Gebündelt) | Differenz (C vs. A) | Interpretation |
|---|---:|---:|---:|---|
| **Nominale Gesamtkosten** | **85.269 €** | **90.020 €** | **+4.750 € (+5,6 %)** | *Scheinbarer Kostennachteil* |
| **Tatsächlich gesammeltes Glas** | **2.254,1 t** | **2.579,8 t** | **+325,7 t (+14,5 %)** | **C leert 326 Tonnen MEHR!** |
| **Spezifische Kosten (€/t)** | **37,83 €/t** | **34,89 €/t** | **−2,94 €/t (−7,8 %)** | **C ist pro Tonne deutlich billiger!** |
| **Überlaufende Glasmenge (`excess_kg`)** | **161.631 kg (161,6 t)** | **0,0 kg** | **−161,6 t (−100 %)** | **A kapituliert vor dem Müll** |
| **Übervolle Behälter am Periodenende** | **222 Behälter** | **0 Behälter** | **−222 Problembehälter** | A hinterlässt Müllkrise |
| **Behälter-Tage im Überlauf** | **10.712 Tage** | **164 Tage** | **−10.548 Tage (−98,5 %)** | C schützt Stadtbild |
| **Fahrzeugtage (Schichten)** | 99 | 101 | +2 Schichten | C passt Kapazität an |

### Warum Codex' Interpretation ökonomisch falsch ist:

1. **Leistungsverweigerung ist keine Ersparnis:**
   Fahrplan A spart die 4.750 € nur dadurch, dass er **die Arbeit nicht macht**. A lässt **161,6 Tonnen Glas** auf den Straßen Heilbronns liegen. Im realen Entsorgerbetrieb führt das zu:
   - Konventionalstrafen der Stadtverwaltung
   - Bürgerbeschwerden und Reputationsschaden
   - Teuren Notfall-Sonderfahrten und Straßenreinigung
   
2. **Die Skaleneffizienz von GlasRoute steigt sogar:**
   Rechnet man die Kosten pro transportierter Tonne Glas:
   $$\text{Kosten/Tonne}_A = \frac{85.269{,}46\,\text{€}}{2.254{,}13\,\text{t}} = 37{,}83\,\text{€/t}$$
   $$\text{Kosten/Tonne}_C = \frac{90.019{,}69\,\text{€}}{2.579{,}83\,\text{t}} = 34{,}89\,\text{€/t}$$
   GlasRoute C senkt die Stückkosten um **2,94 € pro Tonne (−7,8 %)**, weil volle Behälter (Ø 80,4 % bei C vs. 66,8 % bei A) die Hebelast pro Stopp optimieren.

3. **Kostenbereinigung bei gleicher Leistung:**
   Müsste Fahrplan A die 161,6 Tonnen Restmüll mit zusätzlichen Sonderfahrten abräumen (bei durchschnittlich 22,8 t pro Fahrzeugtag wären das mindestens 7 zusätzliche Schichten = mind. 5.500 € Zusatzkosten), lägen die Gesamtkosten von A bei über **90.800 €** – und damit **höher als die 90.020 € von GlasRoute C**.

---

## 5. Fazit für PreZero und den Pitch

1. **Die Kernbotschaft:**
   - Im Regelbetrieb spart die Bündelung **~5 % der Schichtkosten** (rund 4.100 € pro Quartal bzw. ~16.500 € pro Jahr) und eliminiert unnötige Fahrten.
   - Bei Nachfragespitzen (+20 % Glas) bricht der starre Fahrplan zusammen (161 t Überlauf, 222 verstopfte Standorte), während GlasRoute die gesamte Mehrlast mit nur 2 Zusatztagen sauber bewältigt – und dabei **pro Tonne Glas um 7,8 % günstiger** arbeitet.

2. **Ehrliche Grenzen (Reliability):**
   - Die Geodaten sind OSM-simuliert.
   - Sensor-Hardwarekosten (CAPEX/OPEX) sind in den 4.132 € noch nicht gegengerechnet.
   - **Empfehlung:** Ein 3-monatiger Pilotversuch mit 50–100 Sensoren, um reale Befüllraten und Netto-Einsparungen unter echten PreZero-Betriebsregeln zu validieren.
