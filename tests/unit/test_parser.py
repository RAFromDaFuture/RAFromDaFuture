"""
Unit tests for the prediction parser module.
"""

import pytest
from pathlib import Path
from datetime import datetime

from src.prediction_engine.parser import PredictionParser, ParseError
from src.prediction_engine.prediction import PredictionType


class TestPredictionParser:
    """Tests for PredictionParser class."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return PredictionParser()

    def test_parse_gravitational_wave_content(self, parser):
        """Test parsing gravitational wave prediction content."""
        content = """
        # Gravitational Wave Prediction
        Framework: CIA
        Confidence: 85%
        Frequency: 150 Hz
        Amplitude: 1e-21
        Date: 06/15/2025

        This is a prediction for a binary merger event.
        """
        prediction = parser.parse_content(content, "test.md")

        assert prediction.prediction_type == PredictionType.GRAVITATIONAL_WAVE
        assert prediction.framework == "CIA"
        assert prediction.confidence == 0.85
        assert prediction.wave_parameters is not None
        assert prediction.wave_parameters.frequency_hz == 150.0
        assert prediction.wave_parameters.amplitude == 1e-21

    def test_parse_gamma_ray_content(self, parser):
        """Test parsing gamma ray burst prediction."""
        content = """
        # Gamma Ray Burst Prediction
        Framework: SIA
        Confidence: 70%

        Predicting a GRB event in the southern sky.
        """
        prediction = parser.parse_content(content, "grb.md")

        assert prediction.prediction_type == PredictionType.GAMMA_RAY
        assert prediction.framework == "SIA"
        assert prediction.confidence == 0.70

    def test_parse_solar_flare_content(self, parser):
        """Test parsing solar flare prediction."""
        content = """
        Solar Flare Prediction - X-class event expected
        Framework: HIA
        Confidence: 90%
        Date: 07/01/2025
        """
        prediction = parser.parse_content(content, "solar.txt")

        assert prediction.prediction_type == PredictionType.SOLAR_FLARE
        assert prediction.framework == "HIA"
        assert prediction.confidence == 0.90

    def test_parse_tectonic_content(self, parser):
        """Test parsing tectonic/earthquake prediction."""
        content = """
        Earthquake Prediction
        Framework: IIA
        Confidence: 60%
        Seismic activity expected in Pacific region.
        """
        prediction = parser.parse_content(content, "quake.txt")

        assert prediction.prediction_type == PredictionType.TECTONIC
        assert prediction.framework == "IIA"

    def test_parse_with_sky_location(self, parser):
        """Test parsing content with sky location."""
        content = """
        # GW Prediction
        Framework: CIA
        RA: 180.5
        Dec: 45.2
        Frequency: 100 Hz
        Amplitude: 5e-22
        """
        prediction = parser.parse_content(content, "loc.md")

        assert prediction.sky_location is not None
        assert prediction.sky_location.right_ascension == 180.5
        assert prediction.sky_location.declination == 45.2

    def test_parse_with_simulation_id(self, parser):
        """Test parsing content with simulation ID."""
        content = """
        Simulation #28
        Framework: CIA
        LIGO gravitational wave prediction
        """
        prediction = parser.parse_content(content, "sim.md")

        assert "28" in prediction.id

    def test_parse_empty_content_raises_error(self, parser):
        """Test that empty content raises ParseError."""
        with pytest.raises(ParseError, match="Empty prediction content"):
            parser.parse_content("", "empty.md")

    def test_parse_whitespace_only_raises_error(self, parser):
        """Test that whitespace-only content raises ParseError."""
        with pytest.raises(ParseError, match="Empty prediction content"):
            parser.parse_content("   \n\t  \n  ", "whitespace.md")

    def test_parse_missing_framework_defaults_to_experimental(self, parser):
        """Test that missing framework defaults to Experimental."""
        content = "This is a gravitational wave prediction without framework specified."
        prediction = parser.parse_content(content, "no_framework.md")

        assert prediction.framework == "Experimental"

    def test_parse_missing_confidence_defaults_to_0_5(self, parser):
        """Test that missing confidence defaults to 0.5."""
        content = """
        Framework: CIA
        Gravitational wave prediction
        """
        prediction = parser.parse_content(content, "no_conf.md")

        assert prediction.confidence == 0.5

    def test_parse_date_formats(self, parser):
        """Test parsing various date formats."""
        test_cases = [
            ("Date: 06/15/2025", 6, 15, 2025),
            ("Date: 12-25-2025", 12, 25, 2025),
            ("Date: 01/01/25", 1, 1, 2025),
        ]

        for date_content, month, day, year in test_cases:
            content = f"""
            Framework: CIA
            {date_content}
            Gravitational wave prediction
            """
            prediction = parser.parse_content(content, "date_test.md")
            assert prediction.predicted_event_start.month == month
            assert prediction.predicted_event_start.day == day

    def test_parse_extracts_tags(self, parser):
        """Test that hashtags are extracted as tags."""
        content = """
        Framework: CIA
        #gravitational #wave #prediction
        Testing tag extraction
        """
        prediction = parser.parse_content(content, "tags.md")

        assert "gravitational" in prediction.tags
        assert "wave" in prediction.tags
        assert "prediction" in prediction.tags

    def test_parse_description_extraction(self, parser):
        """Test that description is extracted from content."""
        content = """
        # Header
        Framework: CIA
        This is the actual description of the prediction event.
        """
        prediction = parser.parse_content(content, "desc.md")

        assert "description of the prediction" in prediction.description

    def test_parse_file_not_found(self, parser):
        """Test that FileNotFoundError is raised for missing files."""
        with pytest.raises(FileNotFoundError):
            parser.parse_file("/nonexistent/path/file.md")

    def test_parse_wave_parameters_partial(self, parser):
        """Test parsing with only frequency specified."""
        content = """
        Framework: CIA
        Frequency: 200 Hz
        Gravitational wave merger
        """
        prediction = parser.parse_content(content, "partial.md")

        assert prediction.wave_parameters is not None
        assert prediction.wave_parameters.frequency_hz == 200.0
        # Amplitude should default
        assert prediction.wave_parameters.amplitude == 1e-21

    def test_parse_percentage_confidence_variations(self, parser):
        """Test different confidence format variations."""
        test_cases = [
            ("Confidence: 75%", 0.75),
            ("Confidence: 0.80", 0.80),
            ("confidence: 65", 0.65),
        ]

        for conf_str, expected in test_cases:
            content = f"""
            Framework: CIA
            {conf_str}
            Test prediction
            """
            prediction = parser.parse_content(content, "conf_test.md")
            assert abs(prediction.confidence - expected) < 0.01

    def test_generate_id_from_filename(self, parser):
        """Test ID generation from source filename."""
        content = "Framework: CIA\nSimple prediction"
        prediction = parser.parse_content(content, "PIN_GWForecast_060925.md")

        assert "PIN_GWForecast_060925" in prediction.id

    def test_infer_type_with_multiple_keywords(self, parser):
        """Test type inference when multiple keywords are present."""
        # Gravitational wave should take precedence when mentioned first
        content = """
        Framework: CIA
        This predicts a LIGO binary merger event.
        Solar activity may affect detection.
        """
        prediction = parser.parse_content(content, "multi.md")

        assert prediction.prediction_type == PredictionType.GRAVITATIONAL_WAVE

    def test_default_prediction_type(self, parser):
        """Test that default type is gravitational wave."""
        content = """
        Framework: CIA
        Generic prediction with no type keywords.
        """
        prediction = parser.parse_content(content, "generic.md")

        assert prediction.prediction_type == PredictionType.GRAVITATIONAL_WAVE

    def test_chirp_mass_extraction(self, parser):
        """Test extraction of chirp mass from content."""
        content = """
        Framework: CIA
        Frequency: 100 Hz
        Amplitude: 1e-21
        Chirp Mass: 30 solar masses
        """
        prediction = parser.parse_content(content, "chirp.md")

        assert prediction.wave_parameters is not None
        assert prediction.wave_parameters.chirp_mass == 30.0

    def test_snr_extraction(self, parser):
        """Test extraction of SNR from content."""
        content = """
        Framework: CIA
        Frequency: 100 Hz
        Amplitude: 1e-21
        SNR: 25
        """
        prediction = parser.parse_content(content, "snr.md")

        assert prediction.wave_parameters is not None
        assert prediction.wave_parameters.snr == 25.0
