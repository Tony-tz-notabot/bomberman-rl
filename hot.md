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

## 📋 下一步计划

### Phase 3: 训练基础设施与自对弈
- 实现多个自定义 RewardFunction（距离奖励、击杀奖励、探索奖励等）
- 实现 scripted 对手策略（随机、站立、近战、逃跑等）
- 实现 SB3 训练管道：PPO → 保存 → 评估 → 回放
- 实现自对弈训练循环（PettingZoo + SB3 多智能体）
- 对战录像和分析工具
