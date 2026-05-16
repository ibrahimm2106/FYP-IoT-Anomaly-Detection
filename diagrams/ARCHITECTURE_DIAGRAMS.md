# Architecture Diagrams (Mermaid)

Render in GitHub, VS Code Mermaid preview, or export to PNG for the report.
This top-level folder is the canonical home for repository diagrams; source
code remains under `src/`, page code remains under `views/`, and supporting
written documentation remains under `docs/`.

## Final-Year Project Diagram Assets

These PNG diagrams were produced for the final-year project report and are
stored here as submitted visual artefacts.

| Diagram | Purpose |
|---|---|
| [IoT data pipeline design diagram.png](<IoT data pipeline design diagram.png>) | End-to-end IoT-23 anomaly-detection data pipeline from CSV ingestion through Streamlit output. |
| [System interaction sequence diagram.png](<System interaction sequence diagram.png>) | UML-style sequence diagram showing user, Streamlit UI, preprocessor, autoencoder, threshold module, and dashboard interactions. |
| [Edge cloud diagram.png](<Edge cloud diagram.png>) | Edge-to-cloud analytics architecture context for IoT anomaly detection. |
| [IoT anomaly detection use case diagram.png](<IoT anomaly detection use case diagram.png>) | Use case diagram for the network administrator and anomaly detection system capabilities. |
| [IoT anomaly detection data flow diagram.png](<IoT anomaly detection data flow diagram.png>) | Data-flow diagram showing IoT sources, preprocessing, autoencoder scoring, classification, dashboarding, and log export. |

## 1. System Context

```mermaid
flowchart TB
    subgraph Actor
        U[Examiner / student]
    end
    subgraph LocalMachine["Local machine"]
        ST[Streamlit app\napp.py + views/]
        PY[Offline scripts\npreprocess.py, train.py, evaluate.py]
        ART[(Artefacts:\nCSV, models/*)]
    end
    U --> ST
    U --> PY
    PY --> ART
    ST --> ART
```

## 2. Training Vs Inference

```mermaid
flowchart LR
    subgraph Offline["Offline training"]
        RAW[Raw labelled Zeek export] --> PRE[src/preprocess.py]
        PRE --> CSV[data/processed/ctu_iot_34_1.csv]
        CSV --> TR[train.py]
        TR --> M[models/autoencoder.h5]
        TR --> P[models/preprocessor.pkl]
        TR --> T[models/threshold.txt]
    end
    subgraph Online["Streamlit inference"]
        CSV2[CSV upload or project CSV] --> VAL[scoring_engine\nvalidate schema + feature order]
        VAL --> SC[iot_streamlit\nscore_dataframe / compute_scoring]
        M2[models/autoencoder.h5] --> SC
        P2[models/preprocessor.pkl] --> SC
        T2[models/threshold.txt] --> SC
        SC --> OUT[Reconstruction MSE\nflags\nmetrics]
    end
```

## 3. Information Architecture

```mermaid
flowchart TB
    H[Overview views/Home.py]
    subgraph W["Main Workflow - 7-step wizard"]
        S1[1 Select data]
        S2[2 Repair]
        S3[3 Select model]
        S4[4 Prepare]
        S5[5 Test]
        S6[6 Export]
        S7[7 Use model]
    end
    subgraph C["Advanced Tools"]
        D[Data overview]
        DET[Detection results]
        EV[Evaluation]
        MI[Model info]
        EX[Export tools]
        O[Analysis / Explain / Live]
    end
    H --> S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7
    H --> C
    W --> SCORE[Shared scoring\niot_streamlit + scoring_engine]
    C --> SCORE
```

## 4. Module Dependencies

```mermaid
flowchart TB
    views[views/*.py] --> app_core[src/app_core.py]
    app_core --> iot[src/iot_streamlit.py]
    iot --> const[src/iot_constants.py]
    iot --> paths[src/iot_paths.py]
    iot --> eng[src/scoring_engine.py]
    iot --> art[src/artifact_loaders.py]
    iot --> theme[src/ui_theme.py]
    eng --> types[src/scoring_types.py]
    eng --> art
    views --> ui[src/ui_helpers.py]
    ui --> iot
    val[src/validation_helpers.py] --> table[src/table_io.py]
    iot --> val
    iot --> rep[src/repair_helpers.py]
    evh[src/evaluation_helpers.py] --> types
    iot --> evh
```
