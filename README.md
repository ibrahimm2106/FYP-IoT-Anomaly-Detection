# IoT Autoencoder Anomaly Detection

A Streamlit-based anomaly detection artefact for identifying unusual activity in IoT network traffic using an autoencoder model. The project combines data preparation, model scoring, evaluation summaries, and export tools into a guided application suitable for review, demonstration, and final-year software engineering assessment.

## Project Overview

This repository implements an unsupervised anomaly detection workflow for tabular IoT traffic records. The autoencoder is trained on benign-only traffic so it can learn normal connection patterns. During inference, rows with high reconstruction error are flagged as anomalous using a saved threshold.

The application is designed to make the full workflow transparent:

- Inspect the processed IoT dataset.
- Select and prepare a saved model.
- Score records with the trained autoencoder.
- Review anomaly flags, reconstruction error, and evaluation metrics.
- Export scored data, metrics, reports, and supporting artefacts.

The project is not presented as a production intrusion detection system. It is an academic engineering artefact that demonstrates a reproducible machine learning pipeline, a usable interface, and a clear evaluation story.

## Key Features

- **Guided Streamlit workflow** with seven main steps from data selection to model use.
- **Batch anomaly scoring** using saved autoencoder, preprocessor, and threshold artefacts.
- **Evaluation dashboard** with precision, recall, F1-score, PR-AUC, and confusion-style counts where labels are available.
- **Data validation** for uploaded CSV files against the trained preprocessor's expected feature set.
- **Repair tools** for common dataset issues such as missing values, duplicate rows, and column quality checks.
- **Export tools** for scored rows, anomaly tables, metrics, JSON summaries, and markdown reports.
- **Advanced analysis views** for threshold context, model information, explainability, and simulation.
- **Docker support** for running the Streamlit app in a repeatable container environment.

## Application Workflow

The primary user journey is a seven-step wizard shown in the app:

1. **Select Data** - choose the project dataset or upload a compatible CSV.
2. **Repair Data** - apply optional in-memory cleaning and validation.
3. **Select Model** - choose a saved `.keras` or `.h5` model artefact.
4. **Prepare Model** - confirm the preprocessor, feature list, and threshold.
5. **Test Model** - run a one-shot scoring pass and review the summary.
6. **Export** - download model outputs, helper files, and result artefacts.
7. **Use Model** - upload data and check it for unusual activity.

Advanced pages provide deeper inspection for data overview, detection results, evaluation evidence, model information, explainability, live simulation, and export management.

## Repository Structure

```text
app.py                      Streamlit entry point
evaluate.py                 Evaluation script
train.py                    Training script for preprocessor, model, and threshold
requirements.txt            Python dependencies
Dockerfile                  Optional Streamlit container image
docker-compose.yml          Optional Docker Compose configuration

data/processed/             Processed CSV data
models/                     Saved model, preprocessor, threshold, and metrics artefacts
src/                        Core application, scoring, validation, and export modules
views/                      Streamlit pages for the guided workflow and advanced tools
tests/                      Pytest suite
docs/                       Supporting design, architecture, evaluation, and scope notes
diagrams/                   Diagram index and architecture diagram references
```

## Running the App

Use these Windows command-line steps from Command Prompt:

```cmd
cd c:\Users\User\Documents\iot-autoencoder-artifact
.\.venv\Scripts\activate.bat
python -m streamlit run app.py
```

After Streamlit starts, open the local URL shown in the terminal. By default, Streamlit runs on port `8501`.

If dependencies are missing, install them inside the virtual environment:

```cmd
pip install -r requirements.txt
```

## Secure Public Access with ngrok

ngrok is used as a secure tunneling feature to expose the local Streamlit port and generate a live, public HTTP URL. This is useful when the app is running locally but needs to be shared temporarily with a reviewer, supervisor, or tester.

Start the Streamlit app first, then run ngrok against Streamlit's default port:

```cmd
"%LOCALAPPDATA%\Microsoft\WindowsApps\ngrok.exe" config add-authtoken <YOUR_TOKEN>
"%LOCALAPPDATA%\Microsoft\WindowsApps\ngrok.exe" http 8501
```

ngrok will display a public forwarding URL. Anyone with that URL can access the running local Streamlit app while the tunnel is active, so only share it with trusted recipients and stop the tunnel when it is no longer needed.

## Docker

Docker is optional. It can be used when a repeatable runtime is preferred or when running the app on a VM.

```cmd
docker compose up --build
```

Then open:

```text
http://localhost:8501
```

The Compose setup exposes Streamlit on port `8501` and bind-mounts the project data and model directories.

## Dataset Support

The implementation is centred on processed CTU-IoT-23 style Zeek connection records. Expected data is tabular and may include label fields such as `label` and `detailed-label`.

When labels are available, the app compares anomaly flags with the dataset labels to produce evaluation metrics. When labels are unavailable, scoring still works and supervised metrics are reported as unavailable.

## Evaluation

The evaluation views report:

- Reconstruction error values from the autoencoder.
- Binary anomaly flags based on the selected threshold.
- Precision, recall, F1-score, and PR-AUC where labels support them.
- TP, FP, TN, and FN style counts for flag-versus-label comparison.
- Threshold context and interpretation notes.

All metrics are dataset-specific and threshold-specific. They should be interpreted as evidence for the artefact and selected dataset, not as general production security guarantees.

## Diagrams

Diagram references are available in the `/diagrams` folder:

| File | Description |
|------|-------------|
| [`/diagrams/ARCHITECTURE_DIAGRAMS.md`](diagrams/ARCHITECTURE_DIAGRAMS.md) | Mermaid diagrams covering system context, training and inference flow, information architecture, and module dependencies. |

## Documentation

Additional documentation is available in the `docs/` folder:

| Document | Purpose |
|----------|---------|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Application structure, module layout, and session-state notes. |
| [`docs/DESIGN.md`](docs/DESIGN.md) | Design decisions and implementation rationale. |
| [`docs/EVALUATION.md`](docs/EVALUATION.md) | Evaluation process and testing protocol. |
| [`docs/PRIVACY_AND_SCOPE.md`](docs/PRIVACY_AND_SCOPE.md) | Data handling, project scope, and professional limitations. |
| [`docs/ACCESSIBILITY.md`](docs/ACCESSIBILITY.md) | Accessibility considerations for the Streamlit interface. |
| [`docs/MODULE_MAP.md`](docs/MODULE_MAP.md) | Maintainer-oriented file and module index. |
| [`CHANGELOG.md`](CHANGELOG.md) | Project evolution and notable changes. |

## Testing

Run the test suite from the project root:

```cmd
pytest
```

The tests cover validation helpers, repair helpers, scoring support, constants, and selected application behaviours used by the Streamlit interface.

## Contributor

This repository has one contributor:

- **ibrahimm2106** - project owner, developer, and sole contributor.

## Scope

This project demonstrates a complete local anomaly detection workflow for academic review. It supports reproducible preprocessing, model scoring, transparent metric reporting, and exportable evidence. It does not perform live packet capture and should not be treated as a deployed intrusion detection system without further engineering, validation, monitoring, and security review.
