
import argparse
import csv
import json
import sys
from pathlib import Path

import requests

# Project paths
ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "portscan-flows-v2.csv"
METADATA_PATH = ROOT / "backend" / "artifacts" / "nids_metadata.json"
API_URL = "http://127.0.0.1:8000/api/predict"

# Make the project root importable
sys.path.insert(0, str(ROOT))

from tools.flow_adapter import adapt_flow


def main():
    parser = argparse.ArgumentParser(
        description="Map a flow CSV to the NIDS model and send predictions."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=CSV_PATH,
        help="Flow CSV to send (default: portscan-flows-v2.csv).",
    )
    parser.add_argument(
        "--time-unit",
        choices=("seconds", "microseconds"),
        default="seconds",
        help=(
            "Unit used by duration and IAT columns. Use 'microseconds' "
            "for native CICFlowMeter CSV output (default: seconds)."
        ),
    )
    parser.add_argument(
        "--api-url",
        default=API_URL,
        help=f"Prediction API URL (default: {API_URL}).",
    )
    args = parser.parse_args()

    csv_path = args.csv.resolve()
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    with METADATA_PATH.open(encoding="utf-8") as file:
        metadata = json.load(file)

    features = metadata["features"]

    with csv_path.open(
        newline="", encoding="utf-8-sig"
    ) as file:
        rows = list(csv.DictReader(file))

    if not rows:
        print("No flow records found.")
        return

    print(f"Loaded {len(rows)} flows.")
    print(f"Model features: {len(features)}")
    print(f"Time unit: {args.time_unit}")
    print(f"Sending predictions to {args.api_url}\n")

    succeeded = 0
    failed = 0

    for index, row in enumerate(rows, start=1):
        try:
            mapped_features = adapt_flow(
                row,
                features,
                time_unit=args.time_unit,
            )

            flow_id = f"csv-flow-meta-{index:04d}"

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
                **mapped_features,
            }


            response = requests.post(
                args.api_url,
                json=payload,
                timeout=15,
            )

            if not response.ok:
                failed += 1
                print(
                    f"[ERROR] {flow_id}: "
                    f"HTTP {response.status_code} - "
                    f"{response.text[:500]}"
                )
                continue

            result = response.json()
            succeeded += 1

            print(f"[OK] {flow_id}")
            print(json.dumps(result, indent=2))
            print("-" * 50)

        except (ValueError, requests.RequestException) as exc:
            failed += 1
            print(f"[ERROR] CSV row {index}: {exc}")

    print("\nSummary")
    print(f"Successful requests: {succeeded}")
    print(f"Failed requests: {failed}")


def _optional_int(value: str | None) -> int | None:
    return int(float(value)) if value not in (None, "") else None


if __name__ == "__main__":
    main()
