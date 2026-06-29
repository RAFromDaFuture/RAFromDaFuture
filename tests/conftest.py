"""
Pytest configuration and shared fixtures.
"""

import sys
from pathlib import Path
import pytest
from datetime import datetime, timedelta

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.prediction_engine.prediction import (
    Prediction,
    PredictionType,
    SkyLocation,
    WaveParameters,
)
from src.prediction_engine.parser import PredictionParser
from src.prediction_engine.validator import PredictionValidator
from src.prediction_engine.ligo_client import LIGOClient, create_mock_event


# ============================================================================
# Pytest Hooks
# ============================================================================


def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "integration: mark as integration test")
    config.addinivalue_line("markers", "network: mark as requiring network access")


# ============================================================================
# Base Fixtures
# ============================================================================


@pytest.fixture
def parser():
    """Create a prediction parser instance."""
    return PredictionParser()


@pytest.fixture
def validator():
    """Create a prediction validator with default settings."""
    return PredictionValidator()


@pytest.fixture
def strict_validator():
    """Create a prediction validator with strict settings."""
    return PredictionValidator(
        time_tolerance_hours=6,
        location_tolerance_degrees=10,
        frequency_tolerance_percent=20,
    )


@pytest.fixture
def lenient_validator():
    """Create a prediction validator with lenient settings."""
    return PredictionValidator(
        time_tolerance_hours=72,
        location_tolerance_degrees=60,
        frequency_tolerance_percent=100,
    )


@pytest.fixture
def mock_ligo_client():
    """Create a mock LIGO client."""
    return LIGOClient(mock_mode=True)


# ============================================================================
# Prediction Fixtures
# ============================================================================


@pytest.fixture
def base_time():
    """Provide a consistent base time for tests."""
    return datetime(2025, 1, 15, 12, 0, 0)


@pytest.fixture
def sample_sky_location():
    """Create a sample sky location."""
    return SkyLocation(
        right_ascension=180.0,
        declination=30.0,
        uncertainty_radius=10.0,
    )


@pytest.fixture
def sample_wave_parameters():
    """Create sample wave parameters."""
    return WaveParameters(
        frequency_hz=100.0,
        amplitude=1e-21,
        chirp_mass=28.0,
        distance_mpc=400.0,
        snr=15.0,
    )


@pytest.fixture
def sample_prediction(base_time, sample_sky_location, sample_wave_parameters):
    """Create a fully-populated sample prediction."""
    return Prediction(
        id="TEST-SAMPLE-001",
        prediction_type=PredictionType.GRAVITATIONAL_WAVE,
        created_at=base_time - timedelta(days=1),
        predicted_event_start=base_time,
        predicted_event_end=base_time + timedelta(hours=24),
        framework="CIA",
        confidence=0.85,
        description="Sample prediction for testing purposes",
        sky_location=sample_sky_location,
        wave_parameters=sample_wave_parameters,
        tags=["test", "sample"],
    )


@pytest.fixture
def minimal_prediction(base_time):
    """Create a minimal prediction without optional fields."""
    return Prediction(
        id="TEST-MINIMAL-001",
        prediction_type=PredictionType.GRAVITATIONAL_WAVE,
        created_at=base_time,
        predicted_event_start=base_time,
        predicted_event_end=base_time + timedelta(hours=12),
        framework="Experimental",
        confidence=0.5,
        description="Minimal prediction",
    )


# ============================================================================
# Event Fixtures
# ============================================================================


@pytest.fixture
def sample_event(base_time):
    """Create a sample LIGO event."""
    return create_mock_event(
        event_id="S250115a",
        event_time=base_time + timedelta(hours=6),
        event_type="BBH",
        ra=182.0,
        dec=31.0,
        far=1e-10,
    )


@pytest.fixture
def event_batch(base_time):
    """Create a batch of events for testing."""
    return [
        create_mock_event(
            f"S25011{i}",
            base_time + timedelta(hours=i * 6),
            event_type="BBH" if i % 2 == 0 else "BNS",
            ra=180.0 + i * 5,
            dec=30.0 - i * 2,
        )
        for i in range(5)
    ]


@pytest.fixture
def ligo_client_with_events(mock_ligo_client, event_batch):
    """Create a mock LIGO client pre-populated with events."""
    mock_ligo_client.set_mock_events(event_batch)
    return mock_ligo_client


# ============================================================================
# Content Fixtures
# ============================================================================


@pytest.fixture
def gw_prediction_content():
    """Sample gravitational wave prediction content."""
    return """
# Gravitational Wave Prediction

Framework: CIA
Confidence: 85%
Date: 01/15/2025

Frequency: 100 Hz
Amplitude: 1e-21
RA: 180
Dec: 30

This is a test gravitational wave prediction.
#test #gravitational #wave
"""


@pytest.fixture
def gamma_prediction_content():
    """Sample gamma ray burst prediction content."""
    return """
# Gamma Ray Burst Prediction

Framework: SIA
Confidence: 72%
Date: 01/20/2025

Expected GRB in Virgo constellation.
#gamma #burst
"""


@pytest.fixture
def solar_prediction_content():
    """Sample solar flare prediction content."""
    return """
Solar Flare Warning

Framework: HIA
Confidence: 90%
Date: 02/01/2025

X-class flare expected.
#solar #flare
"""


# ============================================================================
# Temporary File Fixtures
# ============================================================================


@pytest.fixture
def temp_prediction_file(tmp_path, gw_prediction_content):
    """Create a temporary prediction file."""
    file_path = tmp_path / "test_prediction.md"
    file_path.write_text(gw_prediction_content)
    return file_path


@pytest.fixture
def temp_prediction_dir(tmp_path, gw_prediction_content, gamma_prediction_content):
    """Create a directory with multiple prediction files."""
    (tmp_path / "gw_prediction.md").write_text(gw_prediction_content)
    (tmp_path / "gamma_prediction.md").write_text(gamma_prediction_content)
    return tmp_path
