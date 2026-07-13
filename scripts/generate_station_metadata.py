#!/usr/bin/env python3
"""Generate per-station hardware/software metadata for the workshop MCP server.

Station locations come from data/stations.csv. Firmware assignments are
deterministic (seeded) so regeneration is stable. A small legacy FORTRAN
cohort — including Oklahoma City Will Rogers — documents SIGNED INT8 wind
speed storage for Module 2 discovery via MCP (not via the README).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
OUT_DIR = DATA_DIR / "station_metadata"
STATIONS_PATH = DATA_DIR / "stations.csv"
RNG_SEED = 42

# Always on legacy FORTRAN LTU stack (workshop anomaly station + a few peers)
FORCE_LEGACY_IDS = {
    "USW00013967",  # OKC Will Rogers — site of the -127 wind reading
    "USW00013969",  # Ponca City
    "USW00003932",  # Clinton-Sherman
    "USW00003981",  # Altus AFB
    "USW00013903",  # Ardmore AFB
}

FIRMWARE_CATALOG = {
    "asos-next-py-2.4": {
        "firmware_id": "asos-next-py-2.4",
        "name": "ASOS-Next Data Acquisition",
        "version": "2.4.3",
        "language": "Python 3 / C extensions",
        "vendor": "NWS ASOS Product Improvement",
        "released": "2021-09-15",
        "description": (
            "Current-generation ASOS acquisition stack. Sensor values are ingested "
            "as IEEE-754 floats, QC'd, and packed into METAR/SPECI without narrow "
            "integer truncation in the wind pathway."
        ),
        "data_types": {
            "wind_speed": {
                "storage_type": "float32",
                "signed": True,
                "units": "m/s (internal); knots in METAR",
                "valid_range": [0.0, 100.0],
                "notes": "Negative speeds rejected by QC before archival.",
            },
            "wind_direction": {
                "storage_type": "uint16",
                "units": "degrees",
                "valid_range": [0, 360],
            },
            "temperature": {
                "storage_type": "float32",
                "units": "°C",
            },
        },
    },
    "awos-c-cpp-1.8": {
        "firmware_id": "awos-c-cpp-1.8",
        "name": "AWOS-C Site Controller",
        "version": "1.8.0",
        "language": "C++17",
        "vendor": "FAA AWOS Program",
        "released": "2018-04-02",
        "description": (
            "FAA AWOS-C controller firmware. Wind is stored as a 16-bit unsigned "
            "integer in 0.1 m/s counts."
        ),
        "data_types": {
            "wind_speed": {
                "storage_type": "uint16",
                "signed": False,
                "units": "0.1 m/s counts",
                "valid_range": [0, 65535],
                "notes": "Saturates at max count; does not wrap to negative.",
            },
            "wind_direction": {
                "storage_type": "uint16",
                "units": "degrees",
                "valid_range": [0, 360],
            },
            "temperature": {
                "storage_type": "int16",
                "units": "0.1 °C counts",
            },
        },
    },
    "asos-classic-c-5.1": {
        "firmware_id": "asos-classic-c-5.1",
        "name": "ASOS Classic Acquisition",
        "version": "5.1.2",
        "language": "C99",
        "vendor": "NWS ASOS",
        "released": "2012-11-30",
        "description": (
            "Widely deployed mid-life ASOS build. Wind speed uses a signed 16-bit "
            "integer in knots."
        ),
        "data_types": {
            "wind_speed": {
                "storage_type": "int16",
                "signed": True,
                "units": "knots",
                "valid_range": [-32768, 32767],
                "notes": "QC clamps negatives to missing; practical range 0–250 kt.",
            },
            "wind_direction": {
                "storage_type": "int16",
                "units": "degrees",
                "valid_range": [0, 360],
            },
            "temperature": {
                "storage_type": "int16",
                "units": "0.1 °C counts",
            },
        },
    },
    "asos-ltu-f77-3.2": {
        "firmware_id": "asos-ltu-f77-3.2",
        "name": "ASOS Legacy Telemetry Unit (LTU)",
        "version": "3.2.1",
        "language": "FORTRAN 77",
        "vendor": "NWS / legacy contractor stack",
        "released": "2003-07-18",
        "last_field_update": "2009-06-01",
        "description": (
            "Legacy LTU telemetry still operating at a minority of ASOS sites. "
            "The acquisition loop and METAR element packer were written in "
            "FORTRAN 77 and have not been migrated to the ASOS-Next stack."
        ),
        "source_notes": (
            "Primary wind packing routine: WNDPAK (WIND PACK) in wndpak.f. "
            "Wind speed is read from the anemometer pulse counter, converted to "
            "integer mph, and stored in a single-byte INTEGER*1 field before "
            "message assembly."
        ),
        "data_types": {
            "wind_speed": {
                "storage_type": "INTEGER*1",
                "fortran_type": "INTEGER*1",
                "signed": True,
                "bit_width": 8,
                "units": "mph",
                "valid_range": [-128, 127],
                "notes": (
                    "Signed 8-bit two's-complement field. Design assumption in the "
                    "original LTU ICD was that reported wind speed would never "
                    "exceed 127 mph. Values of 128 mph and above overflow and wrap "
                    "(e.g. 129 → -127). There is no saturating clamp in WNDPAK."
                ),
            },
            "wind_direction": {
                "storage_type": "INTEGER*2",
                "fortran_type": "INTEGER*2",
                "signed": True,
                "units": "degrees",
                "valid_range": [0, 360],
            },
            "temperature": {
                "storage_type": "INTEGER*2",
                "fortran_type": "INTEGER*2",
                "units": "0.1 °C counts",
            },
        },
        "known_limitations": [
            "Wind speed packed as signed INTEGER*1 (max +127 before overflow).",
            "No runtime check for anemometer readings above 127 mph.",
            "Maintenance bulletins recommend ASOS-Next cutover; several plains sites remain pending.",
        ],
    },
}

HARDWARE_BY_FIRMWARE = {
    "asos-next-py-2.4": {
        "platform": "ASOS-Next shelter",
        "anemometer": "Vaisala WMT700 ultrasonic",
        "barometer": "Vaisala PTB330",
        "hygrometer": "Vaisala HMP155",
        "datalogger": "ASOS-Next DAQ",
    },
    "awos-c-cpp-1.8": {
        "platform": "AWOS-C cabinet",
        "anemometer": "Climatronics F460",
        "barometer": "Setra 270",
        "hygrometer": "Rotronic HC2",
        "datalogger": "AWOS-C site controller",
    },
    "asos-classic-c-5.1": {
        "platform": "ASOS standard shelter",
        "anemometer": "Vaisala WAA151 cup",
        "barometer": "Vaisala PTB220",
        "hygrometer": "Vaisala HMP45",
        "datalogger": "ASOS ACU",
    },
    "asos-ltu-f77-3.2": {
        "platform": "ASOS Legacy Telemetry Unit shelter",
        "anemometer": "Vaisala WAA151 cup (pulse output)",
        "barometer": "Vaisala PTB201A",
        "hygrometer": "Hygro-M1",
        "datalogger": "LTU-2000",
    },
}


def assign_firmware(station_id: str, state: str, rng: np.random.Generator) -> str:
    if station_id in FORCE_LEGACY_IDS:
        return "asos-ltu-f77-3.2"
    # Mostly modern/classic; rare AWOS; very rare additional legacy elsewhere
    r = float(rng.random())
    if state in {"TX", "OK", "KS", "NE"} and r < 0.04:
        return "asos-ltu-f77-3.2"
    if r < 0.12:
        return "awos-c-cpp-1.8"
    if r < 0.55:
        return "asos-classic-c-5.1"
    return "asos-next-py-2.4"


def build_station_doc(row: pd.Series, firmware_id: str, rng: np.random.Generator) -> dict:
    fw = FIRMWARE_CATALOG[firmware_id]
    year = int(rng.integers(1994, 2018)) if firmware_id == "asos-ltu-f77-3.2" else int(
        rng.integers(2005, 2024)
    )
    month = int(rng.integers(1, 13))
    day = int(rng.integers(1, 28))
    return {
        "station_id": row["station_id"],
        "name": row["name"],
        "state": row["state"],
        "latitude": float(row["lat"]),
        "longitude": float(row["lon"]),
        "elevation_m": float(row["elevation_m"]) if pd.notna(row["elevation_m"]) else None,
        "network": "ASOS" if str(row["station_id"]).startswith("USW") else "USHCN/coop",
        "commissioned": f"{year:04d}-{month:02d}-{day:02d}",
        "hardware": HARDWARE_BY_FIRMWARE[firmware_id],
        "software": {
            "firmware_id": firmware_id,
            "name": fw["name"],
            "version": fw["version"],
            "language": fw["language"],
            "vendor": fw["vendor"],
        },
        "maintenance": {
            "last_inspection": f"2025-{int(rng.integers(1, 6)):02d}-{int(rng.integers(1, 28)):02d}",
            "firmware_cutover_scheduled": firmware_id == "asos-ltu-f77-3.2",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stations", type=Path, default=STATIONS_PATH)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--seed", type=int, default=RNG_SEED)
    args = parser.parse_args()

    stations = pd.read_csv(args.stations)
    rng = np.random.default_rng(args.seed)

    stations_dir = args.out_dir / "stations"
    stations_dir.mkdir(parents=True, exist_ok=True)

    index_rows = []
    legacy_count = 0
    for _, row in stations.iterrows():
        firmware_id = assign_firmware(row["station_id"], row["state"], rng)
        if firmware_id == "asos-ltu-f77-3.2":
            legacy_count += 1
        doc = build_station_doc(row, firmware_id, rng)
        out_path = stations_dir / f"{row['station_id']}.json"
        out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        index_rows.append(
            {
                "station_id": doc["station_id"],
                "name": doc["name"],
                "state": doc["state"],
                "firmware_id": firmware_id,
                "software_name": doc["software"]["name"],
                "software_language": doc["software"]["language"],
                "path": str(out_path.relative_to(args.out_dir)),
            }
        )

    catalog_path = args.out_dir / "firmware_catalog.json"
    catalog_path.write_text(json.dumps(FIRMWARE_CATALOG, indent=2) + "\n", encoding="utf-8")

    index = {
        "station_count": len(index_rows),
        "firmware_ids": sorted(FIRMWARE_CATALOG.keys()),
        "stations": index_rows,
    }
    index_path = args.out_dir / "index.json"
    index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")

    readme = args.out_dir / "README.md"
    readme.write_text(
        """# Station metadata

Per-station hardware and software metadata for the workshop **station-metadata** MCP server.

| path | contents |
|---|---|
| `index.json` | Compact index of all stations + firmware ids |
| `firmware_catalog.json` | Firmware/software specifications (data types, languages) |
| `stations/<station_id>.json` | One metadata document per station |

Regenerate with:

```bash
python scripts/generate_station_metadata.py
```

Query at runtime via the MCP server (`scripts/station_metadata_mcp.py`), not by hand-editing these files during the exercise.
""",
        encoding="utf-8",
    )

    print(f"Wrote {len(index_rows)} station docs → {stations_dir}")
    print(f"Legacy FORTRAN LTU stations: {legacy_count}")
    print(f"Firmware catalog → {catalog_path}")
    print(f"Index → {index_path}")


if __name__ == "__main__":
    main()
