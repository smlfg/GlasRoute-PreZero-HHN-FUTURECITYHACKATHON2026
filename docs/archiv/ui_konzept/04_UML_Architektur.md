# GlasRoute — UML-Architektur (aus reMarkable-Skizze)

> **VERALTET (Stand 14.11.2026, 18:30):** Konzept-Dokument aus der Frühphase. Zahlen und Begriffe (z. B. 67,92 km / 260,82 km / −74 %, `osm_heuristic`, `synthetic_placeholder`, „338 Serien“) sind überholt. Gültig ist nur die Website `ui_2026-04-15.html` (`prezero-route run`) und `Pitch/NOTES.md`.

Dieses Dokument übersetzt die drei Stufen aus der reMarkable-Skizze (`01_remarkable_skizze_original.png`) auf das bestehende Python-Paket `src/prezero/` (`ingest.py`, `locations.py`, `features.py`, `scoring.py`, `routing.py`, `viz.py`, `cli.py`) sowie die geplanten UI-, RAG-, Voice- und Human-Approval-Komponenten.

---

## 1. UML Klassendiagramm (Komponenten & Datenfluss)

```mermaid
classDiagram
    class CsvDropController {
        +onFileDrop(file)
        +validateCsvExtension(filename)
        +uploadToBackend(formData)
    }

    class PipelineOrchestrator {
        +runPipeline(csvPath, targetDate)
        +emitProgress(stage, percent)
        +getDashboardPayload()
    }

    class IngestModule {
        <<prezero.ingest>>
        +load_raw(path)
        +clean(df)
        +ingest(input_path, output_path)
    }

    class LocationsModule {
        <<prezero.locations>>
        +load_locations(path)
        +resolve_locations(raw_df, real_path)
        +location_stats(df)
    }

    class FeaturesModule {
        <<prezero.features>>
        +get_season_factor(date)
        +build_features(df, date)
    }

    class ScoringModule {
        <<prezero.scoring>>
        +score_containers(features, date)
    }

    class RoutingModule {
        <<prezero.routing>>
        +OperationalConfig config
        +load_config(path)
        +haversine_km(lat1, lon1, lat2, lon2)
        +build_route(scored, locations, date)
    }

    class VizModule {
        <<prezero.viz>>
        +plot_trends(df, output_path)
        +plot_route(route, output_path, scored, locations)
    }

    class PandasGraphGridPresenter {
        +renderCardsPopIn(metrics)
        +connectNodeWires(cards, ragPanel)
        +selectNode(nodeId)
    }

    class AnomalyHighlighter {
        +detectSeasonalSpikes(df)
        +detectObservationGaps(df)
        +toggleHighlight(nodeIds)
    }

    class RagAgentService {
        +indexMarkdownReports(analysenDir)
        +attachRouteContext(routeJson)
        +answerQuery(question, activeNodeId)
    }

    class VoiceInterface {
        +toggleVoiceMode(enabled)
        +synthesizePiperTts(text, modelPath)
        +captureSpeechPrompt()
    }

    class HumanApprovalGate {
        +reviewRoute(routeJson)
        +approveTour(dispatcherId, timestamp)
        +exportApprovedPlan(routeJson)
    }

    CsvDropController --> PipelineOrchestrator : "POST /api/upload"
    PipelineOrchestrator --> IngestModule : "1. bereinigen"
    PipelineOrchestrator --> LocationsModule : "Standorte aufloesen"
    PipelineOrchestrator --> FeaturesModule : "2. Raten & Lücken"
    PipelineOrchestrator --> ScoringModule : "3. Kritikalität"
    PipelineOrchestrator --> RoutingModule : "4. Route berechnen"
    PipelineOrchestrator --> VizModule : "Plots & Karte"

    PipelineOrchestrator --> PandasGraphGridPresenter : "2x3 Graph-JSON"
    PandasGraphGridPresenter --> AnomalyHighlighter : "Anomalie-Marker"
    PandasGraphGridPresenter --> RagAgentService : "activeNodeId + Kontext"
    AnomalyHighlighter --> RagAgentService : "Anomalie-Fokus"
    RagAgentService --> VoiceInterface : "Text -> Audio (Thorsten)"
    RoutingModule --> HumanApprovalGate : "route_YYYY-MM-DD.json"
    RagAgentService --> HumanApprovalGate : "Erklaerung & Begruendung"
```

---

## 2. UML Sequenzdiagramm (Stufe ① → ② → ③)

```mermaid
sequenceDiagram
    autonumber
    actor Disponent
    participant UI as "UI (Dropzone + 2x3 Grid)"
    participant API as "Backend Adapter (web.py)"
    participant Pipe as "prezero Pipeline"
    participant Anom as "AnomalyHighlighter"
    participant RAG as "RagAgentService"
    participant Voice as "Piper Voice (TTS)"
    participant HAI as "HumanApprovalGate"

    Note over Disponent,UI: Stufe 1: Drag & Drop .csv
    Disponent->>UI: CSV ablegen (glass_fill_levels_anonymized_f.csv)
    UI->>API: POST /api/upload (CSV-Stream + Datum)
    API-->>UI: Stream Status "processing"

    Note over API,Pipe: Stufe 2: Animation "processing" & 6 Pandas Graphs popping up
    API->>Pipe: ingest() -> build_features() -> score_containers() -> build_route()
    Pipe-->>API: cleaned_readings + 6 Kennzahl-Cluster + route_2026-04-15.json
    API-->>UI: Dashboard-Payload (Material, Saison, Risiko, Rate, Luecken, Route)
    UI->>Anom: Markiere Ausreisser (Neujahr 52,7% OF, 458 >90d-Luecken)
    UI-->>Disponent: 2x3 Pandas-Karten animiert einblenden (popIn)

    Note over Disponent,HAI: Stufe 3: Split View (Knoten -> Agent RAG + Voice + Possible Route)
    Disponent->>UI: Klick auf Anomalie-Knoten (z. B. Card 2 oder Card 5)
    UI->>RAG: POST /api/chat (Frage + selected_node_id + route_json)
    RAG-->>UI: Empfehlung mit Quellenbezug (Analysen 01..36 + Stop-Details)
    alt Voice + Text aktiv
        UI->>Voice: Synthetisiere Antwort (de_DE-thorsten-high.onnx)
        Voice-->>Disponent: Audio-Ausgabe + Text im Chat
    else Text-Modus
        UI-->>Disponent: Strukturierte Text-Antwort
    end

    Disponent->>HAI: Klick "Route freigeben (25 Stops, 67,92 km)"
    HAI-->>Disponent: Freigabe-Log gespeichert + Export bereit
```

---

## 3. UML Zustandsdiagramm (UI-Lebenszyklus)

```mermaid
stateDiagram-v2
    [*] --> IdleDropzone : "Stufe 1 bereit (Drag & Drop .csv)"

    IdleDropzone --> ProcessingPipeline : "CSV abgelegt / Demo-Upload"
    ProcessingPipeline --> IdleDropzone : "Schema-Fehler (Pflichtspalte fehlt)"
    ProcessingPipeline --> PoppingGraphs : "Pipeline OK (11.701 Zeilen)"

    PoppingGraphs --> InteractiveWorkspace : "6 Pandas-Karten eingeblendet"

    state InteractiveWorkspace {
        [*] --> AllNodesConnected
        AllNodesConnected --> AnomalyHighlighted : "Toggle Anomalie-Highlight"
        AnomalyHighlighted --> NodeSelectedInRag : "Klick auf Karte 1..6"
        AllNodesConnected --> NodeSelectedInRag : "Klick auf Karte 1..6"
        NodeSelectedInRag --> RagAnswering : "Voice- oder Text-Prompt"
        RagAnswering --> NodeSelectedInRag : "Antwort + TTS fertig"
    }

    InteractiveWorkspace --> RouteApproved : "Mensch klickt Route freigeben (HAI)"
    RouteApproved --> InteractiveWorkspace : "Freigabe zuruecknehmen / anpassen"
    RouteApproved --> [*] : "Export route_YYYY-MM-DD.json"
```
