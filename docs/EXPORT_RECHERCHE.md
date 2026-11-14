# Export-Recherche: Stop-Listen an Fahrer-Geräte

## Übersicht
Logistik- und Entsorgungstools übergeben geplante Routen typischerweise als Datei-Export oder Deep-Link. Die gängigen Formate sind **GPX**, **KML/KMZ** und **CSV/Excel**.

## Formate

### GPX 1.1
De-facto-Standard für GPS-Geräte und Navigations-Apps. Zwei Varianten:
- **Waypoint-GPX (`<wpt>`)**: Liste einzelner Stopps. Sinnvoll, wenn das Endgerät mit eigener Karte und Verkehrsdaten neu routen soll.
- **Route-GPX (`<rte>` mit `<rtept>`)**: Geordnete Route; das Gerät navigiert von Punkt zu Punkt.

Viele Route-Planer (RouteSavvy, RouteXL, Furkot) bieten beide Varianten an.

### KML/KMZ
Google-Format für Google Earth / My Maps / Google Maps. My Maps Import-Limits: ungezippte KML/KMZ max. 5 MB, andere Dateien 40 MB, max. 2.000 Zeilen. Geeignet zur Visualisierung, nicht immer für Turn-by-Turn.

### CSV/Excel
Stoppliste mit Adressen/Koordinaten für Tabellenkalkulation und Import in Planer. Enthält keine Routengeometrie.

## Geräte-/App-Support

| Ziel | GPX | KML | CSV | Hinweise |
|---|---|---|---|---|
| **Google Maps** | über My Maps | ja | ja (Layer) | Consumer-UI max. 10 Ziele; Maps-URL max. 9 Wegpunkte (Desktop) / 3 (Mobil); URL-Länge max. 2.048 Zeichen |
| **OsmAnd** | ja (GPX 1.1) | Import → GPX | nein | `<trk>` / `<wpt>` am besten unterstützt; `<rte>` nur über Map-Marker |
| **Garmin** | ja | teilweise | nein | GPX in `Garmin/GPX` kopieren; modelabhängige Limits (z. B. eTrex SE: 10 Routen / 50 Wegpunkte; Explore-Web: 500 Wegpunkte/Import, 200 Punkte/Route) |
| **Truck-Nav-Apps** | ja | ja | ja | z. B. Drivant Pro mit HERE Truck-Routing |

## Google Maps Limits & Workarounds
- Offizielle Maps-URL (`google.com/maps/dir/?api=1&waypoints=…`): max. **9 Zwischenstopps** auf Desktop, **3 auf mobilen Browsern**.
- Consumer-Planer: max. **10 Ziele gesamt** (Start + 9 Stopps).
- Workaround: Route in Abschnitte (“legs”) à ≤9/10 Stopps aufteilen; Endpunkt eines Abschnitts = Startpunkt des nächsten.

## Empfehlung für dieses Projekt
- **GPX**: Route-GPX (`<rtept>`) mit allen Stopps in Reihenfolge inkl. Betriebshof, Entladen, Ende; zusätzlich `<wpt>` für Kompatibilität.
- **Google Maps**: Mehrere Links bei >9/10 Stopps; QR-Code auf erste Leg.
- **CSV/Druck**: unverändert beibehalten.

## Quellen
- Google Developers: Maps URLs – Directions & waypoint limits
- RouteXL Download-Dokumentation
- RouteSavvy Print/Export Guide
- OsmAnd GPX-Dokumentation
- Garmin eTrex SE Manual; OptimoRoute Garmin Export Guide
- Mappy / Routerra / InstaMaps / MyRouteOnline Artikel zu Google Maps Stop-Limits
