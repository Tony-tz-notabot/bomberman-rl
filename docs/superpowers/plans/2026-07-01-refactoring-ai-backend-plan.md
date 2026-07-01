# Phase 1 Refactoring — Backend/Frontend Separation + Frame Sync

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split monolith `main.py` (~1250 lines) into modules, create frame-based `GameEngine` with no pygame dependency, expose `GameSnapshot` read-only API for future AI/Gym integration.

**Architecture:** Backend (`GameEngine` — pure logic, zero pygame) + Frontend (`Renderer`, `InputHandler`, `SettingsUI`). Engine uses `DT_OVER_DTAU` (= 1/FPS) for movement conversion and integer frame counters for all timers. Frontend reads only `GameSnapshot` to draw.

**Tech Stack:** Python 3, pygame 2.x, pytest

## Global Constraints

1. **No behavior changes** — all game rules, collision behavior, and parameter defaults must match the original (only units change: seconds → frames)
2. **Zero pygame dependency in `game_engine.py`** — must import cleanly in headless environment
3. **`DT_OVER_DTAU = 1.0 / FPS`** — replaces `dt` in movement formulas; all timers decrement by 1 per step
4. **`GameSnapshot` is `@dataclass(frozen=True)`** — read-only for AI/renderer
5. **`unknown_subtype` never exposed** in `BuffItemSnapshot` — hidden info fairness
6. **All import lines in `main.py` remain backward-compatible** — existing `from main import cfg, Player, ...` continues to work
7. **All 99 tests pass** after refactoring (some updated for new API)

---
## File Structure

```
main.py              游戏入口胶水 (~150行)
├── config.py         Config 类 + 全局 cfg + CellType 枚举
├── constants.py      颜色常量 (COLOR_*) + GameState 枚举
├── utils.py          坐标工具 (grid_to_pixel, pixel_to_grid, clamp, sign, box_overlap)
├── models.py         数据类: Player, Bomb, BuffItem
│                     + Snapshot 数据类: GameSnapshot, PlayerSnapshot,
│                       BombSnapshot, BuffItemSnapshot
├── game_engine.py    GameEngine — 纯逻辑, 零 pygame
├── renderer.py       Renderer — 读 GameSnapshot, 绘制所有内容
├── input_handler.py  InputHandler — pygame 键盘 → action dict
└── settings_ui.py    SettingsUI — 参数面板绘制 + 交互

tests/
├── conftest.py       夹具更新: game 夹具创建 GameEngine 而非 BombermanGame
├── test_utils.py     工具函数测试 (不变)
└── test_game_mechanics.py  游戏机制测试 (更新 GameEngine API)
```

---

### Task 1: Extract `config.py` — Config class + frame conversion

**Files:**
- Create: `config.py`
- Modify: `main.py` (remove Config class, import from config)
- Test: `tests/test_utils.py::TestConfig` (update import path)

**Interfaces:**
- Consumes: nothing
- Produces: `cfg` global singleton, `Config` class with all params converted to frame-based units

- [ ] **Step 1: Create `config.py` with frame-converted Config class**

```python
# config.py — 全局配置
class Config:
    def __init__(self):
        self.FPS = 24
        self.DT_OVER_DTAU = 1.0 / self.FPS   # dt/dτ 换算率

        self.CELL_SIZE = 40
        self.MAP_COLS = 19
        self.MAP_ROWS = 11
        self.UI_BAR_HEIGHT = 80
        self.BRICK_GEN_PROB = 0.7

        # 速度类 (cells/sec, 通过 DT_OVER_DTAU 换算)
        self.INIT_SPEED = 2.5
        self.SPEED_INCREMENT = 0.5
        self.MAX_SPEED = 6
        self.SPEED_LEVEL_CAP = 7
        self.KICK_INIT_VEL = 6.0
        self.KICK_ACCEL = -2.0

        # 整数类 (直接帧数)
        self.INIT_BOMB_MAX = 1
        self.MAX_BOMB_CAP = 7
        self.INIT_BLAST_RANGE = 2
        self.MAX_BLAST_RANGE = 8
        self.PLAYER_HITBOX_SIZE = 0.8
        self.BOMB_FUSE = 48              # = 2.0 × 24
        self.BOMB_FLICKER_START = 12      # = 0.5 × 24
        self.DEATH_ANIM_DUR = 12          # = 0.5 × 24
        self.SHIELD_INVINCIBLE_DUR = 12   # = 0.5 × 24
        self.WIN_SCORE = 5
        self.ROUND_DELAY = 72             # = 3.0 × 24
        self.BRICK_DROP_PROB = 0.15
        self.BUFF_PROTECTION_TIME = 7     # ≈ 0.3 × 24
        self.REFRESH_INTERVAL = 720       # = 30.0 × 24
        self.WEIGHT_BOMB_PLUS = 0.2
        self.WEIGHT_BLAST_PLUS = 0.2
        self.WEIGHT_SPEED_PLUS = 0.2
        self.WEIGHT_UNKNOWN = 0.4
        self.DURATION_KICK = 720          # = 30.0 × 24
        self.DURATION_REMOTE = 720        # = 30.0 × 24
        self.DURATION_SHIELD = 480        # = 20.0 × 24
        self.DURATION_DIARRHEA = 192      # = 8.0 × 24
        self.DURATION_REVERSE = 240       # = 10.0 × 24
        self.DURATION_FLOAT = 480         # = 20.0 × 24

    def reset_defaults(self):
        self.__init__()

cfg = Config()
```

- [ ] **Step 2: Update `main.py` — remove original Config, add import**

In `main.py`, replace the original `Config` class (lines 10–52) with:
```python
from config import Config, cfg
```

Remove lines 10–52 entirely.

- [ ] **Step 3: Run tests to verify**

Run: `python -m pytest tests/test_utils.py::TestConfig -v`
Expected: PASS (all 2 tests)

- [ ] **Step 4: Full test pass**

Run: `python -m pytest tests/ -v`
Expected: 99 passed

- [ ] **Step 5: Run the game once to confirm it starts**

Run: `python -c "from main import BombermanGame; g = BombermanGame(); print('OK:', g.state)"`
Expected: `OK: 0` (MENU state)

- [ ] **Step 6: Commit**

```bash
git add config.py main.py
git commit -m "refactor: extract config.py, convert all time params to frames"
```

---

### Task 2: Extract `constants.py` — color constants + GameState

**Files:**
- Create: `constants.py`
- Modify: `main.py` (remove COLOR_* and GameState, import from constants)

**Interfaces:**
- Consumes: nothing
- Produces: All `COLOR_*` constants, `GameState` class

- [ ] **Step 1: Create `constants.py`**

```python
# constants.py
COLOR_BG = (34, 40, 49)
COLOR_FLOOR = (200, 200, 200)
COLOR_STONE = (80, 80, 80)
COLOR_BRICK = (205, 133, 63)
COLOR_RED = (220, 50, 50)
COLOR_BLUE = (50, 100, 220)
COLOR_BOMB_BODY = (30, 30, 30)
COLOR_BOMB_FUSE = (255, 200, 0)
COLOR_EXPLOSION = (255, 100, 0)
COLOR_TEXT = (255, 255, 255)
COLOR_UI_BAR_BG = (20, 20, 30)
COLOR_SHIELD = (0, 255, 255)

BUFF_BOMB_COLOR = (255, 100, 0)
BUFF_BLAST_COLOR = (255, 200, 0)
BUFF_SPEED_COLOR = (0, 200, 100)
BUFF_UNKNOWN_COLOR = (180, 100, 255)

ABILITY_KICK_COLOR = (220, 80, 80)
ABILITY_REMOTE_COLOR = (80, 140, 240)
ABILITY_SHIELD_COLOR = (0, 220, 100)
ABILITY_DIARRHEA_COLOR = (139, 90, 43)
ABILITY_REVERSE_COLOR = (180, 100, 255)
ABILITY_FLOAT_COLOR = (160, 160, 160)

class GameState:
    MENU = 0
    ROUND_RUNNING = 1
    ROUND_END_DELAY = 2
    MATCH_END = 3
    SETTINGS = 4
    SETTINGS_PAUSED = 5
```

- [ ] **Step 2: Update `main.py` — remove originals, add import**

Replace lines 68–91 (color constants) with:
```python
from constants import (
    COLOR_BG, COLOR_FLOOR, COLOR_STONE, COLOR_BRICK,
    COLOR_RED, COLOR_BLUE, COLOR_BOMB_BODY, COLOR_BOMB_FUSE,
    COLOR_EXPLOSION, COLOR_TEXT, COLOR_UI_BAR_BG, COLOR_SHIELD,
    BUFF_BOMB_COLOR, BUFF_BLAST_COLOR, BUFF_SPEED_COLOR, BUFF_UNKNOWN_COLOR,
    ABILITY_KICK_COLOR, ABILITY_REMOTE_COLOR, ABILITY_SHIELD_COLOR,
    ABILITY_DIARRHEA_COLOR, ABILITY_REVERSE_COLOR, ABILITY_FLOAT_COLOR,
    GameState,
)
```

Remove the original `GameState` class (lines 203–209) and all color constant lines (68–91).

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/ -v`
Expected: 99 passed

- [ ] **Step 4: Commit**

```bash
git add constants.py main.py
git commit -m "refactor: extract constants.py with colors and GameState"
```

---

### Task 3: Extract `utils.py` — coordinate tools

**Files:**
- Create: `utils.py`
- Modify: `main.py` (remove coordinate functions, import from utils)

**Interfaces:**
- Consumes: `cfg` from config
- Produces: `grid_to_pixel`, `grid_center`, `pixel_to_grid`, `clamp`, `sign`, `get_map_width`, `get_map_height`, `get_window_width`, `get_window_height`, `box_overlap`

- [ ] **Step 1: Create `utils.py`**

```python
# utils.py
from config import cfg

def grid_to_pixel(x, y):
    return (x - 1) * cfg.CELL_SIZE, cfg.UI_BAR_HEIGHT + (y - 1) * cfg.CELL_SIZE

def grid_center(x, y):
    left, top = grid_to_pixel(x, y)
    return left + cfg.CELL_SIZE // 2, top + cfg.CELL_SIZE // 2

def pixel_to_grid(px, py):
    gx = round((px - cfg.CELL_SIZE / 2) / cfg.CELL_SIZE) + 1
    gy = round((py - cfg.UI_BAR_HEIGHT - cfg.CELL_SIZE / 2) / cfg.CELL_SIZE) + 1
    return clamp(gx, 1, cfg.MAP_COLS), clamp(gy, 1, cfg.MAP_ROWS)

def clamp(val, lo, hi):
    return max(lo, min(hi, val))

def sign(x):
    if x > 0: return 1.0
    if x < 0: return -1.0
    return 0.0

def get_map_width():
    return cfg.CELL_SIZE * cfg.MAP_COLS

def get_map_height():
    return cfg.CELL_SIZE * cfg.MAP_ROWS

def get_window_width():
    return get_map_width()

def get_window_height():
    return get_map_height() + cfg.UI_BAR_HEIGHT

def box_overlap(L1, R1, T1, B1, L2, R2, T2, B2):
    return not (R1 < L2 or R2 < L1 or B1 < T2 or B2 < T1)
```

- [ ] **Step 2: Update `main.py` — replace originals with import**

Remove lines 55–65 (get_map_width/height, get_window_width/height), lines 94–119 (coordinate functions), and line 489–491 (box_overlap). Add:
```python
from utils import grid_to_pixel, grid_center, pixel_to_grid, clamp, sign, \
    get_map_width, get_map_height, get_window_width, get_window_height, box_overlap
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/ -v`
Expected: 99 passed

- [ ] **Step 4: Commit**

```bash
git add utils.py main.py
git commit -m "refactor: extract utils.py with coordinate tools"
```

---

### Task 4: Extract `models.py` — data classes + Snapshot dataclasses

**Files:**
- Create: `models.py`
- Modify: `main.py` (remove Player, Bomb, BuffItem, import from models)

**Interfaces:**
- Consumes: `cfg` from config, `pixel_to_grid`, `grid_center` from utils
- Produces: `Player`, `Bomb`, `BuffItem` + `GameSnapshot`, `PlayerSnapshot`, `BombSnapshot`, `BuffItemSnapshot`

- [ ] **Step 1: Create `models.py` with original data classes + Snapshot types**

```python
# models.py
from dataclasses import dataclass, field
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
    # ⚠️ 不包含: unknown_subtype, remote_queue, input_*, vx, vy, prev_action


@dataclass(frozen=True)
class BombSnapshot:
    id: int
    owner: str
    type: str
    pos_x: float
    pos_y: float
    grid_x: int
    grid_y: int
    fuse_frames: int  # -1 表示遥控炸弹
    vx: float
    vy: float


@dataclass(frozen=True)
class BuffItemSnapshot:
    type: str
    pos_x: float
    pos_y: float
    grid_x: int
    grid_y: int
    # ⚠️ 无 unknown_subtype


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
```

Key changes from original:
- `Player.death_timer` starts as `0` (int) not `0.0`
- `Player.invincible_timer` starts as `0` not `0.0`
- `Bomb.__init__` takes `fuse_frames` (int) instead of `timer` (float)
- `Bomb.fuse_frames` replaces `Bomb.timer`

- [ ] **Step 2: Update `main.py` — remove originals, add import**

Remove original `Player`, `Bomb`, `BuffItem` classes (lines 122–201). Add:
```python
from models import Player, Bomb, BuffItem
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/ -v`
Expected: Some tests may fail because `Bomb(fuse_frames)` replaces `Bomb(timer)` and timers changed from float to int.

- [ ] **Step 4: Fix `tests/test_utils.py::TestBomb` for new Bomb API**

Update `test_construction`:
```python
def test_construction(self, cfg):
    from models import Bomb
    b = Bomb(0, "red", "normal", 3, 5, 48)  # 48 frames = 2s at 24fps
    assert b.id == 0
    assert b.owner == "red"
    assert b.type == "normal"
    assert b.fuse_frames == 48
    assert b.vx == 0.0
    assert b.vy == 0.0
    assert b.exploding is False
    assert b.exploded is False
```

Update `test_remote_bomb_has_minus_one_timer`:
```python
def test_remote_bomb_has_minus_one_fuse(self, cfg):
    from models import Bomb
    b = Bomb(2, "blue", "remote", 1, 1, -1)
    assert b.fuse_frames == -1
```

Keep `test_grid_pos_roundtrip` unchanged (it uses `b.grid_pos()` which is unchanged logic).

- [ ] **Step 5: Fix `tests/test_utils.py::TestBuffItem` for `BUFF_PROTECTION_TIME` as int**

No change needed — `BUFF_PROTECTION_TIME` is now 7 (int), the test does `b.protection_timer -= 0.1` which still works (Python float math works on ints). But the assertion should use the new value:
```python
def test_protection_timer_decays(self, cfg):
    from models import BuffItem
    b = BuffItem("speed_plus", "", 1, 1)
    b.protection_timer -= 0.1
    assert b.protection_timer == pytest.approx(7 - 0.1)  # 7 frames ≈ 0.3s
```

- [ ] **Step 6: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: 99 passed

- [ ] **Step 7: Commit**

```bash
git add models.py main.py tests/test_utils.py
git commit -m "refactor: extract models.py with data classes + snapshot types"
```

---

### Task 5: Create `game_engine.py` — GameEngine with full game logic

**Files:**
- Create: `game_engine.py`
- Modify: `main.py` (import and integrate GameEngine, step 1: coexist)

**Interfaces:**
- Consumes: `cfg` (config), `CellType` (constants), `Player`, `Bomb`, `BuffItem`, all `*Snapshot` (models), `pixel_to_grid`, `grid_center`, `sign`, `box_overlap`, `clamp`, `get_map_width`, `get_map_height`, `get_window_width` (utils)
- Produces: `GameEngine` class with `step()`, `get_snapshot()`, `reset_match()`, `reset_round()`

**This is the core task. GameEngine takes all game state and logic from BombermanGame, converts timing to frame-based.**

- [ ] **Step 1: Create `game_engine.py` — imports and class skeleton**

```python
# game_engine.py
import random
import math
from config import cfg
from constants import GameState
from utils import pixel_to_grid, grid_center, grid_to_pixel, sign, \
    box_overlap, clamp, get_map_width, get_window_height
from models import Player, Bomb, BuffItem, \
    GameSnapshot, PlayerSnapshot, BombSnapshot, BuffItemSnapshot
```

- [ ] **Step 2: Copy all game state from BombermanGame.__init__**

```python
class GameEngine:
    def __init__(self):
        self.state = GameState.MENU
        self.grid = [[None for _ in range(cfg.MAP_ROWS + 1)] for _ in range(cfg.MAP_COLS + 1)]
        from constants import COLOR_RED, COLOR_BLUE
        self.red_player = Player("red", COLOR_RED)
        self.blue_player = Player("blue", COLOR_BLUE)
        self.bombs = []
        self.buffs = []
        self.explosion_cells = set()
        self.round_frame = 0
        self.refresh_timer = cfg.REFRESH_INTERVAL
        self.round_delay_timer = 0
        self.current_winner = ""
        self.next_bomb_id = 0
        self.safe_spots = self.compute_safe_spots()
        self.reset_match()
```

Note: `round_time` (float seconds) → `round_frame` (int). Refresh timer becomes int (frames).

- [ ] **Step 3: Copy `compute_safe_spots`, `reset_match`, `reset_round`, `generate_map`**

These methods are extracted verbatim from BombermanGame with frame adaptations:

```python
def compute_safe_spots(self):
    return {(1, 2), (2, 1), (cfg.MAP_COLS - 1, cfg.MAP_ROWS), (cfg.MAP_COLS, cfg.MAP_ROWS - 1)}

def reset_match(self):
    self.red_player.wins = 0
    self.blue_player.wins = 0
    self.reset_round()

def reset_round(self):
    self.generate_map()
    self.red_player.reset(1, 1)
    self.blue_player.reset(cfg.MAP_COLS, cfg.MAP_ROWS)
    self.bombs.clear()
    self.buffs.clear()
    self.explosion_cells.clear()
    self.round_frame = 0
    self.refresh_timer = cfg.REFRESH_INTERVAL
    self.round_delay_timer = 0
    self.current_winner = ""
    self.next_bomb_id = 0
    self.state = GameState.ROUND_RUNNING

def generate_map(self):
    for x in range(1, cfg.MAP_COLS + 1):
        for y in range(1, cfg.MAP_ROWS + 1):
            if x % 2 == 0 and y % 2 == 0:
                self.grid[x][y] = "stone"
            elif (x % 2 == 0) != (y % 2 == 0):
                if (x, y) in self.safe_spots:
                    self.grid[x][y] = "floor"
                else:
                    self.grid[x][y] = "brick" if random.random() < cfg.BRICK_GEN_PROB else "floor"
            else:
                self.grid[x][y] = "floor"
```

- [ ] **Step 4: Copy all update methods with DT_OVER_DTAU conversion**

Copy from BombermanGame and modify:
- `update_round()` → no `dt` param, call frame-based subs
- All timer decrements: `timer -= dt` → `timer -= 1`
- Movement: `vx * dt` → `vx * cfg.DT_OVER_DTAU`
- `round_time += dt` → `round_frame += 1`
- `death_timer = 0.0` → `death_timer = 0`
- `invincible_timer` is int frame count

```python
def step(self, p1_actions, p2_actions):
    """Advance one frame. dτ = 1."""
    self.apply_actions(p1_actions, p2_actions)

    if self.state == GameState.ROUND_RUNNING:
        self.update_round()
    elif self.state == GameState.ROUND_END_DELAY:
        self.update_round_delay()

    return self.get_snapshot()

def apply_actions(self, p1, p2):
    """Copy action dict into Player input fields."""
    for p, actions in [(self.red_player, p1), (self.blue_player, p2)]:
        p.input_up = actions.get("up", False)
        p.input_down = actions.get("down", False)
        p.input_left = actions.get("left", False)
        p.input_right = actions.get("right", False)
        # action and ignite are per-step, not held state
        # Build them here; player uses them same frame
        p.input_action = actions.get("action", False)
        p.input_ignite = actions.get("ignite", False)

def update_round(self):
    """One frame of game logic — no dt param."""
    self.round_frame += 1
    self.update_buff_refresh()
    self.update_buff_protection()
    self.update_player_movement()
    # Diarrhea bomb placement is handled inside movement
    self.update_bomb_timers_and_movement()
    self.process_explosions()
    self.process_player_death()
    self.process_buff_pickups()
    self.update_ability_timers()
    self.check_round_end()

def update_round_delay(self):
    self.round_delay_timer -= 1
    if self.round_delay_timer <= 0:
        self.reset_round()
```

Now copy each subsystem with the dt → DT_OVER_DTAU / -1 conversion:

```python
def update_player_movement(self):
    for p in (self.red_player, self.blue_player):
        if not p.alive:
            continue
        old_gx, old_gy = pixel_to_grid(p.pos_x, p.pos_y)
        dir_x, dir_y = self._get_input_direction(p)
        if "reverse" in p.abilities:
            dir_x = -dir_x
            dir_y = -dir_y
        speed_val = p.velocity
        if dir_x != 0 and dir_y != 0:
            speed_val *= 0.70710678
        desired_vx = dir_x * speed_val * cfg.CELL_SIZE
        desired_vy = dir_y * speed_val * cfg.CELL_SIZE
        self._move_player(p, desired_vx, desired_vy)

        if "kick" in p.abilities and (dir_x != 0 or dir_y != 0):
            self._try_kick_bomb(p, dir_x, dir_y)

        # Action (place bomb)
        if p.input_action:
            if "remote" in p.abilities:
                self._place_remote_bomb(p)
            else:
                self._place_normal_bomb(p)

        if p.input_ignite:
            if "remote" in p.abilities and p.remote_queue:
                self._detonate_earliest_remote(p)

        # Diarrhea
        self._check_diarrhea_on_move(p, old_gx, old_gy)

def _get_input_direction(self, p):
    dx, dy = 0, 0
    if p.input_up: dy -= 1
    if p.input_down: dy += 1
    if p.input_left: dx -= 1
    if p.input_right: dx += 1
    count = (p.input_up + p.input_down + p.input_left + p.input_right)
    if count > 2:
        return 0, 0
    return dx, dy

def _move_player(self, p, vx_ps, vy_ps):
    """vx_ps/vy_ps are in pixels/sec, multiply by DT_OVER_DTAU."""
    old_x, old_y = p.pos_x, p.pos_y
    dt_factor = cfg.DT_OVER_DTAU  # = 1/FPS
    new_x = old_x + vx_ps * dt_factor
    if not self._player_collision_at(p, new_x, old_y, old_x, old_y):
        p.pos_x = new_x
    new_y = old_y + vy_ps * dt_factor
    if not self._player_collision_at(p, p.pos_x, new_y, old_x, old_y):
        p.pos_y = new_y

def _player_collision_at(self, p, new_x, new_y, old_x, old_y):
    """Same logic as original — pure pixel coords, no dt."""
    half = (cfg.PLAYER_HITBOX_SIZE * cfg.CELL_SIZE) / 2
    L, R = new_x - half, new_x + half
    T, B = new_y - half, new_y + half

    if L < 0 or R > get_map_width() or T < cfg.UI_BAR_HEIGHT or B > get_window_height():
        return True

    if "float" in p.abilities:
        for cell in self._cells_overlapping(L, R, T, B):
            if self.grid[cell[0]][cell[1]] == "stone":
                return True
    else:
        for cell in self._cells_overlapping(L, R, T, B):
            if self.grid[cell[0]][cell[1]] in ("stone", "brick"):
                return True

    for other in (self.red_player, self.blue_player):
        if other is p or not other.alive:
            continue
        if box_overlap(L, R, T, B, *other.hitbox()):
            return True

    if "float" not in p.abilities:
        for bomb in self.bombs:
            bgx, bgy = bomb.grid_pos()
            new_gx, new_gy = pixel_to_grid(new_x, new_y)
            old_gx, old_gy = pixel_to_grid(old_x, old_y)
            if (new_gx, new_gy) == (bgx, bgy) and (old_gx, old_gy) != (bgx, bgy):
                return True
    return False

def _cells_overlapping(self, L, R, T, B):
    cells = set()
    min_gx = max(1, int(L // cfg.CELL_SIZE) + 1)
    max_gx = min(cfg.MAP_COLS, int((R - 1) // cfg.CELL_SIZE) + 1)
    min_gy = max(1, int((T - cfg.UI_BAR_HEIGHT) // cfg.CELL_SIZE) + 1)
    max_gy = min(cfg.MAP_ROWS, int((B - 1 - cfg.UI_BAR_HEIGHT) // cfg.CELL_SIZE) + 1)
    for gx in range(min_gx, max_gx + 1):
        for gy in range(min_gy, max_gy + 1):
            cells.add((gx, gy))
    return cells
```

- [ ] **Step 5: Copy bomb placement and kick methods**

```python
def _place_normal_bomb(self, p):
    gx, gy = pixel_to_grid(p.pos_x, p.pos_y)
    if self.grid[gx][gy] != "floor":
        return
    if p.bomb_placed_count >= p.bomb_max:
        return
    # Prevent place on existing bomb
    for b in self.bombs:
        if b.grid_pos() == (gx, gy):
            return
    self._create_bomb(p, "normal", gx, gy, cfg.BOMB_FUSE)

def _place_remote_bomb(self, p):
    gx, gy = pixel_to_grid(p.pos_x, p.pos_y)
    if self.grid[gx][gy] != "floor":
        return
    if p.bomb_placed_count >= p.bomb_max:
        return
    for b in self.bombs:
        if b.grid_pos() == (gx, gy):
            return
    self._create_bomb(p, "remote", gx, gy, -1)

def _create_bomb(self, owner, bomb_type, gx, gy, fuse):
    bomb = Bomb(self.next_bomb_id, owner, bomb_type, gx, gy, fuse)
    self.bombs.append(bomb)
    owner.bomb_placed_count += 1
    self.next_bomb_id += 1
    if bomb_type == "remote":
        owner.remote_queue.append(bomb.id)

def _detonate_earliest_remote(self, p):
    target_id = p.remote_queue.pop(0)
    for bomb in self.bombs:
        if bomb.id == target_id:
            bomb.exploding = True
            break

def _try_kick_bomb(self, p, dir_x, dir_y):
    for bomb in self.bombs:
        if self._player_touches_bomb(p, bomb):
            self._kick_bomb(bomb, dir_x, dir_y)
            break

def _player_touches_bomb(self, p, bomb):
    phalf = (cfg.PLAYER_HITBOX_SIZE * cfg.CELL_SIZE) / 2
    br = cfg.CELL_SIZE * 0.35
    return math.hypot(p.pos_x - bomb.pos_x, p.pos_y - bomb.pos_y) < (phalf + br)

def _kick_bomb(self, bomb, dx, dy):
    bomb.vx = dx * cfg.KICK_INIT_VEL * cfg.CELL_SIZE
    bomb.vy = dy * cfg.KICK_INIT_VEL * cfg.CELL_SIZE

def count_bombs_owned_by(self, owner):
    return sum(1 for b in self.bombs if b.owner is owner)
```

- [ ] **Step 6: Copy bomb timers and movement with DT_OVER_DTAU**

```python
def update_bomb_timers_and_movement(self):
    for bomb in list(self.bombs):
        if bomb.vx != 0 or bomb.vy != 0:
            self._move_bomb(bomb)
        if bomb.type in ("normal", "converted"):
            if bomb.fuse_frames > 0:
                bomb.fuse_frames -= 1
                if bomb.fuse_frames <= 0:
                    bomb.exploding = True
        if bomb.type == "remote" and "remote" not in bomb.owner.abilities:
            bomb.type = "converted"
            bomb.fuse_frames = cfg.BOMB_FUSE

def _move_bomb(self, bomb):
    dt_factor = cfg.DT_OVER_DTAU
    bomb.vx += sign(bomb.vx) * cfg.KICK_ACCEL * cfg.CELL_SIZE * dt_factor
    bomb.vy += sign(bomb.vy) * cfg.KICK_ACCEL * cfg.CELL_SIZE * dt_factor
    if abs(bomb.vx) < 0.5: bomb.vx = 0
    if abs(bomb.vy) < 0.5: bomb.vy = 0

    new_x = bomb.pos_x + bomb.vx * dt_factor
    new_y = bomb.pos_y + bomb.vy * dt_factor
    if self._bomb_collision_at(bomb, new_x, new_y):
        self._snap_bomb_to_grid_center(bomb)
        bomb.vx = bomb.vy = 0
    else:
        bomb.pos_x = new_x
        bomb.pos_y = new_y

def _bomb_collision_at(self, bomb, cx, cy):
    """Same as original — pixel coords, no dt."""
    r = cfg.CELL_SIZE * 0.35
    if cx - r < 0 or cx + r > get_map_width() or cy - r < cfg.UI_BAR_HEIGHT or cy + r > get_window_height():
        return True
    gx, gy = pixel_to_grid(cx, cy)
    if self.grid[gx][gy] in ("stone", "brick"):
        return True
    for p in (self.red_player, self.blue_player):
        if not p.alive: continue
        if math.hypot(cx - p.pos_x, cy - p.pos_y) < (cfg.PLAYER_HITBOX_SIZE * cfg.CELL_SIZE / 2 + r):
            return True
    for other in self.bombs:
        if other is bomb: continue
        if math.hypot(cx - other.pos_x, cy - other.pos_y) < 2 * r:
            return True
    return False

def _snap_bomb_to_grid_center(self, bomb):
    gx, gy = bomb.grid_pos()
    bomb.pos_x, bomb.pos_y = grid_center(gx, gy)
```

- [ ] **Step 7: Copy explosion BFS, death, buff, ability, and lifecycle methods**

```python
def process_explosions(self):
    queue = []
    for bomb in self.bombs:
        if bomb.exploding and not bomb.exploded:
            queue.append(bomb)
            bomb.exploded = True

    all_cells = set()
    bombs_to_remove = []
    buffs_to_remove = []

    while queue:
        bomb = queue.pop(0)
        cells = self._get_explosion_cells(bomb)
        all_cells.update(cells)
        for gx, gy in cells:
            for other in self.bombs:
                if not other.exploded and other.grid_pos() == (gx, gy):
                    queue.append(other)
                    other.exploded = True
                    other.exploding = True
            if self.grid[gx][gy] == "brick":
                self.grid[gx][gy] = "floor"
                if random.random() < cfg.BRICK_DROP_PROB:
                    self._spawn_buff_at(gx, gy)
            for buff in self.buffs:
                if buff.grid_pos() == (gx, gy) and buff.protection_timer <= 0:
                    if buff not in buffs_to_remove:
                        buffs_to_remove.append(buff)

    for bomb in self.bombs:
        if bomb.exploded and bomb.exploding:
            bombs_to_remove.append(bomb)
    for bomb in bombs_to_remove:
        for p in (self.red_player, self.blue_player):
            while bomb.id in p.remote_queue:
                p.remote_queue.remove(bomb.id)
        self.bombs.remove(bomb)

    for buff in buffs_to_remove:
        if buff in self.buffs:
            self.buffs.remove(buff)

    for p in (self.red_player, self.blue_player):
        p.bomb_placed_count = self.count_bombs_owned_by(p)

    self.explosion_cells = all_cells

def _get_explosion_cells(self, bomb):
    gx, gy = bomb.grid_pos()
    cells = {(gx, gy)}
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        for i in range(1, bomb.owner.blast_range + 1):
            nx, ny = gx + dx * i, gy + dy * i
            if nx < 1 or nx > cfg.MAP_COLS or ny < 1 or ny > cfg.MAP_ROWS:
                break
            cells.add((nx, ny))
            if self.grid[nx][ny] in ("stone", "brick"):
                break
    return cells

def process_player_death(self):
    for p in (self.red_player, self.blue_player):
        if not p.alive: continue
        if p.invincible_timer > 0: continue
        pgx, pgy = pixel_to_grid(p.pos_x, p.pos_y)
        if (pgx, pgy) in self.explosion_cells:
            if "shield" in p.abilities:
                del p.abilities["shield"]
                p.invincible_timer = cfg.SHIELD_INVINCIBLE_DUR
            else:
                p.alive = False
                p.death_timer = cfg.DEATH_ANIM_DUR

def update_buff_protection(self):
    for buff in self.buffs:
        if buff.protection_timer > 0:
            buff.protection_timer -= 1

def process_buff_pickups(self):
    for p in (self.red_player, self.blue_player):
        if not p.alive: continue
        for buff in self.buffs[:]:
            if math.hypot(p.pos_x - buff.pos_x, p.pos_y - buff.pos_y) < (cfg.PLAYER_HITBOX_SIZE * cfg.CELL_SIZE / 2 + 8):
                self._apply_buff(p, buff)
                self.buffs.remove(buff)

def _apply_buff(self, p, buff):
    if buff.type == "bomb_plus":
        p.perm_bomb_plus += 1
        p.bomb_max = min(cfg.INIT_BOMB_MAX + p.perm_bomb_plus, cfg.MAX_BOMB_CAP)
    elif buff.type == "blast_plus":
        p.perm_blast_plus += 1
        p.blast_range = min(cfg.INIT_BLAST_RANGE + p.perm_blast_plus, cfg.MAX_BLAST_RANGE)
    elif buff.type == "speed_plus":
        p.perm_speed_plus += 1
        p.velocity = min(cfg.INIT_SPEED + p.perm_speed_plus * cfg.SPEED_INCREMENT, cfg.MAX_SPEED)
    elif buff.type == "unknown":
        ability = buff.unknown_subtype
        duration = self._get_ability_duration(ability)
        p.abilities[ability] = duration

def _get_ability_duration(self, ability):
    return {
        "kick": cfg.DURATION_KICK,
        "remote": cfg.DURATION_REMOTE,
        "shield": cfg.DURATION_SHIELD,
        "diarrhea": cfg.DURATION_DIARRHEA,
        "reverse": cfg.DURATION_REVERSE,
        "float": cfg.DURATION_FLOAT,
    }.get(ability, 10)

def update_buff_refresh(self):
    self.refresh_timer -= 1
    if self.refresh_timer <= 0:
        self._spawn_random_buff()
        self.refresh_timer += cfg.REFRESH_INTERVAL

def _spawn_random_buff(self):
    for _ in range(100):
        gx = random.randint(1, cfg.MAP_COLS)
        gy = random.randint(1, cfg.MAP_ROWS)
        if (self.grid[gx][gy] == "floor"
                and not self._is_player_at(gx, gy)
                and not self._is_bomb_at(gx, gy)
                and not self._is_buff_at(gx, gy)):
            self._spawn_buff_at(gx, gy)
            return

def _spawn_buff_at(self, gx, gy):
    r = random.random()
    cum = 0
    weights = [cfg.WEIGHT_BOMB_PLUS, cfg.WEIGHT_BLAST_PLUS, cfg.WEIGHT_SPEED_PLUS, cfg.WEIGHT_UNKNOWN]
    for i, w in enumerate(weights):
        cum += w
        if r < cum:
            if i == 0:
                self.buffs.append(BuffItem("bomb_plus", "", gx, gy))
            elif i == 1:
                self.buffs.append(BuffItem("blast_plus", "", gx, gy))
            elif i == 2:
                self.buffs.append(BuffItem("speed_plus", "", gx, gy))
            else:
                sub = random.choice(["kick", "remote", "shield", "diarrhea", "reverse", "float"])
                self.buffs.append(BuffItem("unknown", sub, gx, gy))
            return

def _is_player_at(self, gx, gy):
    for p in (self.red_player, self.blue_player):
        if p.alive and pixel_to_grid(p.pos_x, p.pos_y) == (gx, gy):
            return True
    return False

def _is_bomb_at(self, gx, gy):
    for b in self.bombs:
        if b.grid_pos() == (gx, gy):
            return True
    return False

def _is_buff_at(self, gx, gy):
    for b in self.buffs:
        if b.grid_pos() == (gx, gy):
            return True
    return False

def update_ability_timers(self):
    for p in (self.red_player, self.blue_player):
        for ability in list(p.abilities.keys()):
            p.abilities[ability] -= 1
            if p.abilities[ability] <= 0:
                self._remove_ability(p, ability)
        if p.invincible_timer > 0:
            p.invincible_timer -= 1
        if not p.alive and p.death_timer > 0:
            p.death_timer -= 1

def _remove_ability(self, p, ability):
    if ability not in p.abilities:
        return
    del p.abilities[ability]
    if ability == "remote":
        p.remote_queue.clear()
        for bomb in self.bombs:
            if bomb.owner is p and bomb.type == "remote":
                bomb.type = "converted"
                bomb.fuse_frames = cfg.BOMB_FUSE
    elif ability == "float":
        self._handle_float_end(p)

def _handle_float_end(self, p):
    gx, gy = pixel_to_grid(p.pos_x, p.pos_y)
    needs_evict = (self.grid[gx][gy] == "brick") or self._is_bomb_at(gx, gy)
    if not needs_evict:
        return
    candidates = []
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        nx, ny = gx + dx, gy + dy
        if nx < 1 or nx > cfg.MAP_COLS or ny < 1 or ny > cfg.MAP_ROWS:
            continue
        if self.grid[nx][ny] == "floor" and not self._is_player_at(nx, ny) and not self._is_bomb_at(nx, ny):
            cx, cy = grid_center(nx, ny)
            dist = abs(p.pos_x - cx) + abs(p.pos_y - cy)
            candidates.append((dist, (nx, ny)))
    if candidates:
        candidates.sort(key=lambda x: x[0])
        target_gx, target_gy = candidates[0][1]
        old_gx, old_gy = pixel_to_grid(p.pos_x, p.pos_y)
        p.pos_x, p.pos_y = grid_center(target_gx, target_gy)
        if "diarrhea" in p.abilities:
            self._check_diarrhea_on_move(p, old_gx, old_gy)
    else:
        self._kill_player(p)

def _check_diarrhea_on_move(self, p, old_gx, old_gy):
    if not p.alive or "diarrhea" not in p.abilities:
        return
    new_gx, new_gy = pixel_to_grid(p.pos_x, p.pos_y)
    if (new_gx, new_gy) != (old_gx, old_gy):
        if self.grid[new_gx][new_gy] == "floor" and not self._is_bomb_at(new_gx, new_gy):
            if p.bomb_placed_count < p.bomb_max:
                self._create_bomb(p, "normal", new_gx, new_gy, cfg.BOMB_FUSE)

def _kill_player(self, p):
    p.alive = False
    p.death_timer = 0

def check_round_end(self):
    red_alive = self.red_player.alive
    blue_alive = self.blue_player.alive
    if red_alive and blue_alive:
        return

    red_dead = not red_alive
    blue_dead = not blue_alive

    if red_dead and blue_dead:
        self._start_round_delay("")
        return

    if red_dead and blue_alive:
        if self.red_player.death_timer <= 0:
            self.blue_player.wins += 1
            if self.blue_player.wins >= cfg.WIN_SCORE:
                self.state = GameState.MATCH_END
            else:
                self._start_round_delay("blue")
    elif blue_dead and red_alive:
        if self.blue_player.death_timer <= 0:
            self.red_player.wins += 1
            if self.red_player.wins >= cfg.WIN_SCORE:
                self.state = GameState.MATCH_END
            else:
                self._start_round_delay("red")

def _start_round_delay(self, winner_id):
    self.current_winner = winner_id
    self.state = GameState.ROUND_END_DELAY
    self.round_delay_timer = cfg.ROUND_DELAY
```

- [ ] **Step 8: Implement `get_snapshot()`**

```python
# CellType encoding for map_grid
CELL_EMPTY = 0
CELL_STONE = 1
CELL_BRICK = 2
CELL_BUFF = 3
CELL_BOMB = 4
CELL_EXPLOSION = 5

def get_snapshot(self):
    """Build a read-only GameSnapshot from current engine state."""
    # Build map_grid (COLS × ROWS)
    map_grid = [[CELL_EMPTY for _ in range(cfg.MAP_ROWS + 1)] for _ in range(cfg.MAP_COLS + 1)]
    for x in range(1, cfg.MAP_COLS + 1):
        for y in range(1, cfg.MAP_ROWS + 1):
            cell = self.grid[x][y]
            if cell == "stone":
                map_grid[x][y] = CELL_STONE
            elif cell == "brick":
                map_grid[x][y] = CELL_BRICK
            elif cell == "floor":
                map_grid[x][y] = CELL_EMPTY

    # Overlay buffs
    for buff in self.buffs:
        gx, gy = buff.grid_pos()
        map_grid[gx][gy] = CELL_BUFF

    # Overlay bombs
    for bomb in self.bombs:
        gx, gy = bomb.grid_pos()
        map_grid[gx][gy] = CELL_BOMB

    # Overlay explosions
    for gx, gy in self.explosion_cells:
        map_grid[gx][gy] = CELL_EXPLOSION

    # Player snapshots
    def _psnap(p):
        gx, gy = pixel_to_grid(p.pos_x, p.pos_y)
        return PlayerSnapshot(
            id=p.id, color=p.color,
            pos_x=p.pos_x, pos_y=p.pos_y,
            grid_x=gx, grid_y=gy,
            alive=p.alive, velocity=p.velocity,
            death_timer=p.death_timer,
            bomb_max=p.bomb_max, bomb_placed_count=p.bomb_placed_count,
            blast_range=p.blast_range, invincible_timer=p.invincible_timer,
            wins=p.wins,
            perm_bomb_plus=p.perm_bomb_plus,
            perm_blast_plus=p.perm_blast_plus,
            perm_speed_plus=p.perm_speed_plus,
            abilities=dict(p.abilities),
        )

    # Bomb snapshots
    def _bsnap(b):
        gx, gy = pixel_to_grid(b.pos_x, b.pos_y)
        return BombSnapshot(
            id=b.id, owner=b.owner, type=b.type,
            pos_x=b.pos_x, pos_y=b.pos_y,
            grid_x=gx, grid_y=gy,
            fuse_frames=b.fuse_frames,
            vx=b.vx, vy=b.vy,
        )

    # Buff snapshots
    def _bufsnap(b):
        gx, gy = b.grid_pos()
        return BuffItemSnapshot(
            type=b.type,
            pos_x=b.pos_x, pos_y=b.pos_y,
            grid_x=gx, grid_y=gy,
            # ⚠️ no unknown_subtype
        )

    return GameSnapshot(
        state=self.state,
        round_frame=self.round_frame,
        map_grid=map_grid,
        players=(_psnap(self.red_player), _psnap(self.blue_player)),
        bombs=tuple(_bsnap(b) for b in self.bombs),
        buffs=tuple(_bufsnap(b) for b in self.buffs),
        explosion_cells=tuple(self.explosion_cells),
        scores={"red": self.red_player.wins, "blue": self.blue_player.wins},
    )
```

- [ ] **Step 9: Write a quick smoke test**

Create a tiny script or test to verify GameEngine runs without pygame:
```python
# test_engine_smoke.py
from game_engine import GameEngine
engine = GameEngine()
snap = engine.step({"up": False, "down": False, "left": False, "right": False,
                     "action": False, "ignite": False},
                    {"up": False, "down": False, "left": False, "right": False,
                     "action": False, "ignite": False})
assert snap.state == 1  # ROUND_RUNNING
assert len(snap.players) == 2
assert snap.map_grid is not None
print("GameEngine smoke test PASSED")
```

Run: `python test_engine_smoke.py` (no pygame needed — the SDL_VIDEODRIVER=dummy env var not needed here since GameEngine has no pygame imports)
Expected: `GameEngine smoke test PASSED`

- [ ] **Step 10: Commit**

```bash
git add game_engine.py test_engine_smoke.py
git commit -m "feat: create GameEngine with full game logic and frame-based timing"
```

---

### Task 6: Refactor BombermanGame to delegate to GameEngine

**Files:**
- Modify: `main.py` (BombermanGame now wraps GameEngine)

- [ ] **Step 1: Refactor `BombermanGame.__init__` to create a GameEngine**

```python
class BombermanGame:
    def __init__(self):
        pygame.init()
        self.engine = GameEngine()  # ← all game state lives here
        self.screen = pygame.display.set_mode(
            (get_window_width(), get_window_height()), pygame.RESIZABLE)
        pygame.display.set_caption("炸弹人 双人PVP v2.8")
        self.clock = pygame.time.Clock()
        self.running = True
        # Keep font objects (rendering concern)
        self.font_small = pygame.font.Font(None, 18)
        self.font_medium = pygame.font.Font(None, 24)
        self.font_big = pygame.font.Font(None, 48)
        # Input state (kept in BombermanGame as before)
        self.keys_red = {'W': False, 'A': False, 'S': False, 'D': False, 'E': False, 'Q': False}
        self.keys_blue = {'UP': False, 'LEFT': False, 'DOWN': False, 'RIGHT': False, 'DEL': False, 'END': False}
        # Settings
        self.show_settings = False
        self.settings_pause_state = None
        self.settings_buttons = []
        self.settings_scroll = 0
        self.init_settings_ui()
        # Previous references kept as properties for backward compat
        self.state = self.engine.state
```

- [ ] **Step 2: Forward game state access through engine**

Remove all direct state fields (`self.grid`, `self.red_player`, etc.) and replace with properties:
```python
@property
def grid(self): return self.engine.grid

@property
def red_player(self): return self.engine.red_player

@property
def blue_player(self): return self.engine.blue_player

@property
def bombs(self): return self.engine.bombs

@property
def buffs(self): return self.engine.buffs

@property
def explosion_cells(self): return self.engine.explosion_cells

@property
def state(self): return self.engine.state

@state.setter
def state(self, val): self.engine.state = val
```

- [ ] **Step 3: Refactor `update()` and `update_round()` to call engine**

```python
def update(self, _dt_unused=None):
    # Read keyboard → build action dicts
    p1_actions = self._build_red_actions()
    p2_actions = self._build_blue_actions()
    self.engine.step(p1_actions, p2_actions)
    # Sync state reference
    self._state = self.engine.state

def _build_red_actions(self):
    return {
        "up": self.keys_red['W'],
        "down": self.keys_red['S'],
        "left": self.keys_red['A'],
        "right": self.keys_red['D'],
        "action": self.keys_red['E'] and not self.red_player.prev_action,
        "ignite": self.keys_red['Q'],
    }

def _build_blue_actions(self):
    return {
        "up": self.keys_blue['UP'],
        "down": self.keys_blue['DOWN'],
        "left": self.keys_blue['LEFT'],
        "right": self.keys_blue['RIGHT'],
        "action": self.keys_blue['DEL'] and not self.blue_player.prev_action,
        "ignite": self.keys_blue['END'],
    }
```

- [ ] **Step 4: Remove all update methods from BombermanGame**

Remove (they live in GameEngine now):
- `update_player_movement`, `get_input_direction`, `move_player`, `player_collision_at`, `cells_overlapping`
- `try_kick_bomb`, `player_touches_bomb`, `kick_bomb`
- `place_normal_bomb`, `place_remote_bomb`, `create_bomb`, `detonate_earliest_remote`
- `count_bombs_owned_by`
- `update_bomb_timers_and_movement`, `move_bomb`, `bomb_collision_at`, `snap_bomb_to_grid_center`
- `process_explosions`, `get_explosion_cells`
- `process_player_death`
- `update_buff_protection`, `process_buff_pickups`, `apply_buff`, `get_ability_duration`
- `update_buff_refresh`, `spawn_random_buff`, `spawn_buff_at`
- `is_player_at`, `is_bomb_at`, `is_buff_at`
- `update_ability_timers`, `remove_ability`, `handle_float_end`, `check_diarrhea_on_move`
- `kill_player`
- `check_round_end`, `start_round_delay`, `update_round_delay`
- `reset_match`, `reset_round`, `generate_map`, `compute_safe_spots`

Remove `sync_input()` — input is now handled by `_build_*_actions()`.

- [ ] **Step 5: Refactor `handle_events()`**

Keep pygame event handling, remove `self.sync_input()`:
```python
def handle_events(self):
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN:
            self.handle_key(event.key, True)
        elif event.type == pygame.KEYUP:
            self.handle_key(event.key, False)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if self.state in (GameState.SETTINGS, GameState.SETTINGS_PAUSED):
                self.handle_settings_click(event.pos)
```

- [ ] **Step 6: Run tests (some may fail due to API changes)**

Run: `python -m pytest tests/ -v`

- [ ] **Step 7: Fix `conftest.py` `game` fixture and update test references**

Update `conftest.py`:
```python
@pytest.fixture
def game():
    from main import BombermanGame
    g = BombermanGame()
    return g
```
(The fixture itself may still work but some tests access `game.grid` etc. which now go through properties — they should still work if the properties are correct.)

Tests that call `game.get_input_direction(p)` will fail since that method moved to engine. Fix by accessing `game.engine._get_input_direction(p)` or by adding a public method.

For the test `test_opposing_directions_cancel`, update:
```python
def test_opposing_directions_cancel(self, game):
    p = game.red_player
    p.input_up = True
    p.input_down = True
    assert game.engine._get_input_direction(p) == (0, 0)
    p.input_up = p.input_down = False
    p.input_left = p.input_right = True
    assert game.engine._get_input_direction(p) == (0, 0)
```

Similarly update other tests that call BombermanGame methods directly — they now go through engine.

- [ ] **Step 8: Run tests until all pass**

Run: `python -m pytest tests/ -v`
Expected: 99 passed

- [ ] **Step 9: Run game to verify visual behavior**

Run: `python main.py`
Expected: Game starts and plays identically to before (speed feels same, bombs explode at same rate).

- [ ] **Step 10: Commit**

```bash
git add main.py tests/conftest.py tests/test_game_mechanics.py
git commit -m "refactor: BombermanGame delegates to GameEngine, remove duplicate logic"
```

---

### Task 7: Extract `renderer.py` — all drawing logic

**Files:**
- Create: `renderer.py`
- Modify: `main.py` (remove render methods, import Renderer)

- [ ] **Step 1: Create `renderer.py`**

Move all rendering methods from `BombermanGame.render()` into a `Renderer` class that takes `pygame.surface` and `GameSnapshot`:

```python
# renderer.py
import pygame
import math
import random
from config import cfg
from constants import *
from utils import grid_to_pixel, grid_center, get_map_width, get_window_height
from models import GameSnapshot

class Renderer:
    def __init__(self, screen):
        self.screen = screen
        self.font_small = pygame.font.Font(None, 18)
        self.font_medium = pygame.font.Font(None, 24)
        self.font_big = pygame.font.Font(None, 48)

    def draw(self, snapshot):
        """Main draw call — reads GameSnapshot only."""
        self.screen.fill(COLOR_BG)
        self._draw_map(snapshot)
        self._draw_buffs(snapshot)
        self._draw_bombs(snapshot)
        self._draw_explosions(snapshot)
        self._draw_players(snapshot)
        self._draw_ui_bar(snapshot)

    def _draw_map(self, snap):
        """Draw terrain grid from snap.map_grid using CellType enum."""
        # Read original code at main.py lines 868-900 for reference
        # Replace self.grid[x][y] with CellType decoding:
        cell_colors = {0: COLOR_FLOOR, 1: COLOR_STONE, 2: COLOR_BRICK}
        for gx in range(1, cfg.MAP_COLS + 1):
            for gy in range(1, cfg.MAP_ROWS + 1):
                cell = snap.map_grid[gx][gy]
                if cell in cell_colors:
                    left, top = grid_to_pixel(gx, gy)
                    rect = (left, top, cfg.CELL_SIZE, cfg.CELL_SIZE)
                    pygame.draw.rect(self.screen, cell_colors[cell], rect)
                    if cell == 1:  # stone outline
                        pygame.draw.rect(self.screen, (60, 60, 60), rect, 1)
                else:
                    # Buff/Bomb/Explosion — draw floor underneath
                    left, top = grid_to_pixel(gx, gy)
                    pygame.draw.rect(self.screen, COLOR_FLOOR,
                                     (left, top, cfg.CELL_SIZE, cfg.CELL_SIZE))
        # Grid lines
        for gx in range(1, cfg.MAP_COLS + 2):
            x = (gx - 1) * cfg.CELL_SIZE
            pygame.draw.line(self.screen, (180, 180, 180), (x, cfg.UI_BAR_HEIGHT),
                             (x, get_window_height()), 1)
        for gy in range(1, cfg.MAP_ROWS + 2):
            y = cfg.UI_BAR_HEIGHT + (gy - 1) * cfg.CELL_SIZE
            pygame.draw.line(self.screen, (180, 180, 180), (0, y),
                             (get_map_width(), y), 1)

    def _draw_buffs(self, snap):
        """Draw buff items using geometric shapes (same as original)."""
        for buff in snap.buffs:
            cx, cy = buff.pos_x, buff.pos_y
            r = cfg.CELL_SIZE * 0.3
            color = BUFF_BOMB_COLOR  # default
            if buff.type == "bomb_plus":
                color = BUFF_BOMB_COLOR
            elif buff.type == "blast_plus":
                color = BUFF_BLAST_COLOR
            elif buff.type == "speed_plus":
                color = BUFF_SPEED_COLOR
            elif buff.type == "unknown":
                color = BUFF_UNKNOWN_COLOR
            pygame.draw.ellipse(self.screen, color, (cx - r, cy - r, 2 * r, 2 * r))
            # Draw question mark for unknown
            if buff.type == "unknown":
                text = self.font_small.render("?", True, (255, 255, 255))
                self.screen.blit(text, (cx - 4, cy - 8))

    def _draw_bombs(self, snap):
        """Draw bombs with spark effect."""
        for bomb in snap.bombs:
            cx, cy = bomb.pos_x, bomb.pos_y
            r = cfg.CELL_SIZE * 0.35
            # Bomb body
            color = COLOR_BOMB_BODY
            if bomb.type == "remote":
                color = (50, 50, 150)  # bluish for remote
            elif bomb.type == "converted":
                color = (80, 80, 80)   # darker for converted
            pygame.draw.circle(self.screen, color, (int(cx), int(cy)), int(r))
            # Spark / fuse (only for ticking bombs)
            if bomb.fuse_frames > 0 and bomb.fuse_frames < cfg.BOMB_FLICKER_START:
                # Flicker intensity increases as fuse runs out
                intensity = random.randint(0, 255)
                spark_color = (255, intensity, 0)
                pygame.draw.circle(self.screen, spark_color, (int(cx), int(cy)), int(r * 0.4))

    def _draw_explosions(self, snap):
        """Draw explosion cells with randomized intensity."""
        for gx, gy in snap.explosion_cells:
            left, top = grid_to_pixel(gx, gy)
            intensity = random.randint(150, 255)
            color = (intensity, intensity // 2, 0)
            pygame.draw.rect(self.screen, color,
                             (left, top, cfg.CELL_SIZE, cfg.CELL_SIZE))

    def _draw_players(self, snap):
        """Draw both players with direction-facing eyes and shield aura."""
        for ps in snap.players:
            if not ps.alive:
                continue
            cx, cy = ps.pos_x, ps.pos_y
            half = cfg.CELL_SIZE * cfg.PLAYER_HITBOX_SIZE / 2
            # Shield aura
            if ps.invincible_timer > 0:
                glow = pygame.Surface((cfg.CELL_SIZE, cfg.CELL_SIZE), pygame.SRCALPHA)
                glow.fill((COLOR_SHIELD[0], COLOR_SHIELD[1], COLOR_SHIELD[2], 80))
                self.screen.blit(glow, (cx - cfg.CELL_SIZE // 2, cy - cfg.CELL_SIZE // 2))
            # Body
            pygame.draw.rect(self.screen, ps.color,
                             (cx - half, cy - half, half * 2, half * 2),
                             border_radius=4)
            # Direction eyes (same as original — eyes toward direction of last move)
            # Original code reads direction from vx/vy, simplified here:
            eye_radius = 3
            for dx, dy in [(-1, -1), (1, -1)]:  # two eyes
                ex = cx + dx * 5
                ey = cy + dy * 5
                pygame.draw.circle(self.screen, (255, 255, 255), (int(ex), int(ey)), eye_radius)
                pygame.draw.circle(self.screen, (0, 0, 0), (int(ex), int(ey)), 1)

    def _draw_ui_bar(self, snap):
        """Draw top UI bar with scores, bomb indicators, ability icons."""
        # Background
        pygame.draw.rect(self.screen, COLOR_UI_BAR_BG,
                         (0, 0, get_window_width(), cfg.UI_BAR_HEIGHT))
        # Scores
        score_text = self.font_big.render(
            f"{snap.scores['red']} - {snap.scores['blue']}", True, COLOR_TEXT)
        self.screen.blit(score_text, (get_map_width() // 2 - 30, 10))
        # Player indicators
        for i, ps in enumerate(snap.players):
            x_base = 10 if i == 0 else get_map_width() - 200
            # Name
            name = self.font_small.render(
                f"P{i+1} ({ps.id})", True, ps.color)
            self.screen.blit(name, (x_base, 5))
            # Bomb count
            bomb_info = self.font_small.render(
                f"Bombs: {ps.bomb_placed_count}/{ps.bomb_max} Range: {ps.blast_range}",
                True, COLOR_TEXT)
            self.screen.blit(bomb_info, (x_base, 25))
            # Speed
            speed_info = self.font_small.render(
                f"Speed: {ps.velocity:.1f}", True, COLOR_TEXT)
            self.screen.blit(speed_info, (x_base, 45))
            # Ability icons (small colored squares with letters)
            y_off = 25
            for ability, remaining in ps.abilities.items():
                color_map = {
                    "kick": ABILITY_KICK_COLOR, "remote": ABILITY_REMOTE_COLOR,
                    "shield": ABILITY_SHIELD_COLOR, "diarrhea": ABILITY_DIARRHEA_COLOR,
                    "reverse": ABILITY_REVERSE_COLOR, "float": ABILITY_FLOAT_COLOR,
                }
                icon_color = color_map.get(ability, (200, 200, 200))
                icon_x = x_base + (list(ps.abilities.keys()).index(ability)) * 30 + 100
                if i == 0:
                    icon_x = x_base + (list(ps.abilities.keys()).index(ability)) * 30 + 150
                pygame.draw.rect(self.screen, icon_color,
                                 (icon_x, y_off, 20, 20))
                # Letter
                letter = ability[0].upper()
                let = self.font_small.render(letter, True, (255, 255, 255))
                self.screen.blit(let, (icon_x + 6, y_off + 2))
```

Copy all original drawing code (lines 868–1171 from original `main.py`) into the `Renderer` class. Adapt references:
- `self.grid` → `snapshot.map_grid` (with CellType enum decoding)
- `self.red_player` → `snapshot.players[0]` (or [0] for red, [1] for blue)
- `self.bombs` → `snapshot.bombs`
- `self.buffs` → `snapshot.buffs`
- `self.explosion_cells` → `snapshot.explosion_cells`
- `self.round_time` → `snapshot.round_frame / cfg.FPS` (for display)
- `self.current_winner` → this needs to be added to the engine/state... 

Actually, `current_winner` is not in GameSnapshot yet. Add it to the snapshot: `current_winner: str` field in `GameSnapshot`, and set it in `get_snapshot()`.

- [ ] **Step 2: Update `GameSnapshot` to include `current_winner`**

In `models.py`:
```python
@dataclass(frozen=True)
class GameSnapshot:
    ...
    current_winner: str = ""  # "red", "blue", or ""
```

In `game_engine.py`, update `get_snapshot()`:
```python
return GameSnapshot(
    ...
    current_winner=self.current_winner,
)
```

- [ ] **Step 3: Wire Renderer into BombermanGame**

```python
# main.py
from renderer import Renderer

class BombermanGame:
    def __init__(self):
        ...
        self.renderer = Renderer(self.screen)

    def render(self):
        snapshot = self.engine.get_snapshot()
        self.renderer.draw(snapshot)
```

Remove all rendering methods from BombermanGame (the entire `render()` method and everything under it up to the settings UI section).

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/ -v`
Expected: All pass (rendering changes don't affect tests)

- [ ] **Step 5: Run game to verify rendering**

Run: `python main.py`
Expected: Game looks identical

- [ ] **Step 6: Commit**

```bash
git add renderer.py models.py game_engine.py main.py
git commit -m "refactor: extract Renderer, read GameSnapshot for drawing"
```

---

### Task 8: Extract `input_handler.py` — keyboard input

**Files:**
- Create: `input_handler.py`
- Modify: `main.py` (remove input handling, use InputHandler)

- [ ] **Step 1: Create `input_handler.py`**

```python
# input_handler.py
import pygame
from config import cfg
from constants import GameState

class InputHandler:
    def __init__(self):
        self.keys_red = {'W': False, 'A': False, 'S': False, 'D': False, 'E': False, 'Q': False}
        self.keys_blue = {'UP': False, 'LEFT': False, 'DOWN': False, 'RIGHT': False, 'DEL': False, 'END': False}
        self.running = True

    def handle_events(self, state=None):
        """Process pygame events. Returns (p1_actions, p2_actions) or None if quit."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return None
            elif event.type == pygame.KEYDOWN:
                self._handle_key(event.key, True, state)
            elif event.type == pygame.KEYUP:
                self._handle_key(event.key, False, state)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # Settings click — return special signal
                if state in (GameState.SETTINGS, GameState.SETTINGS_PAUSED):
                    return ("settings_click", event.pos)

        p1 = self._build_actions(self.keys_red)
        p2 = self._build_actions(self.keys_blue)
        return (p1, p2)

    def _handle_key(self, key, pressed, state):
        """Key mapping (same as original handle_key)."""
        if state == GameState.MENU:
            if pressed and key == pygame.K_RETURN:
                return  # signal to caller
            return
        if key == pygame.K_p and pressed:
            return  # toggle settings signal
        # Red keys
        if key == pygame.K_w: self.keys_red['W'] = pressed
        elif key == pygame.K_a: self.keys_red['A'] = pressed
        elif key == pygame.K_s: self.keys_red['S'] = pressed
        elif key == pygame.K_d: self.keys_red['D'] = pressed
        elif key == pygame.K_e: self.keys_red['E'] = pressed
        elif key == pygame.K_q: self.keys_red['Q'] = pressed
        # Blue keys
        elif key == pygame.K_UP: self.keys_blue['UP'] = pressed
        elif key == pygame.K_LEFT: self.keys_blue['LEFT'] = pressed
        elif key == pygame.K_DOWN: self.keys_blue['DOWN'] = pressed
        elif key == pygame.K_RIGHT: self.keys_blue['RIGHT'] = pressed
        elif key == pygame.K_DELETE: self.keys_blue['DEL'] = pressed
        elif key == pygame.K_END: self.keys_blue['END'] = pressed

    def _build_actions(self, keys):
        prev_action = getattr(self, '_prev_action', False)
        cur_action = keys.get('E' if keys is self.keys_red else 'DEL', False)
        self._prev_action = cur_action  # simplified — need per-player prev_action

    # Actually: prev_action must be per-player since each has separate key
```

Wait, `prev_action` is per-player. Let me redesign:

```python
class InputHandler:
    def __init__(self):
        self.keys_red = {'W': False, 'A': False, 'S': False, 'D': False, 'E': False, 'Q': False}
        self.keys_blue = {'UP': False, 'LEFT': False, 'DOWN': False, 'RIGHT': False, 'DEL': False, 'END': False}
        self.red_prev_action = False
        self.blue_prev_action = False
        self.running = True

    def handle_events(self, state=None):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return None
            elif event.type == pygame.KEYDOWN:
                self._handle_key(event.key, True, state)
            elif event.type == pygame.KEYUP:
                self._handle_key(event.key, False, state)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if state in (GameState.SETTINGS, GameState.SETTINGS_PAUSED):
                    return ("settings_click", event.pos)

        p1 = self._build_red_actions()
        p2 = self._build_blue_actions()
        return (p1, p2, self._settings_toggle)
```

This is getting complex. Let me simplify — keep the event handling logic in BombermanGame for now and extract it later. The `input_handler.py` extraction can be done in a separate pass.

Actually, the skill says "Each task should produce self-contained changes that make sense independently." Let me keep input simpler. I'll have InputHandler just handle key state tracking, and BombermanGame still handles the event loop and settings toggling.

- [ ] **Step 1: Create `input_handler.py` with per-player key tracking + action building**

Reference implementation (simplified from the original sync_input logic):

```python
class InputHandler:
    def __init__(self):
        self.keys = {
            "red": {'W': False, 'A': False, 'S': False, 'D': False, 'E': False, 'Q': False},
            "blue": {'UP': False, 'LEFT': False, 'DOWN': False, 'RIGHT': False, 'DEL': False, 'END': False},
        }
        self.prev_action = {"red": False, "blue": False}

    def press(self, key):
        """Call on KEYDOWN."""
        self._set(key, True)

    def release(self, key):
        """Call on KEYUP."""
        self._set(key, False)

    def _set(self, key, value):
        if key == pygame.K_w: self.keys["red"]['W'] = value
        elif key == pygame.K_a: self.keys["red"]['A'] = value
        elif key == pygame.K_s: self.keys["red"]['S'] = value
        elif key == pygame.K_d: self.keys["red"]['D'] = value
        elif key == pygame.K_e: self.keys["red"]['E'] = value
        elif key == pygame.K_q: self.keys["red"]['Q'] = value
        elif key == pygame.K_UP: self.keys["blue"]['UP'] = value
        elif key == pygame.K_LEFT: self.keys["blue"]['LEFT'] = value
        elif key == pygame.K_DOWN: self.keys["blue"]['DOWN'] = value
        elif key == pygame.K_RIGHT: self.keys["blue"]['RIGHT'] = value
        elif key == pygame.K_DELETE: self.keys["blue"]['DEL'] = value
        elif key == pygame.K_END: self.keys["blue"]['END'] = value

    def build_actions(self):
        """Return (p1_actions, p2_actions) from current key state."""
        p1 = self._player_actions(self.keys["red"], self.prev_action["red"])
        p2 = self._player_actions(self.keys["blue"], self.prev_action["blue"])
        # Update prev_action with edge-trigger for next frame
        self.prev_action["red"] = p1["action"]
        self.prev_action["blue"] = p2["action"]
        return p1, p2

    @staticmethod
    def _player_actions(keys, prev_action):
        cur_action = keys.get('E' if 'E' in keys else 'DEL', False)
        # Edge trigger: only true on rising edge
        action_triggered = cur_action and not prev_action
        return {
            "up": keys.get('W', keys.get('UP', False)),
            "down": keys.get('S', keys.get('DOWN', False)),
            "left": keys.get('A', keys.get('LEFT', False)),
            "right": keys.get('D', keys.get('RIGHT', False)),
            "action": action_triggered,
            "ignite": keys.get('Q', keys.get('END', False)),
        }
```

- [ ] **Step 2: Wire into BombermanGame**

```python
# main.py
from input_handler import InputHandler

class BombermanGame:
    def __init__(self):
        ...
        self.input_handler = InputHandler()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self.input_handler.press(event.key)
                self._check_menu_key(event.key)
            elif event.type == pygame.KEYUP:
                self.input_handler.release(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if self.state in (GameState.SETTINGS, GameState.SETTINGS_PAUSED):
                    self.handle_settings_click(event.pos)

    def update(self, _dt_unused=None):
        p1_actions, p2_actions = self.input_handler.build_actions()
        self.engine.step(p1_actions, p2_actions)
```

Remove `self.keys_red`, `self.keys_blue` fields from BombermanGame.__init__.
Remove `sync_input()`, `handle_key()`, `_build_red_actions()`, `_build_blue_actions()`.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/ -v`
Expected: All pass (input refactor doesn't affect test game fixture logic)

- [ ] **Step 4: Run game to verify controls**

Run: `python main.py`
Expected: Both players' controls work exactly as before

- [ ] **Step 5: Commit**

```bash
git add input_handler.py main.py
git commit -m "refactor: extract InputHandler for key state management"
```

---

### Task 9: Extract `settings_ui.py`

**Files:**
- Create: `settings_ui.py`
- Modify: `main.py` (remove settings code, use SettingsUI)

- [ ] **Step 1: Create `settings_ui.py`**

Move settings panel drawing and parameter list into a `SettingsUI` class.

```python
# settings_ui.py
import pygame
from config import cfg
from constants import COLOR_TEXT, COLOR_BG
from utils import get_window_width, get_window_height, get_map_width

class SettingsUI:
    def __init__(self):
        self.font = pygame.font.Font(None, 30)
        self.font_small = pygame.font.Font(None, 18)
        self.scroll = 0
        self.param_list = [
            ("CELL_SIZE", "int", 20, 80),
            ("MAP_COLS", "int", 13, 25),
            ("MAP_ROWS", "int", 9, 15),
            ("BRICK_GEN_PROB", "float", 0.0, 1.0),
            ("INIT_SPEED", "float", 0.5, 5.0),
            ("SPEED_INCREMENT", "float", 0.1, 1.0),
            ("MAX_SPEED", "float", 2.0, 10.0),
            ("INIT_BOMB_MAX", "int", 1, 10),
            ("MAX_BOMB_CAP", "int", 1, 15),
            ("INIT_BLAST_RANGE", "int", 1, 10),
            ("MAX_BLAST_RANGE", "int", 1, 15),
            ("BOMB_FUSE", "int", 12, 240),           # was float 1-10 (×24)
            ("BOMB_FLICKER_START", "int", 2, 120),    # was float 0.1-5
            ("KICK_INIT_VEL", "float", 1.0, 10.0),
            ("KICK_ACCEL", "float", -5.0, -0.1),
            ("DEATH_ANIM_DUR", "int", 2, 48),         # was float 0.1-2
            ("SHIELD_INVINCIBLE_DUR", "int", 2, 48),   # was float 0.1-2
            ("WIN_SCORE", "int", 1, 20),
            ("ROUND_DELAY", "int", 24, 240),          # was float 1-10
            ("BRICK_DROP_PROB", "float", 0.0, 1.0),
            ("BUFF_PROTECTION_TIME", "int", 1, 120),  # was float 0.1-5
            ("REFRESH_INTERVAL", "int", 120, 1440),   # was float 5-60
            ("WEIGHT_BOMB_PLUS", "float", 0.0, 1.0),
            ("WEIGHT_BLAST_PLUS", "float", 0.0, 1.0),
            ("WEIGHT_SPEED_PLUS", "float", 0.0, 1.0),
            ("WEIGHT_UNKNOWN", "float", 0.0, 1.0),
            ("DURATION_KICK", "int", 120, 1440),      # was float 5-60
            ("DURATION_REMOTE", "int", 120, 1440),
            ("DURATION_SHIELD", "int", 120, 1440),
            ("DURATION_DIARRHEA", "int", 120, 1440),
            ("DURATION_REVERSE", "int", 120, 1440),
            ("DURATION_FLOAT", "int", 120, 1440),
        ]

    def draw(self, screen, engine):
        """Draw settings overlay."""
        panel = pygame.Surface((get_window_width(), get_window_height()), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 220))
        screen.blit(panel, (0, 0))
        y = 20
        for name, typ, lo, hi in self.param_list:
            if y > get_window_height() - 100:
                break
            val = getattr(cfg, name)
            text = self.font.render(
                f"{name}: {val:.2f}" if typ == "float" else f"{name}: {int(val)}",
                True, COLOR_TEXT)
            screen.blit(text, (50, y))
            y += 30
        # Hints
        hint = self.font_small.render(
            "Press P to close settings. Click anywhere to RESET defaults.",
            True, COLOR_TEXT)
        screen.blit(hint, (50, get_window_height() - 80))

    def handle_click(self, pos, engine):
        """Reset defaults on click."""
        cfg.reset_defaults()
        engine.safe_spots = engine.compute_safe_spots()
        engine.reset_match()
```

Update param types: all frame-based values (BOMB_FUSE, DURATION_*) change from "float" to "int" with updated min/max ranges (multiplied by 24).

- [ ] **Step 2: Wire into main.py**

```python
from settings_ui import SettingsUI

class BombermanGame:
    def __init__(self):
        ...
        self.settings_ui = SettingsUI()

    def render(self):
        self.renderer.draw(self.engine.get_snapshot())
        if self.state in (GameState.SETTINGS, GameState.SETTINGS_PAUSED):
            self.settings_ui.draw(self.screen, self.engine)
```

Remove `init_settings_ui()`, `draw_settings_panel()`, `handle_settings_click()` from BombermanGame.
Remove `self.show_settings`, `self.settings_buttons`, `self.settings_scroll`, `self.param_list`.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 4: Run game and verify settings panel**

Run: `python main.py`
Expected: Settings panel (P key) opens/closes, clicking resets defaults

- [ ] **Step 5: Commit**

```bash
git add settings_ui.py main.py
git commit -m "refactor: extract SettingsUI"
```

---

### Task 10: Strip `main.py` to clean glue code

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Clean up `main.py`**

Remove all now-unused imports and dead code. The final `main.py` should be:
```python
"""
bomberman version 2.0.2 — refactored
"""
import pygame
import sys

from config import cfg
from constants import COLOR_BG, GameState
from utils import get_window_width, get_window_height
from game_engine import GameEngine
from renderer import Renderer
from input_handler import InputHandler
from settings_ui import SettingsUI


class BombermanGame:
    def __init__(self):
        pygame.init()
        self.engine = GameEngine()
        self.screen = pygame.display.set_mode(
            (get_window_width(), get_window_height()), pygame.RESIZABLE)
        pygame.display.set_caption("炸弹人 双人PVP v2.8")
        self.clock = pygame.time.Clock()
        self.running = True
        self.input_handler = InputHandler()
        self.renderer = Renderer(self.screen)
        self.settings_ui = SettingsUI()

    def run(self):
        while self.running:
            # Event handling
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    self.input_handler.press(event.key)
                    if event.key == pygame.K_RETURN and self.engine.state == GameState.MENU:
                        self.engine.reset_match()
                    if event.key == pygame.K_p:
                        self._toggle_settings()
                elif event.type == pygame.KEYUP:
                    self.input_handler.release(event.key)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if self.engine.state in (GameState.SETTINGS, GameState.SETTINGS_PAUSED):
                        self.settings_ui.handle_click(event.pos, self.engine)

            # Update
            if self.engine.state not in (GameState.SETTINGS, GameState.SETTINGS_PAUSED):
                p1, p2 = self.input_handler.build_actions()
                self.engine.step(p1, p2)

            # Render
            snapshot = self.engine.get_snapshot()
            self.renderer.draw(snapshot)
            if self.engine.state in (GameState.SETTINGS, GameState.SETTINGS_PAUSED):
                self.settings_ui.draw(self.screen, self.engine)

            pygame.display.flip()
            self.clock.tick(cfg.FPS)

        pygame.quit()
        sys.exit()

    def _toggle_settings(self):
        s = self.engine.state
        if s in (GameState.SETTINGS, GameState.SETTINGS_PAUSED):
            if self.engine.settings_pause_state is not None:
                self.engine.state = self.engine.settings_pause_state
                self.engine.settings_pause_state = None
            else:
                self.engine.state = GameState.ROUND_RUNNING
        else:
            if s == GameState.ROUND_RUNNING:
                self.engine.settings_pause_state = GameState.ROUND_RUNNING
            else:
                self.engine.settings_pause_state = None
            self.engine.state = GameState.SETTINGS
```

Also add `settings_pause_state` to GameEngine.__init__:
```python
class GameEngine:
    def __init__(self):
        ...
        self.settings_pause_state = None
```


if __name__ == "__main__":
    game = BombermanGame()
    game.run()
```

Implement `_toggle_settings()` matching original logic (lines 349-361).

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 3: Run game to verify everything works**

Run: `python main.py`
Expected: Game plays identically to original

- [ ] **Step 4: Verify GameEngine has zero pygame dependency**

Run: `python -c "from game_engine import GameEngine; e = GameEngine(); print('No pygame needed:', type(e).__name__)"`
Expected: No pygame import error

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "refactor: main.py as glue code, all game logic in GameEngine"
```

---

### Task 11: Verify and final cleanup

**Files:**
- All files

- [ ] **Step 1: Run full test suite**

```bash
python -m pytest tests/ -v
```
Expected: All 99 tests pass

- [ ] **Step 2: Remove smoke test**

```bash
rm test_engine_smoke.py
```

- [ ] **Step 3: Verify git status is clean**

```bash
git status
```
Expected: Only expected files modified/created

- [ ] **Step 4: Update `hot.md`**

Record completion of Phase 1 refactoring.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: cleanup after Phase 1 refactoring"
```
