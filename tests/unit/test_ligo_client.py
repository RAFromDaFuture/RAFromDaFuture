"""
Unit tests for the LIGO client module.
"""

import pytest
from datetime import datetime, timedelta

from src.prediction_engine.ligo_client import (
    LIGOClient,
    LIGOClientError,
    GravitationalWaveEvent,
    create_mock_event,
)


class TestGravitationalWaveEvent:
    """Tests for GravitationalWaveEvent dataclass."""

    def test_create_event(self):
        """Test creating a gravitational wave event."""
        event = GravitationalWaveEvent(
            event_id="S230518h",
            event_time=datetime(2023, 5, 18, 12, 0, 0),
            detection_pipeline="gstlal",
            far=1e-10,
            instruments=["H1", "L1", "V1"],
            event_type="BBH",
        )

        assert event.event_id == "S230518h"
        assert event.detection_pipeline == "gstlal"
        assert len(event.instruments) == 3

    def test_is_significant_true(self):
        """Test significance check for significant event."""
        event = GravitationalWaveEvent(
            event_id="S230518h",
            event_time=datetime.now(),
            detection_pipeline="gstlal",
            far=1e-12,  # Very low FAR
            instruments=["H1", "L1"],
            event_type="BBH",
        )

        assert event.is_significant is True

    def test_is_significant_false(self):
        """Test significance check for non-significant event."""
        event = GravitationalWaveEvent(
            event_id="S230518h",
            event_time=datetime.now(),
            detection_pipeline="gstlal",
            far=1.0,  # High FAR (1 per second)
            instruments=["H1", "L1"],
            event_type="BBH",
        )

        assert event.is_significant is False

    def test_event_with_all_optional_fields(self):
        """Test event with all optional fields populated."""
        event = GravitationalWaveEvent(
            event_id="GW150914",
            event_time=datetime(2015, 9, 14, 9, 50, 45),
            detection_pipeline="pycbc",
            far=1e-15,
            instruments=["H1", "L1"],
            event_type="BBH",
            right_ascension=180.0,
            declination=45.0,
            distance_mpc=410.0,
            snr=24.0,
            chirp_mass=28.1,
            gracedb_url="https://gracedb.ligo.org/superevents/GW150914/",
        )

        assert event.right_ascension == 180.0
        assert event.declination == 45.0
        assert event.distance_mpc == 410.0
        assert event.snr == 24.0
        assert event.chirp_mass == 28.1


class TestCreateMockEvent:
    """Tests for the create_mock_event factory function."""

    def test_create_mock_event_defaults(self):
        """Test creating mock event with default values."""
        event = create_mock_event(
            event_id="MOCK-001",
            event_time=datetime.now(),
        )

        assert event.event_id == "MOCK-001"
        assert event.event_type == "BBH"
        assert event.detection_pipeline == "mock"
        assert event.right_ascension == 180.0
        assert event.declination == 0.0

    def test_create_mock_event_custom(self):
        """Test creating mock event with custom values."""
        event = create_mock_event(
            event_id="MOCK-002",
            event_time=datetime.now(),
            event_type="BNS",
            ra=90.0,
            dec=-45.0,
            far=1e-8,
        )

        assert event.event_type == "BNS"
        assert event.right_ascension == 90.0
        assert event.declination == -45.0
        assert event.far == 1e-8


class TestLIGOClient:
    """Tests for LIGOClient class."""

    @pytest.fixture
    def mock_client(self):
        """Create a client in mock mode."""
        return LIGOClient(mock_mode=True)

    @pytest.fixture
    def sample_events(self):
        """Create sample events for testing."""
        now = datetime.now()
        return [
            create_mock_event("S001", now - timedelta(days=2)),
            create_mock_event("S002", now - timedelta(days=1)),
            create_mock_event("S003", now),
            create_mock_event("S004", now + timedelta(days=1)),
        ]

    def test_client_initialization_default(self):
        """Test client initialization with defaults."""
        client = LIGOClient()

        assert client.api_base == LIGOClient.GRACEDB_API_BASE
        assert client.timeout == LIGOClient.DEFAULT_TIMEOUT
        assert client.mock_mode is False

    def test_client_initialization_custom(self):
        """Test client initialization with custom settings."""
        client = LIGOClient(
            api_base="https://custom.api.org",
            timeout=60,
            mock_mode=True,
        )

        assert client.api_base == "https://custom.api.org"
        assert client.timeout == 60
        assert client.mock_mode is True

    def test_set_mock_events(self, mock_client, sample_events):
        """Test setting mock events."""
        mock_client.set_mock_events(sample_events)

        events = mock_client.get_superevents()
        assert len(events) == 4

    def test_get_superevents_all(self, mock_client, sample_events):
        """Test getting all superevents."""
        mock_client.set_mock_events(sample_events)

        events = mock_client.get_superevents()
        assert len(events) == 4

    def test_get_superevents_with_start_time(self, mock_client, sample_events):
        """Test filtering superevents by start time."""
        mock_client.set_mock_events(sample_events)
        now = datetime.now()

        events = mock_client.get_superevents(start_time=now - timedelta(hours=12))
        assert len(events) == 2  # Only S003 and S004

    def test_get_superevents_with_end_time(self, mock_client, sample_events):
        """Test filtering superevents by end time."""
        mock_client.set_mock_events(sample_events)
        now = datetime.now()

        events = mock_client.get_superevents(end_time=now - timedelta(hours=12))
        assert len(events) == 2  # Only S001 and S002

    def test_get_superevents_with_time_range(self, mock_client, sample_events):
        """Test filtering superevents by time range."""
        mock_client.set_mock_events(sample_events)
        now = datetime.now()

        events = mock_client.get_superevents(
            start_time=now - timedelta(days=1, hours=12),
            end_time=now + timedelta(hours=12),
        )
        assert len(events) == 2  # S002 and S003

    def test_get_superevents_with_limit(self, mock_client, sample_events):
        """Test limiting number of returned events."""
        mock_client.set_mock_events(sample_events)

        events = mock_client.get_superevents(limit=2)
        assert len(events) == 2

    def test_get_event_found(self, mock_client, sample_events):
        """Test getting a specific event that exists."""
        mock_client.set_mock_events(sample_events)

        event = mock_client.get_event("S002")
        assert event.event_id == "S002"

    def test_get_event_not_found(self, mock_client, sample_events):
        """Test getting a specific event that doesn't exist."""
        mock_client.set_mock_events(sample_events)

        with pytest.raises(LIGOClientError, match="Event not found"):
            mock_client.get_event("NONEXISTENT")

    def test_get_events_in_window(self, mock_client, sample_events):
        """Test getting events within a time window."""
        mock_client.set_mock_events(sample_events)
        now = datetime.now()

        events = mock_client.get_events_in_window(now, window_hours=36)
        assert len(events) >= 1  # At least S003 should be included

    def test_gps_to_datetime(self):
        """Test GPS time conversion."""
        # GPS time for GW150914 was approximately 1126259462
        gps_time = 1126259462
        dt = LIGOClient._gps_to_datetime(gps_time)

        # Should be around September 14, 2015
        assert dt.year == 2015
        assert dt.month == 9
        assert dt.day == 14

    def test_safe_float_valid(self):
        """Test safe float conversion with valid input."""
        assert LIGOClient._safe_float("123.45") == 123.45
        assert LIGOClient._safe_float(123.45) == 123.45
        assert LIGOClient._safe_float(123) == 123.0

    def test_safe_float_invalid(self):
        """Test safe float conversion with invalid input."""
        assert LIGOClient._safe_float(None) is None
        assert LIGOClient._safe_float("not a number") is None
        assert LIGOClient._safe_float([1, 2, 3]) is None

    def test_empty_mock_events(self, mock_client):
        """Test with no mock events set."""
        events = mock_client.get_superevents()
        assert len(events) == 0

    def test_multiple_filters_combined(self, mock_client):
        """Test combining multiple filter options."""
        now = datetime.now()
        events = [
            create_mock_event("S001", now - timedelta(days=5)),
            create_mock_event("S002", now - timedelta(days=3)),
            create_mock_event("S003", now - timedelta(days=1)),
            create_mock_event("S004", now),
            create_mock_event("S005", now + timedelta(days=1)),
        ]
        mock_client.set_mock_events(events)

        result = mock_client.get_superevents(
            start_time=now - timedelta(days=4),
            end_time=now + timedelta(hours=12),
            limit=2,
        )

        assert len(result) == 2
        # Should get S002 and S003 (first 2 after applying time filters)
        assert result[0].event_id == "S002"
        assert result[1].event_id == "S003"


class TestLIGOClientRealAPI:
    """Tests for real API interactions (skipped by default)."""

    @pytest.fixture
    def real_client(self):
        """Create a client for real API calls."""
        return LIGOClient(mock_mode=False, timeout=10)

    @pytest.mark.skip(reason="Requires network access and real LIGO API")
    def test_real_api_connection(self, real_client):
        """Test that we can connect to the real API."""
        # This test would only run in integration testing
        events = real_client.get_superevents(limit=1)
        assert len(events) <= 1

    @pytest.mark.skip(reason="Requires network access and real LIGO API")
    def test_real_api_specific_event(self, real_client):
        """Test fetching a known event from real API."""
        # GW150914 is the first detected gravitational wave
        event = real_client.get_event("S190425z")
        assert event is not None
