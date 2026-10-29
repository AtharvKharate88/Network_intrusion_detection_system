# NIDS: Network Intrusion Detection System

A machine-learning-based Network Intrusion Detection System (NIDS) built around a FastAPI backend and a trained XGBoost multiclass classifier. The project currently focuses on flow-level network intrusion prediction using CIC-IDS2017-derived features and stores prediction events in PostgreSQL via SQLAlchemy.

## Table of contents

- [Project status](#project-status)
- [Overview and motivation](#overview-and-motivation)
- [Features currently implemented](#features-currently-implemented)
- [Architecture overview](#architecture-overview)
- [Technology stack](#technology-stack)
- [Machine-learning pipeline](#machine-learning-pipeline)
- [Supported classification categories](#supported-classification-categories)
- [Dataset source, attribution, and usage notes](#dataset-source-attribution-and-usage-notes)
- [Model evaluation results](#model-evaluation-results)
- [Project directory structure](#project-directory-structure)
- [Prerequisites](#prerequisites)
- [Installation and environment setup for Windows PowerShell](#installation-and-environment-setup-for-windows-powershell)
- [Environment variable configuration](#environment-variable-configuration)
- [Database setup and initialization](#database-setup-and-initialization)
- [How to run the FastAPI backend](#how-to-run-the-fastapi-backend)
- [API documentation and endpoint descriptions](#api-documentation-and-endpoint-descriptions)
- [Example prediction request and response](#example-prediction-request-and-response)
- [Model artifacts and reproducibility](#model-artifacts-and-reproducibility)
- [Testing and troubleshooting](#testing-and-troubleshooting)
- [Known limitations](#known-limitations)
- [Security and responsible-use notes](#security-and-responsible-use-notes)
- [Future improvements](#future-improvements)

## Project status

| Area | Status | Notes |
| --- | --- | --- |
| FastAPI backend | Implemented | Core API, event storage, prediction endpoint, health checks |
| ML model loading and inference | Implemented | XGBoost model loads from `backend/artifacts/nids_xgboost_reduced.json` |
| Database integration | Implemented | SQLAlchemy + PostgreSQL/Neon configuration |
| Event persistence | Implemented | Prediction and event records saved to `network_events` |
| Training notebook | Implemented | The ML pipeline is in `ml/nids_training.ipynb` |
| Frontend React app | Implemented | `frontend/` dashboard reads live API event data |
| Real-time packet capture / live monitoring | Planned | Not implemented |
| Automatic blocking / active mitigation | Planned | Not implemented |
| Production deployment | Planned | Not implemented |

## Overview and motivation

This project explores a flow-based approach to network intrusion detection using supervised machine learning. The backend consumes a fixed set of 73 precomputed connection-flow features, predicts the likely attack class, and stores an event record in a database for later inspection.

This is a good fit for a college project, portfolio, and technical review because it combines:

- a real network intrusion detection problem,
- a tabular ML pipeline,
- an API layer for serving predictions,
- and a small persistence layer for event tracking.

## Features currently implemented

The following features were confirmed in the codebase during inspection:

- FastAPI application with root and health-check endpoints
- `POST /api/predict` endpoint to score a flow record against the trained model
- Validation of the required 73 input features via Pydantic and runtime checks
- XGBoost model loading from a saved artifact file
- Metadata loading for the exact feature list and class names from `backend/artifacts/nids_metadata.json`
- SQLAlchemy-based PostgreSQL integration via a `DATABASE_URL` environment variable
- Event creation and listing endpoints under `/api/events`
- Basic database initialization via `backend/app/init_db.py`
- Event persistence for `flow_id`, predicted class, confidence, alert flag, and timestamps
- Model contract endpoint at `/api/model`, event filters, and `/api/events/stats` aggregates
- React command-center dashboard with event filters and event inspection

## Architecture overview

The repository is organized into a lightweight backend-first ML service:

- `backend/app/main.py` creates the FastAPI app and registers routers
- `backend/app/api/predict.py` implements the prediction endpoint
- `backend/app/api/events.py` implements manual event creation and listing
- `backend/app/services/predictor.py` loads the model and performs inference
- `backend/app/db/database.py` configures SQLAlchemy and the database engine
- `backend/app/db/models.py` defines the persisted `NetworkEvent` schema
- `backend/app/schemas/*.py` defines request/response validation models
- `backend/artifacts/` stores the trained model and metadata artifacts
- `ml/nids_training.ipynb` contains the notebook-based training pipeline and dataset inspection steps

## Technology stack

The current codebase relies on the following stack:

- Python 3.x runtime
- FastAPI
- Pydantic v2
- SQLAlchemy
- PostgreSQL / Neon
- XGBoost
- scikit-learn / joblib / NumPy / pandas
- python-dotenv
- psycopg
- uvicorn

## Machine-learning pipeline

The training notebook and runtime artifacts indicate a flow-based supervised learning workflow:

1. Load the CIC-IDS2017 flow dataset from the local `dataset/CIC-IDS2017/MachineLearningCVE` directory.
2. Inspect and validate feature columns and label values.
3. Remove a small set of redundant or weakly informative columns during feature preparation.
4. Train an XGBoost multiclass classifier.
5. Save the trained model to `backend/artifacts/nids_xgboost_reduced.json`.
6. Save model metadata to `backend/artifacts/nids_metadata.json`.
7. Load that metadata at runtime and validate the expected number of features.
8. Accept a single feature vector at inference time and return the predicted class and confidence.

Important: the current prediction endpoint does not extract features from raw packets or PCAP files. It expects a precomputed 73-feature flow vector in the model's exact feature names.

## Supported classification categories

The model metadata defines these nine classes:

| Class name | Meaning |
| --- | --- |
| Bot | Botnet traffic |
| BruteForce | Brute-force attack |
| DDoS | Distributed denial of service |
| DoS | Denial of service |
| Heartbleed | Heartbleed exploit |
| Infiltration | Infiltration attempt |
| Normal | Benign traffic |
| PortScan | Port scanning |
| WebAttack | Web-related attack |

## Dataset source, attribution, and usage notes

The project references the CIC-IDS2017 MachineLearningCVE dataset as the source used for model training. The notebook output confirms the dataset directory structure under `dataset/CIC-IDS2017/MachineLearningCVE` and shows CSV files for Monday through Friday traffic captures.

Usage notes:

- This dataset is large and is not suitable for casual Git or release distribution.
- The raw CSV files are intentionally kept local in this repo snapshot and should be retrieved from the original dataset source when needed.
- The project currently does not include dataset licensing text in the repository, so original distribution terms should be reviewed before publication or redistribution.
- CIC-IDS2017 is a benchmark dataset with known class imbalance and rare attack classes, which should be considered when interpreting results.

## Model evaluation results

The saved artifact was evaluated locally using the notebook's preprocessing and
label grouping, concatenated CIC-IDS2017 CSVs, and the same stratified
`train_test_split(test_size=0.20, random_state=42)` protocol. This is an
offline benchmark, not live-traffic validation or an independent-day test.

| Metric | Result |
| --- | ---: |
| Held-out rows | 565,576 |
| Accuracy | 0.9992609 |
| Macro-F1 | 0.9232179 |
| PortScan recall | 0.999622 |

Per-class results:

| Class | Precision | Recall | F1 | Support |
| --- | ---: | ---: | ---: | ---: |
| Bot | 0.913580 | 0.757033 | 0.827972 | 391 |
| BruteForce | 0.999638 | 0.998915 | 0.999277 | 2,766 |
| DDoS | 0.999922 | 0.999883 | 0.999902 | 25,605 |
| DoS | 0.998472 | 0.999623 | 0.999047 | 50,343 |
| Heartbleed | 1.000000 | 0.500000 | 0.666667 | 2 |
| Infiltration | 1.000000 | 0.714286 | 0.833333 | 7 |
| Normal | 0.999716 | 0.999395 | 0.999555 | 454,265 |
| PortScan | 0.994456 | 0.999622 | 0.997032 | 31,761 |
| WebAttack | 0.990741 | 0.981651 | 0.986175 | 436 |

The benchmark is subject to dataset leakage and class imbalance risks because
the split is random across captures. It does not establish performance on
new networks. The 11-flow local sample was all predicted `Normal` with
confidence 0.999989–0.999999; those rows describe loopback, localhost, and
mDNS traffic, not a labelled PortScan test, so no attack prediction was
forced.

## Project directory structure

```text
NIDS/
├── backend/
│   ├── .env
│   ├── .venv/                 # local virtual environment
│   ├── app/
│   │   ├── api/
│   │   │   ├── events.py
│   │   │   └── predict.py
│   │   ├── db/
│   │   │   ├── database.py
│   │   │   └── models.py
│   │   ├── schemas/
│   │   │   ├── event.py
│   │   │   └── prediction.py
│   │   ├── services/
│   │   │   ├── __init___.py
│   │   │   └── predictor.py
│   │   ├── init_db.py
│   │   ├── inspect_dataset.py
│   │   ├── inspect_dataset_quality.py
│   │   ├── main.py
│   │   └── test_db.py
│   ├── artifacts/
│   │   ├── label_encoder.joblib
│   │   ├── nids_metadata.json
│   │   └── nids_xgboost_reduced.json
│   └── .env.example (if created in this folder)
├── dataset/
│   └── CIC-IDS2017/
│       └── MachineLearningCVE/
├── ml/
│   └── nids_training.ipynb
├── real_normal_test.json
├── test_prediction.json
├── README.md
├── .gitignore
├── .env.example
└── .venv/ (optional local environment at repo root if created)
```

## Prerequisites

Before running the project, make sure you have:

- Python 3.x installed on your Windows machine
- A PostgreSQL-compatible database (Neon/PostgreSQL is used here)
- Access to the local dataset or a valid training artifact bundle
- A terminal with PowerShell or similar shell
- Network access to the configured database host

## Installation and environment setup for Windows PowerShell

From the repository root:

```powershell
cd "C:\path\to\NIDS"

# Create a virtual environment
python -m venv backend\.venv

# Activate it
.\backend\.venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip

# Install runtime and ML dependencies
python -m pip install fastapi uvicorn sqlalchemy pydantic python-dotenv psycopg xgboost joblib numpy pandas scikit-learn
```

If you are working from inside the `backend` directory, use:

```powershell
cd "C:\path\to\NIDS\backend"
.\.venv\Scripts\Activate.ps1
```

## Environment variable configuration

The application reads `DATABASE_URL` and `NEON_AUTH_BASE_URL` using `python-dotenv`.

Use the provided template:

```powershell
Copy-Item .env.example backend\.env
```

The repository includes a safe template at `.env.example` with placeholders only. Do not insert real credentials into the template or commit a populated `.env` file.

Example:

```env
DATABASE_URL="postgresql+psycopg://username:password@host:5432/database_name?sslmode=require"
NEON_AUTH_BASE_URL="https://your-project-name.neonauth.region.neon.tech/database_name/auth"
```

## Database setup and initialization

After setting the environment variables, initialize the tables:

```powershell
cd "C:\path\to\NIDS\backend"
.\.venv\Scripts\Activate.ps1
python app\init_db.py
```

This calls `Base.metadata.create_all(bind=engine)` and creates the `network_events` table if the database is reachable.

## How to run the FastAPI backend

From the backend directory:

```powershell
cd "C:\path\to\NIDS\backend"
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Then open:

- `http://localhost:8000/`
- `http://localhost:8000/api/health`
- `http://localhost:8000/docs`

## How to run the React dashboard

In a second PowerShell window:

```powershell
cd "C:\path\to\NIDS\frontend"
npm install
npm run dev
```

Open the Vite URL (normally `http://localhost:5173`). Set
`VITE_API_URL` if the backend is hosted somewhere other than
`http://127.0.0.1:8000`. The dashboard displays persisted API events only; it
does not invent traffic. No events appear until flows are posted to the
prediction endpoint.

## API documentation and endpoint descriptions

The FastAPI app exposes the following endpoints based on the confirmed code:

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/` | GET | Basic status message |
| `/api/health` | GET | Health check |
| `/api/predict` | POST | Predict the class of a flow using the trained model |
| `/api/events` | POST | Create a manual event record |
| `/api/events` | GET | List recent events |
| `/api/events/stats` | GET | Aggregate event counts for the dashboard |
| `/api/model` | GET | Return the loaded model feature/class contract |

### `/api/predict`

This endpoint accepts a JSON body containing `flow_id` plus the 73 required flow features. The runtime validator requires the exact feature names found in `backend/artifacts/nids_metadata.json`.

It returns:

- `flow_id`
- `predicted_class`
- `confidence`
- `alert`
- `model_status`

The `alert` field is set to `true` whenever the predicted class is not `Normal`.

### `/api/events`

The event routes allow storing or retrieving event history in the PostgreSQL database. `GET /api/events` supports `limit` (1–100), `alert`, `predicted_class`, `source_ip`, and `destination_ip` filters.

## Example prediction request and response

The backend expects the full feature vector in the model's exact names. A sample payload follows the same shape as `real_normal_test.json` and uses a subset for readability:

```json
{
  "flow_id": "flow-001",
  "Destination Port": 54865.0,
  "Flow Duration": 3.0,
  "Total Fwd Packets": 2.0,
  "Total Backward Packets": 0.0,
  "Total Length of Fwd Packets": 12.0,
  "Total Length of Bwd Packets": 0.0,
  "Fwd Packet Length Max": 6.0,
  "Fwd Packet Length Min": 6.0,
  "Fwd Packet Length Mean": 6.0,
  "Fwd Packet Length Std": 0.0,
  "Bwd Packet Length Max": 0.0,
  "Bwd Packet Length Min": 0.0,
  "Flow Bytes/s": 4000000.0,
  "Flow Packets/s": 666666.6875,
  "Flow IAT Mean": 3.0,
  "Flow IAT Std": 0.0,
  "Flow IAT Max": 3.0,
  "Flow IAT Min": 3.0,
  "...": "remaining 73-feature vector fields",
  "Idle Min": 0.0
}
```

Example response:

```json
{
  "flow_id": "flow-001",
  "predicted_class": "Normal",
  "confidence": 0.9678,
  "alert": false,
  "model_status": "loaded"
}
```

The exact prediction will vary with the input values. Confidence is the probability assigned by the model for the winning class; it is not a guarantee of correctness.

## Model artifacts and reproducibility

The model is stored in:

- `backend/artifacts/nids_xgboost_reduced.json`
- `backend/artifacts/nids_metadata.json`
- `backend/artifacts/label_encoder.joblib`

The runtime loader in `backend/app/services/predictor.py` loads the XGBoost model and validates that the number of model features matches the metadata and the expected 73-feature setup.

Notes:

- The saved XGBoost artifact is compact enough for GitHub hosting in a typical repository (about 5.8 MB in this working copy), but GitHub file-size limits still matter for large assets.
- The raw CIC-IDS2017 CSV files are much larger and should not be committed unless there is a specific, well-justified reason and redistribution is allowed.
- The project currently does not include a formal reproducibility script beyond the notebook and artifact bundle.

## Testing and troubleshooting

### Safe validation checks

The project was checked with:

```powershell
cd "C:\path\to\NIDS\backend"
.\.venv\Scripts\Activate.ps1
python -m compileall app
```

This passed for the Python package.

### No test suite was found

The repository currently contains no explicit pytest or unittest suite in the checked-in code. A fast API smoke check can be done by importing the app and requesting the health endpoint, but live database-dependent routes require a valid `DATABASE_URL`.

### Troubleshooting hints

- If `DATABASE_URL` is missing or invalid, the app will fail during startup because `database.py` raises a runtime error.
- If model metadata or feature names do not match the XGBoost model, the predictor raises a runtime error.
- If you are using the app from the repo root rather than the `backend` directory, ensure the environment file is in the working directory or copy the values into the active shell environment.
- The first model import may take a few seconds because the XGBoost artifact is loaded into memory.

## Known limitations

- The backend predicts on precomputed flow features only; it does not read raw packet capture data.
- The system is a research-oriented proof of concept rather than a hardened production IDS.
- The frontend is a demonstration dashboard, not a packet-capture UI; it polls persisted API data every five seconds.
- The reported benchmark is a random held-out split and should not be presented as live or independent-network accuracy.
- CIC-IDS2017 is class-imbalanced, and rare attack classes are statistically harder to model reliably.
- The current implementation stores event records but does not perform live packet inspection, active blocking, or automated response actions.

## Security and responsible-use notes

- Do not commit `.env` or any credentials to Git history.
- Keep database credentials in local environment files only.
- Treat predictive outputs as decision-support signals, not as proof of malicious activity.
- Validate the model against your own network environment before any operational or production use.
- Ensure that any network telemetry processed by the system is compliant with your institution's privacy and security policies.

## Future improvements

Planned or recommended next steps include:

- add automated tests for schema validation and model inference,
- add a data ingestion or feature-engineering pipeline for real packet or flow extraction,
- add a capture-separated and time-separated evaluation report,
- add CI/CD automation for linting and backend tests,
- add deployment guidance for Docker, Render, Railway, or a self-hosted server,
- consider a production-ready logging, alerting, and retention design.

The project is currently best described as a backend-first ML prototype rather than a full, production-ready NIDS deployment.
