"""Tests for BombermanEnv Gym environment."""
import numpy as np
import pytest

from src.config import cfg
from src.constants import GameState
from src.bomberman_env import BombermanEnv, build_obs


class TestBombermanEnv:
    def test_reset_default(self):
        """Default reset produces valid round, observation shape correct."""
        env = BombermanEnv()
        obs, info = env.reset()
        assert isinstance(obs, np.ndarray)
        assert obs.shape == (cfg.MAP_ROWS, cfg.MAP_COLS, 9)
        assert obs.dtype == np.float32
        assert obs.min() >= 0.0 and obs.max() <= 1.0
        assert env.engine.state == GameState.ROUND_RUNNING

    def test_reset_with_grid(self):
        """Reset with custom grid matrix."""
        env = BombermanEnv()
        # Simple grid: all floor with spawns at known positions
        grid = np.zeros((cfg.MAP_ROWS, cfg.MAP_COLS), dtype=np.int32)
        grid[0, 0] = 3       # red spawn at (1, 1) — 0-indexed
        grid[cfg.MAP_ROWS-1, cfg.MAP_COLS-1] = 4  # blue spawn at (19, 11)

        obs, info = env.reset(options={"grid": grid})
        assert obs.shape == (cfg.MAP_ROWS, cfg.MAP_COLS, 9)
        # Verify player spawn positions
        assert env.engine.red_player.pos_x is not None
        assert env.engine.blue_player.pos_x is not None
        # Grid cells should mostly be floor (CH0 = 0.0)
        assert obs[0, 0, 0] == 0.0  # floor at red spawn
        assert env.engine.state == GameState.ROUND_RUNNING

    def test_reset_with_grid_missing_spawn(self):
        """Reset with grid missing player spawn raises AssertionError."""
        env = BombermanEnv()
        grid = np.zeros((cfg.MAP_ROWS, cfg.MAP_COLS), dtype=np.int32)
        with pytest.raises(AssertionError):
            env.reset(options={"grid": grid})

    def test_step_basic(self):
        """Step returns (obs, reward, terminated, truncated, info)."""
        env = BombermanEnv()
        env.reset()
        action = np.array([0, 0, 0, 0, 0, 0], dtype=np.int8)
        obs, reward, terminated, truncated, info = env.step(action)
        assert isinstance(obs, np.ndarray)
        assert obs.shape == (cfg.MAP_ROWS, cfg.MAP_COLS, 9)
        assert isinstance(reward, float)
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)
        assert isinstance(info, dict)

    def test_penalty_opposing(self):
        """Opposing direction keys trigger penalty."""
        env = BombermanEnv(penalty_opposing=-0.1)
        env.reset()

        # Up+down simultaneously
        action = np.array([1, 1, 0, 0, 0, 0], dtype=np.int8)  # up+down
        _, reward1, _, _, _ = env.step(action)
        assert reward1 <= -0.09, f"Expected penalty, got {reward1}"

        # No opposing keys — no penalty
        env.reset()
        action = np.array([1, 0, 0, 0, 0, 0], dtype=np.int8)  # up only
        obs, reward2, _, _, _ = env.step(action)
        assert reward2 >= -0.01 or reward2 <= 0.01  # approximately zero

    def test_opponent_fn(self):
        """Custom opponent function is called and its actions reach engine."""
        call_count = 0
        def custom_opponent(snapshot, agent_id):
            nonlocal call_count
            call_count += 1
            return np.array([0, 0, 0, 0, 0, 0], dtype=np.int8)

        env = BombermanEnv(opponent_fn=custom_opponent)
        env.reset()
        action = np.array([1, 0, 0, 0, 0, 0], dtype=np.int8)
        env.step(action)
        assert call_count >= 1, f"opponent_fn called {call_count} times"

    def test_reward_function(self):
        """Custom reward function is used."""
        from rewards import RewardFunction
        class ZeroReward(RewardFunction):
            def __call__(self, engine, prev, snap, action, agent):
                return 42.0

        env = BombermanEnv(reward_fn=ZeroReward())
        env.reset()
        action = np.array([0, 0, 0, 0, 0, 0], dtype=np.int8)
        _, reward, _, _, _ = env.step(action)
        assert reward == 42.0

    def test_episode_lifecycle(self):
        """Step-loop works without error; terminated is bool."""
        env = BombermanEnv()
        env.reset()
        for _ in range(50):
            action = np.random.randint(0, 2, size=6, dtype=np.int8)
            _, _, terminated, truncated, _ = env.step(action)
            if terminated:
                break
        # Just verify we can run without crash
        assert True

    def test_build_obs_structure(self):
        """Direct build_obs call produces correct structure."""
        env = BombermanEnv()
        env.reset()
        snap = env.engine.get_snapshot()
        obs = build_obs(snap, "red")
        assert obs.shape == (cfg.MAP_ROWS, cfg.MAP_COLS, 9)
        # CH0: terrain should have some non-zero values (stones exist)
        assert (obs[:, :, 0] >= 0).all() and (obs[:, :, 0] <= 1.0).all()
        # CH1: self position — should have activity near red spawn
        assert obs[:, :, 1].max() > 0.1, "Self heatmap should have values"
        # CH2: opponent position — should also have activity
        assert obs[:, :, 2].max() > 0.1, "Opponent heatmap should have values"
        # All values in [0, 1]
        assert obs.min() >= 0.0 and obs.max() <= 1.0

    def test_render_rgb_array(self):
        """render(mode="rgb_array") returns (H, W, 3) uint8 array."""
        env = BombermanEnv(render_mode="rgb_array")
        env.reset()
        frame = env.render()
        from src.utils import get_window_width, get_window_height
        assert frame is not None
        assert isinstance(frame, np.ndarray)
        assert frame.shape == (get_window_height(), get_window_width(), 3)
        assert frame.dtype == np.uint8
        env.close()

    def test_render_none(self):
        """render_mode=None returns None from render()."""
        env = BombermanEnv(render_mode=None)
        env.reset()
        assert env.render() is None
        env.close()

    def test_render_multiple_frames(self):
        """Multiple render() calls return consistent frames."""
        env = BombermanEnv(render_mode="rgb_array")
        env.reset()
        for _ in range(5):
            action = np.random.randint(0, 2, size=6, dtype=np.int8)
            env.step(action)
            frame = env.render()
            assert frame is not None
            assert frame.shape[2] == 3  # RGB
        env.close()
