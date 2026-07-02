"""Smoke tests for the training pipeline (no long training)."""
import pytest
from pathlib import Path


class TestTrainingPipelineSmoke:
    def test_import_train_script(self):
        """The training script can be imported as a module."""
        import scripts.train_phase1  # noqa: F401

    def test_create_training_pipeline_config(self, tmp_path):
        """TrainingPipeline initializes from config dict."""
        from scripts.train_phase1 import TrainingPipeline
        config = {
            "run": {"output_dir": str(tmp_path / "run"), "seed": 42},
            "ppo": {"learning_rate": 3e-4, "n_steps": 128, "batch_size": 64,
                    "n_epochs": 3, "gamma": 0.99, "gae_lambda": 0.95,
                    "clip_range": 0.2, "ent_coef": 0.01, "vf_coef": 0.5,
                    "max_grad_norm": 0.5},
            "network": {"features_dim": 256},
            "phases": {"1.1": {"min_steps": 100, "max_steps": 200},
                       "1.2": {"min_steps": 100, "max_steps": 200},
                       "1.3": {"min_steps": 100, "max_steps": 200}},
            "evaluation": {"interval": 100, "episodes": 1, "video_episodes": 0,
                           "deterministic": True},
            "composite_score": {
                "phase_1_1": {"survival_rate": 1.0},
                "phase_1_2": {"survival_rate": 1.0},
                "phase_1_3": {"survival_rate": 1.0},
            },
            "progression": {"composite_threshold": 0.0, "patience": 1},
            "checkpoint": {"interval": 200},
            "logging": {"heartbeat_seconds": 3600},
            "device": "cpu",
        }
        pipeline = TrainingPipeline(config)
        assert pipeline.run_dir.exists()

    def test_smoke_train_one_phase(self, tmp_path):
        """Train for a tiny number of steps in Phase 1.1."""
        from scripts.train_phase1 import TrainingPipeline
        config = {
            "run": {"output_dir": str(tmp_path / "smoke_run"), "seed": 42},
            "ppo": {"learning_rate": 3e-4, "n_steps": 128, "batch_size": 64,
                    "n_epochs": 3, "gamma": 0.99, "gae_lambda": 0.95,
                    "clip_range": 0.2, "ent_coef": 0.01, "vf_coef": 0.5,
                    "max_grad_norm": 0.5},
            "network": {"features_dim": 256},
            "phases": {"1.1": {"min_steps": 10, "max_steps": 50},
                       "1.2": {"min_steps": 10, "max_steps": 50},
                       "1.3": {"min_steps": 10, "max_steps": 50}},
            "evaluation": {"interval": 30, "episodes": 1, "video_episodes": 0,
                           "deterministic": True},
            "composite_score": {
                "phase_1_1": {"survival_rate": 1.0},
                "phase_1_2": {"survival_rate": 1.0},
                "phase_1_3": {"survival_rate": 1.0},
            },
            "progression": {"composite_threshold": 0.0, "patience": 1},
            "checkpoint": {"interval": 50},
            "logging": {"heartbeat_seconds": 3600},
            "device": "cpu",
        }
        pipeline = TrainingPipeline(config)
        pipeline.run()
        # Verify artifacts exist
        assert (pipeline.run_dir / "checkpoints").exists()
        assert (pipeline.run_dir / "logs").exists()
        # Should have at least one event file or log
        log_files = list((pipeline.run_dir / "logs").iterdir())
        assert len(log_files) > 0

    def test_checkpoint_round_trip(self, tmp_path):
        """Checkpoint state round-trips through JSON."""
        from scripts.train_phase1 import TrainingPipeline, save_state, load_state
        config = {
            "run": {"output_dir": str(tmp_path / "checkpoint_test"), "seed": 42},
            "ppo": {"learning_rate": 3e-4, "n_steps": 128, "batch_size": 64,
                    "n_epochs": 3, "gamma": 0.99, "gae_lambda": 0.95,
                    "clip_range": 0.2, "ent_coef": 0.01, "vf_coef": 0.5,
                    "max_grad_norm": 0.5},
            "network": {"features_dim": 256},
            "phases": {"1.1": {"min_steps": 10, "max_steps": 50},
                       "1.2": {"min_steps": 10, "max_steps": 50},
                       "1.3": {"min_steps": 10, "max_steps": 50}},
            "evaluation": {"interval": 100, "episodes": 1, "video_episodes": 0,
                           "deterministic": True},
            "composite_score": {
                "phase_1_1": {"survival_rate": 1.0},
                "phase_1_2": {"survival_rate": 1.0},
                "phase_1_3": {"survival_rate": 1.0},
            },
            "progression": {"composite_threshold": 0.0, "patience": 1},
            "checkpoint": {"interval": 50},
            "logging": {"heartbeat_seconds": 3600},
            "device": "cpu",
        }
        pipeline = TrainingPipeline(config)
        original_state = {
            "current_phase": 1.2,
            "total_timesteps": 5000,
            "phase_timesteps": 3000,
            "best_composite_score": 0.75,
            "patience_counter": 2,
        }
        state_path = pipeline.run_dir / "checkpoints" / "latest_state.json"
        save_state(original_state, str(state_path))
        loaded = load_state(str(state_path))
        assert loaded["current_phase"] == 1.2
        assert loaded["total_timesteps"] == 5000
        assert loaded["best_composite_score"] == 0.75

    def test_resume_nonexistent_dir_raises(self, tmp_path):
        """Resuming from a non-existent directory raises FileNotFoundError."""
        from scripts.train_phase1 import TrainingPipeline
        config = {"run": {"output_dir": str(tmp_path / "resume_test"), "seed": 42},
                  "ppo": {}, "network": {}, "phases": {"1.1": {}, "1.2": {}, "1.3": {}},
                  "evaluation": {}, "composite_score": {"phase_1_1": {}, "phase_1_2": {},
                  "phase_1_3": {}}, "progression": {}, "checkpoint": {}, "logging": {},
                  "device": "cpu"}
        with pytest.raises(FileNotFoundError):
            TrainingPipeline(config, resume_dir=str(tmp_path / "nonexistent_run"))
