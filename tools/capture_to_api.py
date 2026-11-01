"""Capture or process PCAP traffic, extract CICFlowMeter flows, and predict them."""

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
FLOWMETER_DIR = ROOT / "tools" / "CICFlowMeter-master"
METADATA_PATH = ROOT / "backend" / "artifacts" / "nids_metadata.json"
DEFAULT_OUTPUT_DIR = ROOT / "runtime" / "captures"
sys.path.insert(0, str(ROOT))
from tools.flow_adapter import adapt_flow


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


def capture_pcap(tshark: str, interface: str, duration: int, output: Path) -> None:
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
    marker = target_dir / ".nids-jnetpcap-version"
    if jars and marker.is_file() and marker.read_text(encoding="utf-8").strip() == "1.4":
        return jars[-1]
    mvn = shutil.which("mvn")
    if not mvn:
        raise FileNotFoundError(
            "CICFlowMeter is not built and Maven was not found. Install Maven "
            "or build the bundled project with Java 17 before running capture."
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
        [mvn, "-q", "-DskipTests", "package"],
        cwd=flowmeter_dir,
        check=True,
    )
    jars = sorted(target_dir.glob("CICFlowMeterV3-*.jar"))
    if not jars:
        raise RuntimeError("Maven completed but no CICFlowMeter executable JAR was produced.")
    marker.write_text("1.4", encoding="utf-8")
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
    run_id = int(time.time())
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TShark/CICFlowMeter to NIDS API demonstration pipeline."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--pcap", type=Path, help="Process an existing PCAP file.")
    source.add_argument("--interface", help="TShark interface number or name to capture.")
    parser.add_argument("--duration", type=int, default=30, help="Capture duration in seconds.")
    parser.add_argument("--tshark", help="Path to tshark.exe when it is not on PATH.")
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
    if args.pcap:
        pcap = args.pcap.resolve()
        if not pcap.is_file():
            raise FileNotFoundError(f"PCAP not found: {pcap}")
    else:
        if args.duration < 1:
            raise ValueError("--duration must be at least 1 second")
        tshark = find_tshark(args.tshark)
        pcap = output_dir / f"capture-{time.strftime('%Y%m%d-%H%M%S')}.pcapng"
        capture_pcap(tshark, args.interface, args.duration, pcap)

    flow_csv = extract_flows(
        pcap,
        output_dir,
        args.flowmeter_dir.resolve(),
        args.tshark,
        args.heap,
    )
    print(f"Flow CSV: {flow_csv}")
    if not args.no_send:
        send_predictions(flow_csv, args.api_url, METADATA_PATH)


if __name__ == "__main__":
    main()
