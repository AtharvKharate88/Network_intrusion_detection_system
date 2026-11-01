# NIDS Laptop B/K Demonstration Guide

This guide demonstrates the complete two-laptop workflow for the Network
Intrusion Detection System. In this guide:

- **Laptop B** is this computer. It hosts the demonstration website and runs
  TShark, CICFlowMeter, the ML model, FastAPI, PostgreSQL, and the React
  dashboard.
- **Laptop K** is the second laptop. It opens the website on Laptop B and can
  generate authorized test traffic.

The physical workflow is:

```text
Laptop K browser
    ↓ Wi-Fi request to Laptop B
Website hosted on Laptop B
    ↓ packets arrive on Laptop B's Wi-Fi interface
TShark capture on Laptop B
    ↓
CICFlowMeter flow extraction
    ↓
Existing 73-feature adapter
    ↓
FastAPI + XGBoost prediction
    ↓
PostgreSQL event storage
    ↓
React dashboard on Laptop B
```

Only use the suspicious-traffic steps against Laptop B or another system for
which you have explicit authorization. Do not run scans or stress traffic
against public websites, school networks, or other devices.

The API accepts precomputed flow features. It does **not** read a PCAP file
directly. A PCAP must first be processed by a flow extractor such as
CICFlowMeter, and the resulting CSV can then be adapted and submitted.

## Physical setup and important network limitation

Connect both laptops to the same Wi-Fi router. Laptop B must be able to
receive connections from Laptop K. Wi-Fi client isolation, guest-network
settings, or a firewall can prevent this even when both laptops show the same
Wi-Fi name.

This design captures traffic because Laptop B is the **destination** of the
website connection. The packets are delivered to B's Wi-Fi adapter, so TShark
running on B can capture them. B does not need to be in monitor mode and does
not need to observe arbitrary traffic between other Wi-Fi clients.

Laptop B's Wi-Fi IP address is the address Laptop K must use. Do not use
`localhost` or `127.0.0.1` from Laptop K; those addresses refer to Laptop K
itself.

On Laptop B, find the Wi-Fi IPv4 address:

```powershell
Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object {$_.InterfaceAlias -match "Wi-Fi|Wireless"} |
  Select-Object InterfaceAlias,IPAddress
```

Record the result as `B_IP`, for example `192.168.1.30`. On Laptop K, verify
reachability before starting the NIDS:

```powershell
ping 192.168.1.30
```

If ping is blocked, test the website connection after hosting it below. If
Laptop K still cannot connect, check Windows Firewall and router client
isolation before changing the NIDS code.

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

## 3. Host the demonstration website on Laptop B

The NIDS dashboard is an operator interface, not the test website that Laptop
K will browse. For a simple, repeatable demonstration, host a small static
website on Laptop B with Python's built-in HTTP server.

On Laptop B, open a separate PowerShell window from the repository root:

```powershell
New-Item -ItemType Directory -Force demo-site | Out-Null
@'
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Laptop B Test Website</title>
</head>
<body>
  <h1>Laptop B NIDS demonstration website</h1>
  <p>This page is intentionally hosted on Laptop B for authorized testing.</p>
  <p><a href="/page-two.html">Open another test page</a></p>
</body>
</html>
'@ | Set-Content demo-site\index.html
@'
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Second page</title></head>
<body><h1>Second test page</h1><a href="/">Back</a></body>
</html>
'@ | Set-Content demo-site\page-two.html

Push-Location demo-site
& ..\backend\.venv\Scripts\python.exe -m http.server 8080 --bind 0.0.0.0
Pop-Location
```

Keep this PowerShell window open. The website is now listening on every
interface on Laptop B at TCP port `8080`. If Windows displays a firewall
prompt, allow Python on the private network only.

From Laptop K, open this address in a browser:

```text
http://B_IP:8080
```

For example:

```text
http://192.168.1.30:8080
```

If the page does not load, verify the B IP address, the Windows Firewall rule,
the router's client-isolation setting, and that the Python server window is
still running. The page must load from Laptop K before packet capture can be
demonstrated.

## 4. Start the backend on Laptop B

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

## 5. Submit one local demonstration flow

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

## 6. Confirm the stored event

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

## 7. Replay CSV flows

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

For a different shortened flow CSV, pass its path explicitly:

```powershell
.\backend\.venv\Scripts\python.exe tools\send_flows_to_api.py `
  --csv .\path\to\flows.csv `
  --time-unit seconds
```

For native CICFlowMeter output, use `microseconds` instead:

```powershell
.\backend\.venv\Scripts\python.exe tools\send_flows_to_api.py `
  --csv .\path\to\capture_Flow.csv `
  --time-unit microseconds
```

The CSV must contain the columns expected by `tools\flow_adapter.py`.
Declaring the wrong unit changes duration and inter-arrival-time features by a
factor of 1,000,000 and invalidates predictions.

## 8. Capture normal Laptop K website traffic

The repository includes an orchestration script that connects TShark,
CICFlowMeter, the existing feature adapter, and `/api/predict`.

First, verify that TShark is installed. If `tshark.exe` is not on PATH, pass
its full path with `--tshark`. List capture interfaces:

```powershell
& "C:\Program Files\Wireshark\tshark.exe" -D
```

Start the backend and the demonstration website on Laptop B, then capture for
30 seconds. Replace `5` with the interface number shown by `tshark -D`:

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

The default workflow captures one fixed-duration batch. Continuous mode below
repeats these batches; it is not packet-by-packet streaming. This is
intentionally the first integration milestone: verify that the monitor can see
authorized traffic and that the resulting flows match the model contract before
adding WebSockets.

### Restricting capture to Laptop K and Laptop B

Find Laptop K's address and Laptop B's Wi-Fi address, then restrict TShark to
that pair and the website port. For example, if K is `192.168.1.20`, B is
`192.168.1.30`, and the demonstration website is HTTP on port `8080`:

```powershell
.\backend\.venv\Scripts\python.exe tools\capture_to_api.py `
  --interface 5 `
  --duration 30 `
  --client-ip 192.168.1.20 `
  --server-ip 192.168.1.30 `
  --server-port 8080 `
  --tshark "C:\Program Files\Wireshark\tshark.exe"
```

The generated TShark capture filter is:

```text
host 192.168.1.20 and host 192.168.1.30 and tcp port 8080
```

This is a capture filter applied before packets are written, so unrelated
traffic on Laptop B is excluded. If the website uses HTTPS, use its HTTPS
port, commonly `443`. If the website uses another port, use that port instead.
The router must allow Laptop K to reach Laptop B, and Laptop B's firewall must
allow the website port.

Now perform normal activity from Laptop K while the capture is running:

1. Open `http://B_IP:8080`.
2. Refresh the page several times.
3. Open `page-two.html`.
4. Return to the home page.

When the capture ends, the script converts the packets into flows, sends each
flow to FastAPI, and stores the results. The dashboard on Laptop B will show
the source as Laptop K's IP and the destination as Laptop B's IP. Normal
browsing is expected to be classified as `Normal`, but verify the actual
prediction.

## 9. Authorized suspicious-traffic demonstration

The safest first suspicious demonstration is a limited TCP port scan from
Laptop K against Laptop B. This is appropriate for the model's `PortScan`
class and does not require attacking a third-party system.

Prepare a capture on Laptop B without restricting it to port 8080:

```powershell
.\backend\.venv\Scripts\python.exe tools\capture_to_api.py `
  --interface 5 `
  --duration 60 `
  --client-ip 192.168.1.20 `
  --server-ip 192.168.1.30 `
  --tshark "C:\Program Files\Wireshark\tshark.exe" `
  --heap 2g
```

The capture filter is:

```text
host 192.168.1.20 and host 192.168.1.30
```

From Laptop K, install Nmap and run this only against Laptop B's private
address:

```powershell
nmap -sT -Pn -p 1-1024 --max-rate 50 192.168.1.30
```

This is a bounded TCP connect scan of Laptop B. Do not scan a subnet, the
public Internet, or devices outside your lab. Do not use flood,
denial-of-service, credential-guessing, or exploit commands for this
demonstration.

After Laptop B finishes processing, inspect the events:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/events?limit=50&source_ip=192.168.1.20" |
  Format-Table flow_id, predicted_class, confidence, alert, destination_port
```

The expected outcome is one or more `PortScan` events with `alert: true`, but
the result must be measured. The model was trained on CIC-IDS2017-derived
flows, so a private-network scan may be classified differently.

To keep processing short capture chunks continuously until Ctrl+C:

```powershell
.\backend\.venv\Scripts\python.exe tools\capture_to_api.py `
  --interface 5 `
  --duration 30 `
  --client-ip 192.168.1.20 `
  --server-ip 192.168.1.30 `
  --server-port 8080 `
  --continuous `
  --tshark "C:\Program Files\Wireshark\tshark.exe"
```

Each chunk is independently converted, extracted, predicted, and stored. This
is continuous batch monitoring rather than packet-by-packet streaming. Stop it
with Ctrl+C after the demonstration. Generate normal website events by
browsing from K; generate suspicious events only with authorized, isolated
traffic and verify the resulting class rather than assuming the model will
label it correctly.

For continuous port-scan monitoring, remove `--server-port 8080` so multiple
destination ports are captured:

```powershell
.\backend\.venv\Scripts\python.exe tools\capture_to_api.py `
  --interface 5 `
  --duration 30 `
  --client-ip 192.168.1.20 `
  --server-ip 192.168.1.30 `
  --continuous `
  --tshark "C:\Program Files\Wireshark\tshark.exe" `
  --heap 2g
```

## 10. Start the dashboard

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

## 11. Optional validation

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
Laptop K opens http://B_IP:8080
        |
        v
TShark on Laptop B captures K <-> B packets
        |
        v
CICFlowMeter creates flow CSV
        |
        v
flow_adapter.py maps the 73 features
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
React command center on Laptop B
```

For the suspicious demonstration, Laptop K runs the authorized bounded Nmap
scan instead of only browsing the website. The capture filter is changed from
the website-port filter to the K-and-B host filter so scan attempts to
multiple ports are included.
