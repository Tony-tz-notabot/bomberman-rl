"""Smoke tests for the training pipeline (no long training)."""
import pytest
from pathlib import Path
from stable_baselines3.common.vec_env import VecEnv


def _minimal_config(tmp_path):
    """Helper to create a minimal config dict for pipeline tests."""
    return {
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


class TestVecEnvEdgeCases:
    """Edge cases and backward compatibility for VecEnv (Phase 4)."""

    def test_n_envs_1_backward_compat_full(self, tmp_path):
        """n_envs=1 produces same output as original single-env pipeline."""
        from scripts.train_phase1 import TrainingPipeline

        config = _minimal_config(tmp_path)
        config["run"]["n_envs"] = 1
        config["ppo"]["n_steps"] = 32
        config["phases"]["1.1"]["min_steps"] = 10
        config["phases"]["1.1"]["max_steps"] = 30
        pipeline = TrainingPipeline(config)
        pipeline.run()
        assert (pipeline.run_dir / "checkpoints" / "latest.zip").exists()
        assert (pipeline.run_dir / "logs").exists()

    def test_n_envs_full_training_completes(self, tmp_path):
        """n_envs=2 end-to-end: train, evaluate, checkpoint."""
        from scripts.train_phase1 import TrainingPipeline

        config = _minimal_config(tmp_path)
        config["run"]["n_envs"] = 2
        config["run"]["seed"] = 42
        config["ppo"]["n_steps"] = 32
        config["phases"]["1.1"]["min_steps"] = 10
        config["phases"]["1.1"]["max_steps"] = 30
        config["phases"]["1.2"]["min_steps"] = 10
        config["phases"]["1.2"]["max_steps"] = 30
        config["phases"]["1.3"]["min_steps"] = 10
        config["phases"]["1.3"]["max_steps"] = 30
        pipeline = TrainingPipeline(config)
        pipeline.run()
        assert (pipeline.run_dir / "checkpoints" / "latest.zip").exists()

    def test_config_hash_stable_with_n_envs(self):
        """Config hash is deterministic when n_envs is present."""
        from src.config_loader import compute_config_hash

        cfg1 = {"run": {"n_envs": 8}, "ppo": {"n_steps": 2048}}
        cfg2 = {"run": {"n_envs": 8}, "ppo": {"n_steps": 2048}}
        assert compute_config_hash(cfg1) == compute_config_hash(cfg2)
        # Different n_envs → different hash
        cfg3 = {"run": {"n_envs": 4}, "ppo": {"n_steps": 2048}}
        assert compute_config_hash(cfg1) != compute_config_hash(cfg3)

    def test_n_envs_large_does_not_crash(self):
        """n_envs=8 spawns workers without crashing (Windows spawn overhead)."""
        from scripts.train_phase1 import _build_vec_env

        config = {"run": {"n_envs": 8, "seed": 42}}
        env = _build_vec_env(1.1, config, 42)
        assert env.num_envs == 8
        obs = env.reset()
        assert obs.shape[0] == 8
        env.close()


class TestVecEnvFactory:
    """Tests for vectorized environment factory functions (Phase 2)."""

    def test_patch_env_reset_preserves_phase(self):
        """_patch_env_reset ensures reset without options preserves phase."""
        from scripts.train_phase1 import _patch_env_reset, _stationary_opponent
        from src.bomberman_env import BombermanEnv
        from rewards.sparse import SparseReward

        env = BombermanEnv(reward_fn=SparseReward(), opponent_fn=_stationary_opponent)
        env = _patch_env_reset(env, phase=1.2)
        # Reset once to set up phase
        env.reset(seed=42, options={"phase": 1.2})
        assert env._phase == 1.2
        # Simulate SB3 reset without options
        obs, info = env.reset(seed=43)
        assert env._phase == 1.2, "Phase should be preserved after optionless reset"

    def test_build_vec_env_n_envs_4(self):
        """_build_vec_env with n_envs=4 returns SubprocVecEnv with 4 envs."""
        from scripts.train_phase1 import _build_vec_env

        config = {"run": {"n_envs": 4, "seed": 42}}
        env = _build_vec_env(1.1, config, 42)
        assert env.num_envs == 4
        env.close()

    def test_build_vec_env_n_envs_1_backward_compat(self):
        """_build_vec_env with n_envs=1 returns non-VecEnv (single env)."""
        from scripts.train_phase1 import _build_vec_env

        config = {"run": {"n_envs": 1, "seed": 42}}
        env = _build_vec_env(1.1, config, 42)
        # Should be a plain env, not a VecEnv
        assert not isinstance(env, VecEnv)
        # Should have the env API
        assert hasattr(env, "reset")
        assert hasattr(env, "step")
        env.close()

    def test_build_vec_env_observations_valid(self):
        """VecEnv observation shape is (n_envs, 11, 19, 9)."""
        from scripts.train_phase1 import _build_vec_env

        config = {"run": {"n_envs": 2, "seed": 42}}
        env = _build_vec_env(1.1, config, 42)
        obs = env.reset()
        assert obs.shape == (2, 11, 19, 9)
        env.close()


class TestVecEnvPipelineIntegration:
    """Integration tests for VecEnv in TrainingPipeline (Phase 3)."""

    def test_pipeline_with_n_envs_2_smoke(self, tmp_path):
        """n_envs=2: create env + model successfully, verify num_envs."""
        from scripts.train_phase1 import TrainingPipeline

        config = _minimal_config(tmp_path)
        config["run"]["n_envs"] = 2
        config["ppo"]["n_steps"] = 64
        pipeline = TrainingPipeline(config)
        try:
            pipeline._setup_phase_env()
            pipeline._create_phase_model()
            assert pipeline.env.num_envs == 2
            assert pipeline.model is not None
        finally:
            if pipeline.env is not None:
                pipeline.env.close()

    def test_pipeline_n_steps_adjusted(self, tmp_path):
        """n_envs=4 → per_env_steps = n_steps // 4."""
        from scripts.train_phase1 import TrainingPipeline

        config = _minimal_config(tmp_path)
        config["run"]["n_envs"] = 4
        config["ppo"]["n_steps"] = 2048
        pipeline = TrainingPipeline(config)
        try:
            pipeline._setup_phase_env()
            pipeline._create_phase_model()
            # n_steps passed to PPO should be divided by n_envs
            expected = 2048 // 4  # = 512
            assert pipeline.model.n_steps == expected, (
                f"Expected n_steps={expected}, got {pipeline.model.n_steps}"
            )
        finally:
            if pipeline.env is not None:
                pipeline.env.close()

    def test_pipeline_vec_advance_phase_works(self, tmp_path):
        """VecEnv mode: phase advancement (model.set_env) works with VecEnv."""
        from scripts.train_phase1 import TrainingPipeline

        config = _minimal_config(tmp_path)
        config["run"]["n_envs"] = 2
        config["ppo"]["n_steps"] = 64
        pipeline = TrainingPipeline(config)
        try:
            pipeline._setup_phase_env()
            pipeline._create_phase_model()
            # Simulate advancing to next phase
            old_env = pipeline.env
            pipeline.current_phase = 1.2
            pipeline._setup_phase_env()  # creates new VecEnv
            pipeline.model.set_env(pipeline.env)
            # Both old and new should be VecEnvs
            assert old_env.num_envs == 2
            assert pipeline.env.num_envs == 2
            assert pipeline.env is not old_env
            old_env.close()
        finally:
            if pipeline.env is not None:
                pipeline.env.close()

    def test_pipeline_vec_evaluate_uses_single_env(self, tmp_path):
        """VecEnv mode: _evaluate creates its own single eval env (not VecEnv).

        This would fail if evaluate_phase receives a VecEnv because it
        accesses env.engine.grid directly.
        """
        from scripts.train_phase1 import TrainingPipeline

        config = _minimal_config(tmp_path)
        config["run"]["n_envs"] = 2
        config["ppo"]["n_steps"] = 64
        pipeline = TrainingPipeline(config)
        try:
            pipeline._setup_phase_env()
            pipeline._create_phase_model()
            metrics = pipeline._evaluate()
            assert metrics is not None
            assert "mean_eval_reward" in metrics
            assert "composite_score" in metrics
        finally:
            if pipeline.env is not None:
                pipeline.env.close()
