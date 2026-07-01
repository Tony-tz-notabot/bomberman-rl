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

## 🚧 当前进度

**阶段：AI 系统加入前的结构性重构 — 已完成 Task 1-7**

## 📋 下一步计划

### 1. 代码模块化重构 (第一阶段)
将 `main.py` 拆分为以下模块：

| 模块 | 职责 | 状态 |
|------|------|------|
| `config.py` | Config 类、全局 cfg 实例、全部可调参数 | ✅ |
| `constants.py` | 颜色常量、游戏常量 + GameState 枚举 | ✅ |
| `utils.py` | 坐标工具 (grid↔pixel)、clamp、sign、box_overlap | ✅ |
| `models.py` | Player、Bomb、BuffItem 数据类 + Snapshot 类型 | ✅ |
| `game_state.py` | GameState 枚举 | (合并到 constants) |
| `game_engine.py` | 纯逻辑引擎（独立于 pygame） | ✅ |
| `renderer.py` | 所有绘制函数（地图、UI、玩家、炸弹、爆炸等） | ✅ |
| `input_handler.py` | 键盘输入映射、按键状态同步 | |
| `settings_ui.py` | 设置面板参数列表绘制与交互 | |

### 2. AI 系统设计 (第二阶段)
- 确定 AI 接入点：AI 控制一名玩家的输入 (move/place bomb/ignite)
- 设计 AI 接口 / 抽象类
- 支持两种 AI 模式：取代玩家操作 或 作为独立玩家对战

### 3. AI 实现 (第三阶段)
- 简单策略：随机移动 + 随机放炸弹 (baseline)
- 进阶策略：基于状态的规则 AI (寻路、躲避爆炸、寻找道具)
- 后续可扩展：强化学习 / 搜索算法
