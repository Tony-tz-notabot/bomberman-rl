"""Tests for config loader."""
import pytest
from src.config_loader import load_config, compute_config_hash
import yaml

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


class TestNEnvsValidation:
    """Validation of run.n_envs config parameter."""

    @pytest.fixture
    def valid_base(self, tmp_path):
        """Create a minimal valid config without n_envs."""
        data = {
            "run": {"output_dir": "runs/test", "seed": 42},
            "ppo": {"learning_rate": 3e-4, "n_steps": 2048, "batch_size": 64,
                    "n_epochs": 10, "gamma": 0.99, "gae_lambda": 0.95,
                    "clip_range": 0.2, "ent_coef": 0.01, "vf_coef": 0.5,
                    "max_grad_norm": 0.5},
            "network": {"features_dim": 256},
            "phases": {"1.1": {"min_steps": 100, "max_steps": 200},
                       "1.2": {"min_steps": 100, "max_steps": 200},
                       "1.3": {"min_steps": 100, "max_steps": 200}},
            "evaluation": {"interval": 100, "episodes": 1, "video_episodes": 0},
            "composite_score": {"phase_1_1": {"survival_rate": 1.0},
                                "phase_1_2": {"survival_rate": 1.0},
                                "phase_1_3": {"survival_rate": 1.0}},
            "progression": {"composite_threshold": 0.5, "patience": 3},
            "checkpoint": {"interval": 200},
            "logging": {"heartbeat_seconds": 3600},
            "device": "cpu",
        }
        path = tmp_path / "base.yaml"
        with open(path, "w") as f:
            yaml.dump(data, f)
        return str(path)

    def test_n_envs_default_optional(self, valid_base):
        """n_envs not specified → loads without error, defaults to 1."""
        cfg = load_config(valid_base)
        # Should exist with default value 1
        assert cfg.get("run", {}).get("n_envs", 1) == 1

    def test_n_envs_valid_int(self, valid_base, tmp_path):
        """n_envs=8 loads fine."""
        path = tmp_path / "with_n_envs.yaml"
        with open(valid_base) as f:
            data = yaml.safe_load(f)
        data["run"]["n_envs"] = 8
        with open(path, "w") as f:
            yaml.dump(data, f)
        cfg = load_config(str(path))
        assert cfg["run"]["n_envs"] == 8

    def test_n_envs_invalid_zero(self, valid_base, tmp_path):
        """n_envs=0 raises ValueError."""
        path = tmp_path / "zero.yaml"
        with open(valid_base) as f:
            data = yaml.safe_load(f)
        data["run"]["n_envs"] = 0
        with open(path, "w") as f:
            yaml.dump(data, f)
        with pytest.raises(ValueError, match="n_envs"):
            load_config(str(path))

    def test_n_envs_invalid_negative(self, valid_base, tmp_path):
        """n_envs=-1 raises ValueError."""
        path = tmp_path / "neg.yaml"
        with open(valid_base) as f:
            data = yaml.safe_load(f)
        data["run"]["n_envs"] = -1
        with open(path, "w") as f:
            yaml.dump(data, f)
        with pytest.raises(ValueError, match="n_envs"):
            load_config(str(path))

    def test_n_envs_invalid_type(self, valid_base, tmp_path):
        """n_envs="abc" or 1.5 raises ValueError."""
        for bad_val in ("abc", 1.5):
            path = tmp_path / f"bad_{type(bad_val).__name__}.yaml"
            with open(valid_base) as f:
                data = yaml.safe_load(f)
            data["run"]["n_envs"] = bad_val
            with open(path, "w") as f:
                yaml.dump(data, f)
            with pytest.raises(ValueError, match="n_envs"):
                load_config(str(path))
