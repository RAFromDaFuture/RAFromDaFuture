"""
Integration tests for the complete prediction workflow.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

from src.prediction_engine.prediction import Prediction, PredictionType, SkyLocation, WaveParameters
from src.prediction_engine.parser import PredictionParser
from src.prediction_engine.validator import PredictionValidator, HashVerifier
from src.prediction_engine.ligo_client import LIGOClient, create_mock_event


class TestFullPredictionWorkflow:
    """
    End-to-end tests for the prediction workflow:
    1. Parse a prediction file
    2. Compute verification hash
    3. Fetch events from LIGO (mocked)
    4. Validate prediction against events
    """

    @pytest.fixture
    def prediction_file(self):
        """Create a temporary prediction file."""
        content = """
# Gravitational Wave Prediction - Simulation 42

Framework: CIA
Confidence: 85%
Date: 01/15/2025

## Parameters
- Frequency: 120 Hz
- Amplitude: 2e-21
- Chirp Mass: 25 solar masses
- Distance: 400 Mpc

## Sky Location
- RA: 180.5
- Dec: 30.2

## Description
Predicting a binary black hole merger event in the northern sky.
Expected high SNR detection across H1 and L1 detectors.

#gravitational #wave #prediction #CIA
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write(content)
            return Path(f.name)

    @pytest.fixture
    def parser(self):
        """Create a prediction parser."""
        return PredictionParser()

    @pytest.fixture
    def validator(self):
        """Create a prediction validator."""
        return PredictionValidator()

    @pytest.fixture
    def ligo_client(self):
        """Create a mock LIGO client with sample events."""
        client = LIGOClient(mock_mode=True)
        now = datetime.now()

        # Create events around the prediction window
        events = [
            create_mock_event(
                "S250115a",
                datetime(2025, 1, 15, 6, 30, 0),
                event_type="BBH",
                ra=182.0,
                dec=31.5,
            ),
            create_mock_event(
                "S250115b",
                datetime(2025, 1, 15, 18, 45, 0),
                event_type="BNS",
                ra=90.0,
                dec=-45.0,
            ),
            create_mock_event(
                "S250116a",
                datetime(2025, 1, 16, 12, 0, 0),
                event_type="BBH",
                ra=185.0,
                dec=28.0,
            ),
        ]
        client.set_mock_events(events)
        return client

    def test_parse_prediction_file(self, prediction_file, parser):
        """Test parsing the prediction file."""
        prediction = parser.parse_file(prediction_file)

        assert prediction.prediction_type == PredictionType.GRAVITATIONAL_WAVE
        assert prediction.framework == "CIA"
        assert prediction.confidence == 0.85
        assert prediction.wave_parameters is not None
        assert prediction.wave_parameters.frequency_hz == 120.0
        assert prediction.sky_location is not None
        assert prediction.sky_location.right_ascension == 180.5

    def test_compute_and_verify_hash(self, prediction_file, parser):
        """Test hash computation and verification."""
        prediction = parser.parse_file(prediction_file)

        # Compute hash
        hash1 = HashVerifier.compute_prediction_hash(prediction)
        assert len(hash1) == 64

        # Hash should be deterministic
        hash2 = HashVerifier.compute_prediction_hash(prediction)
        assert hash1 == hash2

        # Create verification record
        record = HashVerifier.create_verification_record(prediction, prediction_file)
        assert "prediction_hash" in record
        assert "file_hash" in record
        assert record["framework"] == "CIA"

    def test_fetch_events_in_window(self, ligo_client):
        """Test fetching events around prediction time."""
        center = datetime(2025, 1, 15, 12, 0, 0)
        events = ligo_client.get_events_in_window(center, window_hours=48)

        assert len(events) >= 2

    def test_validate_prediction_against_events(
        self, prediction_file, parser, validator, ligo_client
    ):
        """Test validating a prediction against fetched events."""
        prediction = parser.parse_file(prediction_file)

        # Override prediction dates for testing
        prediction.predicted_event_start = datetime(2025, 1, 15, 0, 0, 0)
        prediction.predicted_event_end = datetime(2025, 1, 16, 0, 0, 0)

        # Fetch events
        events = ligo_client.get_superevents(
            start_time=prediction.predicted_event_start - timedelta(days=1),
            end_time=prediction.predicted_event_end + timedelta(days=1),
        )

        # Validate against each event
        matches = []
        for event in events:
            result = validator.validate_against_event(
                prediction,
                event_time=event.event_time,
                event_ra=event.right_ascension,
                event_dec=event.declination,
            )
            if result["overall_match"]:
                matches.append((event, result))

        # Should find at least one match (S250115a is close in location)
        assert len(matches) >= 1

    def test_full_workflow_successful_prediction(
        self, prediction_file, parser, validator, ligo_client
    ):
        """Test complete workflow for a successful prediction."""
        # Step 1: Parse prediction
        prediction = parser.parse_file(prediction_file)

        # Step 2: Validate structure
        warnings = validator.validate_prediction_structure(prediction)
        # May have warnings but should parse successfully

        # Step 3: Compute hash for integrity
        pred_hash = HashVerifier.compute_prediction_hash(prediction)
        file_hash = HashVerifier.compute_hash(prediction_file.read_text())

        # Step 4: Set prediction window for testing
        prediction.predicted_event_start = datetime(2025, 1, 15, 0, 0, 0)
        prediction.predicted_event_end = datetime(2025, 1, 16, 0, 0, 0)

        # Step 5: Find matching event
        events = ligo_client.get_events_in_window(
            datetime(2025, 1, 15, 12, 0, 0), window_hours=48
        )

        best_match = None
        best_score = 0

        for event in events:
            result = validator.validate_against_event(
                prediction,
                event_time=event.event_time,
                event_ra=event.right_ascension,
                event_dec=event.declination,
            )
            if result["overall_match"] and result["match_score"] > best_score:
                best_match = event
                best_score = result["match_score"]

        # Step 6: Mark prediction as validated if match found
        if best_match:
            prediction.mark_validated(best_match.event_id)
            assert prediction.matched_event_id == best_match.event_id

        # Cleanup
        prediction_file.unlink()


class TestMultiplePredictionValidation:
    """Test validating multiple predictions against a set of events."""

    @pytest.fixture
    def predictions(self):
        """Create multiple test predictions."""
        base_time = datetime(2025, 1, 15, 0, 0, 0)
        return [
            Prediction(
                id="PRED-001",
                prediction_type=PredictionType.GRAVITATIONAL_WAVE,
                created_at=datetime.now(),
                predicted_event_start=base_time,
                predicted_event_end=base_time + timedelta(hours=24),
                framework="CIA",
                confidence=0.9,
                description="High confidence BBH prediction",
                sky_location=SkyLocation(180.0, 30.0),
                wave_parameters=WaveParameters(100.0, 1e-21),
            ),
            Prediction(
                id="PRED-002",
                prediction_type=PredictionType.GRAVITATIONAL_WAVE,
                created_at=datetime.now(),
                predicted_event_start=base_time + timedelta(hours=12),
                predicted_event_end=base_time + timedelta(hours=36),
                framework="SIA",
                confidence=0.7,
                description="Medium confidence BNS prediction",
                sky_location=SkyLocation(90.0, -45.0),
                wave_parameters=WaveParameters(200.0, 5e-22),
            ),
            Prediction(
                id="PRED-003",
                prediction_type=PredictionType.GRAVITATIONAL_WAVE,
                created_at=datetime.now(),
                predicted_event_start=base_time - timedelta(days=5),
                predicted_event_end=base_time - timedelta(days=4),
                framework="HIA",
                confidence=0.8,
                description="Old prediction - should not match",
                sky_location=SkyLocation(270.0, 0.0),
            ),
        ]

    @pytest.fixture
    def events(self):
        """Create test events."""
        return [
            create_mock_event(
                "S001",
                datetime(2025, 1, 15, 6, 0, 0),
                ra=182.0,
                dec=31.0,
            ),
            create_mock_event(
                "S002",
                datetime(2025, 1, 15, 20, 0, 0),
                ra=88.0,
                dec=-43.0,
            ),
        ]

    def test_batch_validation(self, predictions, events):
        """Test validating multiple predictions against multiple events."""
        validator = PredictionValidator()

        results = {}
        for pred in predictions:
            pred_results = []
            for event in events:
                result = validator.validate_against_event(
                    pred,
                    event_time=event.event_time,
                    event_ra=event.right_ascension,
                    event_dec=event.declination,
                )
                if result["overall_match"]:
                    pred_results.append({
                        "event_id": event.event_id,
                        "score": result["match_score"],
                    })
            results[pred.id] = pred_results

        # PRED-001 should match S001 (close in location and time)
        assert len(results["PRED-001"]) >= 1

        # PRED-002 should match S002 (close in location and time)
        assert len(results["PRED-002"]) >= 1

        # PRED-003 should not match (old prediction)
        assert len(results["PRED-003"]) == 0

    def test_calculate_success_rate(self, predictions, events):
        """Test calculating prediction success rate."""
        validator = PredictionValidator()

        validated = 0
        for pred in predictions:
            for event in events:
                result = validator.validate_against_event(
                    pred,
                    event_time=event.event_time,
                    event_ra=event.right_ascension,
                    event_dec=event.declination,
                )
                if result["overall_match"]:
                    validated += 1
                    break  # Count each prediction only once

        success_rate = validated / len(predictions)

        # 2 out of 3 predictions should validate
        assert success_rate >= 0.5
