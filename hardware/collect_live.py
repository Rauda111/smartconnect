import json
from datetime import datetime, timezone
from pathlib import Path

from hardware.live_path_monitor import measure_path, PATHS

OUTPUT = Path("results/live_measurements.json")

def main():
    measurements = {}

    for path, mark in PATHS.items():
        measurements[path] = measure_path(path, mark)

    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "measurements": measurements,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, indent=2))

    print("Live measurements saved successfully.")

if __name__ == "__main__":
    main()
