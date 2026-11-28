# NIDS - Development Handover

## Project Objective

Develop an AI-powered Network Intrusion Detection and
Attack Classification System capable of monitoring network
traffic, identifying suspected attack categories, and
displaying results through a web dashboard.

## Current Architecture

Network Traffic
    -> TShark / Npcap
    -> PCAP Capture
    -> Corrected CICFlowMeter
    -> 36-Feature Harmonization
    -> XGBoost Multiclass Classifier
    -> FastAPI Backend
    -> PostgreSQL Database
    -> React Dashboard

A separate stateful behavioral detector identifies
suspected port scans across consecutive capture batches.

## Completed Implementation

- Multi-source dataset preprocessing and integration.
- Feature compatibility and quality analysis.
- Binary and multiclass model training.
- Standalone and hierarchical architecture comparison.
- Corrected CICFlowMeter packet and flow handling.
- Automatic network capture and prediction submission.
- Stateful behavioral port scan detection.
- Backend, database and dashboard integration.
- Source-aware Java build caching.
- Python dependency configuration.
- Git exclusions for generated files and local captures.

## Active AI Model

Model: XGBoost standalone multiclass
Version: multiclass-v2
Features: 36
Classes: 12
Training samples: 266418
Validation samples: 57090
Test samples: 57090

Supported categories:

- Normal
- Analysis
- Backdoor
- BruteForce
- DoS
- Exploits
- Fuzzers
- Generic
- Reconnaissance
- Shellcode
- WebAttack
- Worms

Binary and hierarchical models are retained as research
alternatives.

## Offline Model Evaluation

Standalone multiclass test results:

- Accuracy: 83.38%
- Balanced accuracy: 55.19%
- Macro F1: 54.97%
- Weighted F1: 83.03%
- Attack detection recall: 84.54%
- Normal false positive rate: 6.52%
- Attack-type accuracy: 72.20%

These results use a stratified row-level holdout and
do not establish independent real-world accuracy.

## Behavioral Detection

Suspected port scans are detected when at least five
distinct destination ports are targeted by initial TCP
SYN packets within a 30-second observation window.

State is preserved across consecutive capture batches.

Behavioral alerts are stored and displayed separately
from AI classifications.

## Windows Setup

Required software:

- Python 3.12
- Node.js and npm
- Java 8 JDK
- Apache Maven
- Wireshark with TShark and Npcap
- PostgreSQL database access

From the repository root:

    python -m venv backend/.venv
    .\backend\.venv\Scripts\Activate.ps1
    python -m pip install -r backend/requirements.txt

Configure backend/.env with the authorized DATABASE_URL.
Never commit database credentials.

Configure JAVA_HOME to point to Java 8 and ensure Java
and Maven are available on PATH.

The capture script automatically builds CICFlowMeter
when the executable is missing or build inputs change.

The bundled Windows jNetPcap 1.4 library is installed
under Maven coordinates version 1.4.1 for compatibility.

## Running the Application

Terminal 1 - Backend, from repository root:

    .\backend\.venv\Scripts\Activate.ps1
    python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

Terminal 2 - Frontend:

    cd frontend
    npm ci
    npm run dev

Dashboard:

    http://127.0.0.1:5173

Terminal 3 - Capture:

    .\backend\.venv\Scripts\Activate.ps1
    python tools/capture_to_api.py --help

List available network interfaces:

    & "C:\Program Files\Wireshark\tshark.exe" -D

Two-laptop capture command template:

    python tools/capture_to_api.py --interface INTERFACE --duration 15 --continuous --client-ip CLIENT_IP --server-ip MONITOR_IP --heap 1g

Replace interface and IP placeholders with actual values.
Configure Java 8 and Maven in the capture terminal.

## Two-Laptop Demonstration

Laptop A: Authorized traffic-generating client.
Laptop B: Monitoring system, backend and dashboard.

Both laptops should use the same trusted network.

Validate:

- Normal client-to-server traffic.
- Authorized suspicious traffic.
- Automatic flow extraction.
- AI attack classification.
- Stateful behavioral alerts.
- Database persistence.
- Dashboard updates.
- Graceful monitoring shutdown.

The actual two-laptop demonstration remains pending.

## Known Limitations

- Independent live-network model evaluation is pending.
- Rare attack categories have weaker classification results.
- Recent browsing captures showed concerning alert rates.
- Model scores are not calibrated probabilities.
- Capture batch boundaries can split network flows.
- Behavioral alerts indicate suspected, not confirmed, scans.
- Graceful shutdown requires final verification.
- Fresh-machine dependency installation remains unverified.
- Maven compiler plugin version warning remains.
- The dashboard may contain historical predictions from
  earlier model versions and validation sessions.
- Current capture and extraction setup is Windows-oriented.

## Next Development Milestone

Perform the actual two-laptop end-to-end demonstration.

Record the results and correct any issues discovered.
Do not claim production readiness until independent
validation and reliability testing are completed.

## Version Control

Keep source code, intentional model artifacts and
documentation under version control.

Exclude credentials, virtual environments, local
captures, generated Java binaries and training outputs.

Consolidate related improvements into meaningful commits.
