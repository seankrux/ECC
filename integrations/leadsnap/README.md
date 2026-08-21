# LeadSnap Heatmaps API adapter

A **zero-dependency, mostly read-only** client for the [LeadSnap public API
(Beta)](https://app.leadsnap.com/docs/#tag/heatmaps) — pull Google Business
Profile "geogrid" ranking heatmaps (where a business ranks for a keyword across
a grid of map points), their competitors, grid points, and recurring schedules.

- **Zero dependencies** — pure Python stdlib (`urllib`). Vendor the `leadsnap/`
  folder, no `pip install`.
- **Token via env** — the Sanctum bearer token is read from
  `LEADSNAP_API_TOKEN`. It is never hardcoded, logged, or included in
  exception messages.
- **Read-first** — `list_*`/`get_*` calls are safe. Writes (`create_heatmap`,
  `create_schedule`, `update_schedule`, `pause_schedule`, `resume_schedule`)
  are explicit methods; nothing runs on import.
- **Injectable transport** — every request goes through a `_transport` seam, so
  the test suite runs fully offline.

## Get a token

LeadSnap issues personal API tokens at
**Account → Settings → API Tokens**
(`https://app.leadsnap.com/account/settings/api-tokens`). Tokens are shown
**once** — copy it immediately and store it in an environment variable. Never
commit a token to source control.

```bash
export LEADSNAP_API_TOKEN='1234567|xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
```

The API authenticates with a standard `Authorization: Bearer <token>` header
against the base URL `https://app.leadsnap.com`.

## Quick start

```python
from leadsnap import LeadSnapClient

client = LeadSnapClient()                      # reads LEADSNAP_API_TOKEN
# or: LeadSnapClient(token="1234567|...")

# List completed heatmaps (paginated, 25/page by default)
page = client.list_heatmaps(status="completed", per_page=25)
for hm in page.data:
    print(hm["id"], hm["keyword"], "avg pos:", hm["average"])
print("total:", page.total, "more pages:", page.has_next)

# Walk every heatmap across all pages
for hm in client.iter_heatmaps(status="completed"):
    ...

# One heatmap, including its grid points
detail = client.get_heatmap(1223564)

# Competitor ranking stats across the grid
competitors = client.get_heatmap_competitors(1223564)

# One grid point's ranking + organic results
point = client.get_heatmap_point(heatmap_id=1223564, point_id=42)
```

## Running a new heatmap

The target of a heatmap is any **Google Place ID**. For a location you manage,
look up its `place_id` via `list_locations()`.

```python
# Find the place_id of a managed location
locs = client.list_locations()
place_id = locs.data[0]["place_id"]

# Auto-generate the grid from a center + size + radius
client.create_heatmap(
    place_id=place_id,
    keyword=["roofing", "roof repair"],   # one heatmap per keyword × search_type
    search_type=["google_maps", "local_pack"],
    lat=44.670381, lng=-88.122418,
    grid_size=7,                          # 7×7 = 49 points (max 13×13 = 169)
    grid_radius=3495.0,
    distance_type="m",                    # "km" | "mi" | "m"
)

# ...or pre-compute the grid points and pass them explicitly
grid = client.generate_grid_points(
    lat=44.670381, lng=-88.122418,
    grid_size=7, grid_radius=3495.0, distance_type="m",
)
client.create_heatmap(
    place_id=place_id, keyword="roofing", search_type="google_maps",
    lat=44.670381, lng=-88.122418, points=grid,
)
```

## Schedules (recurring heatmaps)

```python
schedules = client.list_schedules()
one = client.get_schedule(schedule_id)
client.pause_schedule(schedule_id)
client.resume_schedule(schedule_id)
client.update_schedule(schedule_id, interval="monthly")
```

## Endpoints covered

| Method | Endpoint | Client call |
|---|---|---|
| GET | `/public/api/v1/heatmaps` | `list_heatmaps` / `iter_heatmaps` |
| POST | `/public/api/v1/heatmaps` | `create_heatmap` |
| GET | `/public/api/v1/heatmaps/{id}` | `get_heatmap` |
| GET | `/public/api/v1/heatmaps/{id}/competitors` | `get_heatmap_competitors` |
| GET | `/public/api/v1/heatmaps/locations` | `list_locations` |
| POST | `/public/api/v1/heatmap/grid-points` | `generate_grid_points` |
| GET | `/public/api/v1/heatmaps/{id}/points/{pid}` | `get_heatmap_point` |
| GET | `/public/api/v1/heatmap/schedules` | `list_schedules` |
| POST | `/public/api/v1/heatmap/schedules` | `create_schedule` |
| GET | `/public/api/v1/heatmap/schedules/{id}` | `get_schedule` |
| PATCH | `/public/api/v1/heatmap/schedules/{id}` | `update_schedule` |
| POST | `/public/api/v1/heatmap/schedules/{id}/pause` | `pause_schedule` |
| POST | `/public/api/v1/heatmap/schedules/{id}/resume` | `resume_schedule` |

## Errors

- `LeadSnapAuthError` — HTTP 401/403 (missing/invalid token or insufficient
  scope). Subclass of `LeadSnapError`.
- `LeadSnapError` — any other non-2xx response or transport failure. Carries
  `.status` (HTTP code, `0` on transport failure) and `.body` (parsed error
  payload when present).

## Tests

```bash
python -m pytest integrations/leadsnap/tests -q
# or, standalone:
python integrations/leadsnap/tests/test_client.py
```

All tests replay canned responses through the `_transport` seam — no network,
no real token required.

See [THREAT_MODEL.md](./THREAT_MODEL.md) for data boundaries and handling of
the token and returned business data.
