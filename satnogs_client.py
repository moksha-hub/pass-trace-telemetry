"""Small, defensive client for the public SatNOGS Network observations API."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import requests


API_URL = "https://network.satnogs.org/api/observations/"
API_HOST = "network.satnogs.org"
TIMEOUT_SECONDS = 20
MAX_PAGES = 4


class SatNOGSError(RuntimeError):
    """Raised for API transport, response, or pagination errors."""


def _utc_iso(value: date, *, end_of_day: bool = False) -> str:
    point = datetime.combine(value, time.max if end_of_day else time.min, tzinfo=timezone.utc)
    return point.isoformat(timespec="seconds").replace("+00:00", "Z")


def _check_next_url(next_url: str) -> None:
    parsed = urlparse(next_url)
    if parsed.scheme != "https" or parsed.hostname != API_HOST:
        raise SatNOGSError("SatNOGS returned an unexpected pagination URL; stopped safely.")


def fetch_observations(
    start_date: date,
    end_date: date,
    *,
    max_pages: int = MAX_PAGES,
) -> tuple[list[dict[str, Any]], bool]:
    """Fetch observations in a UTC date range, following the API's Link header.

    Returns ``(rows, truncated)``. The API currently returns arrays and advertises
    its next cursor in an HTTP Link header; deprecated ``page=`` parameters are
    intentionally not used.
    """
    if end_date < start_date:
        raise ValueError("End date must be on or after start date.")
    if (end_date - start_date).days > 13:
        raise ValueError("Choose a date range of 14 days or less.")
    if max_pages < 1:
        raise ValueError("max_pages must be positive.")

    session = requests.Session()
    session.headers.update({"User-Agent": "PASS-TRACE/1.0 (student research project)"})
    url: str | None = API_URL
    params: dict[str, str] | None = {
        "start": _utc_iso(start_date),
        "end": _utc_iso(end_date, end_of_day=True),
    }
    rows: list[dict[str, Any]] = []
    pages = 0

    try:
        while url and pages < max_pages:
            _check_next_url(url)
            try:
                response = session.get(url, params=params, timeout=TIMEOUT_SECONDS)
                response.raise_for_status()
            except requests.Timeout as exc:
                raise SatNOGSError("SatNOGS did not respond in time. Please retry shortly.") from exc
            except requests.RequestException as exc:
                raise SatNOGSError(f"Could not reach the SatNOGS API: {exc}") from exc

            try:
                payload = response.json()
            except ValueError as exc:
                raise SatNOGSError("SatNOGS returned a response that was not valid JSON.") from exc

            if isinstance(payload, dict) and payload.get("error"):
                raise SatNOGSError(str(payload["error"]))
            if not isinstance(payload, list):
                raise SatNOGSError("SatNOGS returned an unexpected response format.")

            rows.extend(item for item in payload if isinstance(item, dict))
            pages += 1
            next_link = response.links.get("next", {}).get("url")
            if next_link:
                _check_next_url(next_link)
            url = next_link
            params = None  # Cursor URL already contains the original filters.
    finally:
        session.close()

    return rows, bool(url)


def normalize_observations(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Normalize SatNOGS records into a compact, display-ready table."""
    columns = [
        "observation_id", "start_utc", "end_utc", "satellite", "norad_id",
        "station", "station_id", "status", "waterfall_status", "has_signal",
        "demodulated_frames", "max_altitude_deg", "frequency_hz", "mode", "url",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)

    frame = pd.DataFrame.from_records(rows)
    for name in ("start", "end"):
        if name not in frame:
            frame[name] = pd.NaT
    for name in ("id", "norad_cat_id", "ground_station", "station_name", "status",
                 "waterfall_status", "tle0", "demoddata", "max_altitude",
                 "observation_frequency", "transmitter_mode"):
        if name not in frame:
            frame[name] = None

    times_start = pd.to_datetime(frame["start"], utc=True, errors="coerce")
    times_end = pd.to_datetime(frame["end"], utc=True, errors="coerce")
    tle_name = frame["tle0"].fillna("").astype(str).str.replace(r"^0\s+", "", regex=True)
    sat_names = tle_name.where(tle_name.ne(""), "Satellite")
    demod_count = frame["demoddata"].map(lambda value: len(value) if isinstance(value, list) else 0)
    waterfall = frame["waterfall_status"].fillna("unknown").astype(str).str.lower()

    normalized = pd.DataFrame({
        "observation_id": frame["id"],
        "start_utc": times_start,
        "end_utc": times_end,
        "satellite": sat_names,
        "norad_id": frame["norad_cat_id"],
        "station": frame["station_name"].fillna("Unknown station"),
        "station_id": frame["ground_station"],
        "status": frame["status"].fillna("unknown").astype(str).str.lower(),
        "waterfall_status": waterfall,
        "has_signal": waterfall.eq("with-signal"),
        "demodulated_frames": demod_count,
        "max_altitude_deg": pd.to_numeric(frame["max_altitude"], errors="coerce"),
        "frequency_hz": pd.to_numeric(frame["observation_frequency"], errors="coerce"),
        "mode": frame["transmitter_mode"].fillna("Unknown").astype(str),
        "url": frame["id"].map(lambda value: f"https://network.satnogs.org/observations/{value}/" if pd.notna(value) else ""),
    })
    return normalized.sort_values("start_utc", ascending=False, na_position="last").reset_index(drop=True)

