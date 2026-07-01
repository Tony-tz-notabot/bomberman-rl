# Bomberman PVP: 代码重构与 AI 后端设计

**日期**: 2026-07-01  
**状态**: 已批准设计  
**后续**: → writing-plans → 实现

---

## 1. 目标

1. **后端/前端分离**：将单文件 `main.py` (~1250行) 拆分为模块化结构
2. **逻辑不变**：所有游戏规则、行为、参数保持完全一致（仅单位从秒改为帧）
3. **纯后端可运行**：`GameEngine` 零 pygame 依赖，可在无头环境运行
4. **AI 预留接口**：`step()` + 只读快照，为后续 Gym 封装和强化学习铺路
5. **时序统一**：全部时间单位为帧（默认 24fps = 1s），渲染层可控制时间流速

## 2. 模块结构

```
main.py              入口胶水: 创建 GameEngine + Renderer + InputHandler, 主循环
│
├── config.py         Config 类 + 全局 cfg 实例 (所有参数帧化)
├── constants.py      颜色常量 + 枚举 (CellType, GameState, BuffType)
├── utils.py          坐标工具 (grid↔pixel, clamp, sign, box_overlap)
├── models.py         数据类: Player, Bomb, BuffItem
│                     + Snapshot 数据类族
├── game_engine.py    ✦ 核心: GameEngine, 纯逻辑, 零 pygame 依赖
├── renderer.py       全部绘制逻辑 (读 GameSnapshot → 渲染)
├── input_handler.py  键盘输入 → action dict
└── settings_ui.py    游戏内设置面板 (绘制 + 交互)
```

### 数据流

```
键盘 → InputHandler → {p1_actions, p2_actions}
                               ↓
                      GameEngine.step(p1, p2)
                               ↓
                         GameSnapshot (只读)
                               ↓
                    ┌──────────────────────┐
                    ↓                      ↓
                Renderer.draw()      AI 模型 / Gym 环境
                (pygame 依赖)        (无头, 零 pygame)
```

## 3. GameEngine 接口

```python
class GameEngine:
    def __init__(self) -> None:
        """初始化引擎, 不调用 pygame.init()"""

    def step(self, p1_actions: dict, p2_actions: dict) -> GameSnapshot:
        """
        步进一帧 (dτ = 1), 返回当前状态快照.
        内部通过 cfg.DT_OVER_DTAU (= 1/FPS) 换算位移.
        """

    def get_snapshot(self) -> GameSnapshot:
        """取当前快照 (不步进)."""

    def reset_match(self) -> GameSnapshot:
        """重置整场比赛 (比分归零, 重新生成地图)."""

    def reset_round(self) -> GameSnapshot:
        """重置当前回合 (保留比分)."""

    @property
    def red_score(self) -> int: ...
    @property
    def blue_score(self) -> int: ...


# action dict 格式:
# {
#     "up": bool, "down": bool, "left": bool, "right": bool,
#     "action": bool,   # 放置炸弹
#     "ignite": bool,   # 引燃遥控炸弹
# }
```

## 4. 帧同步设计

### 核心概念

| 符号 | 含义 |
|------|------|
| `t` | 真实时间 (秒) |
| `τ` | 帧数 (离散帧号) |
| `dτ = 1` | 每次 `step()` 步进 1 帧 |
| `DT_OVER_DTAU = dt/dτ` | 换算率，默认 `1/24` |

### 配置字段

```python
class Config:
    FPS = 24                         # 渲染帧率 (仅用于 clock.tick)
    DT_OVER_DTAU = 1.0 / FPS         # 换算率: 每帧对应多少秒, = 1/24

    # --- 速度类 (保持原始单位: cells/sec, 引擎内部乘 DT_OVER_DTAU 换算) ---
    INIT_SPEED = 2.5                 # cells/sec  → 每帧移动 2.5 × DT_OVER_DTAU cells
    SPEED_INCREMENT = 0.5            # cells/sec
    MAX_SPEED = 6                    # cells/sec
    KICK_INIT_VEL = 6.0             # cells/sec  → 每帧移动 6 × DT_OVER_DTAU cells
    KICK_ACCEL = -2.0               # cells/sec² → 每帧加速 -2 × DT_OVER_DTAU cells/sec

    # --- 计数类 (直接帧数, 无需换算) ---
    BOMB_FUSE = 48                   # = 2.0 × FPS
    BOMB_FLICKER_START = 12          # = 0.5 × FPS
    DEATH_ANIM_DUR = 12              # = 0.5 × FPS
    SHIELD_INVINCIBLE_DUR = 12       # = 0.5 × FPS
    ROUND_DELAY = 72                 # = 3.0 × FPS
    BUFF_PROTECTION_TIME = 7         # ≈ round(0.3 × FPS)
    REFRESH_INTERVAL = 720           # = 30.0 × FPS
    DURATION_KICK = 720              # = 30.0 × FPS
    DURATION_REMOTE = 720            # = 30.0 × FPS
    DURATION_SHIELD = 480            # = 20.0 × FPS
    DURATION_DIARRHEA = 192          # = 8.0 × FPS
    DURATION_REVERSE = 240           # = 10.0 × FPS
    DURATION_FLOAT = 480             # = 20.0 × FPS
```

### 公式推导

原（基于 `dt`）→ 新（基于 `DT_OVER_DTAU × dτ`）：

```
# 移动: 原公式
desired_vx = dir × speed × CELL_SIZE   # pixels/sec
new_x = old_x + desired_vx × dt

# 移动: 新公式 (代入 dt = DT_OVER_DTAU × dτ, 且 dτ = 1)
desired_vx = dir × speed × CELL_SIZE   # 不变, 仍然是 cells/sec × pixels/cell
new_x = old_x + desired_vx × DT_OVER_DTAU   # dt → DT_OVER_DTAU, dτ=1 省略
```

```
# 引信: 原
timer_sec -= dt
if timer_sec <= 0: explode()

# 引信: 新 (帧倒计时)
bomb.fuse_frames -= 1
if bomb.fuse_frames <= 0: explode()
```

```
# 能力倒计时: 原
abilities["kick"] -= dt

# 能力倒计时: 新
abilities["kick"] -= 1   # 帧
```

### 位移公式一览 (全部 dt → DT_OVER_DTAU)

| 逻辑 | 原公式 | 新公式 |
|------|--------|--------|
| 玩家移动 | `new_x = old_x + vx × dt`<br>`vx = dir × speed × CELL_SIZE` | `new_x = old_x + vx × DT_OVER_DTAU` |
| 踢炸弹初速 | `vx = dx × KICK_INIT_VEL × CELL_SIZE` | `vx = dx × KICK_INIT_VEL × CELL_SIZE` (不变) |
| 炸弹减速 | `vx += sign × KICK_ACCEL × CELL_SIZE × dt` | `vx += sign × KICK_ACCEL × CELL_SIZE × DT_OVER_DTAU` |
| 炸弹移动 | `pos.x += bomb.vx × dt` | `pos.x += bomb.vx × DT_OVER_DTAU` |
| 引信倒计时 | `timer -= dt` | `fuse_frames -= 1` |
| 能力倒计时 | `abilities[k] -= dt` | `abilities[k] -= 1` |
| 死亡动画 | `death_timer -= dt` | `death_timer -= 1` |
| 无敌时间 | `invincible_timer -= dt` | `invincible_timer -= 1` |
| 保护时间 | `protection_timer -= dt` | `protection_timer -= 1` |
| 刷新计时 | `refresh_timer -= dt` | `refresh_timer -= 1` |
| 回合延迟 | `round_delay_timer -= dt` | `round_delay_timer -= 1` |

### 碰撞逻辑

**碰撞**（`player_collision_at`, `bomb_collision_at`, `cells_overlapping`, `box_overlap`）接收的是像素坐标，内部不含 dt，**0 改动**。

### 效果

- `step()` 无入参, `dτ = 1` 恒成立
- 改变 `FPS`（进而改变 `DT_OVER_DTAU = 1/FPS`）→ 每次 `step()` 位移量随之变化，但每秒总位移不变
- 定时器全是整数帧，AI 观察空间简洁、确定

## 5. GameSnapshot 快照设计

所有快照类为 `@dataclass(frozen=True)`。

### GameSnapshot

```python
@dataclass(frozen=True)
class GameSnapshot:
    state: int                  # GameState 枚举值
    round_frame: int            # 回合已进行帧数

    map_grid: list              # [[int, ...], ...], COLS × ROWS
                                # CellType: 0=空, 1=石柱, 2=砖块,
                                #           3=地面Buff, 4=炸弹, 5=爆炸

    players: tuple              # (PlayerSnapshot, PlayerSnapshot)
    bombs: tuple                # (BombSnapshot, ...)
    buffs: tuple                # (BuffItemSnapshot, ...)
    explosion_cells: tuple      # ((gx, gy), ...) 爆炸中的格子
    scores: dict                # {"red": int, "blue": int}
```

### PlayerSnapshot

```python
@dataclass(frozen=True)
class PlayerSnapshot:
    id: str                     # "red" / "blue"
    color: tuple                # (R, G, B)

    pos_x: float                # 像素坐标
    pos_y: float
    grid_x: int                 # 所在格子
    grid_y: int

    alive: bool
    velocity: float             # 当前速度 (格/秒)
    death_timer: int            # 死亡动画剩余帧, 0 表示非死亡状态

    bomb_max: int
    bomb_placed_count: int
    blast_range: int
    invincible_timer: int       # 无敌剩余帧, 0 表示不无敌

    wins: int
    perm_bomb_plus: int
    perm_blast_plus: int
    perm_speed_plus: int

    abilities: dict             # {"ability_name": remaining_frames}
                                # e.g. {"kick": 360, "shield": 240}
                                # ⚠️ 不暴露 unknown_subtype
```

### BombSnapshot

```python
@dataclass(frozen=True)
class BombSnapshot:
    id: int
    owner: str                  # "red" / "blue"
    type: str                   # "normal" / "remote" / "converted"

    pos_x: float
    pos_y: float
    grid_x: int
    grid_y: int

    fuse_frames: int            # 引信剩余帧数, -1 = 遥控炸弹
    vx: float                   # 被踢后的速度 (格/秒)
    vy: float
```

### BuffItemSnapshot

```python
@dataclass(frozen=True)
class BuffItemSnapshot:
    type: str                   # "bomb_plus" / "blast_plus" / "speed_plus" / "unknown"
    pos_x: float
    pos_y: float
    grid_x: int
    grid_y: int
    # ⚠️ 无 unknown_subtype — AI 看不到惊喜背后
```

## 6. 地图矩阵编码 (CellType)

```python
class CellType:
    EMPTY   = 0   # 空地
    STONE   = 1   # 石柱 (不可破坏)
    BRICK   = 2   # 砖块 (可破坏)
    BUFF    = 3   # 地面有未捡起 Buff
    BOMB    = 4   # 有炸弹
    EXPLOSION = 5 # 爆炸中
```

`map_grid` 是 `COLS × ROWS` 的二维整数矩阵，供 AI 直接输入神经网络。

## 7. 前端的渲染速度控制

```python
# 正常速度 (1×)
while running:
    input_handler.poll()
    snapshot = engine.step(p1, p2)
    renderer.draw(snapshot)
    clock.tick(cfg.FPS)

# 2× 快进: 每渲染帧步进 2 次
while running:
    for _ in range(2):
        snapshot = engine.step(p1, p2)
    renderer.draw(snapshot)
    clock.tick(cfg.FPS)

# RL 训练 (无头)
while training:
    actions = model.act(snapshot)
    snapshot = engine.step(**actions)  # 纯计算, 无渲染
```

## 8. 重构步骤

### Step 1: 抽取基架 (安全机械操作)

1. 创建 `config.py` — 从 `main.py` 复制 `Config` 类 + `cfg` 实例
2. 创建 `constants.py` — 颜色常量 + 新增 `CellType` 枚举
3. 创建 `utils.py` — `grid_to_pixel`, `pixel_to_grid`, `clamp`, `sign`, `box_overlap`
4. 创建 `models.py` — `Player`, `Bomb`, `BuffItem` 数据类
5. 创建 `game_state.py` — `GameState` 枚举
6. 所有模块从 `main.py` 导入，确保 `main.py` 正常工作（先不拆 BombermanGame）

### Step 2: 创建 GameEngine

1. 创建 `game_engine.py`
2. 将 `BombermanGame` 中的游戏状态字段迁移到 `GameEngine`
3. 将 `update_round()` 中的更新逻辑逐步迁移
4. 实现 `step()` / `get_snapshot()` / `reset_match()` / `reset_round()`
5. 实现所有 `Snapshot` 数据类的生成
6. **所有时间单位换算为帧**

### Step 3: 分离前端

1. 创建 `renderer.py` — 提取渲染逻辑，读 `GameSnapshot` 绘制
2. 创建 `input_handler.py` — 键盘 → action dict
3. 创建 `settings_ui.py` — 设置面板
4. 重构 `main.py` — 胶水代码，不再包含游戏逻辑

### Step 4: 验证

- 全部 99 个测试通过
- 游戏运行行为与重构前一致（帧同步后速度感受相同）
- GameEngine 可在无 pygame 环境导入运行

## 9. 后续规划

### Phase 2: Gym 环境封装

```python
import gymnasium as gym
from game_engine import GameEngine

class BombermanEnv(gym.Env):
    def __init__(self, fps=24):
        self.engine = GameEngine()
        self.fps = fps

    def reset(self):
        return self.engine.reset_match()

    def step(self, action_p1, action_p2):
        snapshot = self.engine.step(action_p1, action_p2)
        reward = compute_reward(snapshot)
        done = snapshot.state in (MATCH_END,)
        return snapshot, reward, done, {}
```

### Phase 3: AI 策略实现

- 规则 AI（寻路、放炸弹、躲避）
- 后续强化学习支持

## 10. 不改变的内容

- Player/Bomb/BuffItem 的核心字段和结构
- 所有游戏规则（碰撞、爆炸链、能力效果、得分、回合流程）
- Config 参数的默认值（仅单位换算）
- 坐标系统 (grid_to_pixel / pixel_to_grid)
- 测试覆盖率
