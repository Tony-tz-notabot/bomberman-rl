"""YAML config loader with validation for the Phase 1 training pipeline."""
import hashlib
import json
from pathlib import Path
from typing import Any, Dict


_REQUIRED_KEYS = [
    "run", "ppo", "network", "phases", "evaluation",
    "composite_score", "progression", "checkpoint", "logging",
]


def load_config(path: str) -> Dict[str, Any]:
    """Load and validate a YAML training config file.

    Returns:
        Nested dict with all config values.

    Raises:
        ValueError: If required top-level keys are missing.
        FileNotFoundError: If the config file does not exist.
    """
    import yaml
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    if config is None:
        raise ValueError(f"Empty config file: {path}")

    for key in _REQUIRED_KEYS:
        if key not in config:
            raise ValueError(f"Missing required config key: '{key}' in {path}")

    # Validate phase keys are numeric strings "1.1", "1.2", "1.3"
    for phase_key in ("1.1", "1.2", "1.3"):
        if phase_key not in config["phases"]:
            raise ValueError(f"Missing phase config for phase {phase_key}")

    # Validate composite_score has all three phases
    for score_key in ("phase_1_1", "phase_1_2", "phase_1_3"):
        if score_key not in config["composite_score"]:
            raise ValueError(f"Missing composite_score config for {score_key}")

    return config


def compute_config_hash(config: Dict[str, Any]) -> str:
    """Deterministic SHA256 hex digest of a config dict."""
    raw = json.dumps(config, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
