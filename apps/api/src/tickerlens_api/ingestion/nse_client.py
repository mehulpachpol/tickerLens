from __future__ import annotations

import datetime as dt

import httpx


DEFAULT_BASE_URL = "https://www.nseindia.com"


def _fmt_date(d: dt.date) -> str:
    # NSE corporate announcements expects DD-MM-YYYY.
    return d.strftime("%d-%m-%Y")


class NseClient:
    """
    Minimal NSE client for Phase 10.

    We prefer calling NSE's JSON endpoints (e.g. /api/corporate-announcements) over scraping HTML.
    It is:
    - more stable (less UI churn)
    - cheaper (no browser automation)
    - easier to make idempotent (stable ids like seq_id)
    """

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        user_agent: str,
        timeout_s: float = 30.0,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout_s,
            headers={
                "User-Agent": user_agent,
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://www.nseindia.com/",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

        # Some NSE endpoints are pickier about cookies; warm the session.
        try:
            self._client.get("/")
        except Exception:
            # Non-fatal: discovery may still work.
            pass

    def close(self) -> None:
        self._client.close()

    def corporate_announcements(
        self,
        *,
        symbol: str,
        index: str = "equities",
        from_date: dt.date | None = None,
        to_date: dt.date | None = None,
    ) -> list[dict]:
        params: dict[str, str] = {"index": index, "symbol": symbol}
        if from_date:
            params["from_date"] = _fmt_date(from_date)
        if to_date:
            params["to_date"] = _fmt_date(to_date)

        resp = self._client.get("/api/corporate-announcements", params=params)
        resp.raise_for_status()
        data = resp.json()

        # NSE sometimes returns a list directly; some wrappers expose {"data":[...]}.
        if isinstance(data, dict):
            items = data.get("data")
            return items if isinstance(items, list) else []
        return data if isinstance(data, list) else []

