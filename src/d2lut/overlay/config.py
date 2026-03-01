"""Overlay configuration module for d2lut overlay system."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class OCRConfig:
    """OCR engine configuration."""
    engine: str = "easyocr"
    confidence_threshold: float = 0.7
    preprocess: dict[str, Any] = field(default_factory=lambda: {
        "contrast_enhance": True,
        "denoise": True,
        "resize_factor": 2.0
    })


@dataclass
class OverlayDisplayConfig:
    """Overlay display configuration."""
    enabled: bool = True
    color_thresholds: dict[str, int] = field(default_factory=lambda: {
        "low": 1000,
        "medium": 10000
    })
    update_interval_ms: int = 1000
    max_cache_age_seconds: int = 300


@dataclass
class PricingConfig:
    """Pricing engine configuration."""
    min_samples: int = 3
    confidence_levels: dict[str, float] = field(default_factory=lambda: {
        "low": 0.5,
        "medium": 0.7,
        "high": 0.9
    })


@dataclass
class RulesConfig:
    """Rule engine configuration."""
    lld_enabled: bool = True
    craft_enabled: bool = True
    affix_adjustments: bool = True


@dataclass
class OverlayConfig:
    """Complete overlay system configuration."""
    ocr: OCRConfig = field(default_factory=OCRConfig)
    overlay: OverlayDisplayConfig = field(default_factory=OverlayDisplayConfig)
    pricing: PricingConfig = field(default_factory=PricingConfig)
    rules: RulesConfig = field(default_factory=RulesConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OverlayConfig":
        """Create configuration from dictionary."""
        return cls(
            ocr=OCRConfig(**data.get("ocr", {})),
            overlay=OverlayDisplayConfig(**data.get("overlay", {})),
            pricing=PricingConfig(**data.get("pricing", {})),
            rules=RulesConfig(**data.get("rules", {}))
        )

    @classmethod
    def from_json(cls, path: Path | str) -> "OverlayConfig":
        """Load configuration from JSON file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return cls.from_dict(data)

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "ocr": {
                "engine": self.ocr.engine,
                "confidence_threshold": self.ocr.confidence_threshold,
                "preprocess": self.ocr.preprocess
            },
            "overlay": {
                "enabled": self.overlay.enabled,
                "color_thresholds": self.overlay.color_thresholds,
                "update_interval_ms": self.overlay.update_interval_ms,
                "max_cache_age_seconds": self.overlay.max_cache_age_seconds
            },
            "pricing": {
                "min_samples": self.pricing.min_samples,
                "confidence_levels": self.pricing.confidence_levels
            },
            "rules": {
                "lld_enabled": self.rules.lld_enabled,
                "craft_enabled": self.rules.craft_enabled,
                "affix_adjustments": self.rules.affix_adjustments
            }
        }

    def to_json(self, path: Path | str, indent: int = 2) -> None:
        """Save configuration to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=indent)

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []
        
        # Validate OCR config
        if self.ocr.engine not in ["easyocr", "pytesseract"]:
            errors.append(f"Invalid OCR engine: {self.ocr.engine}. Must be 'easyocr' or 'pytesseract'")
        
        if not 0.0 <= self.ocr.confidence_threshold <= 1.0:
            errors.append(f"OCR confidence_threshold must be between 0.0 and 1.0, got {self.ocr.confidence_threshold}")
        
        # Validate overlay config
        if self.overlay.update_interval_ms < 100:
            errors.append(f"Overlay update_interval_ms must be >= 100ms, got {self.overlay.update_interval_ms}")
        
        if self.overlay.max_cache_age_seconds < 0:
            errors.append(f"Overlay max_cache_age_seconds must be >= 0, got {self.overlay.max_cache_age_seconds}")
        
        # Validate color thresholds
        if "low" not in self.overlay.color_thresholds or "medium" not in self.overlay.color_thresholds:
            errors.append("Overlay color_thresholds must contain 'low' and 'medium' keys")
        elif self.overlay.color_thresholds["low"] >= self.overlay.color_thresholds["medium"]:
            errors.append("Overlay color_thresholds 'low' must be less than 'medium'")
        
        # Validate pricing config
        if self.pricing.min_samples < 1:
            errors.append(f"Pricing min_samples must be >= 1, got {self.pricing.min_samples}")
        
        # Validate confidence levels
        required_levels = ["low", "medium", "high"]
        for level in required_levels:
            if level not in self.pricing.confidence_levels:
                errors.append(f"Pricing confidence_levels must contain '{level}' key")
            elif not 0.0 <= self.pricing.confidence_levels[level] <= 1.0:
                errors.append(f"Pricing confidence_levels['{level}'] must be between 0.0 and 1.0")
        
        if len(self.pricing.confidence_levels) == 3:
            if not (self.pricing.confidence_levels["low"] < 
                    self.pricing.confidence_levels["medium"] < 
                    self.pricing.confidence_levels["high"]):
                errors.append("Pricing confidence_levels must be in ascending order: low < medium < high")
        
        return errors


def load_config(path: Path | str | None = None) -> OverlayConfig:
    """
    Load overlay configuration from file or return default.
    
    Args:
        path: Path to configuration file. If None, returns default config.
    
    Returns:
        OverlayConfig instance
    
    Raises:
        FileNotFoundError: If path is provided but file doesn't exist
        ValueError: If configuration validation fails
    """
    if path is None:
        return OverlayConfig()
    
    config = OverlayConfig.from_json(path)
    errors = config.validate()
    
    if errors:
        raise ValueError(f"Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors))
    
    return config


def create_default_config(path: Path | str) -> OverlayConfig:
    """
    Create and save a default configuration file.
    
    Args:
        path: Path where to save the configuration file
    
    Returns:
        Default OverlayConfig instance
    """
    config = OverlayConfig()
    config.to_json(path)
    return config
