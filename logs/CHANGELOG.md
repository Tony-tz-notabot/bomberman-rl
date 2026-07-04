# 版本日志 / Version Changelog

> 按时间顺序从旧到新排列。每条记录包含：提交 hash、问题背景、具体数值/代码改动。
>
> 数值格式：`旧值 → 新值`（仅显示该 commit 中实际变更的参数）

---

## Phase 0: 项目初始化

### `29485d3` — first commit
- **调整**: 项目初始提交，单文件 `main.py` (~1250行) 包含全部游戏逻辑

### `bcbfc6e` — Initial commit
- **调整**: GitHub 仓库初始化

---

## Phase 1: 代码库重构 — 单文件拆分为模块

### `70d0c06` — refactor: extract config.py, convert all time params to frames
- **问题**: 全部配置参数散落在 main.py；时间参数用秒但游戏以帧循环驱动（24fps），隐式转换脆弱
- **调整**: 创建 `config.py`，所有时间参数秒→帧（×24）：

| 参数 | 旧值(秒) | 新值(帧) |
|---|---|---|
| `self.FPS` | (新增) | `24` |
| `self.DT_OVER_DTAU` | (新增) | `1.0/24` |
| `BOMB_FUSE` | 2.0 | `48` |
| `BOMB_FLICKER_START` | 0.5 | `12` |
| `DEATH_ANIM_DUR` | 0.5 | `12` |
| `SHIELD_INVINCIBLE_DUR` | 0.5 | `12` |
| `ROUND_DELAY` | 3.0 | `72` |
| `BUFF_PROTECTION_TIME` | 0.3 | `7` |
| `REFRESH_INTERVAL` | 30.0 | `720` |
| `DURATION_KICK` | 30.0 | `720` |
| `DURATION_REMOTE` | 30.0 | `720` |
| `DURATION_SHIELD` | 20.0 | `480` |
| `DURATION_DIARRHEA` | 8.0 | `192` |
| `DURATION_REVERSE` | 10.0 | `240` |
| `DURATION_FLOAT` | 20.0 | `480` |

- main.py 计时器递减：`-= dt` → `-= 1.0`（4处）；显示转换：`int(timer)` → `int(timer / cfg.FPS)`（2处）

### `0bbae25` — refactor: extract constants.py with colors and GameState
- **调整**: 从 main.py 抽出 `constants.py`，含 `Color` 类（16个 RGB 常量）、`GameState` 枚举（MENU/ROUND_RUNNING/ROUND_END_DELAY/MATCH_END/SETTINGS/SETTINGS_PAUSED）
- **新常量**: `CELL_EMPTY=0`, `CELL_STONE=1`, `CELL_BRICK=2`, `CELL_BUFF=3`, `CELL_BOMB=4`, `CELL_EXPLOSION=5`

### `c901360` — refactor: extract utils.py with coordinate tools
- **调整**: 从 main.py 抽出 `utils.py`
- **函数**: `grid_to_pixel(gx, gy)` → `( (gx-1)*CELL_SIZE + CELL_SIZE/2, (gy-1)*CELL_SIZE + CELL_SIZE/2 + UI_BAR_HEIGHT )`
- `pixel_to_grid(px, py)` → `(clamp(round((px-CELL_SIZE/2)/CELL_SIZE+1), 1, COLS), clamp(round((py-UI_BAR_HEIGHT-CELL_SIZE/2)/CELL_SIZE+1), 1, ROWS))`
- `clamp(v, lo, hi)`, `sign(x)`, `box_overlap(a, b)`

### `c55a5b9` — refactor: extract models.py with data classes + snapshot types
- **调整**: 创建 `models.py`，含 Player/Bomb/BuffItem + 4 个 Snapshot 类
- `Bomb`: `timer: float` → `fuse_frames: int`；`Player`: `death_timer: float` → `int`；`invincible_timer: float` → `int`
- 新增 `PlayerSnapshot` / `BombSnapshot` / `BuffItemSnapshot` / `GameSnapshot` 只读 dataclass

### `5db2824` — feat: create GameEngine with full game logic and frame-based timing
- **调整**: 创建 `GameEngine` 类 (~440行)，零 pygame 依赖，纯逻辑
- **参数**: `PLAYER_HITBOX_SIZE=0.8`，`BOMB_RADIUS=35% CELL_SIZE`，`KICK_VX_INITIAL=4.0`，`KICK_DECEL=0.92`
- 全部计时器帧基（int），移动使用 `DT_OVER_DTAU` 比例缩放

### `f9102dc` — fix: remove unused imports in game_engine.py
- **调整**: 清理无用 import（无功能变更）

### `140d919` — refactor: BombermanGame delegates to GameEngine, remove duplicate logic
- **调整**: BombermanGame 创建 `self.engine = GameEngine()`，全部更新逻辑委托；`step(p1_actions, p2_actions)` 驱动

### `84e28a4` — refactor: extract Renderer, read GameSnapshot for drawing
- **调整**: 创建 `Renderer` 类 (~380行)，以 `GameSnapshot` 为唯一数据源
- PlayerSnapshot 新增字段: `dir_x`, `dir_y`（方向眼睛绘制）
- GameSnapshot 新增: `current_winner`, `round_delay_timer`

### `73abb65` — refactor: extract InputHandler for key state management
- **调整**: 创建 `input_handler.py`，`InputHandler` 类管理双人键盘状态
- `build_actions()` → 返回 `(p1_actions, p2_actions)` 字典，6 维 `{up,down,left,right,act,ignite}`

### `2fd65ac` — fix: guard input handler press/release behind game-state check
- **问题**: 非游戏状态误触发按键处理
- **调整**: input_handler 方法添加游戏状态守卫

### `3b88ae0` — refactor: extract SettingsUI
- **调整**: 创建 `settings_ui.py`；`param_list` 所有时间参数从 float 秒改为 int 帧（×24）
- SettingsUI 显示 30+ 参数，点击重置为默认值

### `fc3bda2` — refactor: consolidate CellType constants into constants.py as single source of truth
- **调整**: CellType 常量和 Player 颜色统一到 `constants.py`，消除重复定义

### `1e2fd62` — chore: cleanup after Phase 1 refactoring complete
- **调整**: main.py 1250 行 → 138 行胶水代码；99 测试全通过；GameEngine 零 pygame 依赖

---

## Phase 2: Gym/PettingZoo 环境封装

### `388eb71` — docs: add Gym environment design spec for Phase 2
- **调整**: 添加 Gym 环境设计规格文档

### `f490912` — feat: Phase 2 - Gym/PettingZoo env wrappers with pluggable reward and opponent
- **问题**: 需要标准化 RL 接口以支持 SB3 训练
- **调整**: 新增 `src/bomberman_env.py`、`src/pettingzoo_env.py`、`rewards/__init__.py`、`rewards/sparse.py`
- **观测空间**: `Box(0,1,(11,19,8))`，8 通道:
  - CH0: 地形 (0=空地/0.5=砖块/1.0=石头)
  - CH1: 玩家高斯热力图 (自身 `[0.1,0.5]` = heat×0.4+0.1; 对手 `(0.5,1.0]` = heat×0.4+0.6; sigma=0.3)
  - CH2: 炸弹引信 (fuse_frames/BOMB_FUSE)
  - CH3: Buff+爆炸 合并 (buff 映射: bomb_plus=0.2, blast_plus=0.35, speed_plus=0.5, kick=0.65, remote=0.8, shield=0.9, other=1.0)
  - CH4/CH5: 自身/对手 能力广播 (归一化 max_dur=480.0)
  - CH6/CH7: 自身/对手 状态广播 (`placed / max_bombs`)
- **动作空间**: `MultiBinary(6)` = `[up, down, left, right, act, ignite]`
- **参数**: `BombermanEnv.__init__` 新增: `reward_fn=None`, `opponent_fn=None`, `penalty_opposing=0.0`
- **SparseReward**: +1 赢 / -1 输 / 0 平局 / 0 其余帧
- **reset(options)**: `{"grid": matrix}` 编码: 0=floor/1=stone/2=brick/3=red/4=blue
- `_random_opponent`: `np.random.randint(0, 2, size=6, dtype=np.int8)`

### `e9e5a84` — docs: record CH1 encoding bug fix in hot.md
- **调整**: hot.md 记录

### `c6f6132` — docs: rewrite README for RL training env
- **调整**: README 全面重写为 RL 环境文档

### `1fd5369` — chore: ignore docs/ in gitignore
- **调整**: `.gitignore` 添加 `docs/`

### `9abce76` — Merge branch 'main'
- **调整**: 合并远程 main

### `1db34d9` — refactor: move all source files into src/ directory
- **调整**: 11 个模块从项目根目录移入 `src/` 包；所有 import 路径加 `from src.xxx`

### `1066c3a` — docs: Phase 1 curriculum design spec
- **调整**: 课程训练设计规格文档

### `c8394af` — docs: Gym obs channels (8→9) + standardized render design spec
- **调整**: 观测通道改进与标准化渲染设计规格文档

### `73f3066` — feat: split player channels (8->9) and add standardized render() to gym envs
- **问题**: CH1 自身与对手在同一通道互相遮蔽；缺少标准化 render()
- **调整**: 通道数 8→9：CH1(自己位置 `[0.1,0.5]`) + CH2(对手位置 `(0.5,1.0]`)，全值域不互相遮蔽；CH3~CH8 依次平移
- `render_mode="rgb_array"`: 返回 `(H,W,3)` uint8 帧；`render_mode="human"`: pygame 窗口显示；默认 None

### `bfbb10a` — fix: pettingzoo env import path and pygame module scope
- **问题**: 目录重组后 PettingZoo import 路径错误；pygame 模块作用域问题
- **调整**: 修复 import 路径和 pygame 作用域

### `62b7634` — fix: add missing get_window_width import in renderer.py
- **问题**: renderer.py 缺少 `get_window_width` 导入
- **调整**: 添加缺失 import

### `47007fd` — chore: add videos/ to gitignore, add random agent video example
- **调整**: `.gitignore` 添加 `videos/`；添加 `examples/random_agent_video.py`

---

## Phase 3: Phase1Reward 多阶段奖励函数

### `204bec5` — feat: Phase1Reward with Phase 1.1 components
- **问题**: 需要渐进式奖励函数支持课程训练（Phase 1.1 基础移动 → 1.2 炸弹 → 1.3 拾取）
- **调整**: 创建 `rewards/phase1.py` — `Phase1Reward(RewardFunction)`，`_DEFAULT_CFG` 初始值:

| 参数 | 初始值 | 说明 |
|---|---|---|
| `reward_approach` | 0.1 | 接近对手奖励（每格） |
| `reward_approach_window` | 10 | 接近奖励窗口帧数 |
| `penalty_retreat` | 0.02 | 远离对手惩罚（每格） |
| `penalty_center_dev` | 0.04 | 偏离走廊中心惩罚 |
| `penalty_stall_threshold` | 30 | 停滞计数阈值 |
| `penalty_stall_init` | 0.02 | 停滞惩罚初始值 |
| `penalty_stall_cap` | 0.5 | 停滞惩罚上限 |
| `penalty_wall` | 0.03 | 撞墙惩罚 |
| `penalty_blocked` | 0.02 | 被阻挡惩罚 |
| `reward_survive` | 0.001 | 生存奖励/帧 |
| `penalty_illegal_bomb_cap` | 0.1 | 炸弹已满惩罚 |
| `penalty_illegal_place` | 0.05 | 非法放置惩罚 |
| `penalty_illegal_ignite` | 0.05 | 非法引爆惩罚 |
| `penalty_illegal_dir` | 0.05 | 对向键惩罚 |
| `penalty_death_self` | 1.0 | 自己死亡惩罚 |
| `penalty_death_opp` | 0.5 | 对手死亡惩罚 |
| `penalty_death_self_bomb` | 3.0 | 被自己炸死惩罚 |
| `penalty_death_opp_bomb` | 1.5 | 被对手炸死惩罚 |
| `reward_place_bomb` | 0.1 | 放置炸弹奖励 |
| `reward_destroy_brick_fwd` | 0.5 | 前向炸砖奖励 |
| `reward_destroy_brick_side` | 0.1 | 侧向炸砖奖励 |
| `penalty_bomb_wasted` | 0.2 | 浪费炸弹惩罚 |
| `reward_pickup_normal` | 0.2 | 拾取普通 Buff 奖励 |
| `reward_pickup_unknown` | 0.3 | 拾取未知 Buff 奖励 |

- `_PHASE_WEIGHTS`: Phase 1.1=`{p11:1.0, p12:0.0, p13:0.0}` / 1.2=`{0.5, 1.0, 0.0}` / 1.3=`{0.25, 0.5, 1.0}`

### `d71f05f` — fix: address Task 1 review findings - illegal_dir check, remove dead config, strengthen tests
- **问题**: Review 发现: `_illegal_action` 缺少对向键检查；存在死配置 `penalty_illegal_place`
- **调整**: 添加 `sum(dir4)>2` 对向键检查；移除 `penalty_illegal_place`；强化 `test_death_self_bomb` 正面断言

### `518d443` — feat: add Phase 1.2 bomb/brick + Phase 1.3 buff pickup tests
- **调整**: 新增测试: test_bomb_placement_reward (放弹 +0.1)、test_brick_destruction_forward (前向 +0.5/侧向 +0.1)、test_buff_pickup_reward (+0.2)

### `f4e34d2` — feat: phase weight transition tests + env integration
- **调整**: test_phase_12_weights (Phase 1.2 p11=0.5 验证 survival 从 0.001→0.0005)、test_env_with_phase1_reward (50步集成)

### `22be1ad` — chore: remove unused penalty_blocked config key
- **调整**: 移除 `penalty_blocked: 0.02`（从未使用）

### `2b84139` — feat: add reward_kill_opponent (+4) in Phase 1.2
- **问题**: Phase 1.2 缺乏击杀对手的直接奖励信号
- **调整**: 新增 `reward_kill_opponent: 4.0`，检测对手存活→死亡切换

### `095d4e0` — refactor: scale all reward values down by 1/3 to prevent gradient explosion
- **问题**: 奖励值过大导致梯度爆炸
- **调整**: 全部奖励值除以 3（`_DEFAULT_CFG` 统一缩放）:

| 参数 | 缩放前 | 缩放后(÷3) |
|---|---|---|
| `reward_approach` | 0.1 | **0.033** |
| `penalty_retreat` | 0.02 | **0.007** |
| `penalty_center_dev` | 0.04 | **0.013** |
| `penalty_stall_init` | 0.02 | **0.007** |
| `penalty_stall_cap` | 0.5 | **0.167** |
| `penalty_wall` | 0.03 | **0.01** |
| `reward_survive` | 0.001 | **0.0003** |
| `penalty_illegal_bomb_cap` | 0.1 | **0.033** |
| `penalty_illegal_ignite` | 0.05 | **0.017** |
| `penalty_illegal_dir` | 0.05 | **0.017** |
| `penalty_death_self` | 1.0 | **0.333** |
| `penalty_death_opp` | 0.5 | **0.167** |
| `penalty_death_self_bomb` | 3.0 | **1.0** |
| `penalty_death_opp_bomb` | 1.5 | **0.5** |
| `reward_place_bomb` | 0.1 | **0.033** |
| `reward_kill_opponent` | 4.0 | **1.333** |
| `reward_destroy_brick_fwd` | 0.5 | **0.167** |
| `reward_destroy_brick_side` | 0.1 | **0.033** |
| `penalty_bomb_wasted` | 0.2 | **0.067** |
| `reward_pickup_normal` | 0.2 | **0.067** |
| `reward_pickup_unknown` | 0.3 | **0.1** |

### `dfb2be2` — feat: add phase-aware map generator with connected map (Phase 1.1) and blue spawn sampling
- **问题**: 不同阶段需要不同地图；Phase 1.1 需要连通地图确保可达性
- **调整**: 创建 `src/map_generator.py`
- Phase 1.1: `_generate_connected_map()` — `brick_prob=0.3`，BFS 验证 `>=5` 候选格，最多重试 30 次，回退全空地(`brick_prob=0.0`)
- Phase 1.2/1.3: `_generate_standard_map()` — `brick_prob=cfg.BRICK_GEN_PROB`(0.7)，无连通性要求
- `_sample_blue_spawn()`: Phase 1.1 从同一连通分量；Phase 1.2+ 任意地板格
- 网格生成: 石头在 `(偶数,偶数)`、地板在 `(奇数,奇数)`、走廊在 `(奇,偶)/(偶,奇)`

### `b95cc8d` — fix: address Task 1 review findings — float phase check, test names, fallback test, comment cleanup
- **问题**: Review 发现: 浮点 phase 检查不稳健、测试命名不规范、缺少回退测试
- **调整**: 浮点 phase 检查修复、测试命名改进、添加回退测试

### `2f88ce2` — feat: wire phase-aware map generation into BombermanEnv.reset()
- **问题**: BombermanEnv.reset() 未使用 phase-aware 地图生成
- **调整**: 集成 `_init_phase()` 方法，通过 `reset(options={"phase": 1.1})` 驱动；无 options 回退原始行为

### `100564e` — fix: reset engine refresh_timer/round_delay_timer/next_bomb_id in _init_phase
- **问题**: phase 切换时 engine 的 `refresh_timer`/`round_delay_timer`/`next_bomb_id` 未重置
- **调整**: `_init_phase()` 中重置: `refresh_timer=720`, `round_delay_timer=72`, `next_bomb_id=0`

### `32afa75` — chore: raise connected map min candidate threshold from 5 to 14 (component >= 15 cells)
- **问题**: 连通地图最小候选阈值太低，map generation 不稳定
- **调整**: 候选格阈值 `5 → 14`（连通分量 `>=15` 格）

### `5c8fa3b` — fix: raise Phase 1.1 connected map threshold from 5 to 100 candidate cells for a larger training playground
- **问题**: 连通地图训练场地太小（~15 格），agent 移动空间不足
- **调整**: 候选格阈值 `5 → 100`（连通分量 `>=101` 格），训练场地大幅扩大

### `efd8c5c` — refactor: set reward_survive default to 0.0 in Phase1Reward
- **调整**: `reward_survive` 默认值 `0.0003 → 0.0`

### `f44e7fc` — docs: document phase-aware episode termination strategy
- **调整**: 记录 phase-aware episode 终止策略文档

### `7366057` — test: add failing tests for phase-aware episode termination
- **调整**: TDD — 先写 6 个失败测试覆盖所有终止/截断场景

### `cbfda70` — feat: add phase-aware episode termination with timeout in BombermanEnv
- **问题**: 所有 phase 使用相同终止逻辑，不符合课程训练需求
- **调整**:
  - Phase 1.1: Red 到达 Blue (Chebyshev ≤ 1) → `terminated=True`, `reward=+1`
  - Phase 1.2/1.3: 死亡 → `terminated=True`（使用已有 death/kill 奖励）
  - 超时 Phase 1.1=6000帧(250s), Phase 1.2/1.3=6000帧 → `truncated=True`
  - 默认 `reward_survive` 设为 `0.0`

### `54a4eb7` — fix: guard Phase 1.1 +1 success bonus with not truncated in BombermanEnv
- **问题**: Phase 1.1 超时也可能错误发放 +1 成功奖励
- **调整**: 成功 bonus 仅在 `not truncated` 时发放

### `8c81fd9` — docs: update hot.md with final test count 153/153
- **调整**: hot.md 更新测试计数

### `3f1b626` — docs: add training dependencies guide
- **调整**: 创建 `docs/training_dependencies.md`（PyTorch/SB3/视频/头部环境/CUDA/故障排除表）

---

## Phase 4: 训练管道搭建

### `2cc19b9` — feat: add config system (YAML loader + fast-validation default)
- **问题**: 训练超参数硬编码，无法灵活配置
- **调整**: 新增 `src/config_loader.py` + `configs/phase1_fast.yaml`
- `_REQUIRED_KEYS`: `["run", "ppo", "network", "phases", "evaluation", "composite_score", "progression", "checkpoint", "logging"]`
- YAML 配置初始值:

| 键路径 | 值 |
|---|---|
| `run.output_dir` | `runs/phase1` |
| `run.seed` | 42 |
| `ppo.learning_rate` | 3.0e-4 |
| `ppo.n_steps` | 2048 |
| `ppo.batch_size` | 64 |
| `ppo.n_epochs` | 10 |
| `ppo.gamma` | 0.99 |
| `ppo.gae_lambda` | 0.95 |
| `ppo.clip_range` | 0.2 |
| `ppo.ent_coef` | 0.01 |
| `ppo.vf_coef` | 0.5 |
| `ppo.max_grad_norm` | 0.5 |
| `network.features_dim` | 256 |
| `phases.1.1.min_steps` | 100000 |
| `phases.1.1.max_steps` | 500000 |
| `evaluation.interval` | 25000 |
| `evaluation.episodes` | 10 |
| `evaluation.video_episodes` | 3 |
| `evaluation.deterministic` | true |
| `progression.composite_threshold` | 0.5 |
| `progression.patience` | 5 |
| `checkpoint.interval` | 50000 |
| `logging.heartbeat_seconds` | 60 |
| `device` | auto |

- composite_score 权重初版: Phase 1.1: survival_rate=0.3, approach=0.3, illegal=0.2, low_dist=0.2
- Bugfix: YAML phase 键 `"1.1"` 加引号防 float 解析；`3.0e-4` 使用科学计数法防字符串问题

### `5796b5f` — feat: add Res-CNN feature extractor for grid observations
- **问题**: SB3 默认 CNN (NatureCNN) 不适合 9 通道 HWC 网格观测
- **调整**: `src/feature_extractor.py` — `ResCnnFeatureExtractor`
- **网络结构**:

| 层 | 输入→输出 | 核/步长/填充 |
|---|---|---|
| Conv2d+ReLU | `9→32` | 3×3, 1, 1 |
| Conv2d+ReLU | `32→32` | 3×3, 1, 1 |
| ResidualBlock | `32→32` | conv→relu→conv+skip→relu |
| Conv2d+ReLU | `32→64` | 3×3, 1, 1 |
| Conv2d+ReLU | `64→64` | 3×3, 1, 1 |
| Flatten | — | from sample |
| Linear+ReLU | `n→256` | `_features_dim=256` |

- `HWC→CHW` transpose 适配 SB3 CnnPolicy
- 策略头: `256→128→MultiBinary(6)`；价值头: `256→256→scalar`

### `b2e79d4` — feat: add video recorder with graceful ffmpeg fallback
- **问题**: 训练过程无法录制视频评估 agent 行为
- **调整**: `src/video_recorder.py` — `VideoRecorder(output_dir, fps=24)`；`record_episode(env, model, seed, path, phase)`；`write_frames(frames, path, fps=24)`；ffmpeg 不可用时静默 fallback

### `f9f69a4` — feat: add evaluation module with composite score
- **问题**: 缺乏标准化 agent 评估指标
- **调整**: `src/evaluate.py`
- `evaluate_phase(env, model, episodes=10, seed=42, deterministic=True, render=False)`
- `compute_composite_score(metrics, weights, phase)` — 加权归一化
- 指标: survival_rate, normalized_approach, low_illegal_action_rate, low_final_distance, bomb_efficiency, brick_destroy_rate, buff_pickup_rate, kill_rate

### `71ae175` — feat: add training pipeline script with PPO, evaluation, checkpointing
- **问题**: 需要端到端训练脚本连接所有模块
- **调整**: `scripts/train_phase1.py` — `TrainingPipeline` 类
- 课程推进: 1.1→1.2→1.3，各阶段含 min_steps/max_steps、composite_threshold(0.5)、patience(5)
- 检查点命名: `ppo_phase1.1_step_00050000.zip`；恢复时验证 config hash
- 心跳日志: 每 `heartbeat_seconds`(60s) 打印进度；失败报告含完整 traceback

### `31691f9` — fix: address final review findings
- **问题**: Review 发现 8 个问题:
  - **严重**: Phase 1.3 达标后 `while next_phase` 无哨兵 → 死循环 → 修复: 哨兵 `2.0` 退出
  - **重要**: `normalized_approach` 无法获取在线指标 → 改用 final distance 代理
  - **重要**: `--override-config` CLI 参数未生效 → 修复: 跳过 hash 验证
  - **重要**: `VideoRecorder.record_episode` 将 phase 硬编码为 `1.1` → 修复: 接受 phase 参数
  - **次要**: 双重 final checkpoint → 移除重复保存
  - **次要**: 缺少 `tb_log_name` → 添加 `f"phase{phase}"`
  - **次要**: 死代码 `load_checkpoint` → 移除
  - **次要**: 全局 RNG seed 在 episode 级不应重复 → 改为函数级单次 seed

### `8a6caa7` — chore: auto-add Co-authored-by trailer for samurazdenko
- **调整**: `.githooks/prepare-commit-msg` — 每次 commit 追加 `Co-authored-by: samurazdenko`；`core.hooksPath=.githooks`

### `a5f7d7a` — feat: add SubprocVecEnv parallel env collection
- **问题**: 单环境收集数据太慢，GPU 利用率低
- **调整**:
  - `configs/phase1_fast.yaml`: 新增 `run.n_envs: 8`
  - `config_loader.py`: 验证 `n_envs: int >= 1`，默认 1
  - `n_steps` 自动调整: `n_steps // n_envs`（总经验量不变）
  - `SDL_VIDEODRIVER=dummy` 防止子进程显示冲突
  - 评估使用独立单 env（`evaluate_phase` 需要 `env.engine`）

### `cd97df1` — tune config for T4x2: n_envs=10, n_steps=8192, threshold=0.8
- **问题**: 默认配置不适合 T4x2 GPU
- **调整**: `n_envs 8→10`, `n_steps 2048→8192`, `composite_threshold 0.5→0.8`

### `c18c853` — fix evaluation: use actual initial distance as denominator for approach/low_dist metrics
- **问题**: Phase 1.1 Blue 随机出生，初始距离并非固定 30 格，硬编码分母导致指标偏差
- **调整**: `normalized_approach` 和 `low_final_distance` 改用每局实际初始距离做分母

### `266d28b` — fix: disable bomb placement in Phase 1.1 to prevent self-destruct exploit
- **问题**: Agent 放弹自杀提前结束 episode 逃避后续惩罚
- **调整**: `BombermanEnv.step()` 中 Phase 1.1 时 `action[4]`(放弹)=0, `action[5]`(引爆)=0 强制置零

### `7f67c57` — feat: Phase 1.1 per-frame survival time penalty to prevent standing around exploit
- **问题**: 禁用炸弹后 agent 站桩等待超时，无惩罚
- **调整**: `_survival()` 逻辑变更:
  ```python
  # 之前: return self.cfg["reward_survive"] if alive else 0.0  (0.0)
  # 之后: Phase 1.1: return -0.002 (每帧); Phase 1.2+: return 0.0
  ```
- 新增参数: `penalty_survive_time: 0.002`（整局约 -10.8）

### `876a382` — feat: heatmap stall detection (40-frame distinct grid cells) + remove Phase 1.1 survival_rate weight
- **问题**: 旧 stall 检测基于对手距离，agent 左右横跳时不断重置计数器
- **调整**: `_stall(curr_mdist)` → `_stall(gx, gy)`:
  ```python
  # 之前: if prev_mdist is not None and curr_mdist < prev_mdist: stall_frames=0
  # 之后: 40帧滚动窗口, 用 collections.deque(maxlen=40)
  #       distinct <= 2 格 → 停滞; > 2 → 重置
  ```
- `configs/phase1_fast.yaml` Phase 1.1 composite score:
  - `survival_rate: 0.3` → **移除**（永远 1.0，废权重）
  - `normalized_approach: 0.3` → **0.6**

### `2f21c0d` — change config
- **调整**: 配置中间调整

### `30d1559` — tune: n_envs 10->20 to saturate T4 GPU (70%->~90+%)
- **问题**: GPU 利用率仅 70%，未充分利用
- **调整**: `n_envs 10→20`，GPU 利用率 70%→90%+

### `0519266` — fix: reduce stall cap from 0.167 to 0.00167 (100x) to prevent reward domination
- **问题**: stall cap 0.167 占总惩罚 98.8%，完全淹没了接近奖励（+0.033/格）和到达 bonus（+1.0），agent 无移动动力
- **调整**: `penalty_stall_cap: 0.167 → 0.00167`（除以 100），移动净收益首次为正

### `e90d58f` — feat: continuous float Manhattan distance for approach/retreat (fractional grid units)
- **问题**: 整数格坐标只在跨格线时触发奖励，每像素移动无信号
- **调整**: `__call__()` 新增连续浮点坐标计算:
  ```python
  fx = (pos_x - CELL_SIZE/2) / CELL_SIZE + 1
  fy = (pos_y - UI_BAR_HEIGHT - CELL_SIZE/2) / CELL_SIZE + 1
  fdist = abs(fx - opp_fx) + abs(fy - opp_fy)
  ```
- `_approach_and_retreat` 签名: `(gx,gy,opp_gx,opp_gy,mdist)` → `(fx,fy,opp_fx,opp_fy,fdist)`

### `ef604f3` — tune: reward_approach 0.033->0.231 (7x), penalty_retreat 0.007->0.021 (3x)
- **问题**: 连续浮点距离后奖励信号仍不够强
- **调整**:
  - `reward_approach: 0.033 → 0.231`（7×）
  - `penalty_retreat: 0.007 → 0.021`（3×）

### `14d1bcd` — docs: add scripts/requirements.txt for training environment setup
- **调整**: 创建 `scripts/requirements.txt`（torch, sb3, pygame, opencv-python-headless, matplotlib, pandas）

### `09f7e28` — feat: log loss curve data per PPO update + raw network output every 24 eval frames
- **问题**: 训练中缺乏损失曲线和网络输出可见性，无法诊断 policy collapse
- **调整**: 新增 `LossRecorderCallback`，每次 PPO update 记录 `loss/policy_loss/value_loss/entropy/approx_kl` 到 `logs/losses_phaseXX.jsonl`
- `_record_net_output()`: 评估时每 24 帧记录原始 logits 和 sigmoid 概率到 `evaluations/phase_XX/step_XXXXXXX_net_output.jsonl`

### `f948761` — fix: reduce PLAYER_HITBOX_SIZE 0.8->0.6, penalty_wall 0.01->0.003
- **问题**: 碰撞箱 32px(0.8) 走廊通过性差；撞墙惩罚 -0.01 过重
- **调整**: `PLAYER_HITBOX_SIZE: 0.8 → 0.6`（32px→24px，单边间隙 4px→8px）；`penalty_wall: 0.01 → 0.003`

### `c2e7b70` — fix: access BernoulliDistribution.logits via internal PyTorch distribution
- **问题**: SB3 `BernoulliDistribution` 不直接暴露 `.logits`
- **调整**: `dist.distribution.logits` → `dist.distribution.logits`（访问内部 PyTorch `Bernoulli` 对象）

### `5e773e2` — tune: gradient distance reward + remove P1.1 survival penalty + batch_size 128
- **问题**: 分析日志发现 3 次 update 后 policy 全零（logits 接近随机初始化）
- **调整**: 三项改动:

**1. `_distance_gradient` 替换 `_approach_and_retreat`**:
```python
# 之前(10帧窗口):
def _approach_and_retreat(self, gx, gy, opp_gx, opp_gy, curr_mdist):
  self._pos_buffer.append(curr_mdist)
  if len(self._pos_buffer) >= 10:
    avg = sum(self._pos_buffer) / 10
    # ...

# 之后(每帧梯度):
def _distance_gradient(self, fdist):
  diff = self._prev_fdist - fdist  # 正=接近
  if diff > 0: return 2.0 * diff
  else: return -0.02 * abs(diff)
```
- 移除窗口: `reward_approach_window=10`, `self._pos_buffer`, `self._prev_avg_x`, `self._prev_avg_y`
- 参数: `reward_approach 0.231→2.0`, `penalty_retreat 0.021→0.02`, `penalty_wall 0.01→0.003`

**2. 移除 Phase 1.1 生存惩罚**:
- `penalty_survive_time: 0.002` → **移除**（`_survival` 返回 `reward_survive` = 0.0）

**3. batch_size 减半**:
- `batch_size: 256 → 128`（梯度步数: 32→64/epoch, 320→640/update 翻倍）

### `f1f3272` — feat: use argmax for deterministic eval instead of per-dim >0.5 threshold
- **问题**: **policy collapse 根本原因** — `model.predict(deterministic=True)` 使用 `BernoulliDistribution.mode()` 逐维 `sigmoid(logit)>0.5`。初始化 logits ~ O(0.01)，一次 PPO update 将全部 logits 推负 → 输出全零（6 维无一超过 0.5 阈值）
- **调整**: 替换为 argmax 确定性策略:

```python
# 之前:
action, _ = model.predict(obs, deterministic=True)
# action = [0, 0, 0, 0, 0, 0] ← 全零，agent 什么都不做

# 之后:
def _argmax_action(model, obs) -> np.ndarray:
    with torch.no_grad():
        obs_t = torch.as_tensor(obs).unsqueeze(0).float().to(model.device)
        dist = model.policy.get_distribution(obs_t)
        logits = dist.distribution.logits  # shape (1, 6)
        best = torch.argmax(logits, dim=-1).item()  # `0`~`5`
    action = np.zeros(6, dtype=np.int8)
    action[best] = 1
    return action  # 始终保证至少一个动作为 1
```

- 移除评估中的对向键惩罚计数器（argmax 天然保证不存在对向键）

---

## 统计数据

- **总提交数**: 74
- **测试总数**: 203+ 全部通过
- **主要贡献者**: Tony-tz-notabot, samurazdenko

---

## 附录: Phase1Reward 奖励参数演化全景

| 参数 | `204bec5` 初始 | `095d4e0` ÷3 | `7f67c57` 生存罚 | `876a382` 热力图 | `0519266` stall缩 | `ef604f3` 奖励升 | `5e773e2` 梯度 |
|---|---|---|---|---|---|---|---|---|
| reward_approach | 0.1 | 0.033 | — | — | — | **0.231** | **2.0** |
| reward_approach_window | 10 | 10 | — | — | — | — | **removed** |
| penalty_retreat | 0.02 | 0.007 | — | — | — | **0.021** | **0.02** |
| penalty_center_dev | 0.04 | 0.013 | — | — | — | — | — |
| penalty_stall_cap | 0.5 | 0.167 | — | — | **0.00167** | — | — |
| penalty_wall | 0.03 | 0.01 | — | — | — | — | **0.003** |
| reward_survive | 0.001 | 0.0003 | 0.0 | — | — | — | — |
| penalty_survive_time | — | — | **+0.002** | — | — | — | **removed** |
| penalty_death_self_bomb | 3.0 | 1.0 | — | — | — | — | — |
| reward_kill_opponent | — | 1.333 | — | — | — | — | — |
| reward_destroy_brick_fwd | 0.5 | 0.167 | — | — | — | — | — |
