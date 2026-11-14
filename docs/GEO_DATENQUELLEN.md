# Geo-Datenquellen – Glascontainer Heilbronn

Stand: 2026-11-14. Ziel: reale, materialbeschriebene Glascontainer-Koordinaten für 449 anonymisierte `Location_id`s finden. Ergebnis: **keine verifizierte reale Zuordnung möglich**; Pipeline liefert reproduzierbare, klar markierte Platzhalter.

## Geprüfte Quellen

| Quelle | Abruf | Befund | Nutzbarkeit / Lizenz |
|---|---|---|---|
| Stadt Heilbronn / EBS Altglas | [Altglas-Seite](https://abfallwirtschaft.heilbronn.de/abfallentsorgung/abfallannahme/depotcontainer/altglas), [Amtlicher Stadtplan mit Altglas-Ebene](https://karten.heilbronn.de/heilbronn/index.php?lang=de&zl=33&x=515975.5&y=5443108&bl=stadtplan&bo=1&lo=1&layers=altglascontainerstandorte&service=heilbronn), [Layer-Tree](https://karten.heilbronn.de/heilbronn/ajax/get_tree.php?lang=de&service=heilbronn&c=66021760) | Offizielle Referenz: „über 100 Altglas-Standorte“ und POI-Ebene `altglascontainerstandorte` (ID 413) sind belegt. Getestete GeoJSON-Endpunkte (`qidstr=altglascontainerstandorte`, `qidstr=413`) lieferten HTTP 200 mit leerem Body; **keine einzelnen Koordinaten/Adressen/Materialfelder extrahierbar**. | Kein offener, verifizierter Bulk-Download. Kartenhinweis: „© Stadtplan, Luftbilder und Geodaten: Stadt Heilbronn“; nicht als offene Daten übernehmen. |
| Offene Daten Heilbronn | [Suche „altglas“](https://opendata.heilbronn.de/search?query=altglas), [Kategorie Abfall](https://opendata.heilbronn.de/search/type/dataset/topic/abfall-511?sort_by=changed) | Suche: keine Treffer. Abfallkategorie enthält nur Abfallmengen-Statistiken, **keinen Standortdatensatz**. | n/a |
| OpenStreetMap / Overpass | [amenity=recycling](https://wiki.openstreetmap.org/wiki/Tag:amenity%3Drecycling), [Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API), [ODbL/Copyright](https://www.openstreetmap.org/copyright) | Geeignetes Schema (`recycling:glass_bottles`, `recycling:glass`, Farb-Tags). Live-Fetch durch dieses Projekt (`scripts/fetch_locations.py`, Endpoint `https://overpass-api.de/api/interpreter`, 10 s Connect / 30 s Read, 1 Retry, 2026-11-14): **beide Versuche Timeout → 0 Kandidaten**. Read-only-Recherche meldete zusätzlich 502/Timeouts bei weiteren Instanzen. | OSM-Daten: ODbL 1.0, Attribution „© OpenStreetMap contributors“. Bei erfolgreichem Abruf wäre dies der bevorzugte offene Kandidatenpool; tatsächliche Abdeckung/Tag-Qualität in Heilbronn bleibt damit unbestätigt. |

## Matching-Grenzen

- Anonyme PreZero-IDs haben keinen belegten Fremdschlüssel zu Stadtplan- oder OSM-Objekten. Eine Zuordnung über Material, Anzahl oder Nähe wäre **nur eine Heuristik** und darf nicht als reale 1:1-Identität ausgegeben werden.
- Der Resolver vergibt deshalb für OSM-Heuristiken höchstens `confidence=low`, `source=osm_heuristic` und einen begründeten `match_reason` mit „UNVERIFIED“. Direkte PreZero-Mappings erhalten `confidence=high`, `source=prezero_supplied`.

## Aktueller Lauf

- `data/external/locations_real_attempt.csv`: 0 Kandidaten (Header vorhanden).
- `data/external/locations_matched.csv` / `data/external/locations.csv`: 449/449 IDs, alle `synthetic_placeholder` / `synthetic`, deterministisch (Seed 2026), BBox 49.09–49.23 N, 9.13–9.28 E.
- Austauschpfad ist vorbereitet: echte `Location_id,lat,lon`-Daten können ohne Codeänderung priorisiert werden.
