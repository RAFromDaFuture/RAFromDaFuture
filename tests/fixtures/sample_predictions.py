"""
Sample prediction data for use in tests.
"""

from datetime import datetime, timedelta
from src.prediction_engine.prediction import (
    Prediction,
    PredictionType,
    PredictionStatus,
    SkyLocation,
    WaveParameters,
)
from src.prediction_engine.ligo_client import GravitationalWaveEvent


# Sample prediction content strings for parser testing
SAMPLE_GW_PREDICTION_MD = """
# Gravitational Wave Prediction - Simulation 28

Framework: CIA
Confidence: 88%
Date: 06/09/2025

## Wave Parameters
- Frequency: 135 Hz
- Amplitude: 1.5e-21
- Chirp Mass: 28.5 solar masses
- Distance: 380 Mpc
- SNR: 18

## Sky Location
- RA: 156.3
- Dec: 42.7
- Uncertainty: 10 degrees

## Notes
Binary black hole merger predicted using Chaos Influence Arithmetic.
Strong resonance patterns detected in symbolic simulation.

#simulation28 #gravitational #wave #BBH
"""

SAMPLE_GAMMA_PREDICTION_TXT = """
Gamma Ray Burst Prediction
Framework: SIA
Confidence: 72%
Date: 06/15/2025

Predicted GRB event in the constellation Virgo.
Short-duration burst expected.

Tags: #gamma #burst #SIA
"""

SAMPLE_SOLAR_PREDICTION = """
Solar Flare Alert
Framework: HIA
Confidence: 95%
Date: 07/01/2025

X-class solar flare predicted from active region AR3456.
Potential CME impact on Earth within 48 hours.

#solar #flare #space-weather
"""

SAMPLE_MINIMAL_PREDICTION = """
Simple prediction test.
"""


def create_sample_gw_prediction(
    prediction_id: str = "SAMPLE-GW-001",
    hours_from_now: float = 24,
    confidence: float = 0.85,
) -> Prediction:
    """
    Create a sample gravitational wave prediction.

    Args:
        prediction_id: ID for the prediction.
        hours_from_now: When the event is predicted (hours from now).
        confidence: Confidence level (0-1).

    Returns:
        A sample Prediction object.
    """
    now = datetime.now()
    return Prediction(
        id=prediction_id,
        prediction_type=PredictionType.GRAVITATIONAL_WAVE,
        created_at=now,
        predicted_event_start=now + timedelta(hours=hours_from_now - 12),
        predicted_event_end=now + timedelta(hours=hours_from_now + 12),
        framework="CIA",
        confidence=confidence,
        description="Sample gravitational wave prediction for testing",
        sky_location=SkyLocation(
            right_ascension=180.0,
            declination=30.0,
            uncertainty_radius=15.0,
        ),
        wave_parameters=WaveParameters(
            frequency_hz=100.0,
            amplitude=1e-21,
            chirp_mass=28.0,
            distance_mpc=400.0,
            snr=15.0,
        ),
        tags=["sample", "test", "gravitational-wave"],
    )


def create_sample_gamma_prediction(
    prediction_id: str = "SAMPLE-GRB-001",
) -> Prediction:
    """Create a sample gamma ray burst prediction."""
    now = datetime.now()
    return Prediction(
        id=prediction_id,
        prediction_type=PredictionType.GAMMA_RAY,
        created_at=now,
        predicted_event_start=now + timedelta(hours=6),
        predicted_event_end=now + timedelta(hours=30),
        framework="SIA",
        confidence=0.72,
        description="Sample gamma ray burst prediction for testing",
        sky_location=SkyLocation(right_ascension=220.0, declination=-15.0),
        tags=["sample", "test", "gamma-ray"],
    )


def create_sample_event(
    event_id: str = "S250101a",
    hours_ago: float = 0,
) -> GravitationalWaveEvent:
    """
    Create a sample LIGO event.

    Args:
        event_id: ID for the event.
        hours_ago: When the event occurred (hours ago).

    Returns:
        A sample GravitationalWaveEvent object.
    """
    now = datetime.now()
    return GravitationalWaveEvent(
        event_id=event_id,
        event_time=now - timedelta(hours=hours_ago),
        detection_pipeline="gstlal",
        far=1e-10,
        instruments=["H1", "L1", "V1"],
        event_type="BBH",
        right_ascension=178.5,
        declination=32.1,
        distance_mpc=420.0,
        snr=18.5,
        chirp_mass=27.3,
    )


# Pre-built test fixtures
VALIDATED_PREDICTION = create_sample_gw_prediction("VALID-001", 0, 0.9)
VALIDATED_PREDICTION.mark_validated("S250101a")

INVALIDATED_PREDICTION = create_sample_gw_prediction("INVALID-001", -48, 0.6)
INVALIDATED_PREDICTION.mark_invalidated()

PENDING_PREDICTION = create_sample_gw_prediction("PENDING-001", 48, 0.75)


# Collection of predictions for batch testing
def get_prediction_batch() -> list[Prediction]:
    """Get a batch of diverse predictions for testing."""
    return [
        create_sample_gw_prediction("BATCH-001", 12, 0.95),
        create_sample_gw_prediction("BATCH-002", 24, 0.80),
        create_sample_gw_prediction("BATCH-003", 36, 0.70),
        create_sample_gamma_prediction("BATCH-004"),
        Prediction(
            id="BATCH-005",
            prediction_type=PredictionType.SOLAR_FLARE,
            created_at=datetime.now(),
            predicted_event_start=datetime.now(),
            predicted_event_end=datetime.now() + timedelta(hours=48),
            framework="HIA",
            confidence=0.88,
            description="Solar flare prediction",
        ),
    ]


# Collection of events for batch testing
def get_event_batch() -> list[GravitationalWaveEvent]:
    """Get a batch of events for testing."""
    return [
        create_sample_event("S001", 0),
        create_sample_event("S002", 12),
        create_sample_event("S003", 24),
        create_sample_event("S004", 36),
    ]
