# Geo-Datenquellen – Glascontainer Heilbronn

Stand: 2026-11-14. Ziel: reale, materialbeschriebene Glascontainer-Koordinaten für 449 anonymisierte `Location_id`s finden. Ergebnis: **keine verifizierte reale Zuordnung möglich**; Pipeline liefert reproduzierbare, klar markierte Platzhalter.

## Geprüfte Quellen

| Quelle | Abruf | Befund | Nutzbarkeit / Lizenz |
|---|---|---|---|
| Stadt Heilbronn / EBS Altglas | [Altglas-Seite](https://abfallwirtschaft.heilbronn.de/abfallentsorgung/abfallannahme/depotcontainer/altglas), [Amtlicher Stadtplan mit Altglas-Ebene](https://karten.heilbronn.de/heilbronn/index.php?lang=de&zl=33&x=515975.5&y=5443108&bl=stadtplan&bo=1&lo=1&layers=altglascontainerstandorte&service=heilbronn), [Layer-Tree](https://karten.heilbronn.de/heilbronn/ajax/get_tree.php?lang=de&service=heilbronn&c=66021760) | Offizielle Referenz: „über 100 Altglas-Standorte“ und POI-Ebene `altglascontainerstandorte` (ID 413) sind belegt. Getestete GeoJSON-Endpunkte (`qidstr=altglascontainerstandorte`, `qidstr=413`) lieferten HTTP 200 mit leerem Body; **keine einzelnen Koordinaten/Adressen/Materialfelder extrahierbar**. | Kein offener, verifizierter Bulk-Download. Kartenhinweis: „© Stadtplan, Luftbilder und Geodaten: Stadt Heilbronn“; nicht als offene Daten übernehmen. |
| Offene Daten Heilbronn | [Suche „altglas“](https://opendata.heilbronn.de/search?query=altglas), [Kategorie Abfall](https://opendata.heilbronn.de/search/type/dataset/topic/abfall-511?sort_by=changed) | Suche: keine Treffer. Abfallkategorie enthält nur Abfallmengen-Statistiken, **keinen Standortdatensatz**. | n/a |
| OpenStreetMap / Overpass | [amenity=recycling](https://wiki.openstreetmap.org/wiki/Tag:amenity%3Drecycling), [Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API), [ODbL/Copyright](https://www.openstreetmap.org/copyright) | Erfolgreicher Abruf am 2026-11-14 über `overpass-api.de` mit der vorgegebenen Area-Query (`admin_level` 6; `admin_level` 8 nur als Fallback) und 90-s-Timeout: **126 OSM-Punkte**. Die Mirrors `overpass.kumi.systems` und `overpass.private.coffee` liefen bei einem späteren Kontrollversuch in den Read-Timeout; der erfolgreiche Treffer blieb erhalten. | OSM-Daten: ODbL 1.0, Attribution „© OpenStreetMap contributors“. Alle 449 anonymen IDs werden deterministisch mit Seed 2026 auf reale OSM-Standorte abgebildet und ausdrücklich als `source=osm_assigned`, `confidence=simulated_mapping` markiert. |

## Matching-Grenzen

- Anonyme PreZero-IDs haben keinen belegten Fremdschlüssel zu Stadtplan- oder OSM-Objekten. Eine Zuordnung über Material, Anzahl oder Nähe wäre **nur eine Heuristik** und darf nicht als reale 1:1-Identität ausgegeben werden.
- Bei OSM-Treffern werden reale Standorte mit Seed 2026 deterministisch simuliert zugeordnet: `source=osm_assigned`, `confidence=simulated_mapping`, `match_reason="real OSM site, ID assignment simulated"`. Mehrere IDs dürfen denselben Standort teilen. Direkte PreZero-Mappings erhalten `confidence=high`, `source=prezero_supplied` und haben Vorrang.

## Aktueller Lauf

- `data/external/locations_real_attempt.csv`: 126 reale OSM-Glasstandorte.
- `data/external/osm_glass_raw.json`: liegt mangels erfolgreichem erneuten Raw-Download nicht vor; der erfolgreiche Kandidaten-Snapshot ist in `locations_real_attempt.csv` erhalten.
- `data/external/locations_matched.csv` / `data/external/locations.csv`: 449/449 IDs, alle `osm_assigned` / `simulated_mapping` mit deterministischer Zuordnung (Seed 2026).
- `data/external/location_sanity_check.html`: alle 449 simulierten Zuordnungen, nach Quelle eingefärbt.
- Austauschpfad bleibt vorbereitet: echte `Location_id,lat,lon`-Daten in `locations_real.csv` haben automatisch Vorrang vor OSM und Synthetik.
