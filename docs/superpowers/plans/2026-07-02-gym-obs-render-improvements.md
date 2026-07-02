# Gym 观察通道分离 + 标准化渲染 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Gym 环境观察空间从 8 通道改为 9 通道（双方位置独立），并实现标准化 render(mode="rgb_array"/"human")。

**Architecture:** `build_obs()` 是共享观察构建函数（被 BombermanEnv 和 PettingZooEnv 共用）。通道改动只需修改此函数 + 各环境的 observation_space 形状。渲染使用现有 Renderer 类 + offscreen pygame.Surface，两个环境各自实现 render()。

**Tech Stack:** Python 3, numpy, pygame, gym, pettingzoo

## Global Constraints

- 观察空间值域永远 [0, 1]，float32
- `build_obs(snapshot, agent_id)` 签名不变，仅输出从 8→9 通道
- render_mode 默认 None（完全向后兼容现有代码）
- 所有定时器帧基（int），不引入秒级计时
- 不引入 opencv/ffmpeg 等新依赖；视频录制通过 gym.wrappers.RecordVideo 由外部实现

---

### Task 1: 拆分 build_obs() 的位置通道

**Files:**
- Modify: `src/bomberman_env.py` (build_obs + _gauss_heatmap 所在文件)

**Interfaces:**
- Consumes: `GameSnapshot`, `agent_id: str`
- Produces: `build_obs(snapshot, agent_id) -> np.ndarray(shape=(MAP_ROWS, MAP_COLS, 9))`

- [ ] **Step 1: 修改 build_obs() 将 CH1 拆为两个通道**

将原来 CH1 的混合编码改为两个独立通道：

```python
# 改前 (第 37-47 行)
# CH1: Players - Gaussian heatmap, self in [0.1, 0.5], opponent in (0.5, 1.0]
self_player = snapshot.players[0] if agent_id == snapshot.players[0].id else snapshot.players[1]
opp_player = snapshot.players[1] if self_player is snapshot.players[0] else snapshot.players[0]
self_heat = _gauss_heatmap(self_player.pos_x, self_player.pos_y)
opp_heat = _gauss_heatmap(opp_player.pos_x, opp_player.pos_y)
self_enc = self_heat * 0.4 + 0.1
opp_enc = opp_heat * 0.4 + 0.6
obs[:, :, 1] = np.where(self_heat >= opp_heat, self_enc, opp_enc)
```

改为：

```python
# CH1: Self position — full-range Gaussian [0, 1]
self_player = snapshot.players[0] if agent_id == snapshot.players[0].id else snapshot.players[1]
opp_player = snapshot.players[1] if self_player is snapshot.players[0] else snapshot.players[0]
obs[:, :, 1] = _gauss_heatmap(self_player.pos_x, self_player.pos_y)

# CH2: Opponent position — full-range Gaussian [0, 1]
obs[:, :, 2] = _gauss_heatmap(opp_player.pos_x, opp_player.pos_y)
```

然后将原 CH2~CH7 依次平移到 CH3~CH8：

```python
# CH3: Bomb + fuse (原 CH2)
for bomb in snapshot.bombs:
    if bomb.fuse_frames >= 0:
        val = min(bomb.fuse_frames / cfg.BOMB_FUSE, 1.0)
    else:
        val = 1.0
    gy, gx = bomb.grid_y - 1, bomb.grid_x - 1
    obs[gy, gx, 3] = val

# CH4: Buff + explosion (原 CH3)
BUFF_MAP = {
    "bomb_plus": 0.2, "blast_plus": 0.35, "speed_plus": 0.5,
    "kick": 0.65, "remote": 0.8, "shield": 0.9,
}
for buff in snapshot.buffs:
    val = BUFF_MAP.get(buff.type, 1.0)
    gy, gx = buff.grid_y - 1, buff.grid_x - 1
    obs[gy, gx, 4] = val
for (gx, gy) in snapshot.explosion_cells:
    obs[gy-1, gx-1, 4] = 1.0

# CH5: Self abilities (原 CH4)
_broadcast_abilities(obs[:, :, 5], self_player.abilities)

# CH6: Opponent abilities (原 CH5)
_broadcast_abilities(obs[:, :, 6], opp_player.abilities)

# CH7: Self stats (原 CH6)
_broadcast_stats(obs[:, :, 7], self_player.bomb_placed_count, self_player.bomb_max)

# CH8: Opponent stats (原 CH7)
_broadcast_stats(obs[:, :, 8], opp_player.bomb_placed_count, opp_player.bomb_max)
```

- [ ] **Step 2: 确认改动后 build_obs 正确性**

验证要点：所有通道索引正确递增，`_gauss_heatmap` 不再需要值域压缩（直接全 [0,1]），`np.where` 逻辑已移除。

---

### Task 2: BombermanEnv — observation_space + render()

**Files:**
- Modify: `src/bomberman_env.py`

**Interfaces:**
- Consumes: `BombermanEnv.__init__(..., render_mode=None)`
- Produces: `BombermanEnv.render() -> Optional[np.ndarray]`, `BombermanEnv.close()` 清理 pygame

- [ ] **Step 1: 更新 observation_space 从 8→9**

```python
# 第 144-146 行
self.observation_space = spaces.Box(
    low=0.0, high=1.0, shape=(cfg.MAP_ROWS, cfg.MAP_COLS, 9), dtype=np.float32
)
```

- [ ] **Step 2: 在 __init__ 添加 render_mode 参数和初始化**

在 `__init__` 参数列表添加 `render_mode: Optional[str] = None`，在方法体内添加初始化逻辑（放在 `self._prev_snap = None` 之后）：

```python
self.render_mode = render_mode
self._renderer = None
self._screen = None

if render_mode is not None:
    import pygame
    pygame.init()
    from src.utils import get_window_width, get_window_height
    w, h = get_window_width(), get_window_height()
    if render_mode == "human":
        self._screen = pygame.display.set_mode((w, h), pygame.RESIZABLE)
        pygame.display.set_caption("Bomberman RL Training")
    else:  # rgb_array
        pygame.display.set_mode((1, 1))  # 初始化 display
        self._screen = pygame.Surface((w, h))
    from src.renderer import Renderer
    self._renderer = Renderer(self._screen)
```

- [ ] **Step 3: 实现 render() 方法**

在 `close()` 方法之前插入：

```python
def render(self) -> Optional[np.ndarray]:
    if self.render_mode is None:
        return None

    snap = self.engine.get_snapshot()
    from src.constants import COLOR_BG
    self._screen.fill(COLOR_BG)
    self._renderer.draw(snap)

    if self.render_mode == "human":
        pygame.display.flip()
        return None
    else:  # rgb_array
        return pygame.surfarray.array3d(self._screen).transpose(1, 0, 2)
```

- [ ] **Step 4: 更新 metadata 和 close()**

```python
# 第 126 行
metadata = {"render.modes": ["human", "rgb_array"], "render_fps": 24}
```

```python
# 替换 close() (第 255-256 行)
def close(self):
    if self.render_mode is not None:
        pygame.quit()
```

---

### Task 3: PettingZooEnv — observation_space + render()

**Files:**
- Modify: `src/pettingzoo_env.py`

**Interfaces:**
- Consumes: `BombermanPettingZooEnv.__init__(..., render_mode=None)`
- Produces: `BombermanPettingZooEnv.render() -> Optional[np.ndarray]`

- [ ] **Step 1: 更新 observation_spaces 从 8→9**

```python
# 第 45-49 行
obs_space = spaces.Box(
    low=0.0, high=1.0,
    shape=(cfg.MAP_ROWS, cfg.MAP_COLS, 9),
    dtype=np.float32,
)
```

- [ ] **Step 2: 在 __init__ 添加 render_mode**

在参数列表添加 `render_mode: Optional[str] = None`，在 `self._prev_snap` 初始化之前添加渲染初始化（代码与 Task 2 Step 2 相同，只是 `self._renderer = Renderer(self._screen)` 不需要 import，直接在文件顶部全局 import）：

```python
self.render_mode = render_mode
self._renderer = None
self._screen = None

if render_mode is not None:
    import pygame
    pygame.init()
    from src.utils import get_window_width, get_window_height
    w, h = get_window_width(), get_window_height()
    if render_mode == "human":
        self._screen = pygame.display.set_mode((w, h), pygame.RESIZABLE)
        pygame.display.set_caption("Bomberman PZ Training")
    else:
        pygame.display.set_mode((1, 1))
        self._screen = pygame.Surface((w, h))
    self._renderer = Renderer(self._screen)
```

文件顶部添加 import：
```python
from src.renderer import Renderer
```

- [ ] **Step 3: 更新 metadata**

```python
# 第 26 行
metadata = {"render.modes": ["human", "rgb_array"], "name": "bomberman_v2_pz"}
```

- [ ] **Step 4: 实现 render() 和 close()**

替换 render（第 180-181 行）和 close（第 183-184 行）：

```python
def render(self) -> Optional[np.ndarray]:
    if self.render_mode is None:
        return None

    snap = self.engine.get_snapshot()
    from src.constants import COLOR_BG
    self._screen.fill(COLOR_BG)
    self._renderer.draw(snap)

    if self.render_mode == "human":
        pygame.display.flip()
        return None
    return pygame.surfarray.array3d(self._screen).transpose(1, 0, 2)


def close(self):
    if self.render_mode is not None:
        pygame.quit()
```

---

### Task 4: 更新测试 — 通道形状 8→9 + render 测试

**Files:**
- Modify: `tests/test_bomberman_env.py`
- Modify: `tests/test_pettingzoo_env.py`

- [ ] **Step 1: 更新 test_bomberman_env.py 所有 8→9 断言**

共 4 处需要修改：

```python
# 第 16 行: test_reset_default
assert obs.shape == (cfg.MAP_ROWS, cfg.MAP_COLS, 9)

# 第 30 行: test_reset_with_grid
assert obs.shape == (cfg.MAP_ROWS, cfg.MAP_COLS, 9)

# 第 52 行: test_step_basic
assert obs.shape == (cfg.MAP_ROWS, cfg.MAP_COLS, 9)

# 第 119 行: test_build_obs_structure
assert obs.shape == (cfg.MAP_ROWS, cfg.MAP_COLS, 9)
```

更新 `test_build_obs_structure` 中的 CH1 断言（第 122-123 行），因为 CH1 现在是纯 self 高斯热力图：

```python
# CH1: self position — should have activity near red spawn (always players[0] for "red")
assert obs[:, :, 1].max() > 0.1, "Self heatmap should have values"
# CH2: opponent position — should also have activity
assert obs[:, :, 2].max() > 0.1, "Opponent heatmap should have values"
```

- [ ] **Step 2: 在 test_bomberman_env.py 新增 render 测试**

在 `TestBombermanEnv` 类末尾添加：

```python
def test_render_rgb_array(self):
    """render(mode="rgb_array") returns (H, W, 3) uint8 array."""
    env = BombermanEnv(render_mode="rgb_array")
    env.reset()
    frame = env.render()
    from src.utils import get_window_width, get_window_height
    assert frame is not None
    assert isinstance(frame, np.ndarray)
    assert frame.shape == (get_window_height(), get_window_width(), 3)
    assert frame.dtype == np.uint8
    env.close()

def test_render_none(self):
    """render_mode=None returns None from render()."""
    env = BombermanEnv(render_mode=None)
    env.reset()
    assert env.render() is None
    env.close()

def test_render_multiple_frames(self):
    """Multiple render() calls return consistent frames."""
    env = BombermanEnv(render_mode="rgb_array")
    env.reset()
    for _ in range(5):
        action = np.random.randint(0, 2, size=6, dtype=np.int8)
        env.step(action)
        frame = env.render()
        assert frame is not None
        assert frame.shape[2] == 3  # RGB
    env.close()
```

- [ ] **Step 3: 更新 test_pettingzoo_env.py 断言 8→9**

```python
# 第 24 行: test_pz_reset
assert ob.shape == (cfg.MAP_ROWS, cfg.MAP_COLS, 9)
```

- [ ] **Step 4: 在 test_pettingzoo_env.py 新增 render 测试**

在 `TestPettingZooEnv` 类末尾添加（用 `self._make_env()` 创建支持 render_mode 的 env）：

```python
def test_pz_render_rgb_array(self):
    """PettingZoo render(mode="rgb_array") returns valid frame."""
    env = BombermanPettingZooEnv(render_mode="rgb_array")
    env.reset()
    frame = env.render()
    from src.utils import get_window_width, get_window_height
    assert frame is not None
    assert frame.shape == (get_window_height(), get_window_width(), 3)
    assert frame.dtype == np.uint8
    env.close()
```

注意：这里不能直接使用 `self._make_env()` 因为需要传 `render_mode`。改用以下方式：

```python
def test_pz_render_rgb_array(self):
    """PettingZoo render(mode="rgb_array") returns valid frame."""
    try:
        from pettingzoo_env import BombermanPettingZooEnv
    except ImportError:
        pytest.skip("pettingzoo not installed")
    env = BombermanPettingZooEnv(render_mode="rgb_array")
    env.reset()
    frame = env.render()
    from src.utils import get_window_width, get_window_height
    assert frame is not None
    assert frame.shape == (get_window_height(), get_window_width(), 3)
    assert frame.dtype == np.uint8
    env.close()
```

---

### Task 5: 最终验证

- [ ] **Step 1: 运行全部测试**

```bash
cd "D:\AI2word\boom\bomberman_v2.0-AI"
python -m pytest tests/ -v 2>&1
```

预期：全部测试通过（14+ Gym 测试 + ~6 PettingZoo 测试），无 import 错误，无 shape 不匹配。

- [ ] **Step 2: 运行人工 play 验证**

```bash
cd "D:\AI2word\boom\bomberman_v2.0-AI"
python -m src.main
```

预期：游戏正常运行，双人对战、渲染、菜单等全部不受影响（render_mode 默认 None）。

- [ ] **Step 3: 提交**

```bash
git add -f docs/superpowers/plans/2026-07-02-gym-obs-render-improvements.md
git add src/bomberman_env.py src/pettingzoo_env.py
git add tests/test_bomberman_env.py tests/test_pettingzoo_env.py
git commit -m "feat: split player channels (8→9) and add standardized render() to gym envs"
```
