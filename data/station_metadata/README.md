# Station metadata

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
