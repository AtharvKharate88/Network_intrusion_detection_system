"""Capture or process PCAP traffic, extract CICFlowMeter flows, and predict them."""

import argparse
import csv
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

import requests

ROOT = Path(__file__).resolve().parent.parent
FLOWMETER_DIR = ROOT / "tools" / "CICFlowMeter-master"
METADATA_PATH = ROOT / "backend" / "artifacts" / "nids_metadata_v2.json"
DEFAULT_OUTPUT_DIR = ROOT / "runtime" / "captures"
sys.path.insert(0, str(ROOT))
from tools.flow_adapter import adapt_flow
from tools.scan_detector import PortScanDetector


def find_tshark(explicit_path: str | None) -> str:
    candidates = []
    if explicit_path:
        candidates.append(Path(explicit_path))
    candidates.extend(
        [
            Path(shutil.which("tshark") or ""),
            Path(os.environ.get("ProgramFiles", "")) / "Wireshark" / "tshark.exe",
            Path(os.environ.get("ProgramFiles(x86)", "")) / "Wireshark" / "tshark.exe",
        ]
    )
    for candidate in candidates:
        if str(candidate) and candidate.is_file():
            return str(candidate)
    raise FileNotFoundError(
        "TShark was not found. Install Wireshark with TShark, add its folder "
        "to PATH, or pass --tshark C:\\path\\to\\tshark.exe."
    )


def capture_pcap(
    tshark: str,
    interface: str,
    duration: int,
    output: Path,
    capture_filter: str | None = None,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        tshark,
        "-i",
        interface,
        "-a",
        f"duration:{duration}",
        "-w",
        str(output),
    ]
    if capture_filter:
        command[3:3] = ["-f", capture_filter]
    print(f"Starting TShark capture on interface {interface} for {duration}s...")
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"TShark failed with exit code {result.returncode}. "
            "Try an elevated PowerShell window and verify the interface."
        )
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"TShark did not create a usable capture: {output}")


def normalize_pcap(pcap: Path, output_dir: Path, tshark: str | None) -> Path:
    if pcap.suffix.lower() == ".pcap":
        return pcap
    tshark_path = find_tshark(tshark)
    normalized = output_dir / f"{pcap.stem}-cicflowmeter.pcap"
    print(f"Converting {pcap.name} to classic PCAP format...")
    result = subprocess.run(
        [
            tshark_path,
            "-r",
            str(pcap),
            "-F",
            "pcap",
            "-w",
            str(normalized),
        ],
        check=False,
    )
    if result.returncode != 0 or not normalized.is_file():
        raise RuntimeError("TShark could not convert the capture to PCAP format.")
    return normalized


def build_flowmeter(flowmeter_dir: Path) -> Path:
    target_dir = flowmeter_dir / "target"
    jars = sorted(target_dir.glob("CICFlowMeterV3-*.jar"))
    bundled_jar = next(
        (
            path
            for path in flowmeter_dir.glob("jnetpcap/win/*/jnetpcap.jar")
            if "1.4" in path.parent.name
        ),
        None,
    )
    if bundled_jar is None:
        raise FileNotFoundError(
            "Bundled Windows jNetPcap 1.4 JAR was not found."
        )
    import hashlib

    digest = hashlib.sha256()
    build_inputs = sorted(
        path for path in (flowmeter_dir / "src").rglob("*")
        if path.is_file()
    )
    build_inputs.extend([flowmeter_dir / "pom.xml", bundled_jar])

    for path in build_inputs:
        digest.update(
            path.relative_to(flowmeter_dir).as_posix().encode("utf-8")
        )
        digest.update(path.read_bytes())

    fingerprint = "1.4:" + digest.hexdigest()
    marker = target_dir / ".nids-jnetpcap-version"

    if jars and marker.is_file():
        if marker.read_text(encoding="utf-8").strip() == fingerprint:
            return jars[-1]
    mvn = shutil.which("mvn")
    if not mvn:
        raise FileNotFoundError(
            "CICFlowMeter is not built and Maven was not found. Install Maven "
            "or build the bundled project with Java 8 before running capture."
        )
    print("Building CICFlowMeter with Maven...")
    subprocess.run(
        [
            mvn,
            "install:install-file",
            f"-Dfile={bundled_jar}",
            "-DgroupId=org.jnetpcap",
            "-DartifactId=jnetpcap",
            "-Dversion=1.4.1",
            "-Dpackaging=jar",
        ],
        cwd=flowmeter_dir,
        check=True,
    )
    subprocess.run(
        [mvn, "-q", "-DskipTests", "clean", "package"],
        cwd=flowmeter_dir,
        check=True,
    )
    jars = sorted(target_dir.glob("CICFlowMeterV3-*.jar"))
    if not jars:
        raise RuntimeError("Maven completed but no CICFlowMeter executable JAR was produced.")
    marker.write_text(fingerprint, encoding="utf-8")
    return jars[-1]


def extract_flows(
    pcap: Path,
    output_dir: Path,
    flowmeter_dir: Path,
    tshark: str | None,
    heap: str,
) -> Path:
    pcap = normalize_pcap(pcap, output_dir, tshark)
    jar = build_flowmeter(flowmeter_dir)
    native_candidates = sorted(flowmeter_dir.glob("jnetpcap/win/*"))
    native_dir = next(
        (path for path in native_candidates if "1.4" in path.name),
        native_candidates[-1] if native_candidates else None,
    )
    if native_dir is None or not (native_dir / "jnetpcap.dll").is_file():
        raise FileNotFoundError("Bundled Windows jNetPcap native library was not found.")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Extracting flows from {pcap.name} with CICFlowMeter...")
    subprocess.run(
        [
            "java",
            f"-Xmx{heap}",
            f"-Djava.library.path={native_dir.resolve()}",
            "-cp",
            str(jar.resolve()),
            "cic.cs.unb.ca.ifm.Cmd",
            str(pcap.resolve()),
            str(output_dir.resolve()),
        ],
        cwd=flowmeter_dir,
        check=True,
    )
    flow_csv = output_dir / f"{pcap.name}_Flow.csv"
    if not flow_csv.is_file():
        raise RuntimeError(f"CICFlowMeter did not create the expected CSV: {flow_csv}")
    return flow_csv


def send_predictions(flow_csv: Path, api_url: str, metadata_path: Path) -> None:
    with metadata_path.open(encoding="utf-8") as file:
        features = json.load(file)["features"]
    with flow_csv.open(newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))
    print(f"Sending {len(rows)} extracted flows to {api_url}...")
    succeeded = 0
    failed = 0
    run_id = time.time_ns()
    for index, row in enumerate(rows, start=1):
        flow_id = f"capture-{run_id}-{index:04d}"
        try:
            mapped = adapt_flow(row, features, time_unit="microseconds")
            payload = {
                "flow_id": flow_id,
                "source_ip": row.get("src_ip") or row.get("Src IP"),
                "destination_ip": row.get("dst_ip") or row.get("Dst IP"),
                "source_port": _optional_int(
                    row.get("src_port") or row.get("Src Port")
                ),
                "destination_port": _optional_int(
                    row.get("dst_port") or row.get("Dst Port")
                ),
                **mapped,
            }
            response = requests.post(api_url, json=payload, timeout=30)
            if not response.ok:
                raise RuntimeError(f"HTTP {response.status_code}: {response.text[:300]}")
            succeeded += 1
            print(f"[OK] {flow_id}: {response.json()['predicted_class']}")
        except (ValueError, RuntimeError, requests.RequestException) as exc:
            failed += 1
            print(f"[ERROR] row {index}: {exc}")
    print(f"Completed: {succeeded} succeeded, {failed} failed.")


def _optional_int(value: str | None) -> int | None:
    return int(float(value)) if value not in (None, "") else None


def build_capture_filter(
    explicit_filter: str | None,
    client_ip: str | None,
    server_ip: str | None,
    server_port: int | None,
) -> str | None:
    if explicit_filter and any((client_ip, server_ip, server_port)):
        raise ValueError(
            "Use either --capture-filter or the client/server filter options, not both."
        )
    if explicit_filter:
        return explicit_filter
    if not any((client_ip, server_ip, server_port)):
        return None
    if not client_ip or not server_ip:
        raise ValueError(
            "--client-ip and --server-ip are both required when building a traffic filter."
        )
    expression = f"host {client_ip} and host {server_ip}"
    if server_port is not None:
        expression += f" and tcp port {server_port}"
    return expression


def process_capture(
    pcap: Path,
    output_dir: Path,
    flowmeter_dir: Path,
    tshark: str | None,
    heap: str,
    api_url: str,
    no_send: bool,
) -> None:
    flow_csv = extract_flows(pcap, output_dir, flowmeter_dir, tshark, heap)
    print(f"Flow CSV: {flow_csv}")
    if not no_send:
        send_predictions(flow_csv, api_url, METADATA_PATH)



def send_behavioral_alert(alert, api_url):
    from uuid import uuid5, NAMESPACE_URL

    endpoint = api_url.rstrip("/").rsplit("/", 1)[0]
    endpoint += "/behavioral-alerts"

    identity = (
        f"{alert['session_id']}|"
        f"{alert['source_ip']}|"
        f"{alert['destination_ip']}|"
        f"{alert['timestamp']}"
    )

    payload = {
        "alert_id": f"behavior-{uuid5(NAMESPACE_URL, identity).hex}",
        "alert_type": alert["type"],
        "source_ip": alert["source_ip"],
        "destination_ip": alert["destination_ip"],
        "distinct_ports": alert["distinct_ports"],
        "destination_ports": alert["destination_ports"],
        "window_seconds": alert["window_seconds"],
        "detection_method": "behavioral",
        "capture_file": alert["capture_file"],
        "session_id": alert["session_id"],
        "observed_at": datetime.fromtimestamp(
            alert["timestamp"], tz=timezone.utc
        ).isoformat()
    }

    response = requests.post(
        endpoint, json=payload, timeout=15
    )

    if response.status_code == 409:
        print("[INFO] Behavioral alert already stored")
        return

    response.raise_for_status()
    print("[OK] Behavioral alert stored in database")


def continuous_capture(args, tshark, output_dir, capture_filter):
    from uuid import uuid4

    output_dir.mkdir(parents=True, exist_ok=True)

    # Prepare the extractor before starting network monitoring.
    build_flowmeter(args.flowmeter_dir.resolve())

    session_dir = output_dir / f"session-{uuid4().hex[:12]}"
    session_dir.mkdir()

    scan_detector = PortScanDetector(
        window_seconds=30,
        min_ports=5
    )

    behavioral_log = session_dir / "behavioral_alerts.jsonl"
    behavioral_log.touch()


    command = [
        tshark,
        "-i", args.interface,
        "-F", "pcap",
        "-b", f"duration:{args.duration}",
        "-w", str(session_dir / "traffic.pcap"),
    ]

    if capture_filter:
        command.extend(["-f", capture_filter])

    print(f"Capture session: {session_dir}")
    print("Continuous monitoring started. Press Ctrl+C to stop.")

    process = subprocess.Popen(
        command,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        if os.name == "nt" else 0,
        start_new_session=os.name != "nt"
    )

    processed = set()
    failed_batches = set()
    empty_batches = set()
    stop_requested = False

    def request_stop(signum, frame):
        nonlocal stop_requested

        if not stop_requested:
            stop_requested = True

            if process.poll() is None:
                try:
                    if os.name == "nt":
                        process.send_signal(
                            signal.CTRL_BREAK_EVENT
                        )
                    else:
                        process.send_signal(signal.SIGINT)
                except OSError as exc:
                    print(f"[WARNING] Capture stop signal failed: {exc}")

            print(
                "\n[STOP] Shutdown requested. "
                "Finishing current work...",
                flush=True
            )

    previous_handler = signal.signal(
        signal.SIGINT, request_stop
    )

    def process_ready(final=False):
        files = sorted(session_dir.glob("traffic_*.pcap"))

        # The newest file is still being written.
        ready = files if final else files[:-1]

        pending = [p for p in ready if p not in processed]

        if len(pending) > 3:
            print(f"[WARNING] Processing backlog: {len(pending)} batches")

        for pcap in pending:
            if stop_requested and not final:
                break

            print(f"[BATCH] Processing {pcap.name}")

            # Classic PCAP header only: no captured packets.
            if pcap.stat().st_size <= 24:
                print("[INFO] Empty capture batch skipped.")
                empty_batches.add(pcap)
                processed.add(pcap)
                continue

            try:
                scan_alerts = scan_detector.process_pcap(pcap)

                for alert in scan_alerts:
                    alert["capture_file"] = pcap.name
                    alert["session_id"] = session_dir.name

                    with behavioral_log.open(
                        "a", encoding="utf-8"
                    ) as log:
                        log.write(json.dumps(alert) + "\n")

                    if not args.no_send:
                        try:
                            send_behavioral_alert(
                                alert, args.api_url
                            )
                        except requests.RequestException as exc:
                            print(
                                f"[ERROR] Alert API failed: {exc}"
                            )
                            print(
                                "[INFO] Alert retained in local log"
                            )

                    print(
                        f"[BEHAVIORAL ALERT] {alert['type']} | "
                        f"{alert['source_ip']} -> "
                        f"{alert['destination_ip']} | "
                        f"Ports: {alert['destination_ports']} | "
                        f"Window: {alert['window_seconds']}s"
                    )

            except Exception as exc:
                print(f"[ERROR] Behavioral analysis failed: {exc}")

            try:
                process_capture(
                    pcap,
                    session_dir,
                    args.flowmeter_dir.resolve(),
                    args.tshark,
                    args.heap,
                    args.api_url,
                    args.no_send,
                )
            except Exception as exc:
                failed_batches.add(pcap)
                print(f"[ERROR] Batch processing failed: {exc}")
                print(f"[INFO] Original capture retained: {pcap}")

            processed.add(pcap)

    try:
        while not stop_requested:
            if process.poll() is not None:
                raise RuntimeError(
                    f"TShark stopped unexpectedly: "
                    f"{process.returncode}"
                )

            process_ready()

            if not stop_requested:
                time.sleep(0.5)

    finally:
        try:
            print("[STOP] Stopping packet capture...")

            if process.poll() is None:
                try:
                    if os.name == "nt":
                        process.send_signal(
                            signal.CTRL_BREAK_EVENT
                        )
                    else:
                        process.send_signal(signal.SIGINT)

                    process.wait(timeout=10)

                except (OSError, subprocess.TimeoutExpired):
                    print(
                        "[WARNING] Graceful capture stop failed. "
                        "Forcing termination."
                    )
                    process.terminate()

                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()

            print("[STOP] Processing remaining capture files...")
            process_ready(final=True)

        finally:
            signal.signal(signal.SIGINT, previous_handler)

            all_files = set(
                session_dir.glob("traffic_*.pcap")
            )

            completed = (
                processed - failed_batches - empty_batches
            )

            print("\n--- MONITORING SUMMARY ---")
            print(f"Capture files: {len(all_files)}")
            print(f"Batches handled: {len(processed)}")
            print(f"Extraction completed: {len(completed)}")
            print(f"Failed batches: {len(failed_batches)}")
            print(f"Empty batches: {len(empty_batches)}")
            print(
                f"Unprocessed batches: "
                f"{len(all_files - processed)}"
            )
            print(f"Capture files retained in: {session_dir}")
            print("Monitoring stopped.")



def main() -> None:
    parser = argparse.ArgumentParser(
        description="TShark/CICFlowMeter to NIDS API demonstration pipeline."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--pcap", type=Path, help="Process an existing PCAP file.")
    source.add_argument("--interface", help="TShark interface number or name to capture.")
    parser.add_argument("--duration", type=int, default=30, help="Capture duration in seconds.")
    parser.add_argument("--tshark", help="Path to tshark.exe when it is not on PATH.")
    parser.add_argument(
        "--capture-filter",
        help="TShark BPF filter, for example: 'host 192.168.1.20 and host 192.168.1.30 and tcp port 8000'.",
    )
    parser.add_argument("--client-ip", help="Laptop K IP address for a host-to-host filter.")
    parser.add_argument("--server-ip", help="Laptop B IP address for a host-to-host filter.")
    parser.add_argument("--server-port", type=int, help="Website TCP port for a host-to-host filter.")
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Repeat fixed-duration captures until Ctrl+C.",
    )
    parser.add_argument("--flowmeter-dir", type=Path, default=FLOWMETER_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000/api/predict")
    parser.add_argument(
        "--heap",
        default="2g",
        help="Maximum Java heap for CICFlowMeter (default: 2g).",
    )
    parser.add_argument("--no-send", action="store_true", help="Only create the flow CSV.")
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    capture_filter = build_capture_filter(
        args.capture_filter,
        args.client_ip,
        args.server_ip,
        args.server_port,
    )
    if args.continuous and args.pcap:
        parser.error("--continuous requires --interface, not --pcap.")
    if args.pcap and capture_filter:
        parser.error("Capture filters require --interface; they do not apply to --pcap.")
    if args.pcap:
        pcap = args.pcap.resolve()
        if not pcap.is_file():
            raise FileNotFoundError(f"PCAP not found: {pcap}")
    else:
        if args.duration < 1:
            raise ValueError("--duration must be at least 1 second")
        tshark = find_tshark(args.tshark)
        if capture_filter:
            print(f"Using TShark capture filter: {capture_filter}")
        if args.continuous:
            continuous_capture(
                args, tshark, output_dir, capture_filter
            )
            return

        try:
            while True:
                pcap = output_dir / (
                    f"capture-{time.strftime('%Y%m%d-%H%M%S')}-"
                    f"{time.time_ns() % 1_000_000:06d}.pcapng"
                )
                capture_pcap(
                    tshark,
                    args.interface,
                    args.duration,
                    pcap,
                    capture_filter,
                )
                process_capture(
                    pcap,
                    output_dir,
                    args.flowmeter_dir.resolve(),
                    args.tshark,
                    args.heap,
                    args.api_url,
                    args.no_send,
                )
                if not args.continuous:
                    break
                print("Capture chunk complete; starting the next chunk. Press Ctrl+C to stop.")
                time.sleep(1)
        except KeyboardInterrupt:
            print("Continuous capture stopped.")
        return

    process_capture(
        pcap,
        output_dir,
        args.flowmeter_dir.resolve(),
        args.tshark,
        args.heap,
        args.api_url,
        args.no_send,
    )


if __name__ == "__main__":
    main()
