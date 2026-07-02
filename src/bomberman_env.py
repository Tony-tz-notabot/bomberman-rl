import math
import random as _random_mod
import numpy as np
import pygame
import gym
from gym import spaces
from typing import Callable, Optional, Tuple

from src.config import cfg
from src.constants import GameState, CELL_EMPTY, CELL_STONE, CELL_BRICK
from src.game_engine import GameEngine
from src.map_generator import generate_map
from src.models import GameSnapshot
from src.utils import grid_center, pixel_to_grid

# Type alias for opponent function
OpponentFn = Callable[[GameSnapshot, str], np.ndarray]


def build_obs(snapshot: GameSnapshot, agent_id: str) -> np.ndarray:
    """Build observation for a given agent. Module-level for reuse by PettingZoo.

    agent_id="red" -> self=red, opp=blue
    agent_id="blue" -> self=blue, opp=red

    Returns: (MAP_ROWS, MAP_COLS, 9) float32 array in [0,1].
    """
    obs = np.zeros((cfg.MAP_ROWS, cfg.MAP_COLS, 9), dtype=np.float32)

    # CH0: terrain - 0=empty, 0.5=brick, 1.0=stone
    for x in range(1, cfg.MAP_COLS + 1):
        for y in range(1, cfg.MAP_ROWS + 1):
            val = snapshot.map_grid[x][y]
            if val == CELL_STONE:  # 1
                obs[y-1, x-1, 0] = 1.0
            elif val == CELL_BRICK:  # 2
                obs[y-1, x-1, 0] = 0.5
            # CELL_EMPTY (0): remains 0.0

    # CH1: Self position — full-range Gaussian heatmap [0, 1]
    self_player = snapshot.players[0] if agent_id == snapshot.players[0].id else snapshot.players[1]
    opp_player = snapshot.players[1] if self_player is snapshot.players[0] else snapshot.players[0]
    obs[:, :, 1] = _gauss_heatmap(self_player.pos_x, self_player.pos_y)

    # CH2: Opponent position — full-range Gaussian heatmap [0, 1]
    obs[:, :, 2] = _gauss_heatmap(opp_player.pos_x, opp_player.pos_y)

    # CH3: Bomb + fuse - value = fuse_frames / BOMB_FUSE
    for bomb in snapshot.bombs:
        if bomb.fuse_frames >= 0:
            val = min(bomb.fuse_frames / cfg.BOMB_FUSE, 1.0)
        else:
            val = 1.0  # remote bombs (fuse_frames=-1) show as 1.0
        gy, gx = bomb.grid_y - 1, bomb.grid_x - 1
        obs[gy, gx, 3] = val

    # CH4: Buff + explosion
    # Buff encoding: bomb_plus=0.2, blast_plus=0.35, speed_plus=0.5,
    #               kick=0.65, remote=0.8, shield=0.9, other_ability=1.0
    BUFF_MAP = {
        "bomb_plus": 0.2, "blast_plus": 0.35, "speed_plus": 0.5,
        "kick": 0.65, "remote": 0.8, "shield": 0.9,
    }
    for buff in snapshot.buffs:
        val = BUFF_MAP.get(buff.type, 1.0)
        gy, gx = buff.grid_y - 1, buff.grid_x - 1
        obs[gy, gx, 4] = val
    for (gx, gy) in snapshot.explosion_cells:
        obs[gy-1, gx-1, 4] = 1.0  # explosion overrides buff

    # CH5: Self abilities (broadcast)
    _broadcast_abilities(obs[:, :, 5], self_player.abilities)
    # CH6: Opponent abilities (broadcast)
    _broadcast_abilities(obs[:, :, 6], opp_player.abilities)

    # CH7: Self stats (broadcast)
    _broadcast_stats(obs[:, :, 7], self_player.bomb_placed_count, self_player.bomb_max)
    # CH8: Opponent stats (broadcast)
    _broadcast_stats(obs[:, :, 8], opp_player.bomb_placed_count, opp_player.bomb_max)

    return obs


def _gauss_heatmap(px: float, py: float) -> np.ndarray:
    """Pixel coordinates -> (H, W) Gaussian heatmap in grid units."""
    heatmap = np.zeros((cfg.MAP_ROWS, cfg.MAP_COLS), dtype=np.float32)
    sigma = 0.3
    for gy in range(1, cfg.MAP_ROWS + 1):
        for gx in range(1, cfg.MAP_COLS + 1):
            cx, cy = grid_center(gx, gy)
            dx = (px - cx) / cfg.CELL_SIZE
            dy = (py - cy) / cfg.CELL_SIZE
            heatmap[gy-1][gx-1] = math.exp(-(dx*dx + dy*dy) / (2 * sigma * sigma))
    return heatmap


def _broadcast_abilities(channel: np.ndarray, abilities: dict):
    """Broadcast ability remaining times normalized over max duration, across entire channel.

    Channel shape = (H, W). Each ability contributes a value.
    We sum them, clamp to [0, 1].
    """
    if not abilities:
        return
    total = 0.0
    # Normalize each ability by its max duration (rough upper bound)
    # Use DURATION_FLOAT=480 as the normalization cap (longest standard ability)
    max_dur = 480.0  # max ability duration in frames
    for name, remaining in abilities.items():
        total += min(remaining / max_dur, 1.0)
    channel[:, :] = min(total / 6.0, 1.0)  # normalize by max possible abilities count


def _broadcast_stats(channel: np.ndarray, placed: int, max_bombs: int):
    """Broadcast player numeric stats across entire channel."""
    channel[:, :] = placed / max(max_bombs, 1)


class BombermanEnv(gym.Env):
    """Gym environment for Bomberman PVP single-agent training.

    Controls the red player; blue player is controlled by opponent_fn.
    """

    metadata = {"render.modes": ["human", "rgb_array"], "render_fps": 24}

    def __init__(
        self,
        reward_fn=None,
        opponent_fn: OpponentFn = None,
        penalty_opposing: float = 0.0,
        render_mode: Optional[str] = None,
    ):
        super().__init__()
        from rewards import RewardFunction
        from rewards.sparse import SparseReward

        self.engine = GameEngine()
        self.reward_fn = reward_fn if reward_fn is not None else SparseReward()
        self.opponent_fn = opponent_fn if opponent_fn is not None else _random_opponent
        self.penalty_opposing = penalty_opposing

        self.action_space = spaces.MultiBinary(6)  # [up, down, left, right, action, ignite]
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(cfg.MAP_ROWS, cfg.MAP_COLS, 9), dtype=np.float32
        )
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
                pygame.display.set_caption("Bomberman RL Training")
            else:  # rgb_array
                pygame.display.set_mode((1, 1))
                self._screen = pygame.Surface((w, h))
            from src.renderer import Renderer
            self._renderer = Renderer(self._screen)

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[dict] = None,
    ) -> Tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        if options is not None and "grid" in options:
            self._init_from_matrix(np.asarray(options["grid"]))
        elif options is not None and "phase" in options:
            self._init_phase(float(options["phase"]))
        else:
            self.engine.reset_match()
        snap = self.engine.get_snapshot()
        self._prev_snap = snap
        self.reward_fn.reset({"seed": seed})
        obs = build_obs(snap, "red")
        return obs, {}

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, dict]:
        """Step the environment.

        action: MultiBinary(6) - [up, down, left, right, action, ignite]
        """
        # Convert action to dict
        red_dict = self._action_to_dict(action)

        # Get opponent action
        snap_before = self.engine.get_snapshot()
        blue_action = self.opponent_fn(snap_before, "blue")
        blue_dict = self._action_to_dict(blue_action)

        # Step engine
        snapshot = self.engine.step(red_dict, blue_dict)

        # Compute reward
        reward = self.reward_fn(self.engine, self._prev_snap, snapshot, action, "red")

        # Add opposing-key penalty
        if self.penalty_opposing != 0.0:
            # Check for opposing directions
            if (action[0] and action[1]) or (action[2] and action[3]):
                reward += self.penalty_opposing

        obs = build_obs(snapshot, "red")
        terminated = snapshot.state == GameState.MATCH_END
        truncated = False
        info = {}

        self._prev_snap = snapshot
        return obs, reward, terminated, truncated, info

    def _action_to_dict(self, action: np.ndarray) -> dict:
        """Convert MultiBinary(6) array to action dict."""
        return {
            "up": bool(action[0]),
            "down": bool(action[1]),
            "left": bool(action[2]),
            "right": bool(action[3]),
            "action": bool(action[4]),
            "ignite": bool(action[5]),
        }

    def _init_phase(self, phase: float):
        """Initialize map and spawns using phase-aware map generator."""
        seed_val = int(self.np_random.integers(0, 2**31))
        rng = _random_mod.Random(seed_val)
        result = generate_map(phase, rng)

        self.engine.state = GameState.ROUND_RUNNING
        self.engine.round_frame = 0
        self.engine.bombs.clear()
        self.engine.buffs.clear()
        self.engine.explosion_cells.clear()
        self.engine.refresh_timer = cfg.REFRESH_INTERVAL
        self.engine.round_delay_timer = 0
        self.engine.current_winner = ""
        self.engine.next_bomb_id = 0

        grid = result["grid"]
        for x in range(1, cfg.MAP_COLS + 1):
            for y in range(1, cfg.MAP_ROWS + 1):
                self.engine.grid[x][y] = grid[x][y]

        self.engine.red_player.reset(*result["red_spawn"])
        self.engine.blue_player.reset(*result["blue_spawn"])
        self.engine.safe_spots = result["safe_spots"]

    def _init_from_matrix(self, matrix: np.ndarray):
        """Initialize map from a (MAP_ROWS, MAP_COLS) matrix.

        Encoding: 0=floor, 1=stone, 2=brick, 3=red_spawn, 4=blue_spawn
        """
        # Create fresh grid
        self.engine.state = GameState.ROUND_RUNNING
        self.engine.round_frame = 0
        self.engine.bombs.clear()
        self.engine.buffs.clear()
        self.engine.explosion_cells.clear()
        for x in range(1, cfg.MAP_COLS + 1):
            for y in range(1, cfg.MAP_ROWS + 1):
                self.engine.grid[x][y] = "floor"

        red_spawn = None
        blue_spawn = None

        for y in range(cfg.MAP_ROWS):
            for x in range(cfg.MAP_COLS):
                val = matrix[y, x]
                gx, gy = x + 1, y + 1
                if val == 1:
                    self.engine.grid[gx][gy] = "stone"
                elif val == 2:
                    self.engine.grid[gx][gy] = "brick"
                elif val == 3:
                    self.engine.grid[gx][gy] = "floor"
                    red_spawn = (gx, gy)
                elif val == 4:
                    self.engine.grid[gx][gy] = "floor"
                    blue_spawn = (gx, gy)
                # val 0 remains "floor"

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


def _random_opponent(snapshot: GameSnapshot, agent_id: str) -> np.ndarray:
    """Default random opponent: uniform random MultiBinary(6)."""
    return np.random.randint(0, 2, size=6, dtype=np.int8)
