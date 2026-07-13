#!/usr/bin/env python3
"""Generate synthetic hourly weather readings for real US weather stations.

Station locations come from NOAA GHCN-Daily metadata (real names and GPS).
Hourly readings are fabricated with regional climate baselines, a coherent
synoptic wind field, diurnal cycles, and seeded noise for reproducibility.
"""

from __future__ import annotations

import argparse
import math
import os
import ssl
import urllib.request
from pathlib import Path

try:
    import certifi

    _ca = certifi.where()
    os.environ.setdefault("SSL_CERT_FILE", _ca)
    os.environ.setdefault("REQUESTS_CA_BUNDLE", _ca)
    ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=_ca)
except ImportError:
    pass

import numpy as np
import pandas as pd

# Contiguous US (CONUS) state abbreviations — exclude AK, HI, territories
CONUS_STATES = {
    "AL", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "ID", "IL", "IN",
    "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT",
    "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA",
    "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
}

GHCN_STATIONS_URL = (
    "https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-stations.txt"
)

# Fixed week window for the workshop dataset
WEEK_START = pd.Timestamp("2025-06-09T00:00:00Z")
HOURS = 24 * 7  # 168
TARGET_STATIONS = 500
RNG_SEED = 42

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
CACHE_PATH = DATA_DIR / "ghcnd-stations.txt"


def download_ghcn_stations(dest: Path) -> Path:
    """Download GHCN station metadata if not already cached."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"Using cached station list: {dest}")
        return dest
    print(f"Downloading GHCN stations from {GHCN_STATIONS_URL} ...")
    urllib.request.urlretrieve(GHCN_STATIONS_URL, dest)
    return dest


def parse_ghcn_stations(path: Path) -> pd.DataFrame:
    """Parse fixed-width ghcnd-stations.txt into a DataFrame."""
    rows = []
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            if len(line) < 71:
                continue
            station_id = line[0:11].strip()
            # Prefer USW (ASOS/airport) and USH (Historical Climatology) networks
            if not station_id.startswith(("USW", "USH")):
                continue
            state = line[38:40].strip()
            if state not in CONUS_STATES:
                continue
            try:
                lat = float(line[12:20])
                lon = float(line[21:30])
                elev = float(line[31:37])
            except ValueError:
                continue
            # CONUS bounding box sanity check
            if not (24.0 <= lat <= 50.0 and -125.0 <= lon <= -66.0):
                continue
            name = line[41:71].strip()
            rows.append(
                {
                    "station_id": station_id,
                    "name": name,
                    "state": state,
                    "lat": lat,
                    "lon": lon,
                    "elevation_m": elev if elev > -900 else np.nan,
                }
            )
    return pd.DataFrame(rows)


def select_stations(df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    """Select ~n stations with geographic spread across CONUS.

    Prefer USW (ASOS) stations, ensure every CONUS state is represented when
    possible, then fill remaining slots via grid-based stratified sampling.
    """
    rng = np.random.default_rng(seed)
    usw = df[df["station_id"].str.startswith("USW")].copy()
    if len(usw) < n // 2:
        pool = df.copy()
    else:
        pool = usw

    selected_ids: list[str] = []
    # At least one station per state when available
    for state, group in pool.groupby("state"):
        pick = group.sample(n=1, random_state=int(rng.integers(0, 2**31 - 1)))
        selected_ids.extend(pick["station_id"].tolist())

    remaining = pool[~pool["station_id"].isin(selected_ids)].copy()
    need = n - len(selected_ids)
    if need <= 0:
        out = pool[pool["station_id"].isin(selected_ids)].drop_duplicates("station_id")
        return out.sample(n=n, random_state=seed).reset_index(drop=True)

    # Stratify remaining picks on a lat/lon grid for spatial coverage
    lat_bins = pd.cut(remaining["lat"], bins=10, labels=False)
    lon_bins = pd.cut(remaining["lon"], bins=12, labels=False)
    remaining = remaining.assign(_cell=lat_bins.astype(str) + "_" + lon_bins.astype(str))

    per_cell = max(1, need // remaining["_cell"].nunique())
    extras: list[pd.DataFrame] = []
    for _, group in remaining.groupby("_cell"):
        k = min(len(group), per_cell)
        extras.append(group.sample(n=k, random_state=int(rng.integers(0, 2**31 - 1))))

    extra_df = pd.concat(extras, ignore_index=True) if extras else remaining.iloc[0:0]
    if len(extra_df) < need:
        leftover = remaining[~remaining["station_id"].isin(extra_df["station_id"])]
        more = leftover.sample(
            n=min(need - len(extra_df), len(leftover)),
            random_state=seed,
        )
        extra_df = pd.concat([extra_df, more], ignore_index=True)
    elif len(extra_df) > need:
        extra_df = extra_df.sample(n=need, random_state=seed)

    selected_ids.extend(extra_df["station_id"].tolist())
    out = pool[pool["station_id"].isin(selected_ids)].drop_duplicates("station_id")
    if len(out) > n:
        # Keep all state representatives, trim extras
        state_reps = out.groupby("state").head(1)
        rest = out[~out["station_id"].isin(state_reps["station_id"])]
        rest = rest.sample(n=n - len(state_reps), random_state=seed)
        out = pd.concat([state_reps, rest], ignore_index=True)
    return out.sort_values(["state", "name"]).reset_index(drop=True)


def dew_point_c(temp_c: np.ndarray, rh_pct: np.ndarray) -> np.ndarray:
    """Magnus approximation for dew point from temperature and relative humidity."""
    rh = np.clip(rh_pct, 1.0, 100.0) / 100.0
    a, b = 17.625, 243.04
    gamma = (a * temp_c) / (b + temp_c) + np.log(rh)
    return (b * gamma) / (a - gamma)


def fabricate_readings(stations: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Fabricate hourly readings with coherent regional patterns."""
    rng = np.random.default_rng(seed)
    n_stations = len(stations)
    timestamps = pd.date_range(WEEK_START, periods=HOURS, freq="h", tz="UTC")

    lats = stations["lat"].to_numpy()
    lons = stations["lon"].to_numpy()
    elev = stations["elevation_m"].fillna(200.0).to_numpy()

    # Normalize lon/lat for smooth synoptic fields
    lon_n = (lons + 125.0) / 59.0  # ~0–1 across CONUS
    lat_n = (lats - 24.0) / 26.0

    rows: list[dict] = []
    station_ids = stations["station_id"].to_numpy()

    for t_idx, ts in enumerate(timestamps):
        hour = ts.hour
        day_frac = t_idx / HOURS
        # Local solar hour approximation from longitude
        local_hour = (hour + lons / 15.0) % 24.0

        # Synoptic wind field: slowly rotating large-scale pattern
        phase = 2.0 * math.pi * day_frac
        u = (
            3.0 * np.sin(2.0 * math.pi * lon_n + phase)
            + 2.0 * np.cos(2.0 * math.pi * lat_n - 0.5 * phase)
            + rng.normal(0.0, 0.8, n_stations)
        )
        v = (
            2.5 * np.cos(2.0 * math.pi * lon_n - phase)
            + 2.0 * np.sin(2.0 * math.pi * lat_n + 0.3 * phase)
            + rng.normal(0.0, 0.8, n_stations)
        )
        # Stronger winds in plains / higher elevation
        plains_boost = 1.0 + 0.6 * np.exp(-((lons + 100.0) ** 2) / 200.0)
        elev_boost = 1.0 + 0.0004 * np.clip(elev, 0, 3000)
        wind_speed = np.clip(np.hypot(u, v) * plains_boost * elev_boost, 0.2, 28.0)
        # Meteorological direction: where wind comes FROM
        wind_dir = (270.0 - np.degrees(np.arctan2(v, u))) % 360.0

        # Temperature: latitude + elevation + diurnal
        base_t = 32.0 - 0.55 * (lats - 25.0) - 0.0065 * elev
        diurnal = 6.0 * np.sin((local_hour - 10.0) / 24.0 * 2.0 * math.pi)
        synoptic_t = 2.0 * np.sin(2.0 * math.pi * lon_n + phase)
        temp = base_t + diurnal + synoptic_t + rng.normal(0.0, 1.2, n_stations)

        # Humidity: higher near coasts / Gulf, lower inland west
        gulf = np.exp(-((lats - 28.0) ** 2) / 40.0) * np.exp(-((lons + 90.0) ** 2) / 80.0)
        west_dry = np.clip((-lons - 100.0) / 25.0, 0.0, 1.0)
        coastal = np.minimum(
            np.abs(lons + 122.0) / 8.0,  # west coast proximity (inverse later)
            np.abs(lons + 75.0) / 10.0,
        )
        rh = (
            55.0
            + 25.0 * gulf
            - 20.0 * west_dry
            + 10.0 * (1.0 - np.clip(coastal, 0, 1))
            - 0.8 * diurnal
            + rng.normal(0.0, 4.0, n_stations)
        )
        rh = np.clip(rh, 15.0, 98.0)

        # Pressure: sea-level-ish with synoptic wave
        pressure = (
            1013.25
            - elev / 9.0
            + 6.0 * np.sin(2.0 * math.pi * lon_n - phase)
            + rng.normal(0.0, 1.5, n_stations)
        )

        dew = dew_point_c(temp, rh)

        # Solar radiation: clear-sky-ish diurnal, zero at night
        solar_elev_angle = np.sin((local_hour - 6.0) / 12.0 * math.pi)
        solar = np.where(
            (local_hour >= 6.0) & (local_hour <= 20.0),
            np.clip(950.0 * np.maximum(solar_elev_angle, 0.0), 0.0, 1050.0),
            0.0,
        )
        # Latitude / cloudiness modulation
        solar = solar * (0.85 + 0.15 * (1.0 - lat_n)) * (0.9 + 0.1 * rng.random(n_stations))
        solar = np.clip(solar, 0.0, 1100.0)

        for i in range(n_stations):
            rows.append(
                {
                    "station_id": station_ids[i],
                    "timestamp_utc": ts.isoformat().replace("+00:00", "Z"),
                    "temperature_c": round(float(temp[i]), 2),
                    "humidity_pct": round(float(rh[i]), 1),
                    "pressure_hpa": round(float(pressure[i]), 2),
                    "wind_speed_mps": round(float(wind_speed[i]), 2),
                    "wind_direction_deg": round(float(wind_dir[i]), 1),
                    "dew_point_c": round(float(dew[i]), 2),
                    "solar_radiation_wm2": round(float(solar[i]), 1),
                }
            )

    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stations",
        type=int,
        default=TARGET_STATIONS,
        help=f"Number of stations to select (default: {TARGET_STATIONS})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=RNG_SEED,
        help=f"RNG seed (default: {RNG_SEED})",
    )
    parser.add_argument(
        "--stations-file",
        type=Path,
        default=CACHE_PATH,
        help="Path to ghcnd-stations.txt (downloaded if missing)",
    )
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    download_ghcn_stations(args.stations_file)
    all_stations = parse_ghcn_stations(args.stations_file)
    print(f"Parsed {len(all_stations)} CONUS USW/USH stations from GHCN metadata")

    stations = select_stations(all_stations, args.stations, args.seed)
    print(
        f"Selected {len(stations)} stations across "
        f"{stations['state'].nunique()} states"
    )

    stations_out = DATA_DIR / "stations.csv"
    stations.to_csv(stations_out, index=False)
    print(f"Wrote {stations_out}")

    print("Fabricating hourly readings (this may take a moment)...")
    readings = fabricate_readings(stations, args.seed)
    readings_out = DATA_DIR / "weather_hourly.csv"
    readings.to_csv(readings_out, index=False)
    print(f"Wrote {readings_out} ({len(readings):,} rows)")


if __name__ == "__main__":
    main()
