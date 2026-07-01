# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run

```bash
# Install dependency
pip install pygame

# Run the game
python main.py

# Windows double-click launcher (auto-installs pygame if missing)
launch.bat
```

## Tests

```bash
# Run full test suite (requires pytest: pip install pytest)
python -m pytest tests/

# Run a specific test class
python -m pytest tests/test_game_mechanics.py -v

# Run a single test
python -m pytest tests/test_utils.py::TestPixelToGrid -v
```

Tests cover: coordinate conversion, config defaults, data structures, map generation, bomb placement/explosion/chain-reaction, player collision/death/shield, buff pickup/destruction, all 6 abilities (kick/remote/shield/diarrhea/reverse/float), scoring & round lifecycle, and match reset.

## Project Overview

**Bomberman PVP** — a local 2-player Bomberman game in a single `main.py` (~1250 lines). Uses Pygame 2.x, no other dependencies.

### File structure
```
.
├── main.py          # Entire game: config, game loop, input, logic, rendering, UI
├── launch.bat       # Windows launcher (auto-installs pygame)
├── README.md        # Feature overview and controls
├── RULES.md         # Complete game rules reference (30+ config params documented)
├── MIT license.md
└── CLAUDE.md
```

## Code Architecture (all in main.py)

### Configuration — `Config` class (line 10)
- Global singleton `cfg` (line 52) stores all tunable parameters (map size, speed, bomb behavior, ability durations, etc.)
- `reset_defaults()` reinitializes to defaults
- 30+ parameters accessible via `getattr(cfg, name)` — used in settings panel

### Data structures (lines 122–201)
- **`Player`** (line 122): Tracks position, input state, bomb limits, abilities dict, remote queue.
  - `pos_x/pos_y` in pixel space; `grid_to_pixel`/`pixel_to_grid` convert.
  - `abilities` is `{name: remaining_seconds}` — all temporary abilities stored here.
  - `remote_queue` is FIFO list of bomb IDs for remote detonation.
- **`Bomb`** (line 177): Stores type (normal/remote/converted), timer, velocity (for kicked bombs).
- **`BuffItem`** (line 192): Item on ground with type, optional unknown subtype, protection timer.

### Game states — `GameState` enum (line 203)
`MENU → ROUND_RUNNING → (ROUND_END_DELAY → ROUND_RUNNING loop) → MATCH_END`  
Plus `SETTINGS` and `SETTINGS_PAUSED` for the settings overlay.

### Main game class — `BombermanGame` (line 212)
The game loop in `run()` (line 1236):
1. **`handle_events()`** — keyboard/mouse input, state transitions
2. **`update(dt)`** — game logic (only when not in settings)
3. **`render()`** — draw everything

Key update subsystems (called by `update_round`):
- **Player movement** (line 383): Input direction → speed scaling → per-axis collision with terrain, players, bombs
- **Bomb timers & kick** (line 553): Countdown timers, remote→converted transition, kick physics with acceleration
- **Explosion BFS** (line 603): Queue-based chain reaction; destroys bricks, drops items, triggers remote_queue cleanup
- **Player death** (line 669): Checks explosion_cells set; shield absorbs one hit + invincibility
- **Ability timers** (line 767): Countdown + expiry handlers (float eviction, remote conversion)

### Coordinate system (lines 94–120)
- Map grid: 1-indexed `(gx, gy)` — `(1,1)` bottom-left, `(COLS, ROWS)` top-right
- `grid_to_pixel(gx, gy)` → pixel with `UI_BAR_HEIGHT` offset
- `pixel_to_grid(px, py)` → clamped grid coords (bug-fixed to account for UI_BAR_HEIGHT)
- `grid_center(gx, gy)` → center pixel of a grid cell

### Rendering (lines 868–1171)
All drawing in `render()`: map grid, buff icons (drawn as geometric shapes), bomb with spark, explosion cells (randomized intensity per frame for fire effect), player with direction-facing eyes, shield aura, UI bar with bomb indicators and ability icons.

### Settings panel (lines 1173–1233)
Lists all 30+ params; clicking anywhere resets to defaults. Currently one-way (click = reset) — no individual parameter sliders yet.

### Collision system
- Players: axis-separated movement, overlap tested via `cells_overlapping()` and AABB box overlap
- Bombs: circle collision (radius = `CELL_SIZE * 0.35`) against terrain, players, and other bombs
- Buff pickup: distance < `half_hitbox + 8px`

### Key gameplay mechanics
- **Float end** (line 791): Expulsion to nearest safe floor tile, or death if none found
- **Diarrhea** (line 815): Auto-places bomb when crossing grid cell boundary
- **Kick bomb** (line 505): Sets `vx/vy` with configurable initial velocity and deceleration
- **Shield** (line 674): One-hit block + invincibility window, icon blinks when <2s remaining

## Common Development Tasks

- **Tweak gameplay balance**: Modify `Config.__init__()` default values (line 12–46)
- **Add new ability**: Extend ability names in `get_ability_duration()` (line 711), `spawn_buff_at()` (line 736), `draw_ability_icon_graphic()` (line 1097), and `remove_ability()` (line 778)
- **Add new buff type**: Add weight in `Config`, selection in `spawn_buff_at()`, apply logic in `apply_buff()` (line 696)
- **Modify settings panel**: Edit `param_list` in `init_settings_ui()` (line 1175)
- **Bug fixing**: Single-file means all logic is in one place. Key bug-prone areas: coordinate conversion (pixel_to_grid), float ability end (eviction corner cases), collision (axis-separated can clip corners)

## Known limitations (from README)
- Settings panel only supports click-to-reset (no individual slider/input adjustments planned)
- Kick bomb acceleration is constant — kick distance varies with CELL_SIZE

## Progress Tracking (hot.md)

每次完成有意义的代码改动后（非 trivial 修复/打字错误），必须在 `hot.md` 中更新进展记录。

- **位置**: `hot.md` 项目根目录
- **内容**: 已完成项、当前阶段、下一步计划
- **格式**: 日期标题 → 检查列表 → 自由描述
- **触发**: `.claude/settings.json` 中的 PostToolUse hook 会在每次 Edit/Write 后提示检查 hot.md
- **压缩恢复**: 当上下文被压缩（Summarize）后恢复会话时，必须**首先阅读 `hot.md`** 以恢复心智状态和当前进度，然后再继续工作。

不要连续写入微小步骤（如"修复了一个拼写错误"），而是记录有边界的里程碑（如"完成了碰撞系统重构"）。
