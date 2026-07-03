# Training Scripts

This directory contains training pipeline scripts for Bomberman PVP RL.

## Scripts

| File | Description |
|------|-------------|
| `train_phase1.py` | Phase 1 curriculum training pipeline (SB3 PPO) |

---

## `train_phase1.py` — Phase 1 Curriculum Training Pipeline

Stable-Baselines3 PPO training with curriculum progression (Phase 1.1 → 1.2 → 1.3).

### Quick Start

```bash
# Run with default config (uses CUDA if available, else CPU)
python scripts/train_phase1.py

# Run with explicit config file
python scripts/train_phase1.py --config configs/phase1_fast.yaml
```

### CLI Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--config` | `configs/phase1_fast.yaml` | Path to YAML config |
| `--resume` | (none) | Resume from existing run directory |
| `--total-steps-override` | (none) | Override total training steps (for smoke tests) |
| `--eval-interval` | (none) | Override evaluation interval from config |
| `--device` | `auto` | Device override: `auto`, `cpu`, or `cuda` |
| `--override-config` | (none) | Bypass config hash check on resume |

### Key Config Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `run.n_envs` | `1` | Number of parallel environments (`SubprocVecEnv`). Each env runs on a separate CPU core for game-logic stepping. |
| `ppo.n_steps` | `2048` | **Total** experience per update; divided evenly across `n_envs` internally. Training dynamics are identical regardless of `n_envs`. |
| `device` | `auto` | CUDA auto-detection: `"cuda"` if GPU available, `"cpu"` otherwise. |

**n_steps with parallel envs:**
```
Config:  n_steps: 8192,  n_envs: 8
Actual:  per_env_steps = 8192 // 8 = 1024
         total per update = 1024 × 8 = 8192   ← same total as n_envs=1
```

### Parallel Environment Collection

The pipeline uses `SubprocVecEnv` to parallelize game-logic stepping across multiple CPU cores:

```
                 ┌──────────────────────────────┐
                 │      main process (GPU)       │
                 │  model.predict(obs_batch)     │
                 │  PPO.update(rollout_buffer)   │
                 └──┬──┬──┬──┬──┬──┬──┬──┬──────┘
                    │  │  │  │  │  │  │  │
              ┌─────┴──┴──┴──┴──┴──┴──┴──┴──────┐
              │        SubprocVecEnv(N)            │
              │  worker[0] worker[1] ... worker[N] │
              │  (CPU core) (CPU core)   (CPU core)│
              │  env.step  env.step     env.step   │
              └────────────────────────────────────┘
```

- Environment stepping is the pipeline's bottleneck (pure Python game engine).
- With N parallel envs, throughput scales nearly linearly (N× on N CPU cores).
- The GPU processes batched observations (`N × 11 × 19 × 9`) in a single forward pass — negligible overhead for the tiny Res-CNN.
- Evaluation always uses a single environment (accesses `env.engine.grid` directly).

**Recommended `n_envs` by cloud plan:**

| GPU | CPU Cores | Recommended `n_envs` | Est. throughput |
|-----|-----------|---------------------|-----------------|
| RTX 3080 Ti | 12 | **8** | ~6,400 steps/s |
| RTX 4090 | 16 | **12** | ~9,600 steps/s |
| RTX 5090D | 24 | **16** | ~12,800 steps/s |

> Leave 2–4 cores for the OS and the main process (data loading, GPU coordination).

### Curriculum

| Phase | Goal | Key Rewards |
|-------|------|-------------|
| **1.1** | Red approaches Blue | Survival, approach, low illegal actions |
| **1.2** | Use bombs effectively | Bomb placement, brick destruction, kills |
| **1.3** | Full gameplay with buffs | Buff pickup, bomb efficiency, kills |

Progression is automatic: the pipeline evaluates every `evaluation.interval` steps.
When the composite score exceeds `composite_threshold` for `patience` consecutive
evals, the phase advances.

### Output Structure

```
runs/phase1_YYYYMMDD_HHMMSS/
├── configs/config.yaml          # Frozen config copy
├── checkpoints/
│   ├── latest.zip               # Latest model checkpoint
│   ├── latest_state.json        # Pipeline state (phase, step counters)
│   ├── best_model.zip           # Best model this phase
│   └── phase_*_complete.zip     # Phase-completion snapshots
├── logs/
│   ├── train.log                # Training log
│   └── phase_*/                 # TensorBoard events
├── evaluations/                 # JSON evaluation results
├── videos/                      # Recorded gameplay videos
└── reports/                     # Failure reports (if any)
```

### Common Usage Patterns

```bash
# Smoke test (verify environment in ~2 minutes)
python scripts/train_phase1.py --total-steps-override 2048 --eval-interval 1024

# Resume interrupted training
python scripts/train_phase1.py --resume runs/phase1_20260702_153000

# Force CPU (headless or no GPU)
python scripts/train_phase1.py --device cpu

# Bypass config hash check (config changed since checkpoint)
python scripts/train_phase1.py --resume runs/phase1_20260702_153000 --override-config
```

### Dependencies

See [`docs/training_dependencies.md`](../docs/training_dependencies.md) for full
setup instructions (PyTorch, SB3, imageio-ffmpeg, headless config, CUDA notes).

Key requirements:
- `torch` (CUDA or CPU)
- `stable-baselines3`
- `pyyaml`
- `imageio` + `imageio-ffmpeg` (optional, for video recording)
- Base game dependencies (`pygame`, `numpy`)
