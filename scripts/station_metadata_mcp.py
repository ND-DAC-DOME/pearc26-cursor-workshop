#!/usr/bin/env python3
"""MCP server: query weather station hardware/software metadata.

Stdio transport for Cursor. Do not print to stdout (JSON-RPC only).
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
log = logging.getLogger("station-metadata")

REPO_ROOT = Path(__file__).resolve().parents[1]
META_DIR = REPO_ROOT / "data" / "station_metadata"
INDEX_PATH = META_DIR / "index.json"
CATALOG_PATH = META_DIR / "firmware_catalog.json"
STATIONS_DIR = META_DIR / "stations"

mcp = FastMCP(
    "station-metadata",
    instructions=(
        "Lookup hardware and software metadata for US weather stations in this "
        "workshop dataset. Use get_station for a station_id found in the hourly "
        "CSV, then get_firmware for the station's firmware_id when you need data "
        "type / language details."
    ),
)


def _load_index() -> dict:
    if not INDEX_PATH.exists():
        raise FileNotFoundError(
            f"Missing {INDEX_PATH}. Run: python scripts/generate_station_metadata.py"
        )
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def _load_catalog() -> dict:
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(
            f"Missing {CATALOG_PATH}. Run: python scripts/generate_station_metadata.py"
        )
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _station_path(station_id: str) -> Path:
    return STATIONS_DIR / f"{station_id}.json"


@mcp.tool()
def list_stations(state: str | None = None, firmware_id: str | None = None) -> str:
    """List weather stations (id, name, state, firmware).

    Optionally filter by two-letter state code and/or firmware_id
    (e.g. asos-ltu-f77-3.2, asos-next-py-2.4).
    """
    index = _load_index()
    rows = index["stations"]
    if state:
        state_u = state.strip().upper()
        rows = [r for r in rows if r["state"] == state_u]
    if firmware_id:
        rows = [r for r in rows if r["firmware_id"] == firmware_id]
    return json.dumps(
        {
            "count": len(rows),
            "stations": [
                {
                    "station_id": r["station_id"],
                    "name": r["name"],
                    "state": r["state"],
                    "firmware_id": r["firmware_id"],
                    "software_language": r["software_language"],
                }
                for r in rows
            ],
        },
        indent=2,
    )


@mcp.tool()
def get_station(station_id: str) -> str:
    """Get full hardware/software metadata for one station by station_id.

    Example station_id: USW00013967
    """
    path = _station_path(station_id.strip())
    if not path.exists():
        return json.dumps(
            {
                "error": f"Unknown station_id: {station_id}",
                "hint": "Use list_stations or search_stations to find valid ids.",
            },
            indent=2,
        )
    doc = json.loads(path.read_text(encoding="utf-8"))
    return json.dumps(doc, indent=2)


@mcp.tool()
def search_stations(query: str) -> str:
    """Search stations by name, state, station_id, firmware id, or software language.

    Case-insensitive substring match across the station index.
    """
    q = query.strip().lower()
    if not q:
        return json.dumps({"error": "query must be non-empty"}, indent=2)
    index = _load_index()
    hits = []
    for r in index["stations"]:
        blob = " ".join(
            [
                r["station_id"],
                r["name"],
                r["state"],
                r["firmware_id"],
                r["software_name"],
                r["software_language"],
            ]
        ).lower()
        if q in blob:
            hits.append(r)
    return json.dumps({"query": query, "count": len(hits), "stations": hits[:50]}, indent=2)


@mcp.tool()
def list_firmware() -> str:
    """List available firmware/software packages and their languages."""
    catalog = _load_catalog()
    summary = [
        {
            "firmware_id": fw_id,
            "name": fw["name"],
            "version": fw["version"],
            "language": fw["language"],
            "vendor": fw["vendor"],
        }
        for fw_id, fw in catalog.items()
    ]
    return json.dumps({"firmware": summary}, indent=2)


@mcp.tool()
def get_firmware(firmware_id: str) -> str:
    """Get detailed firmware specification, including typed sensor fields.

    Use the firmware_id from get_station (e.g. asos-ltu-f77-3.2).
    """
    catalog = _load_catalog()
    fw_id = firmware_id.strip()
    if fw_id not in catalog:
        return json.dumps(
            {
                "error": f"Unknown firmware_id: {firmware_id}",
                "known_ids": sorted(catalog.keys()),
            },
            indent=2,
        )
    return json.dumps(catalog[fw_id], indent=2)


def main() -> None:
    if not INDEX_PATH.exists():
        log.error("Metadata missing at %s — run generate_station_metadata.py first", META_DIR)
        raise SystemExit(1)
    log.info("Serving station metadata from %s", META_DIR)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
