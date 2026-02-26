"""Tests for overlay configuration module."""

import json
import tempfile
from pathlib import Path

import pytest

from d2lut.overlay.config import (
    OverlayConfig,
    OCRConfig,
    OverlayDisplayConfig,
    PricingConfig,
    RulesConfig,
    load_config,
    create_default_config,
)


def test_default_config_creation():
    """Test creating default configuration."""
    config = OverlayConfig()
    
    assert config.ocr.engine == "easyocr"
    assert config.ocr.confidence_threshold == 0.7
    assert config.overlay.enabled is True
    assert config.pricing.min_samples == 3
    assert config.rules.lld_enabled is True


def test_config_validation_success():
    """Test configuration validation with valid config."""
    config = OverlayConfig()
    errors = config.validate()
    
    assert len(errors) == 0


def test_config_validation_invalid_ocr_engine():
    """Test configuration validation with invalid OCR engine."""
    config = OverlayConfig()
    config.ocr.engine = "invalid_engine"
    errors = config.validate()
    
    assert len(errors) > 0
    assert any("Invalid OCR engine" in e for e in errors)


def test_config_validation_invalid_confidence_threshold():
    """Test configuration validation with invalid confidence threshold."""
    config = OverlayConfig()
    config.ocr.confidence_threshold = 1.5
    errors = config.validate()
    
    assert len(errors) > 0
    assert any("confidence_threshold must be between 0.0 and 1.0" in e for e in errors)


def test_config_validation_invalid_update_interval():
    """Test configuration validation with invalid update interval."""
    config = OverlayConfig()
    config.overlay.update_interval_ms = 50
    errors = config.validate()
    
    assert len(errors) > 0
    assert any("update_interval_ms must be >= 100ms" in e for e in errors)


def test_config_validation_invalid_color_thresholds():
    """Test configuration validation with invalid color thresholds."""
    config = OverlayConfig()
    config.overlay.color_thresholds = {"low": 10000, "medium": 1000}
    errors = config.validate()
    
    assert len(errors) > 0
    assert any("'low' must be less than 'medium'" in e for e in errors)


def test_config_validation_invalid_min_samples():
    """Test configuration validation with invalid min_samples."""
    config = OverlayConfig()
    config.pricing.min_samples = 0
    errors = config.validate()
    
    assert len(errors) > 0
    assert any("min_samples must be >= 1" in e for e in errors)


def test_config_to_dict():
    """Test converting configuration to dictionary."""
    config = OverlayConfig()
    data = config.to_dict()
    
    assert "ocr" in data
    assert "overlay" in data
    assert "pricing" in data
    assert "rules" in data
    assert data["ocr"]["engine"] == "easyocr"


def test_config_from_dict():
    """Test creating configuration from dictionary."""
    data = {
        "ocr": {
            "engine": "pytesseract",
            "confidence_threshold": 0.8
        },
        "overlay": {
            "enabled": False
        }
    }
    
    config = OverlayConfig.from_dict(data)
    
    assert config.ocr.engine == "pytesseract"
    assert config.ocr.confidence_threshold == 0.8
    assert config.overlay.enabled is False


def test_config_json_roundtrip():
    """Test saving and loading configuration from JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "overlay_config.json"
        
        # Create and save config
        original_config = OverlayConfig()
        original_config.ocr.engine = "pytesseract"
        original_config.overlay.enabled = False
        original_config.to_json(config_path)
        
        # Load config
        loaded_config = OverlayConfig.from_json(config_path)
        
        assert loaded_config.ocr.engine == "pytesseract"
        assert loaded_config.overlay.enabled is False


def test_load_config_with_path():
    """Test loading configuration with path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "overlay_config.json"
        
        # Create config file
        config_data = {
            "ocr": {"engine": "easyocr"},
            "overlay": {"enabled": True},
            "pricing": {"min_samples": 5},
            "rules": {"lld_enabled": False}
        }
        
        with open(config_path, "w") as f:
            json.dump(config_data, f)
        
        # Load config
        config = load_config(config_path)
        
        assert config.ocr.engine == "easyocr"
        assert config.pricing.min_samples == 5
        assert config.rules.lld_enabled is False


def test_load_config_without_path():
    """Test loading configuration without path returns default."""
    config = load_config(None)
    
    assert isinstance(config, OverlayConfig)
    assert config.ocr.engine == "easyocr"


def test_load_config_nonexistent_file():
    """Test loading configuration from nonexistent file raises error."""
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/path/config.json")


def test_load_config_invalid_validation():
    """Test loading configuration with validation errors raises ValueError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "overlay_config.json"
        
        # Create invalid config file
        config_data = {
            "ocr": {"engine": "invalid_engine"},
        }
        
        with open(config_path, "w") as f:
            json.dump(config_data, f)
        
        # Load config should raise ValueError
        with pytest.raises(ValueError, match="Configuration validation failed"):
            load_config(config_path)


def test_create_default_config():
    """Test creating default configuration file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "overlay_config.json"
        
        config = create_default_config(config_path)
        
        assert config_path.exists()
        assert isinstance(config, OverlayConfig)
        
        # Verify file content
        with open(config_path, "r") as f:
            data = json.load(f)
        
        assert "ocr" in data
        assert "overlay" in data
        assert "pricing" in data
        assert "rules" in data
