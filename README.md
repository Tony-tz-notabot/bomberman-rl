# Bomberman-RL

**Gym + PettingZoo reinforcement learning environment for Bomberman PVP.**

Clean, refactored codebase designed for both single-agent training (vs scripted opponents)
and multi-agent self-play. The core game engine runs headless with zero pygame dependency,
so training pipelines need no display or GUI.

```
           ┌──────────┐
           │ GameEngine│  ← pure logic, no pygame
           └─────┬─────┘
              ┌──┴──┐
              ▼     ▼
       ┌─────────┐ ┌──────────────┐
       │ Gym.Env │ │ PettingZoo   │
       │single-  │ │ ParallelEnv  │
       │agent    │ │ multi-agent  │
       └─────────┘ └──────────────┘
```

---

## Features

| | |
|---|---|
| 🎮 **Gym.Env** | Single-agent with pluggable `opponent_fn` for the blue player |
| 🤝 **PettingZoo ParallelEnv** | Multi-agent self-play with tied-policy support |
| 🧠 **8-channel observation** | Terrain, gaussian player heatmaps, bomb fuses, buffs, ability & stat broadcasts — CNN-ready `Box(0,1,(11,19,8))` |
| ⌨️ **MultiBinary(6) action** | Raw key mapping `[up, down, left, right, action, ignite]` |
| 🔌 **Pluggable rewards** | `RewardFunction` adapter — swap at runtime, zero coupling to env |
| 🗺️ **Custom map init** | Pass an `(11×19)` matrix via `reset(options={"grid": ...})` |
| 🏃 **Headless engine** | `GameEngine` runs 5000+ steps/second with no display |
| ✅ **112 tests** | Mechanics, environment API, and observation correctness verified |

---

## Quick Start

```bash
pip install gym pettingzoo numpy pygame
git clone https://github.com/Tony-tz-notabot/bomberman-rl.git
cd bomberman-rl
```

### Single-agent training

```python
from bomberman_env import BombermanEnv
from rewards.sparse import SparseReward
import numpy as np

def random_opponent(snapshot, agent_id):
    return np.random.randint(0, 2, size=6, dtype=np.int8)

env = BombermanEnv(
    reward_fn=SparseReward(),
    opponent_fn=random_opponent,
)
obs, info = env.reset()
action = np.array([1, 0, 0, 0, 0, 0])  # move up
obs, reward, terminated, truncated, info = env.step(action)
```

### Multi-agent (PettingZoo)

```python
from pettingzoo_env import BombermanPettingZooEnv

env = BombermanPettingZooEnv()
obs = env.reset()
actions = {
    "red": np.array([0, 1, 0, 0, 0, 0]),   # blue moves down
    "blue": np.array([1, 0, 0, 0, 0, 0]),   # red moves up
}
obs, rewards, terms, truncs, infos = env.step(actions)
```

### Custom map

```python
import numpy as np
grid = np.zeros((11, 19), dtype=np.int32)
grid[1, 1] = 3   # red spawn
grid[9, 17] = 4  # blue spawn
obs, info = env.reset(options={"grid": grid})
```

### SB3 training example

```bash
pip install stable-baselines3
python examples/train_with_sb3.py
```

---

## Observation Space

`Box(0.0, 1.0, (11, 19, 8), np.float32)` — 8 channels, H×W×C for CNN.

| CH | Name | Values | Description |
|----|------|--------|-------------|
| 0 | terrain | 0 / 0.5 / 1.0 | floor / brick / stone |
| 1 | players | [0.1, 1.0] | Gaussian heatmap: self [0.1, 0.5], opponent (0.5, 1.0] |
| 2 | bomb+fuse | [0, 1] | `fuse_frames / BOMB_FUSE`; remote bombs = 1.0 |
| 3 | buff+explosion | [0, 1] | Buff types 0.2–0.9, explosion = 1.0 |
| 4 | self abilities | [0, 1] | 6 ability timers broadcast (normalized) |
| 5 | opp abilities | [0, 1] | same, for the opponent |
| 6 | self stats | [0, 1] | `bomb_placed / bomb_max` broadcast |
| 7 | opp stats | [0, 1] | same, for the opponent |

Player positions are encoded at **pixel-level** via Gaussian heatmap (σ = 0.3 grid cells),
enabling sub-cell movement perception.

---

## Action Space

`spaces.MultiBinary(6)` — each dimension is 0 or 1.

| Index | Key | Description |
|-------|-----|-------------|
| 0 | up | Move / look up |
| 1 | down | Move / look down |
| 2 | left | Move / look left |
| 3 | right | Move / look right |
| 4 | action | Place bomb (edge-triggered) |
| 5 | ignite | Detonate remote bomb |

Opposing directions (up+down or left+right) can be penalized via `penalty_opposing`.

---

## Reward System

The `RewardFunction` base class decouples reward logic from environment:

```python
from rewards import RewardFunction

class MyReward(RewardFunction):
    def reset(self, episode_info: dict):
        self.my_state = 0

    def __call__(self, engine, prev_snapshot, snapshot, action, agent_id):
        # Access full engine state, compare snapshots, shape rewards
        return 0.01  # per-frame shaping

env.reward_fn = MyReward()  # swap at runtime
```

Built-in: `SparseReward` (+1 win, -1 lose, 0 draw, 0 otherwise).

---

## Environment Parameters

| Param | Default | Description |
|-------|---------|-------------|
| `reward_fn` | `SparseReward()` | Reward strategy |
| `opponent_fn` | `random_opponent` | Blue player policy `(snapshot, agent_id) → action` |
| `penalty_opposing` | `0.0` | Penalty for up+down or left+right simultaneously |

---

## Game Rules (condensed)

| | |
|---|---|
| **Map** | 19×11 grid, indestructible stone pillars at even intersections |
| **Bombs** | Max 1 (upgradeable), 2s fuse, 2-cell blast (upgradeable) |
| **Explosion** | Cross-pattern, stops at stone, destroys brick, chains other bombs |
| **Buffs** | Dropped from bricks (15%) or random refresh (30s). Permanent: bomb+, blast+, speed+. Unknown: 6 temporary abilities |
| **Abilities** | Kick, remote detonate, shield, diarrhea, reverse controls, float (8–30s) |
| **Win** | First to 5 round wins (configurable) |

Full rules: see [RULES.md](RULES.md).

---

## Project Structure

```
.
├── game_engine.py          # Pure game logic (440 lines, zero pygame)
├── main.py                 # Pygame GUI entry point (for human play)
├── bomberman_env.py        # Gym.Env single-agent wrapper
├── pettingzoo_env.py       # PettingZoo ParallelEnv wrapper
├── config.py               # All tunable parameters (30+)
├── constants.py            # Enums, color constants
├── models.py               # Player, Bomb, BuffItem + frozen snapshots
├── utils.py                # Coordinate conversion, collision helpers
├── input_handler.py        # Keyboard input → action dicts
├── renderer.py             # Pygame rendering (engine-agnostic)
├── settings_ui.py          # In-game settings panel
├── rewards/
│   ├── __init__.py          # RewardFunction base class
│   └── sparse.py            # SparseReward (+1/-1/0)
├── tests/
│   ├── test_game_mechanics.py   # 99 engine tests
│   ├── test_bomberman_env.py    # 8 gym env tests
│   └── test_pettingzoo_env.py   # 4 pettingzoo env tests
└── examples/
    └── train_with_sb3.py    # SB3 PPO training example
```

---

## License

MIT
