# PEARC26 Cursor Workshop — Weather Patterns

Hands-on workshop using Cursor to explore US weather patterns. Work is organized into modules; **Modules 1–2** are ready now, with later modules to follow.

## Workshop plan

| Module | Focus | Status |
|---|---|---|
| **1** | Map wind across the CONUS from a provided weather station dataset | Ready |
| **2** | Investigate a severe weather event in the hourly data | Ready |
| **3** | *(coming later)* | Planned |

---

## Prerequisites

Complete this setup before starting Module 1.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Cartopy may need system libraries (GEOS/PROJ) on some platforms. On macOS with Homebrew:

```bash
brew install geos proj
```

The first wind-map run downloads Natural Earth basemap shapefiles into Cartopy's data directory (requires network).

---

## Module 1 — Wind map

Plot meteorological wind barbs across the contiguous United States using the provided dataset in `data/` (~500 real CONUS stations with a week of hourly readings). See [data/README.md](data/README.md) for schema and units.

The dataset spans one week of hourly readings (`2025-06-09` through `2025-06-15`). Each run plots a **single** timestamp. For example, Wednesday noon UTC:

```bash
python scripts/plot_wind_map.py --timestamp 2025-06-11T12:00:00Z
```

Writes `output/wind_map.png`.

---

## Module 2 — Investigate a severe weather event

On the evening of **Friday, 13 June 2025**, a strong storm cell moved through central Oklahoma. Start by mapping winds around that time — for example:

```bash
python scripts/plot_wind_map.py --timestamp 2025-06-13T22:00:00Z
```

Something in the hourly data for this event does not look right. Use Cursor to dig into why.

### Explore the hourly CSV

**1. `@File` the dataset**

In chat, attach the hourly readings with `@File` (or `@data/weather_hourly.csv`) and ask Cursor to inspect them — for example:

> `@data/weather_hourly.csv` Something looks off in this weather data around the Oklahoma storm on 2025-06-13. Can you find any values that don't make physical sense?

Try a few follow-ups if the first pass is too broad (e.g. focus on wind, or on a specific evening window).

**2. Narrow with station metadata**

If you find a suspicious `station_id`, pull in `@data/stations.csv` (or `@data/README.md` for units) so Cursor can tell you *where* that station is and what the columns mean.

**3. Ask Cursor to quantify**

Have Cursor summarize ranges, count impossible values, or walk the hours around the storm for the affected station — whatever helps you explain *why* the map looked wrong.
