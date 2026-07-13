# Weather dataset

Synthetic hourly weather readings on **real** US weather station locations.

## Provenance

- **Station names and GPS** come from NOAA [GHCN-Daily](https://www.ncei.noaa.gov/pub/data/ghcn/daily/) station metadata (`ghcnd-stations.txt`), filtered to CONUS `USW`/`USH` sites and subsampled to ~500 stations with geographic spread.
- **Hourly readings are fabricated** (not observed). They use regional climate baselines, a coherent synoptic-scale wind field, diurnal cycles for temperature and solar radiation, and seeded noise so regeneration is deterministic.

Regenerate with:

```bash
python scripts/generate_weather_data.py
```

## Files

| file | description |
|---|---|
| `stations.csv` | Station metadata |
| `weather_hourly.csv` | One row per station-hour for 7 days (168 hours) |
| `ghcnd-stations.txt` | Cached NOAA metadata used by the generator (gitignored; auto-downloaded) |

## `stations.csv` schema

| column | description |
|---|---|
| `station_id` | GHCN station ID (e.g. `USW00094728`) |
| `name` | Station name |
| `state` | Two-letter USPS state code |
| `lat` | Latitude (decimal degrees) |
| `lon` | Longitude (decimal degrees) |
| `elevation_m` | Elevation in meters |

## `weather_hourly.csv` schema

| column | units / notes |
|---|---|
| `station_id` | Joins to `stations.csv` |
| `timestamp_utc` | ISO-8601 UTC, hourly from `2025-06-09T00:00:00Z` |
| `temperature_c` | °C |
| `humidity_pct` | Relative humidity, 0–100 |
| `pressure_hpa` | hPa |
| `wind_speed_mps` | m/s |
| `wind_direction_deg` | Meteorological direction wind comes **from** (0–360°) |
| `dew_point_c` | °C (consistent with T and RH) |
| `solar_radiation_wm2` | W/m² (~0 at night) |

## Station hardware/software metadata

Per-station equipment and firmware docs live under `station_metadata/` and are queried through the **station-metadata** MCP server (`scripts/station_metadata_mcp.py`). See the Module 2 section of the root README for connection and discovery steps.
