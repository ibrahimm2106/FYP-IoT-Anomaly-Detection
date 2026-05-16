# Privacy, legal context, and professional scope

## How data flows in this artefact

1. **Project CSV** — Read from disk (`data/processed/…`) when the user selects the sample path or when the dashboard loads the default bundle.
2. **User upload (Streamlit)** — File bytes are held in **`st.session_state`** on the user’s machine while the browser tab runs Streamlit **locally**. This repository does **not** implement a multi-user server, database, or cloud upload endpoint.
3. **Repairs** — Wizard step 2 mutates an **in-memory** copy; nothing is written back to `data/processed/` automatically.

## Professional / ethical positioning

- **Scope:** Batch anomaly **scoring** on tabular logs for **analysis and education** — not marketed as a certified intrusion-detection product.
- **Labelling:** When `label` exists, metrics compare flags to Zeek labels **illustratively**; class imbalance and labelling noise affect interpretation (`README.md`).
- **Live monitoring:** Out of scope by design; avoids implying real-time network interception.

## Technical mitigations (current)

- **No custom telemetry** in app code beyond Streamlit’s own usage settings (disabled in `.streamlit/config.toml` via `gatherUsageStats = false`).
- **Explicit caveats** in UI copy and README on batch scoring and evaluation limits.
- **Session threshold** (`SK_WIZARD_SESSION_THRESHOLD`) does not overwrite `models/threshold.txt` on disk unless the user changes files outside the app.

## Recommendations for deployment (if ever extended)

If the app were hosted as a **shared service**, you would need: authentication, upload size limits, virus scanning policy, retention policy, DPIA/GDPR analysis for EU personal data in flows, and audit logging. **This student artefact does not implement those** — document that choice in any formal submission.
