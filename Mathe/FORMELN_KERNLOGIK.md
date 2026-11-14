# Formelsammlung der Kernlogik (Mathe)

Dieses Dokument fasst alle mathematischen Definitionen der GlasRoute-Pipeline zusammen – von der Füllstandsuhr über das Scoring bis zu den VRP-Gleichungen.

---

## 1. Füllstand & Füllrate (src/prezero/features.py)

### 1.1 Tägliche Füllrate aus Intervallen
Jeder Messwert $y_i$ (in Prozent, capped bei $110\,\%$) entsteht bei einer Leerung zum Zeitpunkt $t_i$. Da der Container nach der Leerung bei $0\,\%$ startet, gilt für das Intervall $[t_{i-1}, t_i]$:

$$r_i = \frac{y_i}{t_i - t_{i-1}} \quad \left[\frac{\%}{\text{Tag}}\right]$$

### 1.2 Geschätzter aktueller Füllstand am Tag $t$
Für einen Zeitpunkt $t > t_{\text{last}}$ nach der letzten Leerung:

$$\widehat{\text{fill}}(t) = \min\left(110\,\%,\, r \times (t - t_{\text{last}})\right)$$

### 1.3 Timer-Zielzeitpunkte
* **Fälligkeitstag ($\text{due\_date}$):** Zeitpunkt, an dem der Container $80\,\%$ erreicht:
  $$t_{\text{due}} = t_{\text{last}} + \frac{80\,\%}{r}$$
* **Überlauftag ($\text{overflow\_date}$):** Zeitpunkt, an dem der Container $110\,\%$ erreicht:
  $$t_{\text{overflow}} = t_{\text{last}} + \frac{110\,\%}{r}$$
* **Verbleibende Tage bis Fälligkeit:**
  $$\Delta t_{\text{due}} = t_{\text{due}} - t_{\text{heute}}$$
  *(Negativ $\implies$ Container ist überfällig).*

---

## 2. Urgenz- & Kritikalitäts-Scoring (src/prezero/scoring.py)

### 2.1 Normierter Urgenz-Score
$$\text{Score} = \min\left(1{,}0,\, \frac{\widehat{\text{fill}}(t)}{110\,\%}\right)$$

### 2.2 Kritikalitäts-Kriterium
$$\text{Kritisch} \iff \widehat{\text{fill}}(t) \ge 80{,}0\,\% \quad \lor \quad \Delta t_{\text{due}} \le 0$$

---

## 3. Standort-Aggregation & Bündelung

Ein Standort $L$ umfasst mehrere Glasfraktionen (Weiß, Grün, Braun).

### 3.1 Standort-Gesamtmasse ($M_L$)
$$M_L = \sum_{c \in \{\text{Weiß, Grün, Braun}\}} \left( \frac{\widehat{\text{fill}}_c}{100} \times V_{\text{Behälter}} \times \rho_c \right)$$
Mit $V_{\text{Behälter}} = 2{,}5\,\text{m}^3$ und Standardschüttdichte $\rho = 400\,\text{kg/m}^3$:
$$M_L = \sum_{c} \left( \widehat{\text{fill}}_c \times 10\,\text{kg} \right)$$

### 3.2 Standort-Volumen ($V_L$)
$$V_L = \sum_{c} \left( \frac{\widehat{\text{fill}}_c}{100} \times 2{,}5\,\text{m}^3 \right)$$

---

## 4. Touren- & Restriktionsgleichungen (src/prezero/routing.py)

Die Tourenplanung unterliegt dem kapazitierten Fahrzeugrouten-Problem (CVRP) mit festen Schicht- und Depotschranken:

### 4.1 Kapazitätsschranken je Fahrzeugrunde
Für jede Runde $k$ eines Fahrzeugs:
$$\sum_{j \in \text{Stopps}_k} M_j \le M_{\max} = 11.000\,\text{kg} \quad (11\,\text{t})$$
$$\sum_{j \in \text{Stopps}_k} V_j \le V_{\max} = 26{,}0\,\text{m}^3$$

Sobald $M_k + M_{\text{neu}} > M_{\max}$ oder $V_k + V_{\text{neu}} > V_{\max}$, wird eine Zwischenfahrt zum Recyclinghof ($49.1780, 9.2085$) mit $\Delta t_{\text{unload}} = 20\,\text{min}$ eingefügt.

### 4.2 Schichtzeit-Restriktion (Max. 8,0 h = 480 min)
Die Gesamtarbeitszeit eines Fahrzeugs setzt sich zusammen aus:

$$T_{\text{Schicht}} = T_{\text{Fahrt}} + T_{\text{Rüst}} + T_{\text{Hub}} + T_{\text{Entladung}} \le 480\,\text{min}$$

Wobei:
* **Fahrzeit:** $T_{\text{Fahrt}} = \frac{s_{\text{km}}}{v_{\text{avg}}} \times 60\,\text{min} \quad (v_{\text{avg}} = 25\,\text{km/h}, \, s_{\text{km}} = s_{\text{Haversine}} \times 1{,}35)$
* **Rüstzeit:** $T_{\text{Rüst}} = N_{\text{Stopps}} \times 2{,}0\,\text{min}$
* **Hubzeit:** $T_{\text{Hub}} = N_{\text{Behälter}} \times 3{,}0\,\text{min}$
* **Entladezeit:** $T_{\text{Entladung}} = N_{\text{Runden}} \times 20{,}0\,\text{min}$
