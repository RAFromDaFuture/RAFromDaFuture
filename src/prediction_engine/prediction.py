"""
Core prediction data structures for the forecasting engine.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class PredictionType(Enum):
    """Types of predictions supported by the forecasting system."""
    GRAVITATIONAL_WAVE = "gravitational_wave"
    GAMMA_RAY = "gamma_ray"
    SOLAR_FLARE = "solar_flare"
    TECTONIC = "tectonic"
    BLACK_HOLE = "black_hole"
    TSUNAMI = "tsunami"


class PredictionStatus(Enum):
    """Status of a prediction."""
    PENDING = "pending"
    VALIDATED = "validated"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


@dataclass
class SkyLocation:
    """Represents a location in the sky using right ascension and declination."""
    right_ascension: float  # In degrees (0-360)
    declination: float  # In degrees (-90 to 90)
    uncertainty_radius: float = 0.0  # In degrees

    def __post_init__(self):
        if not 0 <= self.right_ascension <= 360:
            raise ValueError(f"Right ascension must be between 0 and 360, got {self.right_ascension}")
        if not -90 <= self.declination <= 90:
            raise ValueError(f"Declination must be between -90 and 90, got {self.declination}")
        if self.uncertainty_radius < 0:
            raise ValueError(f"Uncertainty radius cannot be negative, got {self.uncertainty_radius}")


@dataclass
class WaveParameters:
    """Parameters for gravitational wave predictions."""
    frequency_hz: float  # Peak frequency in Hz
    amplitude: float  # Strain amplitude
    chirp_mass: Optional[float] = None  # In solar masses
    distance_mpc: Optional[float] = None  # Distance in megaparsecs
    snr: Optional[float] = None  # Signal-to-noise ratio

    def __post_init__(self):
        if self.frequency_hz <= 0:
            raise ValueError(f"Frequency must be positive, got {self.frequency_hz}")
        if self.amplitude <= 0:
            raise ValueError(f"Amplitude must be positive, got {self.amplitude}")


@dataclass
class Prediction:
    """
    Represents a single prediction from the forecasting engine.
    """
    id: str
    prediction_type: PredictionType
    created_at: datetime
    predicted_event_start: datetime
    predicted_event_end: datetime
    framework: str  # CIA, SIA, HIA, IIA, or Experimental
    confidence: float  # 0.0 to 1.0
    description: str
    sky_location: Optional[SkyLocation] = None
    wave_parameters: Optional[WaveParameters] = None
    status: PredictionStatus = PredictionStatus.PENDING
    sha256_hash: Optional[str] = None
    matched_event_id: Optional[str] = None
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not 0 <= self.confidence <= 1:
            raise ValueError(f"Confidence must be between 0 and 1, got {self.confidence}")
        if self.predicted_event_end < self.predicted_event_start:
            raise ValueError("Event end time cannot be before start time")
        valid_frameworks = {"CIA", "SIA", "HIA", "IIA", "Experimental"}
        if self.framework not in valid_frameworks:
            raise ValueError(f"Framework must be one of {valid_frameworks}, got {self.framework}")

    def is_within_window(self, event_time: datetime) -> bool:
        """Check if an event time falls within the prediction window."""
        return self.predicted_event_start <= event_time <= self.predicted_event_end

    def time_window_hours(self) -> float:
        """Return the prediction window duration in hours."""
        delta = self.predicted_event_end - self.predicted_event_start
        return delta.total_seconds() / 3600

    def mark_validated(self, event_id: str) -> None:
        """Mark this prediction as validated with a matching event."""
        self.status = PredictionStatus.VALIDATED
        self.matched_event_id = event_id

    def mark_invalidated(self) -> None:
        """Mark this prediction as invalidated (no matching event found)."""
        self.status = PredictionStatus.INVALIDATED
