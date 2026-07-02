"""Tests for config loader."""
import pytest
from src.config_loader import load_config, compute_config_hash

class TestConfigLoader:
    def test_load_valid_config(self, tmp_path):
        """Valid YAML loads successfully with all required keys."""
        yaml_content = """
run:
  output_dir: runs/test
  seed: 42
ppo:
  learning_rate: 3.0e-4
  n_steps: 2048
  batch_size: 64
  n_epochs: 10
  gamma: 0.99
  gae_lambda: 0.95
  clip_range: 0.2
  ent_coef: 0.01
  vf_coef: 0.5
  max_grad_norm: 0.5
network:
  features_dim: 256
phases:
  "1.1":
    min_steps: 100000
    max_steps: 500000
  "1.2":
    min_steps: 100000
    max_steps: 500000
  "1.3":
    min_steps: 100000
    max_steps: 500000
evaluation:
  interval: 25000
  episodes: 10
  video_episodes: 3
  deterministic: true
composite_score:
  phase_1_1:
    survival_rate: 0.3
    normalized_approach: 0.3
    low_illegal_action_rate: 0.2
    low_final_distance: 0.2
  phase_1_2:
    survival_rate: 0.2
    normalized_approach: 0.2
    bomb_efficiency: 0.2
    brick_destroy_rate: 0.2
    low_illegal_action_rate: 0.1
    kill_rate: 0.1
  phase_1_3:
    survival_rate: 0.15
    normalized_approach: 0.15
    bomb_efficiency: 0.15
    buff_pickup_rate: 0.25
    low_illegal_action_rate: 0.1
    kill_rate: 0.1
    low_final_distance: 0.1
progression:
  composite_threshold: 0.5
  patience: 5
checkpoint:
  interval: 50000
logging:
  heartbeat_seconds: 60
device: auto
"""
        config_path = tmp_path / "test_config.yaml"
        config_path.write_text(yaml_content)
        cfg = load_config(str(config_path))
        assert cfg["ppo"]["learning_rate"] == 3e-4
        assert cfg["network"]["features_dim"] == 256
        assert cfg["phases"]["1.1"]["min_steps"] == 100000
        assert cfg["evaluation"]["interval"] == 25000

    def test_missing_required_key_raises(self, tmp_path):
        """Missing a required top-level key raises ValueError."""
        yaml_content = "run:\n  output_dir: runs/test\nppo:\n  learning_rate: 3.0e-4\n"
        config_path = tmp_path / "bad_config.yaml"
        config_path.write_text(yaml_content)
        with pytest.raises(ValueError, match="Missing required config key"):
            load_config(str(config_path))

    def test_load_default_file(self):
        """Loading the actual default config file succeeds."""
        cfg = load_config("configs/phase1_fast.yaml")
        assert "ppo" in cfg
        assert "phases" in cfg
        assert "evaluation" in cfg

    def test_config_hash_deterministic(self):
        """Same config dict produces same hash."""
        cfg1 = {"a": 1, "b": {"c": 2}}
        cfg2 = {"a": 1, "b": {"c": 2}}
        assert compute_config_hash(cfg1) == compute_config_hash(cfg2)

    def test_config_hash_changes_on_diff(self):
        """Different config produces different hash."""
        cfg1 = {"a": 1}
        cfg2 = {"a": 2}
        assert compute_config_hash(cfg1) != compute_config_hash(cfg2)
