"""
Unit tests for the validator module.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

from src.prediction_engine.validator import (
    PredictionValidator,
    HashVerifier,
    ValidationError,
)
from src.prediction_engine.prediction import (
    Prediction,
    PredictionType,
    PredictionStatus,
    SkyLocation,
    WaveParameters,
)


class TestHashVerifier:
    """Tests for HashVerifier class."""

    def test_compute_hash_deterministic(self):
        """Test that hash computation is deterministic."""
        content = "Test content for hashing"
        hash1 = HashVerifier.compute_hash(content)
        hash2 = HashVerifier.compute_hash(content)
        assert hash1 == hash2

    def test_compute_hash_different_content(self):
        """Test that different content produces different hashes."""
        hash1 = HashVerifier.compute_hash("Content A")
        hash2 = HashVerifier.compute_hash("Content B")
        assert hash1 != hash2

    def test_compute_hash_format(self):
        """Test that hash is valid SHA-256 format."""
        content = "Test"
        hash_result = HashVerifier.compute_hash(content)
        assert len(hash_result) == 64  # SHA-256 produces 64 hex chars
        assert all(c in "0123456789abcdef" for c in hash_result)

    def test_compute_prediction_hash(self):
        """Test computing hash of a prediction."""
        now = datetime.now()
        prediction = Prediction(
            id="TEST-001",
            prediction_type=PredictionType.GRAVITATIONAL_WAVE,
            created_at=now,
            predicted_event_start=now,
            predicted_event_end=now + timedelta(hours=24),
            framework="CIA",
            confidence=0.85,
            description="Test prediction",
        )
        hash_result = HashVerifier.compute_prediction_hash(prediction)

        assert len(hash_result) == 64
        # Same prediction should give same hash
        hash2 = HashVerifier.compute_prediction_hash(prediction)
        assert hash_result == hash2

    def test_prediction_hash_excludes_status(self):
        """Test that status changes don't affect hash."""
        now = datetime.now()
        prediction = Prediction(
            id="TEST-001",
            prediction_type=PredictionType.GRAVITATIONAL_WAVE,
            created_at=now,
            predicted_event_start=now,
            predicted_event_end=now + timedelta(hours=24),
            framework="CIA",
            confidence=0.85,
            description="Test prediction",
        )
        hash1 = HashVerifier.compute_prediction_hash(prediction)

        prediction.mark_validated("EVENT-001")
        hash2 = HashVerifier.compute_prediction_hash(prediction)

        assert hash1 == hash2

    def test_prediction_hash_with_location(self):
        """Test hash includes sky location when present."""
        now = datetime.now()
        pred1 = Prediction(
            id="TEST-001",
            prediction_type=PredictionType.GRAVITATIONAL_WAVE,
            created_at=now,
            predicted_event_start=now,
            predicted_event_end=now + timedelta(hours=24),
            framework="CIA",
            confidence=0.85,
            description="Test prediction",
            sky_location=SkyLocation(right_ascension=180.0, declination=45.0),
        )
        pred2 = Prediction(
            id="TEST-001",
            prediction_type=PredictionType.GRAVITATIONAL_WAVE,
            created_at=now,
            predicted_event_start=now,
            predicted_event_end=now + timedelta(hours=24),
            framework="CIA",
            confidence=0.85,
            description="Test prediction",
            sky_location=SkyLocation(right_ascension=90.0, declination=45.0),
        )

        hash1 = HashVerifier.compute_prediction_hash(pred1)
        hash2 = HashVerifier.compute_prediction_hash(pred2)

        assert hash1 != hash2

    def test_verify_file_hash(self):
        """Test file hash verification."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test file content")
            f.flush()
            file_path = Path(f.name)

        expected_hash = HashVerifier.compute_hash("Test file content")
        assert HashVerifier.verify_file_hash(file_path, expected_hash)

        # Wrong hash should fail
        assert not HashVerifier.verify_file_hash(file_path, "wrong_hash")

        # Cleanup
        file_path.unlink()

    def test_verify_file_hash_nonexistent(self):
        """Test file hash verification with nonexistent file."""
        assert not HashVerifier.verify_file_hash(Path("/nonexistent/file.txt"), "hash")

    def test_create_verification_record(self):
        """Test creating a verification record."""
        now = datetime.now()
        prediction = Prediction(
            id="TEST-001",
            prediction_type=PredictionType.GRAVITATIONAL_WAVE,
            created_at=now,
            predicted_event_start=now,
            predicted_event_end=now + timedelta(hours=24),
            framework="CIA",
            confidence=0.85,
            description="Test prediction",
        )

        record = HashVerifier.create_verification_record(prediction)

        assert record["prediction_id"] == "TEST-001"
        assert "prediction_hash" in record
        assert "verification_timestamp" in record
        assert record["framework"] == "CIA"


class TestPredictionValidator:
    """Tests for PredictionValidator class."""

    @pytest.fixture
    def validator(self):
        """Create a validator with default settings."""
        return PredictionValidator()

    @pytest.fixture
    def sample_prediction(self):
        """Create a sample prediction for testing."""
        now = datetime.now()
        return Prediction(
            id="TEST-001",
            prediction_type=PredictionType.GRAVITATIONAL_WAVE,
            created_at=now,
            predicted_event_start=now,
            predicted_event_end=now + timedelta(hours=24),
            framework="CIA",
            confidence=0.85,
            description="Test gravitational wave prediction",
            sky_location=SkyLocation(right_ascension=180.0, declination=0.0),
            wave_parameters=WaveParameters(frequency_hz=100.0, amplitude=1e-21),
        )

    def test_validate_structure_complete_prediction(self, validator, sample_prediction):
        """Test structure validation of complete prediction."""
        warnings = validator.validate_prediction_structure(sample_prediction)
        assert len(warnings) == 0

    def test_validate_structure_missing_id(self, validator):
        """Test structure validation catches missing ID."""
        now = datetime.now()
        prediction = Prediction(
            id="",
            prediction_type=PredictionType.GRAVITATIONAL_WAVE,
            created_at=now,
            predicted_event_start=now,
            predicted_event_end=now + timedelta(hours=24),
            framework="CIA",
            confidence=0.85,
            description="Test",
        )
        warnings = validator.validate_prediction_structure(prediction)
        assert any("Missing prediction ID" in w for w in warnings)

    def test_validate_structure_missing_wave_params(self, validator):
        """Test structure validation warns about missing wave params."""
        now = datetime.now()
        prediction = Prediction(
            id="TEST-001",
            prediction_type=PredictionType.GRAVITATIONAL_WAVE,
            created_at=now,
            predicted_event_start=now,
            predicted_event_end=now + timedelta(hours=24),
            framework="CIA",
            confidence=0.85,
            description="Test",
        )
        warnings = validator.validate_prediction_structure(prediction)
        assert any("missing wave parameters" in w for w in warnings)

    def test_validate_structure_wide_window(self, validator):
        """Test structure validation warns about very wide window."""
        now = datetime.now()
        prediction = Prediction(
            id="TEST-001",
            prediction_type=PredictionType.GRAVITATIONAL_WAVE,
            created_at=now,
            predicted_event_start=now,
            predicted_event_end=now + timedelta(days=30),  # 720 hours
            framework="CIA",
            confidence=0.85,
            description="Test",
            wave_parameters=WaveParameters(frequency_hz=100.0, amplitude=1e-21),
            sky_location=SkyLocation(right_ascension=0.0, declination=0.0),
        )
        warnings = validator.validate_prediction_structure(prediction)
        assert any("Very wide prediction window" in w for w in warnings)

    def test_check_time_match_within_window(self, validator, sample_prediction):
        """Test time match when event is within prediction window."""
        event_time = sample_prediction.predicted_event_start + timedelta(hours=12)
        is_match, diff = validator.check_time_match(sample_prediction, event_time)

        assert is_match is True
        assert diff <= 12

    def test_check_time_match_outside_window(self, validator, sample_prediction):
        """Test time match when event is outside prediction window."""
        event_time = sample_prediction.predicted_event_end + timedelta(days=2)
        is_match, diff = validator.check_time_match(sample_prediction, event_time)

        assert is_match is False

    def test_check_time_match_within_tolerance(self, validator, sample_prediction):
        """Test time match when event is within tolerance of window edge."""
        # Just outside the window but within 24-hour tolerance
        event_time = sample_prediction.predicted_event_end + timedelta(hours=12)
        is_match, diff = validator.check_time_match(sample_prediction, event_time)

        assert is_match is True

    def test_check_location_match_close(self, validator, sample_prediction):
        """Test location match when event is nearby."""
        is_match, separation = validator.check_location_match(
            sample_prediction, event_ra=185.0, event_dec=5.0
        )

        assert is_match is True
        assert separation < 30  # Within default tolerance

    def test_check_location_match_far(self, validator, sample_prediction):
        """Test location match when event is far away."""
        is_match, separation = validator.check_location_match(
            sample_prediction, event_ra=0.0, event_dec=-80.0
        )

        assert is_match is False
        assert separation > 30

    def test_check_location_match_no_location(self, validator):
        """Test location match when prediction has no location."""
        now = datetime.now()
        prediction = Prediction(
            id="TEST-001",
            prediction_type=PredictionType.GRAVITATIONAL_WAVE,
            created_at=now,
            predicted_event_start=now,
            predicted_event_end=now + timedelta(hours=24),
            framework="CIA",
            confidence=0.85,
            description="Test",
        )

        is_match, separation = validator.check_location_match(
            prediction, event_ra=180.0, event_dec=45.0
        )

        # No constraint means automatic match
        assert is_match is True
        assert separation == 0.0

    def test_check_frequency_match_close(self, validator, sample_prediction):
        """Test frequency match when event frequency is close."""
        is_match, diff = validator.check_frequency_match(sample_prediction, 110.0)

        assert is_match is True
        assert diff == 10.0  # 10% difference

    def test_check_frequency_match_far(self, validator, sample_prediction):
        """Test frequency match when event frequency is far."""
        is_match, diff = validator.check_frequency_match(sample_prediction, 200.0)

        assert is_match is False
        assert diff == 100.0  # 100% difference

    def test_check_frequency_match_no_params(self, validator):
        """Test frequency match when prediction has no wave params."""
        now = datetime.now()
        prediction = Prediction(
            id="TEST-001",
            prediction_type=PredictionType.GRAVITATIONAL_WAVE,
            created_at=now,
            predicted_event_start=now,
            predicted_event_end=now + timedelta(hours=24),
            framework="CIA",
            confidence=0.85,
            description="Test",
        )

        is_match, diff = validator.check_frequency_match(prediction, 100.0)

        assert is_match is True
        assert diff == 0.0

    def test_validate_against_event_full_match(self, validator, sample_prediction):
        """Test full validation against a matching event."""
        event_time = sample_prediction.predicted_event_start + timedelta(hours=6)

        results = validator.validate_against_event(
            sample_prediction,
            event_time=event_time,
            event_ra=182.0,
            event_dec=2.0,
            event_frequency=105.0,
        )

        assert results["overall_match"] is True
        assert results["checks"]["time"]["match"] is True
        assert results["checks"]["location"]["match"] is True
        assert results["checks"]["frequency"]["match"] is True
        assert results["match_score"] > 0.5

    def test_validate_against_event_time_mismatch(self, validator, sample_prediction):
        """Test validation fails when time doesn't match."""
        event_time = sample_prediction.predicted_event_end + timedelta(days=10)

        results = validator.validate_against_event(
            sample_prediction,
            event_time=event_time,
            event_ra=180.0,
            event_dec=0.0,
        )

        assert results["overall_match"] is False
        assert results["checks"]["time"]["match"] is False

    def test_validate_against_event_location_mismatch(self, validator, sample_prediction):
        """Test validation fails when location doesn't match."""
        event_time = sample_prediction.predicted_event_start + timedelta(hours=6)

        results = validator.validate_against_event(
            sample_prediction,
            event_time=event_time,
            event_ra=0.0,
            event_dec=-85.0,
        )

        assert results["overall_match"] is False
        assert results["checks"]["location"]["match"] is False

    def test_custom_tolerances(self):
        """Test validator with custom tolerances."""
        validator = PredictionValidator(
            time_tolerance_hours=48,
            location_tolerance_degrees=60,
            frequency_tolerance_percent=100,
        )

        now = datetime.now()
        prediction = Prediction(
            id="TEST-001",
            prediction_type=PredictionType.GRAVITATIONAL_WAVE,
            created_at=now,
            predicted_event_start=now,
            predicted_event_end=now + timedelta(hours=1),
            framework="CIA",
            confidence=0.85,
            description="Test",
            sky_location=SkyLocation(right_ascension=180.0, declination=0.0),
            wave_parameters=WaveParameters(frequency_hz=100.0, amplitude=1e-21),
        )

        # Event that would fail with default tolerances
        event_time = prediction.predicted_event_end + timedelta(hours=36)

        is_match, _ = validator.check_time_match(prediction, event_time)
        assert is_match is True  # Passes with 48-hour tolerance

    def test_match_score_calculation(self, validator, sample_prediction):
        """Test that match score is calculated correctly."""
        event_time = sample_prediction.predicted_event_start

        results = validator.validate_against_event(
            sample_prediction,
            event_time=event_time,
            event_ra=180.0,
            event_dec=0.0,
            event_frequency=100.0,
        )

        # Perfect match should have high score
        assert results["match_score"] > 0.9
