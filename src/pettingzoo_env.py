"""PettingZoo ParallelEnv wrapper for Bomberman PVP multi-agent self-play.

Wraps GameEngine directly. Both agents' actions come from the training script.
Imports build_obs from bomberman_env as shared observation builder.
"""
import numpy as np
import pygame
from typing import Optional
from gymnasium import spaces
from pettingzoo import ParallelEnv

from src.config import cfg
from src.constants import GameState
from src.game_engine import GameEngine
from src.bomberman_env import build_obs
from src.renderer import Renderer
from rewards import RewardFunction
from rewards.sparse import SparseReward


class BombermanPettingZooEnv(ParallelEnv):
    """PettingZoo multi-agent environment for Bomberman PVP.

    Both agents are controlled externally (no opponent_fn).
    Supports tied policy: observations use build_obs(snapshot, agent_id)
    so CH1 always encodes SELF in [0.1, 0.5] and OPPONENT in (0.5, 1.0].
    """

    metadata = {"render.modes": ["human", "rgb_array"], "render_fps": 24, "name": "bomberman_v2_pz"}

    def __init__(
        self,
        reward_fn: RewardFunction = None,
        penalty_opposing: float = 0.0,
        render_mode: Optional[str] = None,
    ):
        super().__init__()
        self.engine = GameEngine()
        self.reward_fn = reward_fn if reward_fn is not None else SparseReward()
        self.penalty_opposing = penalty_opposing

        self.agents = ["red", "blue"]
        self.possible_agents = ["red", "blue"]

        self.action_spaces = {
            "red": spaces.MultiBinary(6),   # [up, down, left, right, action, ignite]
            "blue": spaces.MultiBinary(6),
        }
        obs_space = spaces.Box(
            low=0.0, high=1.0,
            shape=(cfg.MAP_ROWS, cfg.MAP_COLS, 9),
            dtype=np.float32,
        )
        self.observation_spaces = {
            "red": obs_space,
            "blue": obs_space,
        }
        self._prev_snap = None

        self.render_mode = render_mode
        self._renderer = None
        self._screen = None

        if render_mode is not None:
            import pygame
            pygame.init()
            from src.utils import get_window_width, get_window_height
            w, h = get_window_width(), get_window_height()
            if render_mode == "human":
                self._screen = pygame.display.set_mode((w, h), pygame.RESIZABLE)
                pygame.display.set_caption("Bomberman PZ Training")
            else:  # rgb_array
                pygame.display.set_mode((1, 1))
                self._screen = pygame.Surface((w, h))
            self._renderer = Renderer(self._screen)
        self._cumulative_rewards = {a: 0.0 for a in self.agents}

    def reset(self, seed=None, options=None):
        """Reset environment.

        Args:
            options: can contain "grid" — a (MAP_ROWS, MAP_COLS) matrix
                     0=floor, 1=stone, 2=brick, 3=red_spawn, 4=blue_spawn
        """
        if seed is not None:
            np.random.seed(seed)

        if options is not None and "grid" in options:
            self._init_from_matrix(np.asarray(options["grid"]))
        else:
            self.engine.reset_match()

        snap = self.engine.get_snapshot()
        self._prev_snap = snap
        self.reward_fn.reset({"seed": seed})
        self._cumulative_rewards = {a: 0.0 for a in self.agents}

        obs = {a: build_obs(snap, a) for a in self.agents}
        return obs

    def step(self, actions: dict):
        """Step environment.

        actions: {"red": ndarray(6,), "blue": ndarray(6,)}
        Returns: (observations, rewards, terminations, truncations, infos)
        """
        red_dict = self._action_to_dict(actions.get("red", np.zeros(6, dtype=np.int8)))
        blue_dict = self._action_to_dict(actions.get("blue", np.zeros(6, dtype=np.int8)))

        snapshot = self.engine.step(red_dict, blue_dict)

        observations = {}
        rewards = {}
        terminations = {}
        truncations = {}
        infos = {}

        for agent in self.agents:
            observations[agent] = build_obs(snapshot, agent)
            action = actions.get(agent, np.zeros(6, dtype=np.int8))
            base_reward = self.reward_fn(self.engine, self._prev_snap, snapshot, action, agent)

            # Opposing-key penalty
            penalty = 0.0
            if self.penalty_opposing != 0.0:
                if (action[0] and action[1]) or (action[2] and action[3]):
                    penalty = self.penalty_opposing
            rewards[agent] = base_reward + penalty

            terminations[agent] = snapshot.state == GameState.MATCH_END
            truncations[agent] = False
            infos[agent] = {}

            self._cumulative_rewards[agent] += rewards[agent]

        terminations["__all__"] = all(t for a, t in terminations.items() if a != "__all__")
        truncations["__all__"] = False

        self._prev_snap = snapshot

        # PettingZoo ParallelEnv expects dones for alive agents
        # When MATCH_END, both agents are done
        if snapshot.state == GameState.MATCH_END:
            self.agents = []
        else:
            self.agents = ["red", "blue"]

        return observations, rewards, terminations, truncations, infos

    def observe(self, agent: str):
        """Returns the observation for agent."""
        snap = self.engine.get_snapshot()
        return build_obs(snap, agent)

    def state(self):
        """Global state for centralized training (e.g., QMIX)."""
        snap = self.engine.get_snapshot()
        return build_obs(snap, "red")  # full state from red's perspective

    def _action_to_dict(self, action: np.ndarray) -> dict:
        return {
            "up": bool(action[0]),
            "down": bool(action[1]),
            "left": bool(action[2]),
            "right": bool(action[3]),
            "action": bool(action[4]),
            "ignite": bool(action[5]),
        }

    def _init_from_matrix(self, matrix: np.ndarray):
        """Initialize map from a (MAP_ROWS, MAP_COLS) matrix."""
        self.engine.state = GameState.ROUND_RUNNING
        self.engine.round_frame = 0
        self.engine.bombs.clear()
        self.engine.buffs.clear()
        self.engine.explosion_cells.clear()
        for x in range(1, cfg.MAP_COLS + 1):
            for y in range(1, cfg.MAP_ROWS + 1):
                self.engine.grid[x][y] = "floor"

        red_spawn = blue_spawn = None
        for y in range(cfg.MAP_ROWS):
            for x in range(cfg.MAP_COLS):
                val = int(matrix[y, x])
                gx, gy = x + 1, y + 1
                if val == 1:
                    self.engine.grid[gx][gy] = "stone"
                elif val == 2:
                    self.engine.grid[gx][gy] = "brick"
                elif val == 3:
                    red_spawn = (gx, gy)
                elif val == 4:
                    blue_spawn = (gx, gy)

        assert red_spawn is not None, "Matrix must include red spawn (3)"
        assert blue_spawn is not None, "Matrix must include blue spawn (4)"
        self.engine.red_player.reset(*red_spawn)
        self.engine.blue_player.reset(*blue_spawn)
        self.engine.safe_spots = {red_spawn, blue_spawn}

    def render(self) -> Optional[np.ndarray]:
        """Render the current game frame.

        Returns:
            rgb_array: (H, W, 3) uint8 numpy array
            human: None (display updated via pygame)
            None: if render_mode is None
        """
        if self.render_mode is None:
            return None

        snap = self.engine.get_snapshot()
        from src.constants import COLOR_BG
        self._screen.fill(COLOR_BG)
        self._renderer.draw(snap)

        if self.render_mode == "human":
            pygame.display.flip()
            return None
        else:  # rgb_array
            return pygame.surfarray.array3d(self._screen).transpose(1, 0, 2)

    def close(self):
        if self.render_mode is not None:
            pygame.quit()
