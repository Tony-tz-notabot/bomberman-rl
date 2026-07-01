# Bomberman Gym 环境 — 设计文档

> Phase 2: 为 Bomberman PVP 游戏封装 Gym 环境，支持 RL 训练
> 日期: 2026-07-01
> 状态: 设计锁定

---

## 1. 架构总览

```
GameEngine (已有，纯逻辑，零 pygame 依赖)
    │
    ├── ▼
    │   BombermanEnv (gym.Env)      ← bomberman_env.py    [新文件]
    │    - 单智能体接口，控制红方
    │    - opponent_fn 函数参数控制蓝方
    │    - reset(options={"grid": matrix}) 支持矩阵传参
    │    - RewardFunction 适配器可插拔
    │
    └── ▼
        BombermanPettingZooEnv       ← pettingzoo_env.py   [新文件]
         - 多智能体 ParallelEnv 接口
         - 直接包装 GameEngine（跳过 opponent_fn 层）
         - 复用 _build_obs() 作为共享工具函数
         - 支持 tied policy / self-play
```

### 新文件清单

```
├── bomberman_env.py          # BombermanEnv(gym.Env)     — 单智能体环境
├── bomberman_env_test.py     # 环境测试
├── pettingzoo_env.py         # BombermanPettingZooEnv    — 多智能体环境
├── pettingzoo_env_test.py    # 多智能体环境测试
└── rewards/
    ├── __init__.py            # RewardFunction 基类
    └── sparse.py              # +1/-1 稀疏奖励示例
```

---

## 2. 观察空间

### 定义

```python
observation_space = spaces.Box(
    low=0.0, high=1.0, shape=(11, 19, 8), dtype=np.float32
)
```

### 通道布局

| CH | 名称 | 值域 | 编码方式 | 来源参考 |
|----|------|------|---------|---------|
| 0 | 地形 (terrain) | {0, 0.5, 1.0} | 0=空地, 0.5=砖块, 1.0=石头 | Pommerman 墙体编码 |
| 1 | 玩家 (players) | [0, 1] | 高斯热力图编码像素级位置；红方值域 [0.1, 0.5], 蓝方 (0.5, 1.0] | BlastPursuit agent mask 改良 |
| 2 | 炸弹+引信 (bomb) | [0, 1] | 0=无炸弹；>0 时有炸弹，值 = fuse_frames/BOMB_FUSE | Skynet bomb plane |
| 3 | Buff+爆炸 (buff_exp) | [0, 1] | Buff: 0=无, 0.2=bomb+, 0.35=blast+, 0.5=speed+, 0.65=kick, 0.8=remote, 0.9=shield, 1.0=explosion | Pommerman powerup+flame |
| 4 | 红方能力 (red_abilities) | [0, 1] | 6 种能力剩余归一化，广播到全图，无能力=0 | Skynet 全局通道思路 |
| 5 | 蓝方能力 (blue_abilities) | [0, 1] | 同上 | |
| 6 | 红方数值状态 (red_stats) | [0, 1] | bomb_remaining/bomb_max 归一化广播 | |
| 7 | 蓝方数值状态 (blue_stats) | [0, 1] | 同上 | |

### 玩家位置 — 高斯热力图编码

代替格子级的 0/1，用高斯热力图编码子像素位置，体现玩家在两个格子之间的过渡：

```python
def _gauss_heatmap(self, px, py):
    """像素坐标 → (H, W) 热力图"""
    heatmap = np.zeros((cfg.MAP_ROWS, cfg.MAP_COLS), dtype=np.float32)
    sigma = 0.3  # 格子单位下的标准差
    for gx in range(1, cfg.MAP_COLS + 1):
        for gy in range(1, cfg.MAP_ROWS + 1):
            cx, cy = grid_center(gx, gy)
            dx = (px - cx) / cfg.CELL_SIZE
            dy = (py - cy) / cfg.CELL_SIZE
            heatmap[gy-1][gx-1] = math.exp(-(dx*dx + dy*dy) / (2 * sigma * sigma))
    return heatmap
```

---

## 3. 动作空间

```python
action_space = spaces.MultiBinary(6)
# [up, down, left, right, action, ignite]
# 每个维度 0 或 1，支持同时按多个键（如左+上+放炸弹）
```

### 对向键惩罚（环境内置，可选）

```python
env = BombermanEnv(penalty_opposing=-0.1)  # 默认 0.0 关闭
```

在 `step()` 中检测 (up+down) 或 (left+right) 同时为 1 时，自动叠加 `penalty_opposing` 到 reward，对 RewardFunction 透明。约束智能体不产生冲突输入。

### 动作到引擎的映射

```python
# BombermanEnv 中
action_dict = {
    "up":     actions[0],
    "down":   actions[1],
    "left":   actions[2],
    "right":  actions[3],
    "action": actions[4],  # 放炸弹（边沿触发，引擎内部处理）
    "ignite": actions[5],  # 远程引燃
}
# 红方动作直接给引擎，蓝方由 opponent_fn 生成
self.engine.step(red_action_dict, blue_action_dict)
```

---

## 4. 奖励系统 — RewardFunction 适配器

### 基类

```python
# rewards/__init__.py
class RewardFunction:
    """奖励策略基类。完全可插拔，无硬编码于环境。"""

    def reset(self, episode_info: dict):
        """每回合开始时调用，重置内部跟踪状态。"""
        pass

    def __call__(
        self,
        engine,          # GameEngine — 完整内部状态
        prev_snapshot,   # GameSnapshot | None — 上一帧快照
        snapshot,        # GameSnapshot — 当前帧快照
        action,          # dict — 智能体刚执行的动作
        agent_id: str,   # "red" | "blue"
    ) -> float:
        """返回该帧的奖励值。"""
        raise NotImplementedError
```

### 内置示例：稀疏奖励

```python
# rewards/sparse.py
class SparseReward(RewardFunction):
    """赢+1, 输-1, 平局0, 其余帧0"""

    def __call__(self, engine, prev, snap, action, agent):
        if snap.state == GameState.ROUND_END_DELAY or snap.state == GameState.MATCH_END:
            agent_won = snap.scores.get(agent, 0) > snap.scores.get(
                "blue" if agent == "red" else "red", 0
            )
            if agent_won:
                return 1.0
            elif snap.current_winner == "":
                return 0.0  # 平局
            else:
                return -1.0
        return 0.0
```

### 奖励注入方式

```python
# 环境构造函数
env = BombermanEnv(reward_fn=SparseReward())

# 训练中途可切换
env.reward_fn = MyCustomReward()
```

---

## 5. 初始化 — reset(options=)

### 接口

```python
def reset(
    self,
    *,
    seed: Optional[int] = None,
    options: Optional[dict] = None,
) -> Tuple[np.ndarray, dict]:
    """重置环境。

    Args:
        seed: 随机种子
        options:
            - grid: Optional[np.ndarray] — (MAP_ROWS, MAP_COLS) 矩阵
              0=空地, 1=石头, 2=砖块, 3=红方玩家, 4=蓝方玩家
              不传入则使用引擎内置随机生成
            - red_spawn: Optional[str] — 默认 "fixed" (使用矩阵中的3)
            - blue_spawn: Optional[str] — 默认 "fixed"
    """
```

### 矩阵编码

| 编码 | 含义 |
|------|------|
| 0 | 空地 (floor) |
| 1 | 石头 (stone, 不可破坏) |
| 2 | 砖块 (brick, 可破坏) |
| 3 | 红方玩家出生点（出现位置=红方 spawn） |
| 4 | 蓝方玩家出生点（出现位置=蓝方 spawn） |

### 矩阵初始化逻辑

```python
def _init_from_matrix(self, matrix: np.ndarray):
    """解析外部传入的网格配置，覆盖引擎的 generate_map()。"""
    self.engine.grid = [["" for _ in range(cfg.MAP_ROWS + 1)] for _ in range(cfg.MAP_COLS + 1)]
    red_spawn = blue_spawn = None

    for y in range(cfg.MAP_ROWS):
        for x in range(cfg.MAP_COLS):
            val = matrix[y, x]
            gx, gy = x + 1, y + 1
            if val == 0:
                self.engine.grid[gx][gy] = "floor"
            elif val == 1:
                self.engine.grid[gx][gy] = "stone"
            elif val == 2:
                self.engine.grid[gx][gy] = "brick"
            elif val == 3:
                self.engine.grid[gx][gy] = "floor"
                red_spawn = (gx, gy)
            elif val == 4:
                self.engine.grid[gx][gy] = "floor"
                blue_spawn = (gx, gy)

    assert red_spawn, "矩阵必须包含红方 (编码3)"
    assert blue_spawn, "矩阵必须包含蓝方 (编码4)"

    self.engine.red_player.reset(*red_spawn)
    self.engine.blue_player.reset(*blue_spawn)
    self.engine.state = GameState.ROUND_RUNNING
    self.engine.round_frame = 0
    self.engine.bombs.clear()
    self.engine.buffs.clear()
    self.engine.explosion_cells.clear()
```

### 默认初始化分支

不传 grid 时：

```python
# 引擎内置随机生成（含安全区、可解保证）
self.engine.reset_match()
```

---

## 6. 对手函数 — opponent_fn

```python
# 类型签名
OpponentFn = Callable[[GameSnapshot, str], np.ndarray]
# 接收 (snapshot, agent_id) → MultiBinary(6) 动作向量
```

### 内置随机策略

```python
def random_opponent(snapshot, agent_id):
    """纯随机移动+随机放炸弹，用于基线对比。"""
    actions = np.random.randint(0, 2, size=6, dtype=np.int8)
    return actions
```

### 用法

```python
# 构建环境
env = BombermanEnv(opponent_fn=random_opponent)

# 单智能体 step 内部自动调用 opponent_fn
obs, reward, terminated, truncated, info = env.step(red_action)
```

---

## 7. PettingZoo 多智能体接口

### 包装模式 — 直接包装 GameEngine

PettingZoo 模式直接包装 GameEngine，绕过 opponent_fn 层。`_build_obs()` 作为工具函数从 `bomberman_env.py` 导入复用。

```python
class BombermanPettingZooEnv(ParallelEnv):
    def __init__(self, reward_fn: RewardFunction = SparseReward()):
        self.engine = GameEngine()
        self.reward_fn = reward_fn
        self.agents = ["red", "blue"]
        self.possible_agents = ["red", "blue"]
        self.action_spaces = {
            "red": spaces.MultiBinary(6),
            "blue": spaces.MultiBinary(6),
        }
        self.observation_spaces = {
            "red": spaces.Box(0, 1, (11, 19, 8), np.float32),
            "blue": spaces.Box(0, 1, (11, 19, 8), np.float32),
        }
```

### 观察视角 — 自/他对调

单智能体和 PettingZoo 使用同一套观察构建函数 `_build_obs(snapshot, agent_id)`。

**核心原则：CH1 总是编码"自己在前，对手在后"，确保共享策略（tied policy）可直接使用。**

| 角色 | CH1 (玩家) | CH4 | CH5 | CH6 | CH7 |
|------|-----------|-----|-----|-----|-----|
| 单智能体 red | red[0.1,0.5] / blue(0.5,1.0] | red_abilities | blue_abilities | red_stats | blue_stats |
| PettingZoo red | red(self)[0.1,0.5] / blue(0.5,1.0] | red(self) | blue | red(self) | blue |
| PettingZoo blue | blue(self)[0.1,0.5] / red(0.5,1.0] | blue(self) | red | blue(self) | red |

```python
def _build_obs(self, snapshot, agent_id):
    """构建一个智能体的观察。agent_id 决定"自己"和"对手"的通道布局。"""
    obs = np.zeros((cfg.MAP_ROWS, cfg.MAP_COLS, 8), dtype=np.float32)

    # CH0: 地形解码
    ...
    # CH1: 玩家热力图 (自己在前, 对手在后)
    self_player = snapshot.players[0] if agent_id == "red" else snapshot.players[1]
    opp_player = snapshot.players[1] if agent_id == "red" else snapshot.players[0]
    obs[:, :, 1] = self._gauss_heatmap(self_player.pos_x, self_player.pos_y) * 0.4 + 0.1
    opp_heat = self._gauss_heatmap(opp_player.pos_x, opp_player.pos_y)
    obs[:, :, 1] = np.maximum(obs[:, :, 1], opp_heat * 0.4 + 0.6)
    ...
    # CH4: 自己的能力, CH5: 对手的能力
    obs[:, :, 4] = self._abilities_broadcast(snapshot, agent_id, is_self=True)
    obs[:, :, 5] = self._abilities_broadcast(snapshot, agent_id, is_self=False)
    # CH6: 自己的数值状态, CH7: 对手的数值状态
    obs[:, :, 6] = self._stats_broadcast(snapshot, agent_id, is_self=True)
    obs[:, :, 7] = self._stats_broadcast(snapshot, agent_id, is_self=False)
    return obs
```

这样做的好处：
- **tied policy 开箱即用** — 两个智能体可以共享同一套网络权重
- **单智能体迁移到自对弈** — 观察空间不变，只需切换环境封装

### PettingZoo step — 双方动作均由外部传入

PettingZoo 模式下**不需要 opponent_fn**，红蓝双方动作均由训练脚本的 `step()` 参数传入：

```python
def step(self, actions: dict):
    """actions = {"red": ndarray(6,), "blue": ndarray(6,)}"""
    red_dict = self._action_to_dict(actions["red"])
    blue_dict = self._action_to_dict(actions["blue"])
    snapshot = self.engine.step(red_dict, blue_dict)

    obs = {
        "red": build_obs(snapshot, "red"),
        "blue": build_obs(snapshot, "blue"),
    }
    rewards = {
        "red": self.reward_fn(self.engine, self._prev_snap, snapshot,
                              actions["red"], "red"),
        "blue": self.reward_fn(self.engine, self._prev_snap, snapshot,
                               actions["blue"], "blue"),
    }
    terminated = {
        "red": snapshot.state == GameState.MATCH_END,
        "blue": snapshot.state == GameState.MATCH_END,
        "__all__": snapshot.state == GameState.MATCH_END,
    }
    truncated = {"red": False, "blue": False, "__all__": False}
    infos = {"red": {}, "blue": {}}
    self._prev_snap = snapshot
    return obs, rewards, terminated, truncated, infos
```

`build_obs()` 是 `bomberman_env.py` 中的模块级函数，被 BombermanEnv 和 BombermanPettingZooEnv 共同引用。

与 BombermanEnv.step 的关系：

| 模式 | 红方动作来源 | 蓝方动作来源 | 引擎调用 |
|------|-------------|-------------|---------|
| 单智能体 `env.step(red_action)` | 参数传入 | opponent_fn 内部生成 | `engine.step(red_dict, blue_dict)` |
| PettingZoo `env.step({"red": a, "blue": a})` | 外部传入 | 外部传入 | `engine.step(red_dict, blue_dict)` |

---

## 8. 生命周期与状态流转

### 单智能体模式

```
reset()
  │   engine.reset_match() → ROUND_RUNNING
  │   或 _init_from_matrix(grid)
  ▼
┌──────────────────────┐
│  step(red_action)     │  ← 自动调用 opponent_fn(蓝方)
│    engine.step(rd, bd)│
│    reward_fn(…)       │
│    check done/trunc   │
└──────┬───────────────┘
       │ terminated=True (MATCH_END 或一局结束)
       ▼
  reset() 或 close()
```

### 回合/比赛生命周期

- **单回合训练**: 一局结束后 (`MATCH_END` 或 `ROUND_END_DELAY` 后) set `terminated=True`
- **多回合/比赛训练**: `terminated` 只在整场比赛结束后为 True，内部回合循环在 `reset()` 中自动处理

---

## 9. 文件结构

```
.
├── main.py                  # 已有的游戏入口 (不变)
├── game_engine.py           # 已有的引擎 (不变)
├── models.py                # 已有的数据类 (不变)
├── ...
│
├── bomberman_env.py         # [新] Gym.Env 单智能体环境
│
├── pettingzoo_env.py        # [新] PettingZoo ParallelEnv 多智能体环境
│
├── rewards/
│   ├── __init__.py           # [新] RewardFunction 基类
│   ├── sparse.py             # [新] 稀疏奖励示例
│   └── ...                   # [新建] 用户自定奖励策略
│
├── tests/
│   ├── ...
│   ├── test_bomberman_env.py       # [新] Gym 环境测试
│   └── test_pettingzoo_env.py      # [新] PettingZoo 环境测试
│
└── examples/
    └── train_with_sb3.py    # [新] Stable-Baselines3 训练示例
```

---

## 10. 测试计划

### Gym 环境测试

- `test_reset_default` — 默认 reset 产生合法回合，观察形状正确
- `test_reset_with_grid` — 传入 19×11 矩阵，验证地形和玩家位置匹配
- `test_step_basic` — step 返回 (obs, reward, terminated, truncated, info)
- `test_penalty_opposing` — 对向键触发惩罚
- `test_opponent_fn` — opponent_fn 被正确调用
- `test_reward_function` — 自定义 reward_fn 正常注入
- `test_episode_lifecycle` — 完整对局 terminated=True 后 reset 正常工作
- `test_seed_reproducibility` — 相同 seed 产生相同初始状态

### PettingZoo 环境测试

- `test_pz_reset` — reset 返回 {agent: obs} 结构
- `test_pz_step` — step 接受 {agent: action}，返回正确结构
- `test_pz_parallel_api` — 验证 ParallelEnv API 完整性
- `test_pz_agent_rotation` — 双智能体交替轮次测试
