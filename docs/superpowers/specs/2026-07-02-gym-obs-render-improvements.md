# Gym 环境改进：观察通道分离 & 标准化渲染

> Phase 2 补充：在 Phase 3 课程设计之前，对 Gym 环境做两个基础改进
> 日期: 2026-07-02
> 状态: 设计锁定

---

## 1. 概述

在 Phase 3（多阶段学习策略）开始前，对现有 Gym 环境做两项改进：

1. **观察空间通道分离** — 将 CH1 中混合编码的双方玩家位置拆成两个独立通道
2. **标准化视频渲染** — 实现 Gym 标准的 `render(mode="rgb_array")` 和 `render(mode="human")`

两项改动均需同步更新 BombermanEnv 和 BombermanPettingZooEnv。

---

## 2. 通道分离

### 现状

```
CH1: 玩家（单通道，值域分割）
  self  → [0.1, 0.5]
  opponent → (0.5, 1.0]
  np.where(self_heat >= opp_heat, self_enc, opp_enc)
```

每个 grid cell 只能表示一方——对手位置被高斯值较低的玩家完全遮蔽。

### 改动

从 8 通道 → **9 通道**，单纯将 CH1 拆成两个：

| CH | 改前 | 改后 | 值域 |
|----|------|------|------|
| 0 | 地形 | 地形 (不变) | {0, 0.5, 1.0} |
| **1** | **玩家(自己+对手)** | **自己位置** | **[0, 1] 高斯热力图** |
| **2** | **炸弹引信** | **对手位置** | **[0, 1] 高斯热力图** |
| 3 | Buff+爆炸 | 炸弹引信 (平移) | [0, 1] |
| 4 | 自己能力 | Buff+爆炸 (平移) | [0, 1] |
| 5 | 对手能力 | 自己能力 (平移) | [0, 1] |
| 6 | 自己状态 | 对手能力 (平移) | [0, 1] |
| 7 | 对手状态 | 自己状态 (平移) | [0, 1] |
| **8** | — | **对手状态 (平移)** | [0, 1] |

### 代码变更

`build_obs()` 中的核心逻辑简化：

```python
# 改前 — 单通道 + np.where + 值域压缩
self_enc = self_heat * 0.4 + 0.1
opp_enc = opp_heat * 0.4 + 0.6
obs[:, :, 1] = np.where(self_heat >= opp_heat, self_enc, opp_enc)

# 改后 — 各自独立通道，全值域
obs[:, :, 1] = self_heat       # 自己位置
obs[:, :, 2] = opp_heat        # 对手位置
# CH3~CH8 依次平移
```

### 优势

- **无信息丢失** — 双方位置不再互相遮蔽
- **模型更容易学习** — 不需要通过值域 <0.5 判断"这是我"
- **全值域 [0,1]** — 更丰富的距离信息传递
- **tied policy 依然可用** — agent_id 决定谁进 CH1，谁进 CH2

### 影响范围

| 文件 | 改动 |
|------|------|
| `src/bomberman_env.py` | `build_obs()` 通道逻辑重写，`observation_space` 从 8→9 |
| `src/pettingzoo_env.py` | 同上，`observation_spaces` 同步更新 |
| `tests/test_bomberman_env.py` | 观察形状断言 8→9，新增位姿验证 |
| `tests/test_pettingzoo_env.py` | 同上 |

---

## 3. 标准化渲染

### 目标

实现 Gym 标准 `render()` 方法，支持两种模式：

```python
metadata = {"render.modes": ["human", "rgb_array"], "render_fps": 24}
```

### 实现方式

复用现有的 `Renderer` 类，通过 offscreen `pygame.Surface` 完成无头渲染。

#### 构造函数

```python
def __init__(self, ..., render_mode: Optional[str] = None):
    self.render_mode = render_mode
    self._renderer = None
    self._screen = None

    if render_mode is not None:
        import pygame
        pygame.init()
        w, h = get_window_width(), get_window_height()
        if render_mode == "human":
            self._screen = pygame.display.set_mode((w, h), pygame.RESIZABLE)
            pygame.display.set_caption("Bomberman RL Training")
        else:  # rgb_array
            pygame.display.set_mode((1, 1))  # 满足 pygame.display 初始化要求
            self._screen = pygame.Surface((w, h))
        self._renderer = Renderer(self._screen)
```

#### render() 方法

```python
def render(self) -> Optional[np.ndarray]:
    if self.render_mode is None:
        return None

    snap = self.engine.get_snapshot()
    self._screen.fill(COLOR_BG)
    self._renderer.draw(snap)

    if self.render_mode == "human":
        pygame.display.flip()
        return None
    else:  # rgb_array
        # (W, H, 3) → (H, W, 3)
        return pygame.surfarray.array3d(self._screen).transpose(1, 0, 2)
```

#### close() 方法

```python
def close(self):
    if self.render_mode is not None:
        pygame.quit()
```

#### PettingZoo 同步

```python
class BombermanPettingZooEnv(ParallelEnv):
    metadata = {"render.modes": ["human", "rgb_array"], "render_fps": 24}

    def render(self):
        if self.render_mode is None:
            return None
        snap = self.engine.get_snapshot()
        self._screen.fill(COLOR_BG)
        self._renderer.draw(snap)

        if self.render_mode == "human":
            pygame.display.flip()
            return None
        return pygame.surfarray.array3d(self._screen).transpose(1, 0, 2)
```

### 外部录制使用方式

实现标准化 `render(mode="rgb_array")` 后，用户可通过 Gym 内置 wrapper 录制视频：

```python
from gym.wrappers import RecordVideo

env = BombermanEnv(render_mode="rgb_array")
env = RecordVideo(env, video_folder="./videos", episode_trigger=lambda e: True)
```

或者用于自定义渲染：

```python
obs = env.reset()
frame = env.render()          # 返回 (H, W, 3) numpy array
Image.fromarray(frame).save("frame.png")
```

### 注意事项

- **Pygame 重复初始化** — `pygame.init()` 在单进程多环境场景下可能重复调用（幂等）。`close()` 后调用 `pygame.quit()` 不影响其他环境，因为 Pygame 内部维护引用计数。用户如需多环境并行，各环境自己初始化/退出即可。
- **性能** — `rgb_array` 模式使用 `pygame.Surface`（纯内存操作，不涉及 GPU/窗口），每次 `render()` 约 1-3ms。
- **CI/服务器** — `rgb_array` 模式不创建窗口，在无 display 的 Linux 服务器上正常工作（前提是 `pygame.display.set_mode((1,1))` 在无头环境做一次初始化）。

### 测试计划

新增测试：

| 测试 | 内容 |
|------|------|
| `test_render_modes` | 验证 `render_mode=None` / `"human"` / `"rgb_array"` 构造不报错 |
| `test_render_rgb_array` | 调用 `render()` 返回 (H, W, 3) uint8 数组 |
| `test_render_consistency` | 连续两次 `render()` 返回形状一致 |
| `test_record_video_wrapper` | Gym RecordVideo 包装后可正常完成 episode |
| `test_pz_render_rgb_array` | PettingZoo render() 同样返回合法帧 |

---

## 4. 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `src/bomberman_env.py` | 通道逻辑 + render 实现 |
| 修改 | `src/pettingzoo_env.py` | 通道逻辑 + render 实现 |
| 更新 | `tests/test_bomberman_env.py` | 观察断言 8→9，新增 render 测试 |
| 更新 | `tests/test_pettingzoo_env.py` | 同上 |
| 新建 | 本文档 | 设计文档 |

---

## 5. 向后兼容性

- **通道变更不可兼容** — 已训练的策略使用 8 通道观察，更新后须重新训练
- **render 新增完全向后兼容** — `render_mode` 默认为 `None`，所有现有代码无需修改
- **build_obs() 签名不变** — 仍然是 `(snapshot, agent_id) -> ndarray`，只是输出的通道数变化
