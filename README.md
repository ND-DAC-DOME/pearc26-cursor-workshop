# PEARC26 Cursor Workshop — Weather Patterns

Hands-on workshop using Cursor to explore US weather patterns. Work is organized into modules; **Modules 1–2** are ready now, with later modules to follow.

## Workshop plan

| Module | Focus | Status |
|---|---|---|
| **1** | Map wind across the CONUS from a provided weather station dataset | Ready |
| **2** | Investigate a severe weather event and trace it via station-metadata MCP | Ready |
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

Study the map, then use Cursor to inspect the underlying hourly readings.

### Explore the hourly CSV

**Important:** Read these instructions yourself in the editor. During Ask/Agent investigation, attach **only** the data files you want analyzed (e.g. the CSV below). Do **not** `@README.md` — it will leak the exercise framing into the model’s context.

**1. Ask mode + `@File` the dataset**

Switch the chat to **Ask** mode, attach **only** `@data/weather_hourly.csv`, and run an open-ended quality check — for example:

> `@data/weather_hourly.csv` Do a quality check of this weather dataset. Flag any physically impossible or suspicious values.

Try a few follow-ups if the first pass is too broad (e.g. focus on wind, or on a specific evening window).

**2. Narrow the location**

If you find a suspicious `station_id`, you can `@data/stations.csv` (or `@data/README.md` for units) for coordinates and naming. For **hardware/software** details, use the station-metadata MCP in the next section — do not dig through metadata JSON files by hand.

**3. Ask Cursor to quantify**

Have Cursor summarize ranges, count impossible values, or walk the hours around the storm for the affected station — whatever helps you explain *why* the map looked wrong.

### Station metadata MCP (root-cause context)

Each station has hardware/software metadata (platform, sensors, firmware language and typed fields). That catalog is **not** meant to be browsed as raw files during the exercise — query it through a local MCP server so Agent/Ask can pull details on demand.

#### Start / connect the MCP server

1. Ensure the venv is set up (Prerequisites) and metadata exists:

```bash
python scripts/generate_station_metadata.py   # already committed; re-run only if regenerating
```

2. This repo ships a project MCP config at [`.cursor/mcp.json`](.cursor/mcp.json) that launches:

```text
.venv/bin/python scripts/station_metadata_mcp.py
```

3. In Cursor: **Settings → MCP**. Confirm **station-metadata** appears and shows a green/connected status. If needed, click refresh/restart after creating the venv.

4. Open a new Agent or Ask chat and verify tools such as `get_station`, `get_firmware`, `list_stations`, `search_stations`, and `list_firmware` are available.

#### Discovery path

After you have a suspicious `station_id` from the hourly CSV:

1. Ask the agent to look up that station **via the station-metadata MCP** (not by opening JSON files in the editor).
2. Follow the station’s `firmware_id` with `get_firmware`.
3. Inspect how that firmware stores wind speed (language, integer width, signedness, range) and connect it to the impossible reading you found.

Example prompts (attach the CSV only if needed; prefer MCP for metadata):

> Using the station-metadata MCP, call `get_station` for the station_id with the impossible wind value. What hardware and software is it running?

> Using the station-metadata MCP, call `get_firmware` for that station’s firmware_id. How is wind speed stored, and could that explain a reading of -127?
