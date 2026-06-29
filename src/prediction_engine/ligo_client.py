"""
Client for fetching gravitational wave event data from LIGO/GraceDB.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


class LIGOClientError(Exception):
    """Raised when LIGO/GraceDB API calls fail."""
    pass


@dataclass
class GravitationalWaveEvent:
    """
    Represents a gravitational wave event from LIGO/GraceDB.
    """
    event_id: str  # e.g., "S230518h", "GW150914"
    event_time: datetime
    detection_pipeline: str  # e.g., "gstlal", "pycbc"
    far: float  # False Alarm Rate (Hz)
    instruments: list[str]  # e.g., ["H1", "L1", "V1"]
    event_type: str  # e.g., "BBH", "BNS", "NSBH"
    right_ascension: Optional[float] = None  # degrees
    declination: Optional[float] = None  # degrees
    distance_mpc: Optional[float] = None
    snr: Optional[float] = None
    chirp_mass: Optional[float] = None
    gracedb_url: Optional[str] = None

    @property
    def is_significant(self) -> bool:
        """Check if event meets significance threshold (FAR < 1/year)."""
        seconds_per_year = 365.25 * 24 * 3600
        return self.far < 1 / seconds_per_year


class LIGOClient:
    """
    Client for interacting with LIGO GraceDB API.

    Fetches gravitational wave event data for prediction validation.
    Note: In production, this would use the actual GraceDB API.
    For testing, mock data can be injected.
    """

    GRACEDB_API_BASE = "https://gracedb.ligo.org/api"
    SUPEREVENTS_ENDPOINT = "/superevents"
    DEFAULT_TIMEOUT = 30

    def __init__(
        self,
        api_base: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        mock_mode: bool = False,
    ):
        """
        Initialize the LIGO client.

        Args:
            api_base: Override API base URL (for testing).
            timeout: Request timeout in seconds.
            mock_mode: If True, return mock data instead of real API calls.
        """
        self.api_base = api_base or self.GRACEDB_API_BASE
        self.timeout = timeout
        self.mock_mode = mock_mode
        self._mock_events: list[GravitationalWaveEvent] = []

    def set_mock_events(self, events: list[GravitationalWaveEvent]) -> None:
        """
        Set mock events for testing.

        Args:
            events: List of mock events to return.
        """
        self._mock_events = events

    def get_superevents(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[GravitationalWaveEvent]:
        """
        Fetch superevents from GraceDB.

        Args:
            start_time: Filter events after this time.
            end_time: Filter events before this time.
            limit: Maximum number of events to return.

        Returns:
            List of gravitational wave events.

        Raises:
            LIGOClientError: If API request fails.
        """
        if self.mock_mode:
            return self._filter_mock_events(start_time, end_time, limit)

        # Build query URL
        url = f"{self.api_base}{self.SUPEREVENTS_ENDPOINT}/"
        params = []
        if limit:
            params.append(f"count={limit}")

        if params:
            url += "?" + "&".join(params)

        try:
            request = Request(url, headers={"Accept": "application/json"})
            with urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
                return self._parse_superevents(data, start_time, end_time)
        except HTTPError as e:
            raise LIGOClientError(f"HTTP error fetching superevents: {e.code} {e.reason}")
        except URLError as e:
            raise LIGOClientError(f"URL error fetching superevents: {e.reason}")
        except json.JSONDecodeError as e:
            raise LIGOClientError(f"Invalid JSON response: {e}")

    def get_event(self, event_id: str) -> GravitationalWaveEvent:
        """
        Fetch a specific event by ID.

        Args:
            event_id: The event identifier (e.g., "S230518h").

        Returns:
            The gravitational wave event.

        Raises:
            LIGOClientError: If event not found or API fails.
        """
        if self.mock_mode:
            for event in self._mock_events:
                if event.event_id == event_id:
                    return event
            raise LIGOClientError(f"Event not found: {event_id}")

        url = f"{self.api_base}{self.SUPEREVENTS_ENDPOINT}/{event_id}/"

        try:
            request = Request(url, headers={"Accept": "application/json"})
            with urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
                return self._parse_single_event(data)
        except HTTPError as e:
            if e.code == 404:
                raise LIGOClientError(f"Event not found: {event_id}")
            raise LIGOClientError(f"HTTP error fetching event: {e.code} {e.reason}")
        except URLError as e:
            raise LIGOClientError(f"URL error fetching event: {e.reason}")

    def get_events_in_window(
        self,
        center_time: datetime,
        window_hours: float = 24,
    ) -> list[GravitationalWaveEvent]:
        """
        Fetch events within a time window around a center time.

        Args:
            center_time: Center of the time window.
            window_hours: Width of window in hours (symmetric).

        Returns:
            List of events within the window.
        """
        from datetime import timedelta

        half_window = timedelta(hours=window_hours / 2)
        start_time = center_time - half_window
        end_time = center_time + half_window

        return self.get_superevents(start_time=start_time, end_time=end_time)

    def _filter_mock_events(
        self,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        limit: int,
    ) -> list[GravitationalWaveEvent]:
        """Filter mock events by time range."""
        events = self._mock_events

        if start_time:
            events = [e for e in events if e.event_time >= start_time]
        if end_time:
            events = [e for e in events if e.event_time <= end_time]

        return events[:limit]

    def _parse_superevents(
        self,
        data: dict,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
    ) -> list[GravitationalWaveEvent]:
        """Parse superevent list response."""
        events = []

        superevents = data.get("superevents", [])
        for item in superevents:
            try:
                event = self._parse_single_event(item)

                # Apply time filters
                if start_time and event.event_time < start_time:
                    continue
                if end_time and event.event_time > end_time:
                    continue

                events.append(event)
            except (KeyError, ValueError):
                continue  # Skip malformed events

        return events

    def _parse_single_event(self, data: dict) -> GravitationalWaveEvent:
        """Parse a single superevent from JSON."""
        # Parse event time
        time_str = data.get("t_0") or data.get("gpstime") or data.get("created")
        if isinstance(time_str, (int, float)):
            # GPS time - convert to datetime
            event_time = self._gps_to_datetime(time_str)
        else:
            event_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))

        return GravitationalWaveEvent(
            event_id=data.get("superevent_id") or data.get("graceid", "UNKNOWN"),
            event_time=event_time,
            detection_pipeline=data.get("pipeline", "unknown"),
            far=float(data.get("far", 1.0)),
            instruments=data.get("instruments", "").split(",") if data.get("instruments") else [],
            event_type=data.get("group", "unknown"),
            right_ascension=self._safe_float(data.get("ra")),
            declination=self._safe_float(data.get("dec")),
            distance_mpc=self._safe_float(data.get("distance")),
            snr=self._safe_float(data.get("snr")),
            gracedb_url=data.get("links", {}).get("self"),
        )

    @staticmethod
    def _gps_to_datetime(gps_time: float) -> datetime:
        """Convert GPS time to datetime."""
        # GPS epoch is January 6, 1980
        gps_epoch = datetime(1980, 1, 6)
        from datetime import timedelta

        # Account for leap seconds (approximately 18 as of 2023)
        leap_seconds = 18
        return gps_epoch + timedelta(seconds=gps_time - leap_seconds)

    @staticmethod
    def _safe_float(value) -> Optional[float]:
        """Safely convert value to float."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None


def create_mock_event(
    event_id: str,
    event_time: datetime,
    event_type: str = "BBH",
    ra: float = 180.0,
    dec: float = 0.0,
    far: float = 1e-10,
) -> GravitationalWaveEvent:
    """
    Factory function to create mock events for testing.

    Args:
        event_id: Event identifier.
        event_time: When the event occurred.
        event_type: Type of event (BBH, BNS, etc.).
        ra: Right ascension in degrees.
        dec: Declination in degrees.
        far: False alarm rate.

    Returns:
        A mock GravitationalWaveEvent.
    """
    return GravitationalWaveEvent(
        event_id=event_id,
        event_time=event_time,
        detection_pipeline="mock",
        far=far,
        instruments=["H1", "L1"],
        event_type=event_type,
        right_ascension=ra,
        declination=dec,
        distance_mpc=100.0,
        snr=10.0,
    )
