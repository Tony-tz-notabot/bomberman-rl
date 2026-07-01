"""Tests for BombermanPettingZooEnv PettingZoo environment."""
import numpy as np
import pytest

from config import cfg


class TestPettingZooEnv:
    def _make_env(self):
        """Helper to create the env, skipping if pettingzoo is not installed."""
        try:
            from pettingzoo_env import BombermanPettingZooEnv
        except ImportError:
            pytest.skip("pettingzoo not installed")
        return BombermanPettingZooEnv()

    def test_pz_reset(self):
        """Reset returns {agent: obs} structure."""
        env = self._make_env()
        obs = env.reset()
        assert isinstance(obs, dict)
        assert set(obs.keys()) == {"red", "blue"}
        for agent, ob in obs.items():
            assert ob.shape == (cfg.MAP_ROWS, cfg.MAP_COLS, 8)
            assert ob.dtype == np.float32

    def test_pz_step(self):
        """Step accepts {agent: action}, returns correct structure."""
        env = self._make_env()
        env.reset()
        actions = {
            "red": np.array([0, 0, 0, 0, 0, 0], dtype=np.int8),
            "blue": np.array([0, 0, 0, 0, 0, 0], dtype=np.int8),
        }
        obs, rewards, terms, truncs, infos = env.step(actions)
        assert isinstance(obs, dict)
        assert isinstance(rewards, dict)
        assert isinstance(terms, dict)
        assert isinstance(truncs, dict)
        assert isinstance(infos, dict)
        assert "__all__" in terms

    def test_pz_parallel_api(self):
        """Verify ParallelEnv API structure."""
        env = self._make_env()
        # Verify all required attributes exist
        assert hasattr(env, 'agents')
        assert hasattr(env, 'possible_agents')
        assert hasattr(env, 'action_spaces')
        assert hasattr(env, 'observation_spaces')
        assert hasattr(env, 'reset')
        assert hasattr(env, 'step')
        assert hasattr(env, 'observe')
        assert set(env.possible_agents) == {"red", "blue"}

    def test_pz_agent_rotation(self):
        """Running multiple steps works without error."""
        env = self._make_env()
        env.reset()
        for _ in range(20):
            actions = {
                "red": np.random.randint(0, 2, size=6, dtype=np.int8),
                "blue": np.random.randint(0, 2, size=6, dtype=np.int8),
            }
            _, _, terms, _, _ = env.step(actions)
            if terms["__all__"]:
                break
        # Just verify no crash
        assert True
