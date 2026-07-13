#!/usr/bin/env python3
"""Plot CONUS wind speed and direction as meteorological wind barbs.

Reads data/stations.csv and data/weather_hourly.csv, selects one hour, and
saves a map to output/wind_map.png.
"""

from __future__ import annotations

import argparse
import os
import ssl
from pathlib import Path

# Prefer certifi CA bundle so Cartopy's Natural Earth downloads work on macOS
# Python installs that lack system certificates.
try:
    import certifi

    _ca = certifi.where()
    os.environ.setdefault("SSL_CERT_FILE", _ca)
    os.environ.setdefault("REQUESTS_CA_BUNDLE", _ca)
    ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=_ca)
except ImportError:
    pass

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
OUTPUT_DIR = REPO_ROOT / "output"


def load_frame(
    stations_path: Path,
    readings_path: Path,
    timestamp: str | None,
    hour_index: int | None,
) -> tuple[pd.DataFrame, str]:
    stations = pd.read_csv(stations_path)
    readings = pd.read_csv(readings_path)

    timestamps = sorted(readings["timestamp_utc"].unique())
    if not timestamps:
        raise SystemExit("No timestamps found in weather_hourly.csv")

    if timestamp is not None:
        chosen = timestamp
        if chosen not in timestamps:
            # Allow missing Z / timezone variants
            matches = [t for t in timestamps if t.startswith(chosen.rstrip("Z"))]
            if not matches:
                raise SystemExit(
                    f"Timestamp {timestamp!r} not in dataset. "
                    f"Example: {timestamps[len(timestamps) // 2]}"
                )
            chosen = matches[0]
    elif hour_index is not None:
        if hour_index < 0 or hour_index >= len(timestamps):
            raise SystemExit(
                f"--hour-index must be 0..{len(timestamps) - 1}, got {hour_index}"
            )
        chosen = timestamps[hour_index]
    else:
        chosen = timestamps[len(timestamps) // 2]

    hour = readings[readings["timestamp_utc"] == chosen].copy()
    frame = hour.merge(stations, on="station_id", how="inner")
    if frame.empty:
        raise SystemExit(f"No joined rows for timestamp {chosen}")
    return frame, chosen


def wind_to_uv(speed_mps: np.ndarray, direction_deg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Convert meteorological wind (from-direction) to u/v components for barbs.

    Matplotlib barbs expect u/v as vector components pointing in the direction
    the wind is blowing TOWARD (oceanographic convention for the arrow tip).
    Meteorological direction is where the wind comes FROM, so:
      u = -speed * sin(dir),  v = -speed * cos(dir)
    """
    rad = np.deg2rad(direction_deg)
    u = -speed_mps * np.sin(rad)
    v = -speed_mps * np.cos(rad)
    return u, v


def plot_wind_map(frame: pd.DataFrame, timestamp: str, output_path: Path) -> None:
    u, v = wind_to_uv(
        frame["wind_speed_mps"].to_numpy(),
        frame["wind_direction_deg"].to_numpy(),
    )
    # Convert m/s → knots for conventional barb scaling (1 m/s ≈ 1.94384 kt)
    u_kt = u * 1.94384
    v_kt = v * 1.94384

    fig = plt.figure(figsize=(14, 9))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
    ax.set_extent([-125.5, -66.0, 24.0, 50.0], crs=ccrs.PlateCarree())

    ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor="#f2efe6", zorder=0)
    ax.add_feature(cfeature.OCEAN.with_scale("50m"), facecolor="#d6e8f0", zorder=0)
    ax.add_feature(cfeature.COASTLINE.with_scale("50m"), linewidth=0.6, zorder=2)
    ax.add_feature(cfeature.BORDERS.with_scale("50m"), linewidth=0.5, zorder=2)
    ax.add_feature(cfeature.STATES.with_scale("50m"), linewidth=0.35, edgecolor="#555555", zorder=2)
    ax.add_feature(cfeature.LAKES.with_scale("50m"), facecolor="#d6e8f0", edgecolor="#8899aa", linewidth=0.3, zorder=1)

    ax.barbs(
        frame["lon"].to_numpy(),
        frame["lat"].to_numpy(),
        u_kt,
        v_kt,
        length=5.5,
        pivot="middle",
        barbcolor="#1a1a1a",
        flagcolor="#1a1a1a",
        linewidth=0.55,
        transform=ccrs.PlateCarree(),
        zorder=3,
    )

    ax.set_title(
        f"CONUS Wind Speed & Direction\n{timestamp}  ·  {len(frame)} stations  ·  barbs in knots",
        fontsize=14,
        pad=12,
    )
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    gl = ax.gridlines(draw_labels=True, linewidth=0.3, color="gray", alpha=0.5, linestyle="--")
    gl.top_labels = False
    gl.right_labels = False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Wrote {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--timestamp",
        type=str,
        default=None,
        help="UTC timestamp to plot (must match weather_hourly.csv values)",
    )
    parser.add_argument(
        "--hour-index",
        type=int,
        default=None,
        help="0-based hour index within the week (alternative to --timestamp)",
    )
    parser.add_argument(
        "--stations",
        type=Path,
        default=DATA_DIR / "stations.csv",
        help="Path to stations.csv",
    )
    parser.add_argument(
        "--readings",
        type=Path,
        default=DATA_DIR / "weather_hourly.csv",
        help="Path to weather_hourly.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR / "wind_map.png",
        help="Output PNG path",
    )
    args = parser.parse_args()

    if not args.stations.exists() or not args.readings.exists():
        raise SystemExit(
            "Missing data files. Run: python scripts/generate_weather_data.py"
        )

    frame, chosen = load_frame(args.stations, args.readings, args.timestamp, args.hour_index)
    plot_wind_map(frame, chosen, args.output)


if __name__ == "__main__":
    main()
