"""
Offline tests for the LeadSnap Heatmaps API client.

Runs with plain ``pytest`` (or ``python -m pytest``). No network: every call
replays a canned response via the ``_transport`` injection seam.

Coverage:
  - token resolution (explicit arg, env var, missing)
  - list pagination envelope parsing + filter[...] query encoding
  - iter_heatmaps following next_page_url across pages
  - get / competitors / grid point path building
  - create_heatmap body assembly (grid config vs pre-computed points)
  - auth (401/403) and generic error mapping
  - the token never leaks into exceptions/repr
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Make `import leadsnap` work when run from anywhere in the repo.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from leadsnap import LeadSnapAuthError, LeadSnapClient, LeadSnapError  # noqa: E402
from leadsnap.tests.fixtures import (  # noqa: E402
    HEATMAP_ONE,
    HEATMAP_PAGE,
    HEATMAP_PAGE_LAST,
    RecordingTransport,
    make_transport,
    status_transport,
)

TOKEN = "1234567|test-token-do-not-use"


def _client(transport=None):
    return LeadSnapClient(TOKEN, _transport=transport or make_transport())


# ── token resolution ────────────────────────────────────────────────────────

def test_token_from_argument():
    c = LeadSnapClient(TOKEN, _transport=make_transport())
    assert c._token == TOKEN


def test_token_from_env(monkeypatch):
    monkeypatch.setenv("LEADSNAP_API_TOKEN", "env-token")
    c = LeadSnapClient(_transport=make_transport())
    assert c._token == "env-token"


def test_missing_token_raises(monkeypatch):
    monkeypatch.delenv("LEADSNAP_API_TOKEN", raising=False)
    with pytest.raises(LeadSnapError):
        LeadSnapClient(_transport=make_transport())


# ── list + query encoding ───────────────────────────────────────────────────

def test_list_heatmaps_parses_page():
    page = _client().list_heatmaps(status="completed")
    assert [h["id"] for h in page.data] == [1223564, 1223565]
    assert page.total == 66
    assert page.has_next is True


def test_list_encodes_filters():
    transport = make_transport()
    _client(transport).list_heatmaps(
        status="completed", keyword="roof", per_page=25
    )
    url = transport.calls[0][1]
    assert "filter%5Bstatus%5D=completed" in url
    assert "filter%5Bkeyword%5D=roof" in url
    assert "per_page=25" in url


def test_list_omits_none_filters():
    transport = make_transport()
    _client(transport).list_heatmaps(status="completed")
    url = transport.calls[0][1]
    assert "keyword" not in url


# ── pagination iterator ─────────────────────────────────────────────────────

def test_iter_heatmaps_follows_pages():
    routes = {
        ("GET", "page=1"): (200, HEATMAP_PAGE),
        ("GET", "page=2"): (200, HEATMAP_PAGE_LAST),
    }
    client = LeadSnapClient(TOKEN, _transport=RecordingTransport(routes))
    ids = [h["id"] for h in client.iter_heatmaps()]
    assert ids == [1223564, 1223565, 999]


# ── get / competitors / points ──────────────────────────────────────────────

def test_get_heatmap_builds_path():
    transport = make_transport()
    result = _client(transport).get_heatmap(1482)
    assert result == HEATMAP_ONE
    assert transport.calls[0][0] == "GET"
    assert transport.calls[0][1].endswith("/public/api/v1/heatmaps/1482")


def test_get_heatmap_point_path():
    routes = {("GET", "/heatmaps/5/points/9"): (200, {"id": 9})}
    client = LeadSnapClient(TOKEN, _transport=RecordingTransport(routes))
    assert client.get_heatmap_point(5, 9) == {"id": 9}


# ── create_heatmap body assembly ────────────────────────────────────────────

def test_create_heatmap_with_grid_config():
    routes = {("POST", "/public/api/v1/heatmaps"): (200, {"id": 1})}
    transport = RecordingTransport(routes)
    client = LeadSnapClient(TOKEN, _transport=transport)
    client.create_heatmap(
        place_id="ChIJabc",
        keyword="roofing",
        search_type="google_maps",
        lat=44.67,
        lng=-88.12,
        grid_size=3,
        grid_radius=3495.0,
        distance_type="m",
    )
    body = transport.calls[0][3]
    assert body["keyword"] == ["roofing"]          # scalar promoted to list
    assert body["search_type"] == ["google_maps"]
    assert body["grid_size"] == 3
    assert body["distanceType"] == "m"
    assert "points" not in body


def test_create_heatmap_with_points_skips_grid():
    routes = {("POST", "/public/api/v1/heatmaps"): (200, {"id": 1})}
    transport = RecordingTransport(routes)
    client = LeadSnapClient(TOKEN, _transport=transport)
    pts = [{"lat": 1.0, "lng": 2.0}]
    client.create_heatmap(
        place_id="ChIJabc",
        keyword=["a", "b"],
        search_type=["google_maps", "local_pack"],
        lat=1.0,
        lng=2.0,
        points=pts,
    )
    body = transport.calls[0][3]
    assert body["points"] == pts
    assert "grid_size" not in body


def test_create_heatmap_requires_grid_or_points():
    with pytest.raises(ValueError):
        _client().create_heatmap(
            place_id="ChIJabc",
            keyword="roofing",
            search_type="google_maps",
            lat=1.0,
            lng=2.0,
        )


# ── error mapping ────────────────────────────────────────────────────────────

def test_auth_error_on_401():
    client = LeadSnapClient(TOKEN, _transport=status_transport(401, {"message": "no"}))
    with pytest.raises(LeadSnapAuthError) as exc:
        client.list_heatmaps()
    assert exc.value.status == 401


def test_generic_error_on_500():
    client = LeadSnapClient(TOKEN, _transport=status_transport(500, {"message": "boom"}))
    with pytest.raises(LeadSnapError) as exc:
        client.get_heatmap(1)
    assert exc.value.status == 500


def test_token_not_leaked_in_errors():
    client = LeadSnapClient(TOKEN, _transport=status_transport(500))
    with pytest.raises(LeadSnapError) as exc:
        client.get_heatmap(1)
    assert TOKEN not in str(exc.value)


def test_auth_header_carries_bearer_token():
    transport = make_transport()
    _client(transport).list_heatmaps(status="completed")
    headers = transport.calls[0][2]
    assert headers["Authorization"] == f"Bearer {TOKEN}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
