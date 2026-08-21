"""
Canned LeadSnap responses and a recording transport, so the test suite runs
offline with no network. Pass ``make_transport(...)`` as the ``_transport``
argument to :class:`LeadSnapClient` to replay them.

The transport records every request it sees on ``.calls`` (a list of
``(method, url, headers, body, timeout)`` tuples) so tests can assert on the
outgoing request without a live server.
"""

from __future__ import annotations

import json
from typing import Any, Callable

# Two-record page in the Laravel pagination envelope LeadSnap returns.
HEATMAP_PAGE: dict[str, Any] = {
    "current_page": 1,
    "data": [
        {
            "id": 1223564,
            "keyword": "foundation repair savannah",
            "search_type": "local_pack",
            "status": "completed",
            "average": "6.23",
            "total_points": 137,
            "top_3_points": 0,
        },
        {
            "id": 1223565,
            "keyword": "foundation repair savannah ga",
            "search_type": "local_pack",
            "status": "completed",
            "average": "5.50",
            "total_points": 137,
            "top_3_points": 4,
        },
    ],
    "total": 66,
    "per_page": 2,
    "last_page": 33,
    "next_page_url": "https://app.leadsnap.com/public/api/v1/heatmaps?page=2",
    "prev_page_url": None,
}

# The same shape but the final page — no next_page_url.
HEATMAP_PAGE_LAST: dict[str, Any] = {
    "current_page": 33,
    "data": [{"id": 999, "keyword": "final", "status": "completed"}],
    "total": 66,
    "per_page": 2,
    "last_page": 33,
    "next_page_url": None,
    "prev_page_url": "https://app.leadsnap.com/public/api/v1/heatmaps?page=32",
}

HEATMAP_ONE: dict[str, Any] = {
    "id": 1482,
    "keyword": "roofing",
    "status": "Pending",
    "total_points": 9,
    "points": [],
}


class RecordingTransport:
    """A ``_transport`` stand-in that returns a routed canned response and
    records each call. Routes are matched by ``(method, path_substring)``."""

    def __init__(self, routes: dict[tuple[str, str], tuple[int, Any]]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, str, dict[str, str], Any, float]] = []

    def __call__(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout: float,
    ) -> tuple[int, Any]:
        parsed_body = json.loads(body.decode("utf-8")) if body else None
        self.calls.append((method, url, headers, parsed_body, timeout))
        for (m, needle), response in self.routes.items():
            if m == method and needle in url:
                return response
        raise AssertionError(f"no canned route for {method} {url}")


def make_transport(
    routes: dict[tuple[str, str], tuple[int, Any]] | None = None,
) -> RecordingTransport:
    """Default transport: list returns HEATMAP_PAGE, get-one returns HEATMAP_ONE."""
    if routes is None:
        routes = {
            ("GET", "/public/api/v1/heatmaps?"): (200, HEATMAP_PAGE),
            ("GET", "/public/api/v1/heatmaps/1482"): (200, HEATMAP_ONE),
        }
    return RecordingTransport(routes)


def status_transport(status: int, body: Any = None) -> Callable[..., tuple[int, Any]]:
    """A transport that always returns a fixed status/body (for error paths)."""

    def _transport(method, url, headers, req_body, timeout):  # noqa: ANN001
        return status, body

    return _transport
