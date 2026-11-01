# NIDS Demonstration: Laptop B and Laptop K

This is the exact step-by-step demonstration procedure for this project.

-**Laptop B**: this computer. It runs the website, TShark, CICFlowMeter,
  FastAPI, PostgreSQL, the ML model, and the React dashboard.
-**Laptop K**: the second computer. It opens the website and generates
  authorized test traffic.
Do not skip a verification step. If one step fails, fix that step before
continuing. The NIDS cannot capture Laptop K traffic if Laptop K cannot first
reach the website on Laptop B.
## 0. What this demonstration proves
The completed demonstration will prove this path:
```text
Laptop K browser
    ↓
Website hosted on Laptop B
    ↓
Laptop B Wi-Fi adapter receives the packets
    ↓
TShark captures only Laptop K ↔ Laptop B traffic
    ↓
CICFlowMeter creates flow records
    ↓
The adapter creates the model's 73-feature vector
    ↓
FastAPI calls the XGBoost model
    ↓
PostgreSQL stores the prediction
    ↓
The React dashboard displays the event
```
The first test uses normal website browsing. The second test uses a bounded
TCP port scan from Laptop K against Laptop B only. Both laptops must be yours
or explicitly authorized for this test.
## 1. Prepare both laptops
### 1.1 Connect both laptops to the same network

On both laptops:
1. Connect to the same Wi-Fi network name.
2. Do not use a guest Wi-Fi network unless it permits devices to communicate.
3. Turn off VPN software temporarily, or make sure it does not route the test
   traffic elsewhere.
4. Confirm that Laptop B is connected through Wi-Fi, not a different adapter.
The same Wi-Fi name is not sufficient. The router may have **AP isolation**,
**client isolation**, or a guest-network rule that blocks Laptop K from
reaching Laptop B.
### 1.2 Identify Laptop B's Wi-Fi adapter and IP address
Run this on Laptop B in PowerShell:
```powershell
Get-NetAdapter |
  Where-Object {$_.Status -eq "Up"} |
  Format-Table Name,InterfaceDescription,Status,MacAddress,LinkSpeed
```
Find the adapter whose description is the wireless adapter. Note its `Name`,
usually `Wi-Fi`.
Now run:
```powershell
Get-NetIPConfiguration
```
Find the active Wi-Fi section and record its `IPv4Address`. It will commonly
look like `192.168.1.30` or `192.168.0.30`.
You can print only IPv4 addresses with:

```powershell
Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object {
    $_.IPAddress -notlike "127.*" -and
    $_.IPAddress -notlike "169.254.*"
  } |
  Format-Table InterfaceAlias,IPAddress,PrefixLength
```
Write down:
```text
B_IP = the IPv4 address on Laptop B's Wi-Fi adapter 
``'
Example:

```text
B_IP = 192.168.1.30
```

Do not use `127.0.0.1` or `localhost` as `B_IP`. Those addresses mean "this
same computer" and will not take Laptop K to Laptop B.

### 1.3 Identify Laptop K's IP address

Run this on Laptop K:

```powershell
Get-NetIPConfiguration
```

In the active Wi-Fi section, record the IPv4 address.

Write down:

```text
K_IP = the IPv4 address on Laptop K's Wi-Fi adapter
```

Example:

```text
K_IP = 192.168.1.20
```

The first three address sections commonly match:

```text
B_IP = 192.168.1.30
K_IP = 192.168.1.20
```

They do not have to end in particular numbers. They must be addresses from the
same reachable local network.

## 2. Verify that Laptop K can reach Laptop B

Do these tests before starting the website or NIDS.

### 2.1 Check the address range

On Laptop B:

```powershell
Get-NetIPConfiguration
```

On Laptop K:

```powershell
Get-NetIPConfiguration
```

Compare the IPv4 address and prefix length. If the prefix length is `/24`,
addresses such as `192.168.1.20` and `192.168.1.30` are normally in the same
local subnet. If the addresses are on different networks, do not continue
until the router configuration is understood.

### 2.2 Test ping from Laptop K

Replace the example address with the actual `B_IP`:

```powershell
ping 192.168.1.30
```

Interpret the result:

- `Reply from ...` means basic IP reachability works.
- `Request timed out` does **not** always mean the website is unreachable;
  Windows may block ICMP ping. Continue with the TCP test below.
- `Destination host unreachable` usually indicates a wrong address, Wi-Fi
  isolation, or a network connection problem.

### 2.3 Test a TCP port after the website is started

The TCP test in section 4 is more important than ping because the website uses
TCP. Do not proceed to capture until this returns `TcpTestSucceeded: True`.

## 3. Make Laptop B reachable on the private network

### 3.1 Set the Wi-Fi network profile to Private on Laptop B

Run PowerShell as Administrator on Laptop B:

```powershell
Get-NetConnectionProfile
```

Find the Wi-Fi profile and note its `InterfaceIndex`. Then run, replacing
`<INDEX>` with that number:

```powershell
Set-NetConnectionProfile `
  -InterfaceIndex <INDEX> `
  -NetworkCategory Private
```

Verify:

```powershell
Get-NetConnectionProfile |
  Format-Table Name,InterfaceAlias,NetworkCategory,IPv4Connectivity
```

The Wi-Fi row should show:

```text
NetworkCategory : Private
```

If Windows does not allow the profile to be changed, use the normal Windows
Settings application to mark the current Wi-Fi network as Private.

### 3.2 Check Windows Firewall before creating a rule

On Laptop B, run PowerShell as Administrator:

```powershell
Get-NetFirewallProfile |
  Format-Table Name,Enabled,DefaultInboundAction
```

Do not turn the firewall off. Create a narrow inbound rule only for the test
website port:

```powershell
New-NetFirewallRule `
  -DisplayName "NIDS demo website 8080" `
  -Direction Inbound `
  -Action Allow `
  -Protocol TCP `
  -LocalPort 8080 `
  -Profile Private
```

Verify that the rule exists:

```powershell
Get-NetFirewallRule -DisplayName "NIDS demo website 8080" |
  Format-Table DisplayName,Enabled,Direction,Action,Profile
```

This rule permits only TCP port `8080` on the Private profile. Remove it after
the demonstration:

```powershell
Remove-NetFirewallRule -DisplayName "NIDS demo website 8080"
```

### 3.3 Check router client isolation

If Laptop K still cannot reach Laptop B after the firewall rule:

1. Check whether either laptop is connected to a guest network.
2. Open the router's administration page using the router address shown by
   `Get-NetIPConfiguration`.
3. Look for settings named `AP Isolation`, `Client Isolation`, `Wireless
   Isolation`, or `Guest Isolation`.
4. Disable isolation only for this authorized private demonstration network, or
   connect both laptops to a non-guest network that permits client-to-client
   traffic.
5. Reconnect both laptops to Wi-Fi.
6. Repeat the IP and TCP tests.

Do not change router settings if you do not own or administer the network.
Ask the network administrator for a permitted test network instead.

## 4. Host a website on Laptop B

The existing React dashboard is not the website that Laptop K will browse. It
is the monitoring dashboard. Create a separate, simple test website on
Laptop B.

From the repository root on Laptop B, open a new PowerShell window and run:

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
  <p>This site is hosted locally on Laptop B for authorized testing.</p>
  <p><a href="/page-two.html">Open page two</a></p>
</body>
</html>
'@ | Set-Content -Encoding utf8 demo-site\index.html

@'
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Laptop B Test Website - Page Two</title>
</head>
<body>
  <h1>Page two</h1>
  <p>This second page creates another normal HTTP request.</p>
  <p><a href="/">Return home</a></p>
</body>
</html>
'@ | Set-Content -Encoding utf8 demo-site\page-two.html
```

Start the website so it listens on Laptop B's Wi-Fi interface and not only on
Laptop B's loopback interface:

```powershell
Push-Location demo-site
& ..\backend\.venv\Scripts\python.exe -m http.server 8080 --bind 0.0.0.0
```

Keep this window open. The server is running while this command is active.
The address `0.0.0.0` means "listen on all local interfaces"; Laptop K still
connects to the specific address `http://B_IP:8080`.

### 4.1 Verify the website on Laptop B

Open a second PowerShell window on Laptop B:

```powershell
Invoke-WebRequest http://127.0.0.1:8080 |
  Select-Object StatusCode,Content
```

Expected:

```text
StatusCode : 200
```

Verify that the server is listening:

```powershell
Get-NetTCPConnection -LocalPort 8080 -State Listen |
  Format-Table LocalAddress,LocalPort,State,OwningProcess
```

The local address should be `0.0.0.0` or the Wi-Fi address, not only
`127.0.0.1`.

### 4.2 Verify the website from Laptop K

On Laptop K, first run:

```powershell
Test-NetConnection 192.168.1.30 -Port 8080
```

Replace `192.168.1.30` with the actual `B_IP`.

You must see:

```text
TcpTestSucceeded : True
```

Then open this exact address in a browser on Laptop K:

```text
http://192.168.1.30:8080
```

Replace the address with the actual `B_IP`.

If the browser cannot load the page:

1. Confirm the Python server window is still running.
2. Confirm Laptop K uses `B_IP`, not `localhost`.
3. Repeat `Test-NetConnection`.
4. Confirm the firewall rule is enabled.
5. Confirm both laptops are not on an isolated guest network.
6. Check the Python server output for a request from Laptop K.

Do not continue until the page loads from Laptop K.

## 5. Start and verify the NIDS backend on Laptop B

Open another PowerShell window on Laptop B from the repository root:

```powershell
.\backend\.venv\Scripts\python.exe -m uvicorn app.main:app `
  --app-dir backend `
  --host 127.0.0.1 `
  --port 8000 `
  --reload
```

The backend is intentionally bound to `127.0.0.1` because the dashboard and
capture pipeline run on Laptop B. Laptop K does not need to access the FastAPI
API.

Verify from another Laptop B PowerShell window:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

Expected:

```text
status  service
------  -------
healthy nids-backend
```

If this fails, stop and fix the backend before capturing traffic.

## 6. Find Laptop B's TShark interface

On Laptop B:

```powershell
& "C:\Program Files\Wireshark\tshark.exe" -D
```

Example output:

```text
1. \Device\NPF_{...} (Ethernet)
2. \Device\NPF_{...} (Wi-Fi)
```

Use the number next to the active Wi-Fi adapter. Do not assume it is `5`.
Call that value `B_WIFI_INTERFACE`.

To confirm which adapter is active:

```powershell
Get-NetAdapter |
  Where-Object {$_.Status -eq "Up"} |
  Format-Table Name,InterfaceDescription,Status
```

If TShark reports a permission error, close it, open PowerShell as
Administrator, and repeat the interface listing and capture.

## 7. Capture normal website traffic from Laptop K

Use the actual values for `K_IP`, `B_IP`, and `B_WIFI_INTERFACE`.

Start this command on Laptop B:

```powershell
.\backend\.venv\Scripts\python.exe tools\capture_to_api.py `
  --interface B_WIFI_INTERFACE `
  --duration 30 `
  --client-ip K_IP `
  --server-ip B_IP `
  --server-port 8080 `
  --tshark "C:\Program Files\Wireshark\tshark.exe" `
  --heap 2g
```

For example, if the actual values are interface `5`, K `192.168.1.20`, and B
`192.168.1.30`:

```powershell
.\backend\.venv\Scripts\python.exe tools\capture_to_api.py `
  --interface 5 `
  --duration 30 `
  --client-ip 192.168.1.20 `
  --server-ip 192.168.1.30 `
  --server-port 8080 `
  --tshark "C:\Program Files\Wireshark\tshark.exe" `
  --heap 2g
```

The script uses this capture filter:

```text
host K_IP and host B_IP and tcp port 8080
```

This filter is applied by TShark before writing the capture, so unrelated
traffic on Laptop B is excluded.

While the command is running, on Laptop K:

1. Open `http://B_IP:8080`.
2. Refresh it three times.
3. Open `http://B_IP:8080/page-two.html`.
4. Return to the home page.

Wait until the capture and extraction finish. A successful run ends with a
summary similar to:

```text
Sending <number> extracted flows to http://127.0.0.1:8000/api/predict...
Completed: <number> succeeded, 0 failed.
```

The exact number depends on browser requests and timing.

## 8. Verify the normal prediction in the API and dashboard

On Laptop B:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/events?limit=20" |
  Format-Table flow_id,predicted_class,confidence,alert,source_ip,destination_ip,created_at
```

Confirm that recent rows contain:

- Laptop K's IP as `source_ip` or the flow's observed source address,
- Laptop B's IP as `destination_ip` for requests directed to B,
- destination port `8080`,
- a predicted class and confidence.

The existing API stores events in PostgreSQL through
[predict.py](./backend/app/api/predict.py), and the dashboard reads them from
`/api/events` and `/api/events/stats`.

## 9. Start and verify the React dashboard on Laptop B

Open another Laptop B PowerShell window:

```powershell
Push-Location frontend
npm install
npm run dev
```

Open the Vite address shown in the terminal, usually:

```text
http://localhost:5173
```

The dashboard refreshes every five seconds. Confirm that the normal flows
appear in **Recent flow events** and that the totals change after a capture.
Click a row to inspect the flow ID, addresses, ports, confidence, and time.

## 10. Authorized suspicious-traffic demonstration

The recommended first suspicious demonstration is a bounded TCP connect scan
from Laptop K against Laptop B only. It is intended to exercise the model's
`PortScan` category without using flooding, exploitation, or credential
guessing.

### 10.1 Start a scan-focused capture on Laptop B

Do not restrict this capture to port `8080`, because a port scan must include
multiple destination ports:

```powershell
.\backend\.venv\Scripts\python.exe tools\capture_to_api.py `
  --interface 5 `
  --duration 60 `
  --client-ip 192.168.1.20 `
  --server-ip 192.168.1.30 `
  --tshark "C:\Program Files\Wireshark\tshark.exe" `
  --heap 2g
```

Replace all example values with the actual interface, `K_IP`, and `B_IP`.
This produces the filter:

```text
host K_IP and host B_IP
```

### 10.2 Generate the bounded scan from Laptop K

Install Nmap on Laptop K using an approved installation method. Then run this
only against Laptop B's private Wi-Fi address:

```powershell
nmap -sT -Pn -p 1-1024 --max-rate 50 B_IP
```

Example:

```powershell
nmap -sT -Pn -p 1-1024 --max-rate 50 192.168.1.30
```

This scans only ports 1 through 1024 on Laptop B and limits the request rate.
Do not scan the whole subnet, the public Internet, or any device you do not
administer. Do not use flood, denial-of-service, exploit, or password-guessing
commands for this demonstration.

### 10.3 Verify the scan result

Wait for Laptop B's capture, flow extraction, and prediction process to finish:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/events?limit=100&source_ip=K_IP" |
  Format-Table flow_id,predicted_class,confidence,alert,destination_port,created_at
```

Replace `K_IP` with the actual address. Also check the dashboard's **Alerts**
filter.

`PortScan` with `alert: true` is the expected result, but it is not guaranteed.
The model was trained on CIC-IDS2017-derived flow data, so record the actual
class and confidence produced by this private-lab test.

## 11. Optional continuous mode

The current continuous option processes repeated fixed-duration chunks. It is
continuous batch monitoring, not packet-by-packet streaming:

```powershell
.\backend\.venv\Scripts\python.exe tools\capture_to_api.py `
  --interface 5 `
  --duration 30 `
  --client-ip 192.168.1.20 `
  --server-ip 192.168.1.30 `
  --server-port 8080 `
  --continuous `
  --tshark "C:\Program Files\Wireshark\tshark.exe" `
  --heap 2g
```

Press `Ctrl+C` to stop. For a continuous port-scan test, remove
`--server-port 8080` so traffic to multiple ports is captured.

## 12. Troubleshooting decision table

| Symptom | Check |
|---|---|
| Laptop K cannot open the website | Confirm `B_IP`, Python server is running, `Test-NetConnection B_IP -Port 8080`, Private firewall rule, and router client isolation |
| `TcpTestSucceeded: False` | Laptop B firewall, wrong IP, guest Wi-Fi, AP/client isolation, or server not listening |
| Laptop B website works locally but not from K | Server may be bound to `127.0.0.1`; restart with `--bind 0.0.0.0` |
| TShark captures zero packets | Wrong interface number, wrong IPs, wrong port, or K did not browse during the capture |
| TShark permission error | Run the capture PowerShell as Administrator |
| CSV is created but no predictions succeed | Check the backend health endpoint and the generated CSV header |
| Predictions succeed but dashboard is empty | Confirm the dashboard uses `http://127.0.0.1:8000`, refresh it, and query `/api/events` directly |
| Scan is classified as `Normal` | Record the actual result; model predictions are not guaranteed for new traffic |

## 13. Cleanup after the demonstration

Stop the following with `Ctrl+C` in their respective PowerShell windows:

1. TShark/CICFlowMeter pipeline.
2. React dashboard development server.
3. Python test website.
4. FastAPI backend, if no longer needed.

If the temporary firewall rule was created, remove it from an Administrator
PowerShell:

```powershell
Remove-NetFirewallRule -DisplayName "NIDS demo website 8080"
```

The `demo-site` folder and `runtime\captures` contain demonstration data. Keep
or remove them according to your project-record requirements.
