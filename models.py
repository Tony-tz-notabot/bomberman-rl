from dataclasses import dataclass
from config import cfg
from utils import pixel_to_grid, grid_center


# ── Internal data classes (unchanged from original) ──

class Player:
    def __init__(self, pid, color):
        self.id = pid
        self.color = color
        self.pos_x = 0.0
        self.pos_y = 0.0
        self.velocity = cfg.INIT_SPEED
        self.bomb_max = cfg.INIT_BOMB_MAX
        self.bomb_placed_count = 0
        self.blast_range = cfg.INIT_BLAST_RANGE
        self.alive = True
        self.death_timer = 0
        self.invincible_timer = 0
        self.wins = 0
        self.perm_bomb_plus = 0
        self.perm_blast_plus = 0
        self.perm_speed_plus = 0
        self.abilities = {}
        self.remote_queue = []
        self.input_up = False
        self.input_down = False
        self.input_left = False
        self.input_right = False
        self.input_action = False
        self.prev_action = False
        self.input_ignite = False
        self.vx = 0.0
        self.vy = 0.0

    def reset(self, spawn_x, spawn_y):
        self.pos_x, self.pos_y = grid_center(spawn_x, spawn_y)
        self.velocity = cfg.INIT_SPEED
        self.bomb_max = cfg.INIT_BOMB_MAX
        self.bomb_placed_count = 0
        self.blast_range = cfg.INIT_BLAST_RANGE
        self.alive = True
        self.death_timer = 0
        self.invincible_timer = 0
        self.perm_bomb_plus = 0
        self.perm_blast_plus = 0
        self.perm_speed_plus = 0
        self.abilities.clear()
        self.remote_queue.clear()
        self.vx = 0.0
        self.vy = 0.0
        self.input_up = self.input_down = self.input_left = self.input_right = False
        self.input_action = False
        self.input_ignite = False
        self.prev_action = False

    def hitbox(self):
        half = (cfg.PLAYER_HITBOX_SIZE * cfg.CELL_SIZE) / 2
        return (self.pos_x - half, self.pos_x + half,
                self.pos_y - half, self.pos_y + half)


class Bomb:
    def __init__(self, bid, owner, bomb_type, grid_x, grid_y, fuse_frames):
        self.id = bid
        self.owner = owner
        self.type = bomb_type
        self.pos_x, self.pos_y = grid_center(grid_x, grid_y)
        self.fuse_frames = fuse_frames
        self.vx = 0.0
        self.vy = 0.0
        self.exploding = False
        self.exploded = False

    def grid_pos(self):
        return pixel_to_grid(self.pos_x, self.pos_y)


class BuffItem:
    def __init__(self, buff_type, sub_type, gx, gy):
        self.type = buff_type
        self.unknown_subtype = sub_type
        self.pos_x, self.pos_y = grid_center(gx, gy)
        self.protection_timer = cfg.BUFF_PROTECTION_TIME

    def grid_pos(self):
        return pixel_to_grid(self.pos_x, self.pos_y)


# ── Read-only Snapshot dataclasses (for AI/Renderer) ──

@dataclass(frozen=True)
class PlayerSnapshot:
    id: str
    color: tuple
    pos_x: float
    pos_y: float
    grid_x: int
    grid_y: int
    alive: bool
    velocity: float
    death_timer: int
    bomb_max: int
    bomb_placed_count: int
    blast_range: int
    invincible_timer: int
    wins: int
    perm_bomb_plus: int
    perm_blast_plus: int
    perm_speed_plus: int
    abilities: dict  # {name: remaining_frames}
    # ⚠️ excludes: unknown_subtype, remote_queue, input_*, vx, vy, prev_action


@dataclass(frozen=True)
class BombSnapshot:
    id: int
    owner: str
    type: str
    pos_x: float
    pos_y: float
    grid_x: int
    grid_y: int
    fuse_frames: int  # -1 for remote bombs
    vx: float
    vy: float


@dataclass(frozen=True)
class BuffItemSnapshot:
    type: str
    pos_x: float
    pos_y: float
    grid_x: int
    grid_y: int
    # ⚠️ no unknown_subtype


@dataclass(frozen=True)
class GameSnapshot:
    state: int
    round_frame: int
    map_grid: list          # [[int, ...], ...] COLS × ROWS
    players: tuple          # (PlayerSnapshot, PlayerSnapshot)
    bombs: tuple            # (BombSnapshot, ...)
    buffs: tuple            # (BuffItemSnapshot, ...)
    explosion_cells: tuple  # ((gx, gy), ...)
    scores: dict            # {"red": int, "blue": int}
