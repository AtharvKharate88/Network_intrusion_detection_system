# NIDS Demonstration Guide

This guide demonstrates the complete local workflow for the Network Intrusion
Detection System:

1. Start the FastAPI prediction service.
2. Submit a 73-feature network flow.
3. Confirm that the prediction is stored as an event.
4. Replay several CSV flows.
5. View the persisted events in the React command center.

The API accepts precomputed flow features. It does **not** read a PCAP file
directly. A PCAP must first be processed by a flow extractor such as
CICFlowMeter, and the resulting CSV can then be adapted and submitted.

## Prerequisites

- Windows PowerShell
- Python 3.x
- Node.js and npm
- A reachable PostgreSQL database
- A configured `backend\.env` file containing `DATABASE_URL`

The model and metadata are already included in:

- `backend\artifacts\nids_xgboost_reduced.json`
- `backend\artifacts\nids_metadata.json`

## 1. Create the Python environment

Run these commands from the repository root:

```powershell
python -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install fastapi uvicorn sqlalchemy pydantic python-dotenv psycopg xgboost joblib numpy pandas scikit-learn requests
```

If PowerShell blocks script activation, run the following once for the current
PowerShell process and activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\backend\.venv\Scripts\Activate.ps1
```

Before continuing, verify that `backend\.env` contains a valid database URL.
Do not copy credentials into this guide or commit them to Git.

## 2. Initialize the database

From the repository root:

```powershell
Push-Location backend
.\.venv\Scripts\python.exe app\init_db.py
Pop-Location
```

Expected output:

```text
NIDS database tables created successfully.
```

This creates the `network_events` table if it does not already exist.

## 3. Start the backend

Open PowerShell window 1 and run:

```powershell
.\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

Keep this window running. Check that the service is ready from another
PowerShell window:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

Expected response:

```text
status  service
------  -------
healthy nids-backend
```

The interactive API documentation is available at
`http://127.0.0.1:8000/docs`.

## 4. Submit one demonstration flow

The repository includes a complete 73-feature sample payload in
`real_normal_test.json`. Submit it with:

```powershell
$body = Get-Content .\real_normal_test.json -Raw
Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/api/predict `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

The response contains the predicted class, confidence, alert status, and model
status. For example:

```text
flow_id              : real-normal-test-001
predicted_class      : Normal
confidence           : 0.9678
alert                : False
model_status         : loaded
```

The exact class and confidence depend on the saved model and input values.
`alert` is `True` whenever the predicted class is not `Normal`.

The sample has a fixed `flow_id`, so submitting it a second time returns HTTP
409 because event flow IDs must be unique. To run it again, change the
`flow_id` in a copy of the JSON:

```powershell
$body = Get-Content .\real_normal_test.json -Raw | ConvertFrom-Json
$body.flow_id = "demo-flow-002"
$body | ConvertTo-Json -Depth 10 | Set-Content .\demo-flow-002.json

Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/api/predict `
  -Method Post `
  -ContentType "application/json" `
  -Body (Get-Content .\demo-flow-002.json -Raw)
```

## 5. Confirm the stored event

Prediction requests are persisted in PostgreSQL. List the most recent events:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/events?limit=10" |
  Format-Table flow_id, predicted_class, confidence, alert, created_at
```

View aggregate counts used by the dashboard:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/events/stats |
  ConvertTo-Json
```

## 6. Replay CSV flows

The helper script reads `portscan-flows-v2.csv`, maps its columns to the exact
model feature names, and posts each row to `/api/predict`. Start the backend
first, then run:

```powershell
.\backend\.venv\Scripts\python.exe tools\send_flows_to_api.py
```

The script prints one result per row and a final success/failure summary. It
generates unique IDs such as `csv-flow-meta-0001`. If the same CSV is replayed
again, those IDs already exist and the API will report conflicts for those
rows.

For a different CSV, update `CSV_PATH` in
`tools\send_flows_to_api.py`. The CSV must contain the columns expected by
`tools\flow_adapter.py`; duration and inter-arrival-time values are converted
from seconds to the microseconds used by the trained model by default.

## 7. Capture with TShark and extract with CICFlowMeter

The repository includes an orchestration script that connects TShark,
CICFlowMeter, the existing feature adapter, and `/api/predict`.

First, verify that TShark is installed. If `tshark.exe` is not on PATH, pass
its full path with `--tshark`. List capture interfaces:

```powershell
& "C:\Program Files\Wireshark\tshark.exe" -D
```

Start the backend, then capture for 30 seconds. Replace `5` with the interface
number shown by `tshark -D`:

```powershell
.\backend\.venv\Scripts\python.exe tools\capture_to_api.py `
  --interface 5 `
  --duration 30 `
  --tshark "C:\Program Files\Wireshark\tshark.exe" `
  --heap 2g
```

The script:

1. saves a PCAP under `runtime\captures`,
2. converts `.pcapng` to classic `.pcap` when needed,
3. builds and runs the bundled CICFlowMeter with Maven and Java,
4. creates `<capture-name>_Flow.csv`,
5. maps the CICFlowMeter microsecond fields to the model’s 73 features,
6. sends each extracted flow to the running API.

To process an existing PCAP without capturing new traffic:

```powershell
.\backend\.venv\Scripts\python.exe tools\capture_to_api.py `
  --pcap .\portscan-traffic-v2.pcapng
```

To only generate the flow CSV and inspect it before prediction:

```powershell
.\backend\.venv\Scripts\python.exe tools\capture_to_api.py `
  --pcap .\portscan-traffic-v2.pcapng `
  --no-send
```

The bundled CICFlowMeter requires Java and its native jNetPcap library. On
Windows, the repository already contains the native library under
`tools\CICFlowMeter-master\jnetpcap\win`. The integration uses Maven because
the bundled Gradle 4.2 wrapper cannot run on Java 17. Maven installs the
bundled jNetPcap JAR locally and builds the executable JAR automatically on
the first run. Run PowerShell as Administrator if TShark reports a capture
permission error.

If CICFlowMeter processes a particularly large capture, increase the Java heap
with a value such as `--heap 4g`, provided the computer has enough available
memory.

This is a fixed-duration capture-and-process workflow, not continuous packet
streaming. It is intentionally the first integration milestone: verify that
the monitor can see authorized traffic and that the resulting flows match the
model contract before adding continuous capture or WebSockets.

## 8. Start the dashboard

Open PowerShell window 2 and run:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal, normally
`http://localhost:5173`.

The dashboard refreshes every five seconds and displays:

- total persisted flows,
- active alerts,
- normal traffic,
- attack events,
- recent flow events,
- attack-class distribution.

Click a row to inspect its flow ID, confidence, addresses, ports, and
timestamp. The **All**, **Alerts**, and **Normal** buttons filter the recent
event list.

The frontend uses `http://127.0.0.1:8000` by default. To use another backend
address, set `VITE_API_URL` before starting Vite:

```powershell
$env:VITE_API_URL = "http://127.0.0.1:8000"
npm run dev
```

## 9. Optional validation

With the backend stopped, run the Python syntax check:

```powershell
.\backend\.venv\Scripts\python.exe -m compileall backend\app
```

If the dashboard shows `API unavailable`, confirm that the backend terminal is
still running and that `http://127.0.0.1:8000/api/health` responds. If the
backend cannot start, check `backend\.env`, database connectivity, and that
the model artifacts exist in `backend\artifacts`.

## Demo flow summary

```text
real_normal_test.json
        |
        v
POST /api/predict
        |
        +--> XGBoost prediction
        +--> PostgreSQL network_events row
        |
        v
GET /api/events and GET /api/events/stats
        |
        v
React command center
```
