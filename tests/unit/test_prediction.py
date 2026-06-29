"""
Unit tests for the prediction module.
"""

import pytest
from datetime import datetime, timedelta

from src.prediction_engine.prediction import (
    Prediction,
    PredictionType,
    PredictionStatus,
    SkyLocation,
    WaveParameters,
)


class TestSkyLocation:
    """Tests for SkyLocation dataclass."""

    def test_valid_sky_location(self):
        """Test creating a valid sky location."""
        loc = SkyLocation(right_ascension=180.0, declination=45.0)
        assert loc.right_ascension == 180.0
        assert loc.declination == 45.0
        assert loc.uncertainty_radius == 0.0

    def test_sky_location_with_uncertainty(self):
        """Test sky location with uncertainty radius."""
        loc = SkyLocation(right_ascension=90.0, declination=-30.0, uncertainty_radius=5.0)
        assert loc.uncertainty_radius == 5.0

    def test_invalid_right_ascension_negative(self):
        """Test that negative RA raises ValueError."""
        with pytest.raises(ValueError, match="Right ascension must be between"):
            SkyLocation(right_ascension=-10.0, declination=0.0)

    def test_invalid_right_ascension_too_large(self):
        """Test that RA > 360 raises ValueError."""
        with pytest.raises(ValueError, match="Right ascension must be between"):
            SkyLocation(right_ascension=400.0, declination=0.0)

    def test_invalid_declination_too_low(self):
        """Test that declination < -90 raises ValueError."""
        with pytest.raises(ValueError, match="Declination must be between"):
            SkyLocation(right_ascension=0.0, declination=-100.0)

    def test_invalid_declination_too_high(self):
        """Test that declination > 90 raises ValueError."""
        with pytest.raises(ValueError, match="Declination must be between"):
            SkyLocation(right_ascension=0.0, declination=95.0)

    def test_negative_uncertainty(self):
        """Test that negative uncertainty raises ValueError."""
        with pytest.raises(ValueError, match="Uncertainty radius cannot be negative"):
            SkyLocation(right_ascension=0.0, declination=0.0, uncertainty_radius=-1.0)

    def test_boundary_values(self):
        """Test boundary values for coordinates."""
        # These should all be valid
        loc1 = SkyLocation(right_ascension=0.0, declination=-90.0)
        loc2 = SkyLocation(right_ascension=360.0, declination=90.0)
        assert loc1.right_ascension == 0.0
        assert loc2.right_ascension == 360.0


class TestWaveParameters:
    """Tests for WaveParameters dataclass."""

    def test_valid_wave_parameters(self):
        """Test creating valid wave parameters."""
        params = WaveParameters(frequency_hz=100.0, amplitude=1e-21)
        assert params.frequency_hz == 100.0
        assert params.amplitude == 1e-21
        assert params.chirp_mass is None

    def test_wave_parameters_with_all_fields(self):
        """Test wave parameters with all optional fields."""
        params = WaveParameters(
            frequency_hz=150.0,
            amplitude=5e-22,
            chirp_mass=30.0,
            distance_mpc=500.0,
            snr=15.0,
        )
        assert params.chirp_mass == 30.0
        assert params.distance_mpc == 500.0
        assert params.snr == 15.0

    def test_invalid_frequency_zero(self):
        """Test that zero frequency raises ValueError."""
        with pytest.raises(ValueError, match="Frequency must be positive"):
            WaveParameters(frequency_hz=0.0, amplitude=1e-21)

    def test_invalid_frequency_negative(self):
        """Test that negative frequency raises ValueError."""
        with pytest.raises(ValueError, match="Frequency must be positive"):
            WaveParameters(frequency_hz=-50.0, amplitude=1e-21)

    def test_invalid_amplitude_zero(self):
        """Test that zero amplitude raises ValueError."""
        with pytest.raises(ValueError, match="Amplitude must be positive"):
            WaveParameters(frequency_hz=100.0, amplitude=0.0)

    def test_invalid_amplitude_negative(self):
        """Test that negative amplitude raises ValueError."""
        with pytest.raises(ValueError, match="Amplitude must be positive"):
            WaveParameters(frequency_hz=100.0, amplitude=-1e-21)


class TestPrediction:
    """Tests for the Prediction dataclass."""

    @pytest.fixture
    def sample_prediction(self):
        """Create a sample prediction for testing."""
        now = datetime.now()
        return Prediction(
            id="TEST-001",
            prediction_type=PredictionType.GRAVITATIONAL_WAVE,
            created_at=now,
            predicted_event_start=now + timedelta(hours=1),
            predicted_event_end=now + timedelta(hours=25),
            framework="CIA",
            confidence=0.85,
            description="Test gravitational wave prediction",
        )

    def test_valid_prediction(self, sample_prediction):
        """Test creating a valid prediction."""
        assert sample_prediction.id == "TEST-001"
        assert sample_prediction.prediction_type == PredictionType.GRAVITATIONAL_WAVE
        assert sample_prediction.framework == "CIA"
        assert sample_prediction.confidence == 0.85
        assert sample_prediction.status == PredictionStatus.PENDING

    def test_prediction_with_optional_fields(self):
        """Test prediction with sky location and wave parameters."""
        now = datetime.now()
        prediction = Prediction(
            id="TEST-002",
            prediction_type=PredictionType.GRAVITATIONAL_WAVE,
            created_at=now,
            predicted_event_start=now,
            predicted_event_end=now + timedelta(hours=12),
            framework="SIA",
            confidence=0.75,
            description="Test with full parameters",
            sky_location=SkyLocation(right_ascension=120.0, declination=30.0),
            wave_parameters=WaveParameters(frequency_hz=100.0, amplitude=1e-21),
            tags=["test", "gw"],
        )
        assert prediction.sky_location is not None
        assert prediction.wave_parameters is not None
        assert "test" in prediction.tags

    def test_invalid_confidence_too_high(self):
        """Test that confidence > 1 raises ValueError."""
        now = datetime.now()
        with pytest.raises(ValueError, match="Confidence must be between"):
            Prediction(
                id="TEST",
                prediction_type=PredictionType.GRAVITATIONAL_WAVE,
                created_at=now,
                predicted_event_start=now,
                predicted_event_end=now + timedelta(hours=1),
                framework="CIA",
                confidence=1.5,
                description="Invalid",
            )

    def test_invalid_confidence_negative(self):
        """Test that negative confidence raises ValueError."""
        now = datetime.now()
        with pytest.raises(ValueError, match="Confidence must be between"):
            Prediction(
                id="TEST",
                prediction_type=PredictionType.GRAVITATIONAL_WAVE,
                created_at=now,
                predicted_event_start=now,
                predicted_event_end=now + timedelta(hours=1),
                framework="CIA",
                confidence=-0.5,
                description="Invalid",
            )

    def test_invalid_time_window(self):
        """Test that end before start raises ValueError."""
        now = datetime.now()
        with pytest.raises(ValueError, match="end time cannot be before start"):
            Prediction(
                id="TEST",
                prediction_type=PredictionType.GRAVITATIONAL_WAVE,
                created_at=now,
                predicted_event_start=now + timedelta(hours=5),
                predicted_event_end=now,  # End before start
                framework="CIA",
                confidence=0.5,
                description="Invalid",
            )

    def test_invalid_framework(self):
        """Test that invalid framework raises ValueError."""
        now = datetime.now()
        with pytest.raises(ValueError, match="Framework must be one of"):
            Prediction(
                id="TEST",
                prediction_type=PredictionType.GRAVITATIONAL_WAVE,
                created_at=now,
                predicted_event_start=now,
                predicted_event_end=now + timedelta(hours=1),
                framework="INVALID",
                confidence=0.5,
                description="Invalid",
            )

    def test_is_within_window(self, sample_prediction):
        """Test the is_within_window method."""
        now = datetime.now()
        # Time within window
        assert sample_prediction.is_within_window(now + timedelta(hours=5))
        # Time before window
        assert not sample_prediction.is_within_window(now - timedelta(hours=1))
        # Time after window
        assert not sample_prediction.is_within_window(now + timedelta(hours=30))

    def test_time_window_hours(self, sample_prediction):
        """Test the time_window_hours method."""
        hours = sample_prediction.time_window_hours()
        assert hours == 24.0

    def test_mark_validated(self, sample_prediction):
        """Test marking a prediction as validated."""
        sample_prediction.mark_validated("GW230101a")
        assert sample_prediction.status == PredictionStatus.VALIDATED
        assert sample_prediction.matched_event_id == "GW230101a"

    def test_mark_invalidated(self, sample_prediction):
        """Test marking a prediction as invalidated."""
        sample_prediction.mark_invalidated()
        assert sample_prediction.status == PredictionStatus.INVALIDATED

    def test_all_prediction_types(self):
        """Test all prediction types are valid."""
        now = datetime.now()
        for pred_type in PredictionType:
            prediction = Prediction(
                id=f"TEST-{pred_type.value}",
                prediction_type=pred_type,
                created_at=now,
                predicted_event_start=now,
                predicted_event_end=now + timedelta(hours=1),
                framework="Experimental",
                confidence=0.5,
                description=f"Test {pred_type.value}",
            )
            assert prediction.prediction_type == pred_type

    def test_all_frameworks(self):
        """Test all valid frameworks."""
        now = datetime.now()
        for framework in ["CIA", "SIA", "HIA", "IIA", "Experimental"]:
            prediction = Prediction(
                id=f"TEST-{framework}",
                prediction_type=PredictionType.GRAVITATIONAL_WAVE,
                created_at=now,
                predicted_event_start=now,
                predicted_event_end=now + timedelta(hours=1),
                framework=framework,
                confidence=0.5,
                description=f"Test {framework}",
            )
            assert prediction.framework == framework
