"""
Validation and hash verification for predictions.
"""

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .prediction import Prediction, PredictionStatus, PredictionType


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


class HashVerifier:
    """
    Verifies SHA-256 hashes for prediction integrity.

    Provides cryptographic proof that prediction content has not been
    modified after the initial timestamp.
    """

    @staticmethod
    def compute_hash(content: str) -> str:
        """
        Compute SHA-256 hash of content.

        Args:
            content: The content to hash.

        Returns:
            Hexadecimal hash string.
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def compute_prediction_hash(prediction: Prediction) -> str:
        """
        Compute a hash of a prediction's core fields.

        This creates a deterministic hash based on the prediction's
        immutable content (excludes status and matched_event_id).

        Args:
            prediction: The prediction to hash.

        Returns:
            Hexadecimal hash string.
        """
        # Create a dictionary of hashable fields
        hashable_data = {
            "id": prediction.id,
            "type": prediction.prediction_type.value,
            "created_at": prediction.created_at.isoformat(),
            "event_start": prediction.predicted_event_start.isoformat(),
            "event_end": prediction.predicted_event_end.isoformat(),
            "framework": prediction.framework,
            "confidence": prediction.confidence,
            "description": prediction.description,
        }

        if prediction.sky_location:
            hashable_data["sky_location"] = {
                "ra": prediction.sky_location.right_ascension,
                "dec": prediction.sky_location.declination,
            }

        if prediction.wave_parameters:
            hashable_data["wave_params"] = {
                "freq": prediction.wave_parameters.frequency_hz,
                "amp": prediction.wave_parameters.amplitude,
            }

        # Create deterministic JSON string
        content = json.dumps(hashable_data, sort_keys=True, separators=(",", ":"))
        return HashVerifier.compute_hash(content)

    @staticmethod
    def verify_file_hash(file_path: Path, expected_hash: str) -> bool:
        """
        Verify that a file matches an expected hash.

        Args:
            file_path: Path to the file to verify.
            expected_hash: Expected SHA-256 hash.

        Returns:
            True if hash matches, False otherwise.
        """
        if not file_path.exists():
            return False

        content = file_path.read_text(encoding="utf-8", errors="replace")
        actual_hash = HashVerifier.compute_hash(content)
        return actual_hash.lower() == expected_hash.lower()

    @staticmethod
    def create_verification_record(prediction: Prediction, file_path: Optional[Path] = None) -> dict:
        """
        Create a verification record for a prediction.

        Args:
            prediction: The prediction to create a record for.
            file_path: Optional source file path.

        Returns:
            Dictionary containing verification metadata.
        """
        record = {
            "prediction_id": prediction.id,
            "prediction_hash": HashVerifier.compute_prediction_hash(prediction),
            "verification_timestamp": datetime.now().isoformat(),
            "framework": prediction.framework,
        }

        if file_path and file_path.exists():
            record["file_hash"] = HashVerifier.compute_hash(
                file_path.read_text(encoding="utf-8", errors="replace")
            )
            record["file_path"] = str(file_path)

        return record


class PredictionValidator:
    """
    Validates predictions against observed events.

    Provides methods to check if a prediction matches an observed event
    based on timing, location, and wave parameters.
    """

    # Default tolerances for matching
    DEFAULT_TIME_TOLERANCE_HOURS = 24
    DEFAULT_LOCATION_TOLERANCE_DEGREES = 30
    DEFAULT_FREQUENCY_TOLERANCE_PERCENT = 50

    def __init__(
        self,
        time_tolerance_hours: float = DEFAULT_TIME_TOLERANCE_HOURS,
        location_tolerance_degrees: float = DEFAULT_LOCATION_TOLERANCE_DEGREES,
        frequency_tolerance_percent: float = DEFAULT_FREQUENCY_TOLERANCE_PERCENT,
    ):
        """
        Initialize the validator with tolerance settings.

        Args:
            time_tolerance_hours: Maximum time difference for a match.
            location_tolerance_degrees: Maximum angular separation for a match.
            frequency_tolerance_percent: Maximum frequency difference percentage.
        """
        self.time_tolerance = timedelta(hours=time_tolerance_hours)
        self.location_tolerance = location_tolerance_degrees
        self.frequency_tolerance = frequency_tolerance_percent / 100

    def validate_prediction_structure(self, prediction: Prediction) -> list[str]:
        """
        Validate the structure and completeness of a prediction.

        Args:
            prediction: The prediction to validate.

        Returns:
            List of validation warnings (empty if all checks pass).
        """
        warnings = []

        # Check required fields
        if not prediction.id:
            warnings.append("Missing prediction ID")

        if not prediction.description or prediction.description == "No description available":
            warnings.append("Missing or default description")

        if prediction.confidence == 0.5:
            warnings.append("Default confidence value (0.5) - may not be explicitly set")

        # Check time window
        window_hours = prediction.time_window_hours()
        if window_hours > 168:  # More than a week
            warnings.append(f"Very wide prediction window: {window_hours:.1f} hours")
        if window_hours < 1:
            warnings.append(f"Very narrow prediction window: {window_hours:.1f} hours")

        # Check type-specific requirements
        if prediction.prediction_type == PredictionType.GRAVITATIONAL_WAVE:
            if not prediction.wave_parameters:
                warnings.append("Gravitational wave prediction missing wave parameters")
            if not prediction.sky_location:
                warnings.append("Gravitational wave prediction missing sky location")

        return warnings

    def check_time_match(
        self, prediction: Prediction, event_time: datetime
    ) -> tuple[bool, float]:
        """
        Check if an event time matches the prediction window.

        Args:
            prediction: The prediction to check against.
            event_time: The observed event time.

        Returns:
            Tuple of (is_match, time_difference_hours).
        """
        # First check if within the explicit prediction window
        if prediction.is_within_window(event_time):
            # Calculate distance from window center
            window_center = prediction.predicted_event_start + timedelta(
                hours=prediction.time_window_hours() / 2
            )
            diff = abs((event_time - window_center).total_seconds()) / 3600
            return True, diff

        # Check if within tolerance of window edges
        start_diff = abs((event_time - prediction.predicted_event_start).total_seconds())
        end_diff = abs((event_time - prediction.predicted_event_end).total_seconds())
        min_diff_hours = min(start_diff, end_diff) / 3600

        if min_diff_hours <= self.time_tolerance.total_seconds() / 3600:
            return True, min_diff_hours

        return False, min_diff_hours

    def check_location_match(
        self,
        prediction: Prediction,
        event_ra: float,
        event_dec: float,
    ) -> tuple[bool, float]:
        """
        Check if an event location matches the prediction.

        Uses angular separation on the celestial sphere.

        Args:
            prediction: The prediction to check against.
            event_ra: Event right ascension in degrees.
            event_dec: Event declination in degrees.

        Returns:
            Tuple of (is_match, angular_separation_degrees).
        """
        if not prediction.sky_location:
            return True, 0.0  # No location constraint

        import math

        # Convert to radians
        ra1 = math.radians(prediction.sky_location.right_ascension)
        dec1 = math.radians(prediction.sky_location.declination)
        ra2 = math.radians(event_ra)
        dec2 = math.radians(event_dec)

        # Haversine formula for angular separation
        d_ra = ra2 - ra1
        d_dec = dec2 - dec1

        a = (
            math.sin(d_dec / 2) ** 2
            + math.cos(dec1) * math.cos(dec2) * math.sin(d_ra / 2) ** 2
        )
        separation = 2 * math.asin(math.sqrt(a))
        separation_deg = math.degrees(separation)

        # Include uncertainty radius in tolerance
        total_tolerance = self.location_tolerance + prediction.sky_location.uncertainty_radius

        return separation_deg <= total_tolerance, separation_deg

    def check_frequency_match(
        self,
        prediction: Prediction,
        event_frequency: float,
    ) -> tuple[bool, float]:
        """
        Check if an event frequency matches the prediction.

        Args:
            prediction: The prediction to check against.
            event_frequency: Observed peak frequency in Hz.

        Returns:
            Tuple of (is_match, percentage_difference).
        """
        if not prediction.wave_parameters:
            return True, 0.0  # No frequency constraint

        pred_freq = prediction.wave_parameters.frequency_hz
        if pred_freq == 0:
            return False, float("inf")

        diff_percent = abs(event_frequency - pred_freq) / pred_freq

        return diff_percent <= self.frequency_tolerance, diff_percent * 100

    def validate_against_event(
        self,
        prediction: Prediction,
        event_time: datetime,
        event_ra: Optional[float] = None,
        event_dec: Optional[float] = None,
        event_frequency: Optional[float] = None,
    ) -> dict:
        """
        Validate a prediction against an observed event.

        Args:
            prediction: The prediction to validate.
            event_time: When the event occurred.
            event_ra: Event right ascension (optional).
            event_dec: Event declination (optional).
            event_frequency: Event peak frequency (optional).

        Returns:
            Dictionary with validation results and scores.
        """
        results = {
            "prediction_id": prediction.id,
            "overall_match": True,
            "checks": {},
            "match_score": 0.0,
        }

        # Time check (required)
        time_match, time_diff = self.check_time_match(prediction, event_time)
        results["checks"]["time"] = {
            "match": time_match,
            "difference_hours": time_diff,
        }
        if not time_match:
            results["overall_match"] = False

        # Location check (if provided)
        if event_ra is not None and event_dec is not None:
            loc_match, loc_diff = self.check_location_match(prediction, event_ra, event_dec)
            results["checks"]["location"] = {
                "match": loc_match,
                "separation_degrees": loc_diff,
            }
            if not loc_match:
                results["overall_match"] = False

        # Frequency check (if provided)
        if event_frequency is not None:
            freq_match, freq_diff = self.check_frequency_match(prediction, event_frequency)
            results["checks"]["frequency"] = {
                "match": freq_match,
                "difference_percent": freq_diff,
            }
            if not freq_match:
                results["overall_match"] = False

        # Calculate match score
        scores = []
        if "time" in results["checks"]:
            # Score inversely proportional to time difference
            time_score = max(0, 1 - (time_diff / 48))  # 48 hours = 0 score
            scores.append(time_score)

        if "location" in results["checks"]:
            loc_score = max(0, 1 - (results["checks"]["location"]["separation_degrees"] / 90))
            scores.append(loc_score)

        if "frequency" in results["checks"]:
            freq_score = max(0, 1 - (results["checks"]["frequency"]["difference_percent"] / 100))
            scores.append(freq_score)

        results["match_score"] = sum(scores) / len(scores) if scores else 0.0

        return results
