# Bomberman PVP — RL Training Arena

**Gym + PettingZoo reinforcement learning environment for 2-player Bomberman, with a production-grade curriculum training pipeline.**

Clean, modular codebase designed for single-agent training (vs scripted opponents), multi-agent self-play, and curriculum-based PPO training. The core game engine runs headless with zero pygame dependency — training pipelines need no display or GUI.

```
           ┌──────────────┐
           │  GameEngine  │  ← pure logic, no pygame
           └──────┬───────┘
              ┌───┴───┐
              ▼       ▼
       ┌──────────┐ ┌──────────────┐
       │ Gym.Env  │ │  PettingZoo  │
       │single-   │ │  ParallelEnv │
       │agent     │ │  multi-agent │
       └────┬─────┘ └──────┬───────┘
            │              │
            ▼              ▼
       ┌──────────────────────────┐
       │  Training Pipeline       │
       │  (SB3 PPO + Curriculum)  │
       │  1.1 → 1.2 → 1.3        │
       └──────────────────────────┘
```

---

## Features

| | |
|---|---|
| 🎮 **Gym.Env** | Single-agent with pluggable `opponent_fn` for the blue player |
| 🤝 **PettingZoo ParallelEnv** | Multi-agent self-play with tied-policy support |
| 🧠 **9-channel observation** | Terrain, separate self/opponent heatmaps, bomb fuses, buffs & explosions, ability & stat broadcasts — CNN-ready `Box(0,1,(11,19,9), float32)` in HWC |
| ⌨️ **MultiBinary(6) action** | Raw key mapping `[up, down, left, right, action, ignite]` with configurable opposing-key penalty |
| 🔌 **Pluggable rewards** | `RewardFunction` adapter — swap at runtime, zero coupling to env |
| 📈 **Curriculum training** | 3-phase curriculum (approach → bombs → buffs) with automatic progression, SB3 PPO, custom Res-CNN feature extractor |
| 💾 **Checkpoint & resume** | Config-hash validated checkpoints, best-model saving, phase snapshots |
| 🎥 **Video recording** | Automatic episode recording with graceful fallback when ffmpeg unavailable |
| 🗺️ **Custom map init** | Pass an `(11×19)` matrix via `reset(options={"grid": ...})` or use phase-aware map generation |
| 🏃 **Headless engine** | `GameEngine` runs 5000+ steps/second with no display |
| ✅ **185+ tests** | Mechanics, environment API, observation, rewards, training pipeline verified |

---

## Quick Start

```bash
# Core dependencies
pip install gym pettingzoo numpy pygame

# Clone and cd
git clone https://github.com/Tony-tz-notabot/bomberman-rl.git
cd bomberman-rl
```

### Single-agent training (random opponent)

```python
from src.bomberman_env import BombermanEnv
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
from src.pettingzoo_env import BombermanPettingZooEnv

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

### SB3 PPO training (single agent)

```bash
pip install stable-baselines3
python examples/train_with_sb3.py
```

---

## Training Pipeline

`scripts/train_phase1.py` is the production-grade Phase 1 curriculum training script.

### Quick Start

```bash
# Verify environment (smoke test, ~2 min)
python scripts/train_phase1.py --total-steps-override 2048 --eval-interval 1024

# Full training with CUDA auto-detection
python scripts/train_phase1.py --config configs/phase1_fast.yaml
```

### Curriculum

| Phase | Goal | Rewards | Map |
|-------|------|---------|-----|
| **1.1** | Red approaches Blue | Survival, approach, low illegal actions | Connected floor, sparse bricks (30%) |
| **1.2** | Use bombs effectively | Bomb placement, brick destruction, kills | Standard walls (70% bricks) |
| **1.3** | Full gameplay with buffs | Buff pickup, bomb efficiency, kill rate | Standard walls + buff drops |

The pipeline evaluates at regular intervals. When the composite score exceeds the
threshold for N consecutive evaluations, the phase automatically advances.

### Key Components

- **`configs/phase1_fast.yaml`** — All tunable parameters (PPO hyperparams, phase thresholds, evaluation, checkpoint intervals)
- **`src/feature_extractor.py`** — Custom Res-CNN (9→32→64 channels, ResidualBlock, 256-d latent) for SB3 `CnnPolicy`
- **`src/evaluate.py`** — Fixed-seed evaluation with 11 metrics and weighted composite score
- **`src/video_recorder.py`** — Episodic video recording with graceful ffmpeg fallback
- **`src/config_loader.py`** — YAML config validation and deterministic SHA256 hashing
- **`rewards/phase1.py`** — Multi-phase `Phase1Reward` with per-phase reward shaping

### CLI

```bash
python scripts/train_phase1.py \
  --config configs/phase1_fast.yaml \
  --resume runs/phase1_20260702_153000 \   # resume from checkpoint
  --device cuda \                           # force GPU
  --total-steps-override 2048 \             # smoke test mode
  --override-config                         # bypass config hash check
```

See [scripts/README.md](scripts/README.md) for full details.

### Output Structure

```
runs/phase1_20260702_153000/
├── configs/config.yaml
├── checkpoints/
│   ├── latest.zip + latest_state.json
│   ├── best_model.zip
│   └── phase_1_1_complete.zip
├── logs/               # train.log + TensorBoard events
├── evaluations/        # step_0025000.json
├── videos/             # step_0025000_seed_000.mp4
└── reports/            # failure reports
```

---

## Observation Space

`Box(0.0, 1.0, (11, 19, 9), np.float32)` — 9 channels, H×W×C for CNN (permuted to CHW internally by the feature extractor).

| CH | Name | Values | Description |
|----|------|--------|-------------|
| 0 | terrain | 0 / 0.5 / 1.0 | floor / brick / stone |
| 1 | self position | [0.1, 1.0] | Gaussian heatmap; only the agent's position |
| 2 | opponent position | [0.1, 1.0] | Gaussian heatmap; only the opponent's position |
| 3 | bomb + fuse | [0, 1] | `fuse_frames / BOMB_FUSE`; remote bombs = 1.0 |
| 4 | buff + explosion | [0, 1] | Buff types 0.2–0.9, explosion = 1.0 |
| 5 | self abilities | [0, 1] | 6 ability timers broadcast (normalized) |
| 6 | opp abilities | [0, 1] | same, for the opponent |
| 7 | self stats | [0, 1] | `bomb_placed / bomb_max` broadcast |
| 8 | opp stats | [0, 1] | same, for the opponent |

Player positions are encoded at **pixel-level** via Gaussian heatmap (σ = 0.3 grid cells),
enabling sub-cell movement perception. Self and opponent are on **separate channels** to
avoid mutual interference.

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

Built-in reward functions:

| Reward | Description |
|--------|-------------|
| `SparseReward` | +1 win, -1 lose, 0 otherwise |
| `Phase1Reward` | Multi-phase curriculum reward (survival, approach, bombs, bricks, buffs, kills, penalties) |

---

## Game Rules (condensed)

| | |
|---|---|
| **Map** | 19×11 grid, indestructible stone pillars at even intersections |
| **Bombs** | Max 1 (upgradeable via permanent buff), 2s fuse (48 frames), 2-cell blast |
| **Explosion** | Cross-pattern, stops at stone, destroys brick, chain-detonates other bombs |
| **Buffs** | Permanent: bomb up, blast up, speed up. Temporary abilities (8–30s): kick, remote detonate, shield, diarrhea, reverse controls, float |
| **Win** | First to 5 round wins (configurable) |

Full rules: see [RULES.md](RULES.md).

---

## Project Structure

```
.
├── src/                          # Source code package
│   ├── main.py                   # Entry point (glue: imports all modules)
│   ├── config.py                 # Global Config singleton (frame-based)
│   ├── constants.py              # Color/GameState enums, cell type constants
│   ├── utils.py                  # Coordinate conversion, collision helpers
│   ├── models.py                 # Player/Bomb/BuffItem + Snapshot dataclasses
│   ├── game_engine.py            # Pure-logic game engine (zero pygame)
│   ├── renderer.py               # Read-only renderer (GameSnapshot → draw)
│   ├── input_handler.py          # Dual-player keyboard state tracking
│   ├── settings_ui.py            # Settings panel overlay
│   ├── bomberman_env.py          # Gym.Env single-agent wrapper
│   ├── pettingzoo_env.py         # PettingZoo ParallelEnv multi-agent
│   ├── map_generator.py          # Phase-aware map generation
│   ├── config_loader.py          # YAML config validation + hashing
│   ├── evaluate.py               # Fixed-seed evaluation with composite score
│   ├── feature_extractor.py      # Res-CNN feature extractor for SB3
│   └── video_recorder.py         # Episode video recording
├── scripts/
│   ├── README.md                 # Training script documentation
│   └── train_phase1.py           # Phase 1 curriculum PPO training pipeline
├── configs/
│   └── phase1_fast.yaml          # Training configuration
├── rewards/
│   ├── __init__.py               # RewardFunction ABC
│   ├── sparse.py                 # SparseReward (+1/-1/0)
│   └── phase1.py                 # Phase1Reward (curriculum rewards)
├── tests/
│   ├── test_game_mechanics.py    # 99 engine tests
│   ├── test_bomberman_env.py     # Gym env tests
│   ├── test_pettingzoo_env.py    # PettingZoo env tests
│   ├── test_phase1_reward.py     # Phase1Reward tests
│   ├── test_config_loader.py     # Config loader tests
│   ├── test_feature_extractor.py # Res-CNN tests
│   ├── test_video_recorder.py    # Video recorder tests
│   ├── test_evaluate.py          # Evaluation module tests
│   └── test_training_pipeline.py # Pipeline smoke tests
├── examples/
│   └── train_with_sb3.py         # SB3 PPO training example
├── docs/
│   ├── superpowers/specs/        # Design documents
│   └── training_dependencies.md  # ML dependency setup guide
├── .githooks/
│   └── prepare-commit-msg        # Auto-adds Co-authored-by trailer
├── launch.bat                    # Windows launcher
├── RULES.md                      # Full game rules
├── README.md
├── CLAUDE.md
└── MIT license.md
```

---

## Dependencies

| Category | Libraries |
|----------|-----------|
| **Core** | `pygame`, `numpy` |
| **RL** | `gymnasium`, `pettingzoo`, `stable-baselines3` |
| **Training** | `torch`, `sb3-contrib`, `tensorboard` |
| **Config** | `pyyaml` |
| **Video** | `imageio`, `imageio-ffmpeg` (optional) |
| **Test** | `pytest` |

Full setup guide: [docs/training_dependencies.md](docs/training_dependencies.md)

---

## License

MIT
