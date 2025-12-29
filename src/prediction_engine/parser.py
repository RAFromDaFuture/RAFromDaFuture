"""
Parser for reading prediction files in various formats.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .prediction import (
    Prediction,
    PredictionType,
    PredictionStatus,
    SkyLocation,
    WaveParameters,
)


class ParseError(Exception):
    """Raised when a prediction file cannot be parsed."""
    pass


class PredictionParser:
    """
    Parses prediction files from the repository into Prediction objects.

    Supports multiple file formats:
    - Markdown (.md)
    - Plain text
    - Structured prediction format (PIN_*)
    """

    # Patterns for extracting prediction data
    PATTERNS = {
        "frequency": re.compile(r"frequency[:\s]+([0-9.]+)\s*(?:hz)?", re.IGNORECASE),
        "amplitude": re.compile(r"amplitude[:\s]+([0-9.e\-+]+)", re.IGNORECASE),
        "chirp_mass": re.compile(r"chirp\s*mass[:\s]+([0-9.]+)\s*(?:solar\s*masses?|m☉)?", re.IGNORECASE),
        "distance": re.compile(r"distance[:\s]+([0-9.]+)\s*(?:mpc)?", re.IGNORECASE),
        "snr": re.compile(r"snr[:\s]+([0-9.]+)", re.IGNORECASE),
        "confidence": re.compile(r"confidence[:\s]+([0-9.]+)%?", re.IGNORECASE),
        "right_ascension": re.compile(r"(?:ra|right\s*ascension)[:\s]+([0-9.]+)", re.IGNORECASE),
        "declination": re.compile(r"(?:dec|declination)[:\s]+([0-9.\-+]+)", re.IGNORECASE),
        "framework": re.compile(r"framework[:\s]+(CIA|SIA|HIA|IIA|Experimental)", re.IGNORECASE),
        "date": re.compile(r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})"),
        "prediction_id": re.compile(r"(?:id|simulation)[:\s#]*([A-Za-z0-9\-_]+)", re.IGNORECASE),
    }

    TYPE_KEYWORDS = {
        PredictionType.GRAVITATIONAL_WAVE: ["gravitational", "gw", "ligo", "merger", "binary"],
        PredictionType.GAMMA_RAY: ["gamma", "grb", "burst"],
        PredictionType.SOLAR_FLARE: ["solar", "flare", "cme", "sun"],
        PredictionType.TECTONIC: ["tectonic", "earthquake", "seismic", "quake"],
        PredictionType.BLACK_HOLE: ["black hole", "blackhole", "event horizon"],
        PredictionType.TSUNAMI: ["tsunami", "tidal wave"],
    }

    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize the parser.

        Args:
            base_path: Base path for resolving relative file paths.
        """
        self.base_path = base_path or Path.cwd()

    def parse_file(self, file_path: Path | str) -> Prediction:
        """
        Parse a prediction file and return a Prediction object.

        Args:
            file_path: Path to the prediction file.

        Returns:
            Parsed Prediction object.

        Raises:
            ParseError: If the file cannot be parsed.
            FileNotFoundError: If the file does not exist.
        """
        path = Path(file_path)
        if not path.is_absolute():
            path = self.base_path / path

        if not path.exists():
            raise FileNotFoundError(f"Prediction file not found: {path}")

        content = path.read_text(encoding="utf-8", errors="replace")
        return self.parse_content(content, source_file=str(path))

    def parse_content(self, content: str, source_file: str = "unknown") -> Prediction:
        """
        Parse prediction content from a string.

        Args:
            content: The raw content to parse.
            source_file: Source file name for error messages.

        Returns:
            Parsed Prediction object.

        Raises:
            ParseError: If the content cannot be parsed.
        """
        if not content.strip():
            raise ParseError(f"Empty prediction content in {source_file}")

        # Extract basic fields
        prediction_id = self._extract_pattern("prediction_id", content) or self._generate_id(source_file)
        framework = self._extract_pattern("framework", content) or "Experimental"
        prediction_type = self._infer_prediction_type(content)

        # Extract confidence
        confidence_str = self._extract_pattern("confidence", content)
        confidence = float(confidence_str) / 100 if confidence_str else 0.5
        if confidence > 1:
            confidence = confidence / 100  # Handle percentages > 100 typos

        # Extract wave parameters if applicable
        wave_params = None
        if prediction_type == PredictionType.GRAVITATIONAL_WAVE:
            wave_params = self._extract_wave_parameters(content)

        # Extract sky location
        sky_location = self._extract_sky_location(content)

        # Extract dates
        dates = self.PATTERNS["date"].findall(content)
        now = datetime.now()

        if dates:
            try:
                event_date = self._parse_date(dates[0])
            except ValueError:
                event_date = now
        else:
            event_date = now

        # Create prediction with 24-hour default window
        from datetime import timedelta

        return Prediction(
            id=prediction_id,
            prediction_type=prediction_type,
            created_at=now,
            predicted_event_start=event_date,
            predicted_event_end=event_date + timedelta(hours=24),
            framework=framework.upper() if framework != "Experimental" else framework,
            confidence=min(max(confidence, 0.0), 1.0),
            description=self._extract_description(content),
            sky_location=sky_location,
            wave_parameters=wave_params,
            status=PredictionStatus.PENDING,
            tags=self._extract_tags(content),
        )

    def _extract_pattern(self, pattern_name: str, content: str) -> Optional[str]:
        """Extract a value using a named pattern."""
        pattern = self.PATTERNS.get(pattern_name)
        if pattern:
            match = pattern.search(content)
            if match:
                return match.group(1)
        return None

    def _infer_prediction_type(self, content: str) -> PredictionType:
        """Infer the prediction type from content keywords."""
        content_lower = content.lower()
        for pred_type, keywords in self.TYPE_KEYWORDS.items():
            if any(keyword in content_lower for keyword in keywords):
                return pred_type
        return PredictionType.GRAVITATIONAL_WAVE  # Default

    def _extract_wave_parameters(self, content: str) -> Optional[WaveParameters]:
        """Extract gravitational wave parameters from content."""
        frequency = self._extract_pattern("frequency", content)
        amplitude = self._extract_pattern("amplitude", content)

        if not frequency and not amplitude:
            return None

        try:
            return WaveParameters(
                frequency_hz=float(frequency) if frequency else 100.0,
                amplitude=float(amplitude) if amplitude else 1e-21,
                chirp_mass=self._safe_float(self._extract_pattern("chirp_mass", content)),
                distance_mpc=self._safe_float(self._extract_pattern("distance", content)),
                snr=self._safe_float(self._extract_pattern("snr", content)),
            )
        except ValueError:
            return None

    def _extract_sky_location(self, content: str) -> Optional[SkyLocation]:
        """Extract sky location from content."""
        ra = self._extract_pattern("right_ascension", content)
        dec = self._extract_pattern("declination", content)

        if not ra or not dec:
            return None

        try:
            return SkyLocation(
                right_ascension=float(ra),
                declination=float(dec),
            )
        except ValueError:
            return None

    def _extract_description(self, content: str) -> str:
        """Extract a description from the content."""
        lines = content.strip().split("\n")
        # Use first non-empty, non-header line as description
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#") and len(line) > 10:
                return line[:200]  # Limit description length
        return "No description available"

    def _extract_tags(self, content: str) -> list[str]:
        """Extract tags/hashtags from content."""
        tags = re.findall(r"#(\w+)", content)
        return list(set(tags))[:10]  # Limit to 10 unique tags

    def _parse_date(self, date_str: str) -> datetime:
        """Parse a date string in various formats."""
        formats = ["%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%m-%d-%y", "%Y-%m-%d"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse date: {date_str}")

    def _generate_id(self, source: str) -> str:
        """Generate a prediction ID from the source file name."""
        path = Path(source)
        return f"PRED-{path.stem}"

    @staticmethod
    def _safe_float(value: Optional[str]) -> Optional[float]:
        """Safely convert a string to float."""
        if value is None:
            return None
        try:
            return float(value)
        except ValueError:
            return None
