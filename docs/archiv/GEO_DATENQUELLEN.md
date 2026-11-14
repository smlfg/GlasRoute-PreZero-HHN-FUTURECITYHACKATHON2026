# Geo-Datenquellen – Glascontainer Heilbronn

Stand: 2026-11-14, 15:40 Uhr. Ziel: reale, materialbeschriebene Glascontainer-Koordinaten für 449
anonymisierte `Location_id`s finden. Ergebnis: **keine verifizierte reale Zuordnung möglich**; die
Pipeline liefert reale OSM-Standorte mit explizit unbestätigter Zuordnung plus benannte Platzhalter.

## Geprüfte Quellen

| Quelle | Abruf | Befund | Nutzbarkeit / Lizenz |
|---|---|---|---|
| Stadt Heilbronn / EBS Altglas | [Altglas-Seite](https://abfallwirtschaft.heilbronn.de/abfallentsorgung/abfallannahme/depotcontainer/altglas), [Amtlicher Stadtplan mit Altglas-Ebene](https://karten.heilbronn.de/heilbronn/index.php?lang=de&zl=33&x=515975.5&y=5443108&bl=stadtplan&bo=1&lo=1&layers=altglascontainerstandorte&service=heilbronn) | Offizielle Referenz: „über 100 Altglas-Standorte“ und POI-Ebene `altglascontainerstandorte` sind belegt. Getestete GeoJSON-Endpunkte lieferten HTTP 200 mit leerem Body; **keine einzelnen Koordinaten/Adressen/Materialfelder extrahierbar**. | Kein offener, verifizierter Bulk-Download. Kartenhinweis: „© Stadtplan, Luftbilder und Geodaten: Stadt Heilbronn“; nicht als offene Daten übernehmen. |
| Offene Daten Heilbronn | [Suche „altglas“](https://opendata.heilbronn.de/search?query=altglas), [Kategorie Abfall](https://opendata.heilbronn.de/search/type/dataset/topic/abfall-511?sort_by=changed) | Suche: keine Treffer. Abfallkategorie enthält nur Abfallmengen-Statistiken, **keinen Standortdatensatz**. | n/a |
| OpenStreetMap / Overpass | [amenity=recycling](https://wiki.openstreetmap.org/wiki/Tag:amenity%3Drecycling), [Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API), [ODbL/Copyright](https://www.openstreetmap.org/copyright) | **126 reale Glascontainer-Standorte** in Heilbronn gefunden (`recycling:glass_bottles`, `recycling:glass`), inkl. benannter Depots („Recyclinghof“, „Recyclinghof-Ost“, „Recyclinghof Flein“). Area-Query (`admin_level` 6/8) scheitert unter Last regelmäßig an HTTP 400/502/Timeout; die **BBox-Query über denselben Endpunkt** liefert zuverlässig. | OSM-Daten: ODbL 1.0, Attribution „© OpenStreetMap contributors“ – in `location_sanity_check.html` und in den Docs gesetzt. |

## Abruf-Logik

`scripts/fetch_locations.py` versucht in Reihenfolge:

1. Area-Query `admin_level` 6, dann 8, über drei Mirrors (90 s Read-Timeout, 1 Retry).
2. **BBox-Fallback** über denselben Endpunkt mit den dokumentierten Koordinaten
   `49.09–49.23 N, 9.13–9.28 E` — deutlich billiger, deshalb unter Last deutlich robuster.

Bei Treffer wird der Rohpayload in `data/external/osm_glass_raw.json` gespeichert (D1).
Ohne Treffer bleibt `data/external/locations.csv` **unverändert**; die Pipeline läuft mit Platzhaltern weiter.

## Matching-Grenzen

- Anonyme PreZero-IDs haben keinen belegten Fremdschlüssel zu Stadtplan- oder OSM-Objekten. Eine
  Zuordnung über Material, Anzahl oder Nähe wäre **nur eine Heuristik** und darf nicht als reale
  1:1-Identität ausgegeben werden.
- Der Resolver vergibt deshalb für OSM-Heuristiken höchstens `confidence=low`, `source=osm_heuristic`
  und einen begründeten `match_reason` mit „UNVERIFIED“. Direkte PreZero-Mappings erhalten
  `confidence=high`, `source=prezero_supplied`.
- **126 reale Standorte können nicht 449 IDs eindeutig abdecken.** Eine 1:1-Zuordnung ist damit
  unmöglich; verbleibende IDs erhalten benannte Platzhalter (Seed 2026, BBox Heilbronn).

## Aktueller Lauf

- `data/external/osm_glass_raw.json`: Rohpayload des erfolgreichen Abrufs.
- `data/external/locations_real_attempt.csv`: 126 Kandidaten aus OSM.
- `data/external/locations.csv` / `locations_matched.csv`: 449/449 IDs, identisch, je Zeile `source`,
  `confidence`, `match_reason`; `location_sanity_check.html` enthält alle 449 IDs mit Attribution.
- Austauschpfad ist vorbereitet: echte `Location_id,lat,lon`-Daten in `data/external/locations_real.csv`
  legen und `scripts/refresh_locations.py --real …` laufen lassen — ohne Codeänderung priorisiert.
