# Upstream Search — Geo-Positions-Modul

## Prior Art

**Problem:** Eine CSV-Pipeline benötigt öffentliche Container-Geodaten und eine nachvollziehbare, austauschbare ID-/Koordinaten-Auflösung ohne neue GIS-Infrastruktur.

**Searched:** intern ✓ (`data/external/locations_synthetic.csv`, vorhandene Pipeline, `pyproject.toml`) · official ✓ (Overpass, OSM-Tags, OSM-Lizenz) · external ✓ („Python Overpass API library OSMnx overpy“, „geospatial matching CSV material tags OpenStreetMap“).

**Candidates:**
- [Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API) — Lese-API für genau die benötigten OSM-Objekte, BBox und `out center`; Server AGPLv3, [OSM-Daten ODbL](https://www.openstreetmap.org/copyright). **use:** eine kleine begrenzte HTTP-Abfrage; keine andere Quelle liefert den ID-Schlüssel.
- [python-overpy](https://github.com/DinoTools/python-overpy) — MIT, parst Overpass JSON/XML und behandelt Overpass-Fehler. **reject:** neue Laufzeitabhängigkeit spart bei nur einer flachen JSON-Abfrage zu wenig; dieselbe Query bleibt nötig.
- [OSMnx 2.1.1](https://osmnx.readthedocs.io/en/stable/) — MIT, Features-Abfragen als GeoDataFrame. **reject:** funktional passend, aber GeoPandas/NetworkX und teils kompilierte Abhängigkeiten sind für 449 CSV-Zeilen unnötig.
- [NREL mappymatch](https://github.com/NREL/mappymatch) — BSD-3-Clause, GPS-Spuren auf Straßennetze. **reject:** löst Trajectory-/Road-Matching, nicht materialbasierte anonyme Container-ID-Zuordnung.
- Vorhandene `locations_synthetic.csv` — **adapt:** BBox-/Fallback-Idee prüfen, aber durch Seed 2026, vollständige Confidence und Swap-Validierung ersetzen statt unmarkierte Altdatei still zu übernehmen.

**Decision:** **INTEGRATE / ADAPT** — Overpass direkt mit `urllib.request` aus der Standardbibliothek; pandas und bereits deklariertes folium wiederverwenden. Die projektspezifische Materialbewertung bleibt dünner Glue um diese Quellen; kein neues GIS-Paket. Overpass- oder Wrapper-APIs können den Fetcher später unverändert am CSV-Vertrag ersetzen.

**Install / Stack:** keine neue Installation oder `pyproject.toml`-Änderung. Öffentlicher Endpoint `https://overpass-api.de/api/interpreter`, per `OVERPASS_URL` ohne Schlüssel austauschbar; ein Request, 10/30-s-Timeout, höchstens ein Retry. OSM-Attribution kommt in Quellen-Doku und Sanity-Karte.

**Saved:** kein eigener HTTP-/Overpass-Service, keine GeoPandas-/NetworkX-Kette, kein unpassender Map-Matching-Stack.

**Residual risk:** Live-Abdeckung und Material-Tags müssen mit einem echten Overpass-E2E-Lauf geprüft werden; Timeout-/Fehler-Fallback mit Mocks belegen. Ohne PreZero-Schlüssel bleibt jede OSM-ID-Zuordnung `low`, auch bei perfekten Material-Tags.
