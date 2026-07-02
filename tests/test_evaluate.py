"""Tests for evaluation module."""
import numpy as np
import pytest
from src.evaluate import (
    evaluate_phase,
    compute_composite_score,
    format_metrics,
)


class TestComputeCompositeScore:
    def test_perfect_survival_rate(self):
        """100% survival + approach = 1.0 composite on Phase 1.1 weights."""
        weights = {"survival_rate": 1.0, "normalized_approach": 0.0}
        metrics = {"survival_rate": 1.0, "normalized_approach": 0.0}
        score = compute_composite_score(metrics, weights)
        assert score == pytest.approx(1.0)

    def test_zero_survival(self):
        """0% survival = 0.0 composite."""
        weights = {"survival_rate": 1.0}
        metrics = {"survival_rate": 0.0}
        score = compute_composite_score(metrics, weights)
        assert score == pytest.approx(0.0)

    def test_mixed_weights(self):
        """Multiple weighted metrics produce correct average."""
        weights = {"survival_rate": 0.5, "normalized_approach": 0.5}
        metrics = {"survival_rate": 1.0, "normalized_approach": 0.5}
        score = compute_composite_score(metrics, weights)
        assert score == pytest.approx(0.75)

    def test_missing_metric_defaults_to_zero(self):
        """Missing metrics are treated as 0.0 without error."""
        weights = {"survival_rate": 1.0, "missing_metric": 1.0}
        metrics = {"survival_rate": 1.0}
        score = compute_composite_score(metrics, weights)
        assert score == pytest.approx(0.5)

    def test_illegal_action_rate_inverted(self):
        """low_illegal_action_rate = 1 - illegal_rate."""
        weights = {"low_illegal_action_rate": 1.0}
        metrics = {"illegal_action_rate": 0.2}
        score = compute_composite_score(metrics, weights)
        assert score == pytest.approx(0.8)

    def test_final_distance_normalized(self):
        """low_final_distance is normalized by max map distance (11+19=30)."""
        weights = {"low_final_distance": 1.0}
        # Final distance 3 out of max 30 -> normalized = 0.9
        metrics = {"mean_final_distance_to_blue": 3.0}
        score = compute_composite_score(metrics, weights)
        assert score == pytest.approx(0.9)


class TestEvaluatePhase:
    def test_evaluate_short_rollout_returns_dict(self):
        """evaluate_phase with 1 episode returns dict with expected keys."""
        from src.bomberman_env import BombermanEnv
        from rewards.phase1 import Phase1Reward
        from stable_baselines3 import PPO
        from src.feature_extractor import ResCnnFeatureExtractor

        env = BombermanEnv(reward_fn=Phase1Reward({"phase": 1.1}))
        model = PPO(
            "CnnPolicy", env, verbose=0,
            policy_kwargs=dict(
                features_extractor_class=ResCnnFeatureExtractor,
                features_extractor_kwargs=dict(features_dim=256),
                net_arch=dict(pi=[128], vf=[256]),
            ),
            n_steps=128, batch_size=64, n_epochs=3,
        )
        config = {
            "composite_score": {
                "phase_1_1": {"survival_rate": 1.0, "normalized_approach": 0.0},
            }
        }
        metrics = evaluate_phase(model, env, config, phase=1.1, num_episodes=1)
        expected_keys = {
            "mean_eval_reward", "survival_rate", "mean_final_distance_to_blue",
            "illegal_action_rate", "mean_bomb_count", "mean_brick_destroy_count",
            "mean_buff_pickup_count", "kill_rate", "mean_episode_length",
            "composite_score", "phase",
        }
        for key in expected_keys:
            assert key in metrics, f"Missing key: {key}"
        env.close()

    def test_evaluate_with_multiple_episodes(self):
        """Multiple evaluation episodes average correctly."""
        from src.bomberman_env import BombermanEnv
        from rewards.phase1 import Phase1Reward
        from stable_baselines3 import PPO
        from src.feature_extractor import ResCnnFeatureExtractor

        env = BombermanEnv(reward_fn=Phase1Reward({"phase": 1.1}))
        model = PPO(
            "CnnPolicy", env, verbose=0,
            policy_kwargs=dict(
                features_extractor_class=ResCnnFeatureExtractor,
                features_extractor_kwargs=dict(features_dim=256),
                net_arch=dict(pi=[128], vf=[256]),
            ),
            n_steps=128, batch_size=64, n_epochs=3,
        )
        config = {
            "composite_score": {
                "phase_1_1": {"survival_rate": 1.0},
            }
        }
        metrics = evaluate_phase(model, env, config, phase=1.1, num_episodes=3)
        assert metrics["num_episodes"] == 3
        assert 0 <= metrics["survival_rate"] <= 1.0
        env.close()

    def test_evaluate_deterministic_seeds_reproducible(self):
        """Same seeds produce same metrics (approximately)."""
        from src.bomberman_env import BombermanEnv
        from rewards.phase1 import Phase1Reward
        from stable_baselines3 import PPO
        from src.feature_extractor import ResCnnFeatureExtractor

        env = BombermanEnv(reward_fn=Phase1Reward({"phase": 1.1}))
        model = PPO(
            "CnnPolicy", env, verbose=0,
            policy_kwargs=dict(
                features_extractor_class=ResCnnFeatureExtractor,
                features_extractor_kwargs=dict(features_dim=256),
                net_arch=dict(pi=[128], vf=[256]),
            ),
            n_steps=128, batch_size=64, n_epochs=3,
        )
        config = {
            "composite_score": {
                "phase_1_1": {"survival_rate": 1.0},
            }
        }
        seeds = [42, 43]
        m1 = evaluate_phase(model, env, config, phase=1.1, num_episodes=2, seeds=seeds)
        m2 = evaluate_phase(model, env, config, phase=1.1, num_episodes=2, seeds=seeds)
        assert m1["mean_eval_reward"] == m2["mean_eval_reward"]
        env.close()


class TestFormatMetrics:
    def test_format_returns_string(self):
        """format_metrics returns a non-empty string."""
        metrics = {"mean_eval_reward": 1.5, "survival_rate": 0.8, "composite_score": 0.65}
        result = format_metrics(metrics)
        assert isinstance(result, str)
        assert "1.5" in result
        assert "0.65" in result
