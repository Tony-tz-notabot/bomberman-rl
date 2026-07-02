# Phase 1 Training Pipeline Design

## Context

The project already provides:

- `BombermanEnv`, a Gym single-agent environment where the red player is trained and the blue player is controlled by `opponent_fn`.
- `BombermanPettingZooEnv`, a two-agent ParallelEnv for later self-play.
- `Phase1Reward`, with `phase=1.1`, `phase=1.2`, and `phase=1.3`.
- `render_mode="rgb_array"` support, suitable for headless cloud video capture.
- A demo `examples/train_with_sb3.py`, which is not yet sufficient for long-running cloud training.

The first production training script should optimize for remote reliability, repeatable evaluation, early reward-function diagnosis, and easy continuation on a CUDA cloud host.

## Training Scope

Use single-agent training for Phase 1:

- Train the red player.
- Blue is fixed during each episode or round, randomly placed on an empty floor tile at round start.
- In all phases, blue is randomly placed at round start, then static for the round's duration.

This avoids self-play instability while still forcing the red policy to learn navigation toward a valid target. Fixed evaluation seeds will reuse deterministic map and blue-position sampling so progress can be compared across checkpoints.

## Map Generation Strategy

Each phase uses a different map generation strategy, controlling the difficulty of navigation and bomb interaction:

### Phase 1.1 — Special connected map

```
      Phase 1.1 map strategy:
      - Same standard Bomberman layout (stone pillars at (even, even),
        corridor cells at (odd, even) / (even, odd)).
      - BRICK_GEN_PROB is reduced to allow connected paths.
      - After generation, BFS-verify that red's starting region
        and a sampled empty floor tile for blue are in the same
        connected component of floor cells.
      - If the sampled blue tile is not reachable, either resample
        or regenerate the map (configurable, default: resample).
      - Bricks are present but sparse enough that a corridor path
        from red to blue exists without any brick destruction.
```

This phase teaches navigation and survival. The red policy must learn to approach a reachable blue target without needing to open paths with bombs.

### Phase 1.2 — Standard random map (no connectivity guarantee)

```
      Phase 1.2 map strategy:
      - Standard GameEngine.generate_map() with BRICK_GEN_PROB = 0.7.
      - No connectivity check is performed.
      - Blue is randomly placed on any empty floor tile (may or may
        not be reachable from red without destroying bricks).
      - Red must learn to place bombs, destroy bricks, and open
        paths to reach blue.
```

This phase adds bomb and brick interaction. Since connectivity is not guaranteed, the policy must learn to use bombs to open blocked corridors.

### Phase 1.3 — Same standard map as Phase 1.2

```
      Phase 1.3 map strategy:
      - Identical to Phase 1.2: standard random generation.
      - Blue randomly placed on any empty floor tile.
      - Same BRICK_GEN_PROB = 0.7.
```

Only the reward function changes in Phase 1.3, adding buff pickup incentives. Map generation is unchanged from Phase 1.2.

### Blue spawn sampling (all phases)

The blue player's position is sampled at each episode or round reset:

1. Collect all floor cells from the generated map.
2. Filter to cells reachable from red via BFS through floor cells (for Phase 1.1; for Phases 1.2–1.3 all floor tiles are candidates).
3. Randomly pick one cell as blue's spawn position.
4. Verify the picked cell is not the same as red's spawn cell.
5. Blue is placed there and remains stationary throughout the episode or round.

The red player always spawns at the standard bottom-left corner `(1, 1)` in all phases when using procedural map generation. Custom evaluation matrices may override both spawns via the `_init_from_matrix` path.

## Episode Termination

Each training episode corresponds to one game round (not the full match).

| Condition | Phase 1.1 | Phase 1.2 | Phase 1.3 |
|-----------|-----------|-----------|-----------|
| Red reaches Blue (≤1 grid cell) | `terminated=True`, reward +1 | — | — |
| Any player dies | `terminated=True` | `terminated=True` | `terminated=True` |
| Timeout (default 5400 frames) | `truncated=True`, no termination reward/penalty | same | same |

Chebyshev distance (`max(|dx|, |dy|) ≤ 1`) is used for reach detection, covering same-cell and all 8 adjacent cells.

On timeout, per-frame Phase1Reward components (approach, center_dev, stall, wall, illegal_action) are kept as the reward signal, but termination-linked bonuses and penalties (+1 success bonus, death penalty, kill reward) are suppressed. This prevents the agent from learning spurious associations between timeout and negative outcomes.

`reward_survive` defaults to 0.0 in Phase1Reward, removing the constant per-frame survival signal so the agent must rely on phase-specific rewards.

After `terminated=True` or `truncated=True`, call `reset()` to start a new episode with a fresh map and blue spawn.

## Algorithm

Use PPO from Stable-Baselines3, which uses PyTorch internally. Do not write a custom PPO implementation for the first version.

Reasons:

- PPO is already appropriate for `MultiBinary(6)` action control.
- SB3 provides robust rollout collection, GAE, checkpointing, logging, TensorBoard integration, and CUDA support.
- The project risk is currently reward quality and training observability, not PPO implementation details.

The training script will provide a custom PyTorch feature extractor and callbacks while leaving PPO optimization to SB3.

## Network Design

Do not use SB3's default image `CnnPolicy` feature extractor unchanged. It is derived from Atari-style image processing and is too coarse for the current `11 x 19 x 9` structured observation.

Use a Small Res-CNN feature extractor:

```text
input: 11 x 19 x 9, HWC float32
transpose: HWC -> CHW

Conv2d 9 -> 32, kernel=3, stride=1, padding=1
ReLU
Conv2d 32 -> 32, kernel=3, stride=1, padding=1
ReLU

Residual block, channels=32:
  Conv2d 32 -> 32, kernel=3, stride=1, padding=1
  ReLU
  Conv2d 32 -> 32, kernel=3, stride=1, padding=1
  skip add
  ReLU

Conv2d 32 -> 64, kernel=3, stride=1, padding=1
ReLU
Conv2d 64 -> 64, kernel=3, stride=1, padding=1
ReLU

Flatten
Linear -> 256
ReLU
features_dim = 256
```

Policy/value heads:

```text
actor:  256 -> 128 -> MultiBinary(6)
critic: 256 -> 256 -> scalar value
```

The map is small, so all convolutions use `3x3`, `stride=1`, and `padding=1` to preserve spatial detail. The CNN captures local rules such as wall adjacency, bomb risk, explosion cells, and corridor structure. The FC layer captures global relationships such as distance to blue, available paths, and longer-horizon bomb value.

References used for architecture direction:

- Stable-Baselines3 custom policy / feature extractor documentation.
- PPO paper, Schulman et al. 2017.
- Atari DQN / Nature CNN architecture, used as a contrast for large pixel inputs.
- MiniGrid training examples, used as a closer reference for small grid observations.

## Curriculum Progression

Use hybrid progression with configurable stage budgets.

Default fast-validation budget:

```yaml
phase_1_1:
  min_steps: 100000
  max_steps: 500000
phase_1_2:
  min_steps: 100000
  max_steps: 500000
phase_1_3:
  min_steps: 100000
  max_steps: 500000
```

All budget values must be configurable so the same script can later run standard or long training without code changes.

Progression rule:

- A phase cannot advance before `min_steps`.
- After `min_steps`, fixed-seed evaluation must reach the configured composite-score threshold.
- The threshold should require both score improvement and hard safety metrics.
- If the composite score does not improve for the configured patience window, stop early and mark the run as needing review.
- If `max_steps` is reached without meeting the progression criteria, stop the run, save all artifacts, and write a failure report.

This is intentional because the current reward function is not proven. The training script should surface reward issues early instead of blindly consuming cloud time.

## Evaluation

Run fixed-episode evaluation at a fixed training interval. Every evaluation uses deterministic seeds and records metrics to disk.

Metrics:

- `mean_eval_reward`
- `composite_score`
- `survival_rate`
- `mean_final_distance_to_blue`
- `illegal_action_rate`
- `bomb_placement_count`
- `brick_destroy_count`
- `buff_pickup_count`
- `kill_count`
- `mean_episode_length`
- phase id
- total timesteps
- wall-clock elapsed time

Composite score should be phase-aware:

- Phase 1.1 emphasizes approaching reachable blue, survival, low illegal action rate, and low final distance.
- Phase 1.2 adds useful bomb placement and brick destruction while penalizing wasteful bombs and deaths.
- Phase 1.3 adds buff pickup without allowing buff chasing to dominate navigation.

The exact weights belong in the training config. The script should log all raw components so a bad composite-score formula can be diagnosed after the run.

## Video Recording

Every fixed evaluation records videos.

Requirements:

- Format: `mp4`.
- Capture a small fixed set of evaluation episodes, for example 3 seeds per evaluation.
- Use `render_mode="rgb_array"` so the cloud host does not require a visible display.
- Store videos under the run directory by phase and timestep.

Example:

```text
runs/phase1_20260702_153000/videos/phase_1_2/
  step_025000_seed_000.mp4
  step_025000_seed_001.mp4
  step_025000_seed_002.mp4
```

If video generation fails, training should continue only if scalar evaluation succeeds, but the failure must be logged as a warning in the report. Repeated video failures should be visible in the heartbeat logs.

## Logging And Observability

The script must emit visible progress at least every 2 minutes.

Logging outputs:

- stdout heartbeat summary.
- `logs/train.jsonl`
- `logs/eval.jsonl`
- `logs/metrics.csv`
- TensorBoard logs.
- SB3 native metrics.

The heartbeat should include at least:

- current phase
- total timesteps
- phase timesteps
- frames per second
- elapsed time
- latest training reward if available
- latest evaluation composite score if available
- latest checkpoint path

SB3 metrics to persist:

- `policy_loss`
- `value_loss`
- `entropy_loss`
- `approx_kl`
- `clip_fraction`
- `explained_variance`

If a metric is not available at a heartbeat boundary, record `null` rather than omitting the field.

## Checkpoints And Resume

Use a run directory:

```text
runs/phase1_<timestamp>/
  configs/
  checkpoints/
    latest.zip
    latest_state.json
    phase_1_1_step_100000.zip
  best_model/
  logs/
  evaluations/
  videos/
  reports/
```

Resume behavior:

- `--resume <run_dir>` loads `checkpoints/latest.zip` and `checkpoints/latest_state.json`.
- The state file records current phase, total timesteps, phase timesteps, best composite score, patience counter, config hash, and RNG seeds.
- If a matching latest checkpoint exists and the user does not pass `--fresh`, the script may offer or perform automatic resume depending on config.
- Resume must not silently change phase thresholds or budgets. Config mismatch should fail unless the user passes an explicit override flag.

## Headless Cloud Runtime

The training script should set safe defaults for headless rendering:

- On Linux: `SDL_VIDEODRIVER=dummy`.
- On Windows: support the same variable if needed, but do not require it for local development.

CUDA handling:

- Default PPO device is `cuda` when available.
- The script logs `torch.cuda.is_available()`, CUDA device name, PyTorch version, and SB3 version at startup.
- A `--device cpu|cuda|auto` option should be available.

## Dependency Documentation

Implementation must add a dependency document, tentatively `docs/training_dependencies.md`, with copy-paste setup commands.

It should include:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install stable-baselines3 sb3-contrib tensorboard imageio imageio-ffmpeg pygame numpy gym pytest
python -m pytest tests/
python scripts/train_phase1.py --config configs/phase1_fast.yaml
```

It should also include Linux headless setup:

```bash
export SDL_VIDEODRIVER=dummy
```

and Windows PowerShell setup:

```powershell
$env:SDL_VIDEODRIVER = "dummy"
```

The document should explain that the CUDA wheel index may need to change depending on the cloud host's installed CUDA driver compatibility.

## Configuration Files

Implementation should add a fast default config, tentatively `configs/phase1_fast.yaml`.

Configurable areas:

- run id / output directory
- seed list
- PPO hyperparameters
- network size selection
- per-phase min/max steps
- eval interval
- eval episode count
- video episode count
- patience and early-stop thresholds
- composite-score weights
- checkpoint interval
- heartbeat interval seconds
- device
- resume behavior

## Testing Strategy

Automated tests should avoid long training.

Required tests:

- Blue spawn sampler only chooses empty reachable floor cells.
- Evaluation metrics can be computed from a short deterministic rollout.
- Video writer can write a tiny `mp4` from generated frames or is gracefully skipped when codec support is unavailable.
- Config loading validates required phase keys.
- Resume state round-trips through JSON.
- The custom CNN feature extractor accepts `(batch, 11, 19, 9)` or the SB3-transposed equivalent expected by the selected policy path.

Manual smoke command:

```bash
python scripts/train_phase1.py --config configs/phase1_fast.yaml --total-steps-override 2048 --eval-interval 1024
```

The smoke run should create logs, at least one checkpoint, scalar evaluation output, and at least one video unless video dependencies are missing.

## Non-Goals

- Do not implement self-play in this first training script.
- Do not implement MaskablePPO or action masks in this pass.
- Do not replace SB3 PPO with a custom PPO loop.
- Do not tune final long-run hyperparameters before the fast validation pipeline proves observable and resumable.

