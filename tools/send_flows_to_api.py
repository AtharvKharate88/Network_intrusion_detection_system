
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
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV not found: {CSV_PATH}")

    with METADATA_PATH.open(encoding="utf-8") as file:
        metadata = json.load(file)

    features = metadata["features"]

    with CSV_PATH.open(
        newline="", encoding="utf-8-sig"
    ) as file:
        rows = list(csv.DictReader(file))

    if not rows:
        print("No flow records found.")
        return

    print(f"Loaded {len(rows)} flows.")
    print(f"Model features: {len(features)}")
    print(f"Sending predictions to {API_URL}\n")

    succeeded = 0
    failed = 0

    for index, row in enumerate(rows, start=1):
        try:
            mapped_features = adapt_flow(row, features)

            flow_id = f"csv-flow-meta-{index:04d}"

            payload = {
                "flow_id": flow_id,
                "source_ip": row.get("src_ip"),
                "destination_ip": row.get("dst_ip"),
                "source_port": int(row["src_port"]),
                "destination_port": int(row["dst_port"]),
                **mapped_features,
            }


            response = requests.post(
                API_URL,
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


if __name__ == "__main__":
    main()
