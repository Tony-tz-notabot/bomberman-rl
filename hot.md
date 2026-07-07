# 工作进展 — Bomberman PVP + AI 集成

## ✅ 已完成

### 2025-06-30
- [x] **代码库全景分析** — 阅读所有源代码 (main.py ~1250行单文件)、README、RULES
- [x] **CLAUDE.md** — 编写代码库文档，记录架构、关键子系统、坐标系统注意事项、常见开发任务
- [x] **测试基础设施搭建**
  - 创建 `tests/` 目录 + pytest 配置
  - 99 个测试用例，覆盖：坐标转换、Config、数据类、地图生成、炸弹/爆炸/连锁、碰撞、死亡/护盾、6种能力、Buff 系统、得分/回合生命周期
  - 全部通过，无间歇性失败

### 2026-07-01
- [x] **Task 8: 提取 input_handler.py** — 创建 input_handler.py 模块，包含 InputHandler 类。负责双人按键状态追踪（press/release）、边沿检测扣动（action 键上升沿触发）、build_actions() 生成 (p1_actions, p2_actions) 动作字典。BombermanGame 移除 keys_red/keys_blue/handle_key/sync_input/_build_red_actions/_build_blue_actions，改用 self.input_handler 委托。`_check_menu_key()` 处理状态转换键（ENTER/R/P）。全部 99 测试通过，游戏启动正常。
- [x] **Task 9: 提取 settings_ui.py** — 创建 settings_ui.py 模块，包含 SettingsUI 类。从 BombermanGame 移出 init_settings_ui()、draw_settings_panel()、handle_settings_click() 及其相关字段。param_list 所有时间参数从 float 秒改为 int 帧（×24），与 config.py 的帧基设计一致。BombermanGame 保留 toggle_settings() 和 settings_pause_state 用于状态管理。全部 99 测试通过。
- [x] **CLAUDE.md 添加压缩恢复指引** — 要求压缩后先读 hot.md 恢复心智
- [x] **settings.json 配置三个钩子**
  - `PreCompact` — 压缩前检查进度并更新 hot.md，明确交接细节
  - `PostCompact` — 压缩后自动提示阅读 hot.md 恢复心智状态
  - `Stop` — Edit/Write 后验证有意义的改动已记录到 hot.md
  - 修复：`PostCompact` 从 `hookSpecificOutput` 改为顶层 `systemMessage` 字段（原结构不被 PostCompact 事件接受）
  - 修复：`PreCompact` 从 `systemMessage` JSON 输出改为纯文本压缩指令（PreCompact 无法注入模型上下文，exit 0 的 stdout 作为自定义压缩指令指导总结器保留关键信息）
- [x] **Task 1: 提取 config.py** — 创建 config.py 模块，所有时间参数从秒转换为帧（×24），保留 cfg 全局单例。修改 main.py 配置导入、游戏循环改为 cfg.FPS (24fps)、所有计时器递减改为每 tick 减 1 帧。更新测试断言。全部 99 个测试通过。
- [x] **Task 2: 提取 constants.py** — 创建 constants.py 模块，将颜色常量和 GameState 枚举从 main.py 移出。
- [x] **Task 3: 提取 utils.py** — 创建 utils.py 模块，将坐标转换 (grid_to_pixel, grid_center, pixel_to_grid)、clamp、sign、box_overlap 工具函数从 main.py 移出。
- [x] **Task 4: 提取 models.py** — 创建 models.py 模块，包含 Player、Bomb、BuffItem 数据类及 4 个 Snapshot 只读 dataclass (PlayerSnapshot, BombSnapshot, BuffItemSnapshot, GameSnapshot)。Bomb 构造函数参数 `timer` → `fuse_frames`（int），Player 的 `death_timer`/`invincible_timer` 改为 int。更新 main.py 移除原数据类并 import，更新测试断言。99 测试通过。
- [x] **Task 5: 创建 game_engine.py** — 创建纯逻辑 GameEngine 类 (~440行)，零 pygame 依赖。包含完整游戏逻辑：地图生成、玩家移动/碰撞、炸弹放置/踢飞/定时器、爆炸 BFS 连锁、死亡/护盾、Buff 拾取/刷新、6种能力计时器（kick/remote/shield/diarrhea/reverse/float）、得分/回合生命周期。所有定时器帧基（int），移动使用 DT_OVER_DTAU。创建 smoke test，99 现有测试全部通过。
- [x] **Task 6: BombermanGame 委托 GameEngine** — BombermanGame 移除所有重复游戏逻辑，创建 `self.engine = GameEngine()` 并委托全部状态和更新逻辑。GameEngine 通过动作字典驱动 (`step(p1_actions, p2_actions)`)。渲染代码保持不动。测试全部 99 通过。
- [x] **Task 7: 提取 renderer.py** — 创建独立渲染模块 Renderer 类（380 行），所有绘制函数从 main.py 移至 renderer.py。Renderer 以 GameSnapshot 只读 dataclass 为唯一数据源，零引擎耦合。适配要点：`self.grid[x][y]` → CellType 常量解码 (CELL_EMPTY/STONE/BRICK/BUFF/BOMB/EXPLOSION)、玩家方向眼睛 `self.get_input_direction(p)` → `ps.dir_x/dir_y` 快照字段、获取胜利画面 / 回合延迟覆盖层通过 `snap.state`/`snap.current_winner`/`snap.round_delay_timer`。维护全部视觉特效：死亡渐隐、护盾光圈闪烁、炸弹引信闪烁、爆炸强度随机。GameSnapshot 新增 `current_winner` 和 `round_delay_timer` 字段，PlayerSnapshot 新增 `dir_x`/`dir_y`。`get_snapshot()` 更新填充这些字段。主流程 `render()` 简化为调用 `self.renderer.draw(snapshot)`。测试全部 99 通过，游戏运行视觉一致。
- [x] **Task 10: main.py 精简为胶水代码** — main.py 从 1250 行精简至 138 行，仅导入模块+主循环，无游戏逻辑
- [x] **Task 11: 最终验证** — 99 测试全通过，GameEngine 零 pygame 依赖验证通过，smoke test 移除，gitignore 添加

### 2026-07-03
- [x] **scripts/README.md** — 编写训练脚本目录 README，包含 train_phase1.py 简介、CLI 参数表、课程阶段说明、输出结构、常用命令示例
- [x] **README.md 全面更新** — 反映当前项目状态：9通道观测、src/ 目录结构、训练管道（configs/scripts/rewards）、185+ 测试、CUDA 自动检测、Phase1Reward、全套文件树
- [x] **CUDA 自动检测确认** — `device: auto` 默认通过 `torch.cuda.is_available()` 自动检测，无需手动指定

- [x] **Bugfix: `python src/main.py` ModuleNotFoundError** — `main.py` 顶部添加 `sys.path` 修复，使直接运行 `python src/main.py` 和 `python -m src.main` 均能正常工作

## 🚧 当前进度

**阶段：Phase 2 — Gym 环境封装 — 全部完成 ✅**

### 2026-07-01
- [x] **Phase 2: Gym 环境封装全部完成**
  - 设计文档: `docs/superpowers/specs/2026-07-01-bomberman-gym-env-design.md` (设计锁定并提交)
  - `rewards/__init__.py` — RewardFunction 基类 (ABC, reset/__call__)
  - `rewards/sparse.py` — SparseReward (+1/-1/0 稀疏奖励)
  - `bomberman_env.py` — BombermanEnv(gym.Env) 单智能体环境
    - 8 通道观察空间 Box(0,1,(11,19,8)): 地形/玩家高斯热力图/炸弹引信/Buff+爆炸/双能力广播/双方状态
    - 动作空间 MultiBinary(6) + 对向键惩罚
    - build_obs() 模块级函数（PettingZoo 复用）
    - reset(options={"grid": matrix}) 矩阵初始化 + 默认随机回退
    - opponent_fn 函数参数控制蓝方
    - RewardFunction 适配器可插拔
  - `pettingzoo_env.py` — BombermanPettingZooEnv(ParallelEnv) 多智能体环境
    - 直接包装 GameEngine，绕过 opponent_fn
    - 从 bomberman_env 导入 build_obs 作共享观察构建器
    - 支持 tied policy（自/他对调通道编码）
  - bugfix: CH1 玩家编码 — np.maximum 导致对手基线 0.6 覆盖自身位置，改为 np.where(self_heat >= opp_heat) 实现自身[0.1,0.5]/对手(0.5,1.0] 正确分离
  - 测试: 8 个 Gym 测试 + 4 个 PettingZoo 测试，合计 112 测试全部通过
  - 示例: `examples/train_with_sb3.py` — PPO/CnnPolicy 训练脚本

### 新文件
```
├── bomberman_env.py              # Gym.Env 单智能体 (260 行)
├── pettingzoo_env.py             # PettingZoo ParallelEnv (185 行)
├── rewards/
│   ├── __init__.py                # RewardFunction 基类
│   └── sparse.py                  # 稀疏奖励示例
├── tests/
│   ├── test_bomberman_env.py      # 8 个测试
│   └── test_pettingzoo_env.py     # 4 个测试
└── examples/
    └── train_with_sb3.py          # SB3 训练示例
```

### 2026-07-01 (later)
- [x] **目录重组: 所有游戏源文件移入 `src/` 文件夹**
  - `config.py`, `constants.py`, `utils.py`, `models.py`, `game_engine.py`, `renderer.py`, `input_handler.py`, `settings_ui.py`, `main.py`, `bomberman_env.py`, `pettingzoo_env.py` 全部移入 `src/`
  - 所有文件中的 import 路径更新为 `from src.xxx import ...` 前缀
  - 外部引用（tests/、rewards/、examples/）同步更新
  - `launch.bat` 改为执行 `src\main.py`
  - `CLAUDE.md` 文件结构文档更新
  - 112 测试全部通过 (108 pass + 4 skip)

### Phase 2.5: Gym 环境改进 — 通道分离 & 标准化渲染
- [x] **观察空间通道分离 (8→9)** — CH1 拆为 CH1(自己位置) + CH2(对手位置)，全值域 [0,1] 高斯热力图，不再互相遮蔽。CH3~CH8 依次平移。BombermanEnv + PettingZooEnv 同步更新。
- [x] **Gym 标准化 render()** — 实现 `render_mode="rgb_array"` (返回 (H,W,3) uint8 帧) 和 `render_mode="human"` (pygame 窗口显示)。复用现有 Renderer 类 + offscreen pygame.Surface。render_mode 默认为 None，完全向后兼容。
- [x] **测试** — 3 个新 render 测试 (rgb_array、None、多帧稳定性)，1 个 PZ render 测试，111 passed / 5 skipped
- [x] 设计文档: `docs/superpowers/specs/2026-07-02-gym-obs-render-improvements.md`

### Phase 3: Phase1Reward 多阶段奖励函数 — 全部完成 ✅

### 2026-07-02
- [x] **Task 1: Phase1Reward skeleton + Phase 1.1 全部分项**（review clean after fix）
  - `rewards/phase1.py` — Phase1Reward(RewardFunction) 完整实现 (3 个阶段)
  - Phase 1.1: _survival, _approach_and_retreat, _center_deviation, _stall, _wall_collision, _illegal_action, _death, _explosion_cells_set
  - Phase 1.2: _bomb_placement, _brick_destruction, _wasted_bomb
  - Phase 1.3: _buff_pickup
  - `tests/test_phase1_reward.py` — 11 个测试全部通过
  - Bugfix: BombSnapshot.owner 从 Player 对象引用改为 player.id 字符串 (game_engine.py:651)
  - Review 修复: _illegal_action 添加 sum(dir4)>2 检查 + 移除死配置 penalty_illegal_place + 强化 test_death_self_bomb 正面断言
- [x] **Task 2: Phase 1.2 + 1.3 新增奖励测试**
  - test_bomb_placement_reward — 验证成功放弹 +0.1
  - test_brick_destruction_forward — 验证方向性炸砖 (前向+0.5, 侧向+0.1)
  - test_buff_pickup_reward — 验证捡 Buff +0.2
- [x] **Task 3: 阶段权重过渡 + 集成测试**
  - test_phase_12_weights — 验证 Phase 1.2 p11=0.5 权重将 survival 从 0.001 减半至 0.0005
  - test_env_with_phase1_reward — BombermanEnv + Phase1Reward 集成测试 (50步)
  - examples/train_with_sb3.py — 添加 Phase1Reward 配置示例
  - 129 测试全部通过
- [x] **Phase 1.2 加入杀死对手奖励 +4.0**
  - reward_kill_opponent: 4.0, 检测对手存活→死亡切换
  - test_kill_opponent_reward 通过, 130/130 全部通过

### 2026-07-02 (later)
- [x] **三阶段地图初始化与 Blue 随机采样**
  - 更新设计文档 `docs/superpowers/specs/2026-07-02-phase1-training-pipeline-design.md` 添加 Map Generation Strategy 章节
  - `src/map_generator.py` 新模块 (纯函数，无状态):
    - `generate_map()` + `connected_floor_cells()` 公开 API
    - Phase 1.1: `_generate_connected_map()` 砖块概率 0.3 + BFS 连通验证 + 30次重试回退
    - Phase 1.2/1.3: `_generate_standard_map()` 使用 BRICK_GEN_PROB=0.7
    - `_sample_blue_spawn()` Blue 随机出生 (Phase 1.1 连通分量内, Phase 1.2/1.3 任意地板)
    - 12 个测试覆盖连通性、safe_spots、标准/连通地图、回退路径
  - `src/bomberman_env.py` 整合:
    - `_init_phase()` 方法，通过 `reset(options={"phase": 1.1})` 驱动
    - 无 options → 回退原始行为，options={"grid":...} → 兼容
    - 5 个集成测试覆盖 phase reset、连通性验证、回退/兼容、随机性
  - 全套 147 测试通过，计划评审干净

### 2026-07-02
- [x] **Phase-aware Episode Termination (commit cbfda70)**
  - Phase 1.1: red reaches blue (Chebyshev ≤ 1) → terminated + +1 reward
  - Phase 1.2/1.3: death → terminated (existing death/kill rewards)
  - Timeout: truncated, per-frame reward kept, no termination bonuses
  - `reward_survive` default set to 0.0
  - 6 new tests covering all termination/truncation scenarios
  - 153/153 tests passing

### 2026-07-02 (later)
- [x] **Task 1: Config file + YAML loader (SDD Phase 1 pipeline)**
  - `configs/__init__.py` — empty package marker
  - `scripts/__init__.py` — empty package marker
  - `configs/phase1_fast.yaml` — full YAML config (run/ppo/network/phases/evaluation/composite_score/progression/checkpoint/logging/device)
  - `src/config_loader.py` — `load_config()` with validation (9 required top-level keys, phase keys, composite_score keys) + `compute_config_hash()` (SHA256[:16])
  - `tests/test_config_loader.py` — 5 tests: valid load, missing key error, default file load, hash deterministic, hash changes on diff
  - Bugfix: YAML phase keys `"1.1"` quoted to prevent float parsing; `3.0e-4` to avoid string parsing issue
  - 158/158 tests passing (153 existing + 5 new)

### 2026-07-02 (SDD Pipeline - 第一批并行)
- [x] **Task 6: 依赖文档**
  - `docs/training_dependencies.md` — 完整设置指南（PyTorch/SB3/视频/头部环境/CUDA）
  - 测试验证命令和烟雾测试命令
  - 排除故障表
- [x] **Task 2: Res-CNN Feature Extractor**
  - `src/feature_extractor.py` — ResCnnFeatureExtractor(BaseFeaturesExtractor) with ResidualBlock
  - Conv: 9->32->ResBlock(32)->64->64, flatten, Linear->256, ReLU
  - HWC->CHW transpose for SB3 CnnPolicy compatibility
  - `_features_dim=256`, gradient flow verified
  - `tests/test_feature_extractor.py` — 6 tests all passing
- [x] **Task 3: Video Recorder**
  - `src/video_recorder.py` — VideoRecorder class with graceful ffmpeg fallback
  - Public API: `VideoRecorder(output_dir, fps)`, `.available` property, `.record_episode(env, model, seed, path)`
  - `write_frames()` standalone function for direct frame-to-mp4 writing
  - 6 tests: available check (with/without ffmpeg), output dir creation, synthetic frame recording, end-to-end env+model recording, graceful fallback without ffmpeg
  - 170/170 tests passing (153 existing + 6 new + 5 config + 6 feature_extractor)
- [x] **Task 4: Evaluation Module** (commit f9f69a4)
  - `src/evaluate.py` — `evaluate_phase()`, `compute_composite_score()`, `format_metrics()`
  - Fixed-seed evaluation with per-episode global RNG seeding for deterministic reproduction
  - Composite score with normalized metrics (survival, approach, illegal action, distance, bomb efficiency, brick destroy, buff pickup, kill rate)
  - 10 tests covering composite score computation, phase evaluation, metric formatting
  - 180/180 tests passing (170 existing + 10 new)
- [x] **Task 5: Main Training Script** (no commit — API error during commit, files created)
  - `scripts/train_phase1.py` — TrainingPipeline class with:
    - Phase-aware env factory (\_make_phase_aware_env with SB3-safe reset patching)
    - PPO + ResCnnFeatureExtractor model creation
    - Curriculum progression (1.1→1.2→1.3 with min/max steps)
    - Fixed-seed evaluation with video recording
    - Checkpoint/resume with config hash validation
    - Heartbeat logging + failure reports
    - CLI: --config, --resume, --total-steps-override, --eval-interval, --device, --override-config
  - `tests/test_training_pipeline.py` — 5 smoke tests including real PPO training
  - 5/5 smoke tests passing, full suite 185/185 passing
  - **Fix round (commit 31691f9):** 全部 8 个 final review findings 修复:
    - Critical: phase 1.3 提前达标时的无限循环修复 (sentinel `2.0`)
    - Important: `normalized_approach` 指标改为从 final distance 代理计算
    - Important: `--override-config` CLI 参数现在实际生效
    - Important: `VideoRecorder.record_episode` 接受 phase 参数
    - Minor: 移除双重 final checkpoint / 添加 tb_log_name / 移除死代码 load_checkpoint / 全局 RNG 改为函数级单次 seed
- [x] **Git Hook: 自动 Co-authored-by 追加**
  - `.githooks/prepare-commit-msg` — 每次 commit 自动追加 `Co-authored-by: samurazdenko`
  - `core.hooksPath` 配置为 `.githooks`，跨克隆持久化

### 2026-07-03
- [x] **scripts/README.md** — 编写训练脚本目录 README，包含 train_phase1.py 简介、CLI 参数表、课程阶段说明、输出结构、常用命令示例
- [x] **README.md 全面更新** — 反映当前项目状态：9通道观测、src/ 目录结构、训练管道、185+ 测试、CUDA 自动检测、Phase1Reward、完整文件树
- [x] **Phase 1: Config n_envs 参数** — `configs/phase1_fast.yaml` 添加 `run.n_envs: 8`，`config_loader.py` 增加 `int >= 1` 验证，5 个测试
- [x] **Phase 2: VecEnv 工厂函数** — 提取 `_patch_env_reset()` 独立函数；新增 `_make_env_fn()` picklable worker 工厂 + `_build_vec_env()`（n_envs=1 保持单 env 向后兼容）；4 个测试
- [x] **Phase 3: Pipeline 集成 VecEnv** — `_setup_phase_env()` 改用 `_build_vec_env()`；`_create_phase_model()` 自动调整 `n_steps // n_envs`；`_evaluate()` 改用独立的单 eval env（不依赖训练 VecEnv）；phase 推进正确重建 VecEnv；5 个测试
- [x] **Phase 4: 边界 & 端到端** — n_envs=1 向后兼容验证；n_envs=2 完整训练 + 评估 + 检查点通过；n_envs=32 不崩溃；config hash 稳定；4 个测试
- [x] **全量测试: 202 passed** — 原有 185 测试 + 17 个新测试全部通过，零回归
### 2026-07-03 (later)
- [x] **配置文件调优 (commit cd97df1)** — `configs/phase1_fast.yaml` 调整适配 T4x2：n_envs 8→10, n_steps 2048→8192, composite_threshold 0.5→0.8。已 push 到 GitHub。
- [x] **gym → gymnasium 迁移** — 修复 SB3 2.9.0 + NumPy 2.4.4 兼容性。修改 5 个文件 (`src/bomberman_env.py`, `src/pettingzoo_env.py`, `src/feature_extractor.py`, `tests/test_feature_extractor.py`, `examples/random_agent_video.py`) 将 `import gym` / `from gym import spaces` 全部改为 `from gymnasium import spaces`。SB3 `check_env` 通过，202 测试全绿。
- [x] **docs/kaggle_training.ipynb** — 编写 Kaggle 云端训练 Notebook，包含依赖安装、项目代码拷贝、配置调优、自动续训检测、产出打包下载完整流程
- [x] **评估指标修复 (commit c18c853)** — `normalized_approach` 和 `low_final_distance` 改用每局实际初始距离做分母（替代硬编码的 30 格），因为 Phase 1.1 蓝方随机出生，初始距离并非固定 30。
- [x] **Phase 1.1 炸弹禁用修复 (commit 266d28b)** — 防止 agent 自爆 exploit（开局放弹自杀结束 episode 以避免后续惩罚累加）。在 `BombermanEnv.step()` 中 Phase 1.1 时将 `action[4]`(放弹) 和 `action[5]`(引爆) 强制置 0。Phase 1.2/1.3 不受影响。
- [x] **Phase 1.1 每帧生存时间惩罚 (commit 7f67c57)** — 无炸弹、不会死的情况下用 `-0.002/frame` 惩罚制造紧迫感。仅 Phase 1.1 生效，整局约 -10.8。
- [x] **热力图停滞检测 (40帧 distinct 窗口) (commit 876a382)** — 替换旧的基于对手距离的 `_stall(curr_mdist)`。现在用 40 帧滚动窗口累积 `(gx, gy)`，`distinct ≤ 2` 格判为停滞（不动或两格振荡），`distinct > 2` 重置计数器。完全解耦对手位置，消除震荡跨格线重置问题。
- [x] **Phase 1.1 composite score 去 survival_rate (commit 876a382)** — `configs/phase1_fast.yaml` 中 Phase 1.1 删除 `survival_rate: 0.3`（永远 1.0，废权重），`normalized_approach` 从 0.3 增至 0.6。Phase 1.2/1.3 保留不变。
- [x] **大幅降低 stall cap 防 reward 主导 (commit 0519266)** — `penalty_stall_cap` 从 0.167 降至 0.00167（除以 100）。原 cap 占总惩罚 98.8%，完全淹没了接近奖励（+0.033/格）和到达 bonus（+1.0）。调低后移动的净收益首次为正，agent 才有理由动。`rewards/phase1.py` _DEFAULT_CFG。
- [x] **连续浮点曼哈顿距离 for approach/retreat (commit e90d58f)** — `_approach_and_retreat` 从整数格坐标 `(gx, gy)` 改为连续浮点坐标 `(fx, fy)`。每像素移动都产生比例奖励/惩罚，不再只在跨格线程时触发。`__call__` 中新增 `fx, fy, opp_fx, opp_fy, fdist` 计算（连续坐标 = (px - CELL_SIZE/2)/CELL_SIZE + 1）。`_pos_buffer` 和 `_prev_mdist` 均改为浮点。`_stall` 仍用整数 `(gx, gy)` 不变。
- [x] **Reward 参数调优 (commit ef604f3)** — `reward_approach` 从 +0.033/格 调至 +0.231/格（7倍），`penalty_retreat` 从 -0.007/格 调至 -0.021/格（3倍）。配合连续浮点距离，让接近信号有足够强度驱动 agent 移动而非站桩。
- [x] **Loss 曲线 + 网络原始输出日志 (commit 09f7e28)** — `scripts/train_phase1.py` 新增 `LossRecorderCallback`，每次 PPO update 后记录 loss/policy_loss/value_loss/entropy/approx_kl 等到 `logs/losses_phaseXX.jsonl`。`src/evaluate.py` 新增 `_record_net_output()`，评估时每 24 帧记录一次网络原始 logits 和 sigmoid 概率到 `evaluations/phase_XX/step_XXXXXXX_net_output.jsonl`。`_evaluate()` 传递 `net_output_path` 给 `evaluate_phase`。
- [x] **缩小碰撞箱 + 降低撞墙惩罚 (commit f948761)** — `PLAYER_HITBOX_SIZE` 0.8→0.6（碰撞箱 32px→24px，单边间隙 4px→8px），`penalty_wall` 0.01→0.003。走廊通过性明显改善，不再一碰就卡墙。
- [x] **修复 net_output 日志 logits 访问 (commit c2e7b70)** — `_record_net_output()` 中 SB3 的 `BernoulliDistribution` 不直接暴露 `.logits`，需通过内部 `dist.distribution.logits` 访问 PyTorch 原生的 `Bernoulli` 分布对象。修复后 net_output.jsonl 正确输出 logits + probs 而非 error。
- [x] **热力图停滞检测 (40帧 distinct 窗口)** — 替换旧的基于对手距离的 `_stall(curr_mdist)`。现在用 40 帧滚动窗口累积 `(gx, gy)`，`distinct ≤ 2` 格判为停滞（不动或两格振荡），`distinct > 2` 重置计数器。完全解耦对手位置，消除震荡跨格线重置问题。
- [x] **Phase 1.1 composite score 去 survival_rate** — `configs/phase1_fast.yaml` 中 Phase 1.1 删除 `survival_rate: 0.3`（永远 1.0，废权重），`normalized_approach` 从 0.3 增至 0.6。Phase 1.2/1.3 保留不变。
- [x] **梯度距离奖励 + 去掉存活惩罚 + batch_size 128 (commit 5e773e2)** — 分析日志发现 3 次 update 后 policy 全零（logits 接近随机初始化）。修改三项：(1) `_approach_and_retreat` 替换为 `_distance_gradient`，去掉 10 帧窗口，每帧按距离变化直接给奖励，reward_approach 从 0.231 提升到 2.0；(2) 去掉 Phase 1.1 的 `-0.002/帧` 生存惩罚（站立不动=0）；(3) batch_size 256→128，梯度步数翻倍（每 update 320→640 次）。15 个 phase1 测试 + 全量 203 测试通过。Push 到 GitHub。
- [x] **argmax 替代 >0.5 阈值用于确定性评估 (commit f1f3272)** — 修复确定性评估全零问题。`model.predict(deterministic=True)` 使用 BernoulliDistribution.mode() 逐维 round(sigmoid(logit)>0.5)，初始化 logits ~ O(0.01) 时一次 PPO update 即可将全部 logits 推负 → 输出全零。新增 `_argmax_action()` 函数用 `torch.argmax(logits)` 选最高 logit 维度输出 one-hot，保证始终至少一个动作。移除旧的对向键惩罚计数器（argmax 保证不存在对向键）。25 测试通过。
- [x] **翻倍接近/后退奖励 (commit 8826070)** — reward_approach 2.0→4.0, penalty_retreat 0.02→0.04。接近信号现在是碰墙惩罚的 ~130 倍。
- [x] **关闭评估视频录制** — `configs/phase1_fast.yaml` video_episodes 2→0。节省评估时间。
- [x] **罚值重平衡: center 20%, retreat 10% of approach (commit f0c17b9)** — penalty_retreat 0.04→0.40, penalty_center_dev 0.013→0.33。使 center_dev（偏中线10px时 -0.083/帧）占 approach 的 20%，retreat（远离时 -0.042/帧）占 10%。wall/stall 占比 <1%。15 测试通过。
- [x] **中线惩罚→奖励, 安全区线性奖励 (commit e9141e3)** — 去掉 penalty_center_dev，新增 reward_center 0.02。安全区 8px（(40-24)/2，hitbox 24px 不碰墙区间），安全区内线性从 +0.02(中心)降至 0(边界)。十字路口改用 max(X,Y) 取代 min。期望值 +0.005/帧 ≈ 5% of approach，不超过 7% 上限。17 测试通过。
- [x] **center reward 仅在接近时给满 (commit d50b35e)** — 修复"站着不动也有正收益"的吸引子问题。新增 `reward_center_idle: 0.005`，只有 `is_approaching=True`（本帧距离对手在缩小）时才给 0.03；不动/后退时只有 0.005 微弱引导。18 测试通过。
