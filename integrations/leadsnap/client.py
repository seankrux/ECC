"""
LeadSnap Heatmaps API client — a zero-dependency, mostly read-only wrapper
around the LeadSnap public API (Beta).

Drop this module into any agent/host project to pull Google Business Profile
"geogrid" ranking heatmaps — where a business ranks for a keyword across a grid
of map points — and their schedules, competitors and grid points.

Design boundary (intentional):
  - stdlib only:  pure urllib. No third-party imports, no SDK, no `pip install`.
  - token via env: the Sanctum bearer token is read from ``LEADSNAP_API_TOKEN``
                   by default and is never hardcoded, logged, or echoed back.
  - read-first:   list/get calls are safe. The two write paths (``create_heatmap``,
                  ``create_schedule``, ``update_schedule``, ``pause``/``resume``)
                  are explicit methods you have to call on purpose — nothing runs
                  on import.
  - injectable:   every request goes through ``_transport``, an injection seam so
                  tests never touch the network.

Auth: LeadSnap issues personal API tokens at
``https://app.leadsnap.com/account/settings/api-tokens``. Tokens are shown once —
store yours in the ``LEADSNAP_API_TOKEN`` environment variable.

    export LEADSNAP_API_TOKEN='1234567|abcdef...'

    from leadsnap import LeadSnapClient
    client = LeadSnapClient()               # reads LEADSNAP_API_TOKEN
    page = client.list_heatmaps(status="completed", per_page=25)
    for hm in page.data:
        print(hm["id"], hm["keyword"], hm["average"])
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

__all__ = [
    "LeadSnapClient",
    "LeadSnapError",
    "LeadSnapAuthError",
    "Page",
    "DEFAULT_BASE_URL",
    "TOKEN_ENV_VAR",
]

DEFAULT_BASE_URL = "https://app.leadsnap.com"
DEFAULT_TIMEOUT = 30  # seconds
TOKEN_ENV_VAR = "LEADSNAP_API_TOKEN"

# Accepted enum values, surfaced so callers can validate before a round-trip.
SEARCH_TYPES = ("google_maps", "local_pack")
DISTANCE_UNITS = ("km", "mi", "m")
STATUS_SLUGS = ("queue", "in_progress", "completed", "incomplete", "failed")


class LeadSnapError(Exception):
    """A LeadSnap API call failed. ``status`` is the HTTP code (0 on transport
    failure); ``body`` is the parsed error payload when the server sent one."""

    def __init__(self, message: str, status: int = 0, body: Any = None) -> None:
        self.status = status
        self.body = body
        super().__init__(message)


class LeadSnapAuthError(LeadSnapError):
    """Raised on HTTP 401/403 — the token is missing, wrong, or lacks scope."""


@dataclass
class Page:
    """One page of a Laravel-style paginated list response.

    ``data`` is the list of records; the remaining fields mirror the pagination
    envelope LeadSnap returns at the root alongside ``data``. ``raw`` keeps the
    untouched body for callers that need a field not surfaced here.
    """

    data: list[dict[str, Any]]
    total: Optional[int] = None
    per_page: Optional[int] = None
    current_page: Optional[int] = None
    last_page: Optional[int] = None
    next_page_url: Optional[str] = None
    prev_page_url: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def has_next(self) -> bool:
        return bool(self.next_page_url)

    @classmethod
    def from_body(cls, body: dict[str, Any]) -> "Page":
        data = body.get("data")
        if not isinstance(data, list):
            data = []
        return cls(
            data=data,
            total=body.get("total"),
            per_page=body.get("per_page"),
            current_page=body.get("current_page"),
            last_page=body.get("last_page"),
            next_page_url=body.get("next_page_url"),
            prev_page_url=body.get("prev_page_url"),
            raw=body,
        )


# Transport seam: (method, url, headers, body_bytes, timeout) -> (status, dict|None).
# Real callers use the default urllib transport; tests inject a stub.
def _urllib_transport(
    method: str,
    url: str,
    headers: dict[str, str],
    body: Optional[bytes],
    timeout: float,
) -> tuple[int, Any]:
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (https only)
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = raw or None
        return e.code, parsed


class LeadSnapClient:
    """Thin client for the LeadSnap Heatmaps API.

    All methods raise :class:`LeadSnapAuthError` on 401/403 and
    :class:`LeadSnapError` on any other non-2xx response or transport failure —
    they never return a partial or `None` result silently.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        _transport: Callable[..., tuple[int, Any]] = _urllib_transport,
    ) -> None:
        token = token or os.environ.get(TOKEN_ENV_VAR)
        if not token:
            raise LeadSnapError(
                f"No API token. Pass token=... or set the {TOKEN_ENV_VAR} "
                "environment variable (get one at "
                "https://app.leadsnap.com/account/settings/api-tokens)."
            )
        self._token = token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._transport = _transport

    # -- core request plumbing --------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json_body: Optional[dict[str, Any]] = None,
    ) -> Any:
        url = self.base_url + path
        query = _encode_params(params)
        if query:
            url = f"{url}?{query}"

        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "User-Agent": "leadsnap-adapter/1.0",
        }
        body: Optional[bytes] = None
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        try:
            status, parsed = self._transport(
                method, url, headers, body, self.timeout
            )
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise LeadSnapError(f"LeadSnap unreachable: {e}") from e
        except json.JSONDecodeError as e:
            raise LeadSnapError(f"LeadSnap returned non-JSON: {e}") from e

        if status in (401, 403):
            raise LeadSnapAuthError(
                f"LeadSnap auth failed (HTTP {status}) — check {TOKEN_ENV_VAR}.",
                status=status,
                body=parsed,
            )
        if not 200 <= status < 300:
            raise LeadSnapError(
                f"LeadSnap request failed: {method} {path} -> HTTP {status}",
                status=status,
                body=parsed,
            )
        return parsed

    def _list(self, path: str, params: Optional[dict[str, Any]]) -> Page:
        body = self._request("GET", path, params=params)
        if not isinstance(body, dict):
            raise LeadSnapError(f"Expected a paginated object from {path}", body=body)
        return Page.from_body(body)

    # -- Heatmaps ----------------------------------------------------------

    def list_heatmaps(
        self,
        *,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        location_id: Optional[int] = None,
        google_place_id: Optional[str] = None,
        business_name: Optional[str] = None,
        search_type: Optional[str] = None,
        tag: Optional[str] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        sort: Optional[str] = None,
        extra_filters: Optional[dict[str, Any]] = None,
    ) -> Page:
        """List heatmaps for the authenticated account (paginated, 25/page by
        default). Named args map to LeadSnap's ``filter[...]`` query params;
        pass anything not covered here via ``extra_filters={"status": ...}``."""
        filters: dict[str, Any] = {
            "status": status,
            "keyword": keyword,
            "location_id": location_id,
            "google_place_id": google_place_id,
            "business_name": business_name,
            "search_type": search_type,
            "tag": tag,
        }
        if extra_filters:
            filters.update(extra_filters)
        params: dict[str, Any] = {}
        for key, value in filters.items():
            if value is not None:
                params[f"filter[{key}]"] = value
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page
        if sort is not None:
            params["sort"] = sort
        return self._list("/public/api/v1/heatmaps", params)

    def iter_heatmaps(self, **kwargs: Any):
        """Yield every heatmap across all pages, following ``next_page_url``.
        Accepts the same keyword filters as :meth:`list_heatmaps`."""
        page_num = kwargs.pop("page", 1)
        while True:
            page = self.list_heatmaps(page=page_num, **kwargs)
            for record in page.data:
                yield record
            if not page.has_next:
                return
            page_num += 1

    def get_heatmap(self, heatmap_id: int) -> dict[str, Any]:
        """Retrieve a single heatmap, including its grid ``points``."""
        return self._request("GET", f"/public/api/v1/heatmaps/{heatmap_id}")

    def get_heatmap_competitors(self, heatmap_id: int) -> Any:
        """Aggregated ranking stats for competitors seen across the grid."""
        return self._request(
            "GET", f"/public/api/v1/heatmaps/{heatmap_id}/competitors"
        )

    def create_heatmap(
        self,
        *,
        place_id: str,
        keyword: list[str] | str,
        search_type: list[str] | str,
        lat: float,
        lng: float,
        grid_size: Optional[int] = None,
        grid_radius: Optional[float] = None,
        distance_type: Optional[str] = None,
        points: Optional[list[dict[str, float]]] = None,
        batch_id: Optional[str] = None,
        sibling_of: Optional[int] = None,
    ) -> Any:
        """Queue one or more heatmaps. Each keyword × search_type combination
        creates a separate heatmap.

        Provide either ``grid_size`` + ``grid_radius`` + ``distance_type`` to
        auto-generate the grid, or a pre-computed ``points`` list (max 169,
        e.g. from :meth:`generate_grid_points`). ``search_type`` values must be
        in ``SEARCH_TYPES``; ``distance_type`` in ``DISTANCE_UNITS``.
        """
        body: dict[str, Any] = {
            "place_id": place_id,
            "keyword": [keyword] if isinstance(keyword, str) else list(keyword),
            "search_type": (
                [search_type] if isinstance(search_type, str) else list(search_type)
            ),
            "lat": lat,
            "lng": lng,
        }
        if points:
            body["points"] = points
        else:
            if grid_size is None or grid_radius is None or distance_type is None:
                raise ValueError(
                    "Provide points=... or all of grid_size, grid_radius and "
                    "distance_type to auto-generate the grid."
                )
            body["grid_size"] = grid_size
            body["grid_radius"] = grid_radius
            body["distanceType"] = distance_type
        if batch_id is not None:
            body["batch_id"] = batch_id
        if sibling_of is not None:
            body["sibling_of"] = sibling_of
        return self._request("POST", "/public/api/v1/heatmaps", json_body=body)

    # -- Locations & grid points ------------------------------------------

    def list_locations(self, **params: Any) -> Page:
        """List managed GBP locations available as heatmap targets. Use this to
        look up a location's ``place_id`` for :meth:`create_heatmap`."""
        return self._list("/public/api/v1/heatmaps/locations", params or None)

    def generate_grid_points(
        self,
        *,
        lat: float,
        lng: float,
        grid_size: int,
        grid_radius: float,
        distance_type: str,
    ) -> Any:
        """Compute grid point coordinates for a grid config, without running a
        heatmap. Feed the result into :meth:`create_heatmap` as ``points``."""
        body = {
            "lat": lat,
            "lng": lng,
            "grid_size": grid_size,
            "grid_radius": grid_radius,
            "distanceType": distance_type,
        }
        return self._request(
            "POST", "/public/api/v1/heatmap/grid-points", json_body=body
        )

    def get_heatmap_point(self, heatmap_id: int, point_id: int) -> dict[str, Any]:
        """One grid point of a heatmap, with its ranking + organic results."""
        return self._request(
            "GET", f"/public/api/v1/heatmaps/{heatmap_id}/points/{point_id}"
        )

    # -- Schedules ---------------------------------------------------------

    def list_schedules(self, **params: Any) -> Page:
        """List automated heatmap schedules (recurring runs)."""
        return self._list("/public/api/v1/heatmap/schedules", params or None)

    def get_schedule(self, schedule_id: int) -> dict[str, Any]:
        return self._request(
            "GET", f"/public/api/v1/heatmap/schedules/{schedule_id}"
        )

    def create_schedule(self, **body: Any) -> Any:
        """Create a recurring heatmap schedule. Pass the schedule fields as
        keyword arguments (see the API docs for the accepted shape)."""
        return self._request(
            "POST", "/public/api/v1/heatmap/schedules", json_body=body
        )

    def update_schedule(self, schedule_id: int, **body: Any) -> Any:
        return self._request(
            "PATCH",
            f"/public/api/v1/heatmap/schedules/{schedule_id}",
            json_body=body,
        )

    def pause_schedule(self, schedule_id: int) -> Any:
        return self._request(
            "POST", f"/public/api/v1/heatmap/schedules/{schedule_id}/pause"
        )

    def resume_schedule(self, schedule_id: int) -> Any:
        return self._request(
            "POST", f"/public/api/v1/heatmap/schedules/{schedule_id}/resume"
        )


def _encode_params(params: Optional[dict[str, Any]]) -> str:
    """URL-encode query params, dropping ``None`` values and expanding lists
    into repeated keys. Everything else is stringified as-is."""
    if not params:
        return ""
    pairs: list[tuple[str, str]] = []
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            for item in value:
                if item is not None:
                    pairs.append((key, str(item)))
        elif isinstance(value, bool):
            pairs.append((key, "true" if value else "false"))
        else:
            pairs.append((key, str(value)))
    return urllib.parse.urlencode(pairs)
