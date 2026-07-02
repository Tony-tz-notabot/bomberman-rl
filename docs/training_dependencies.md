# Training Pipeline Dependencies

## Prerequisites

The Phase 1 training pipeline requires PyTorch, Stable-Baselines3, and
supporting libraries for video recording and logging.

## Quick Install

```bash
# Base ML stack
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install stable-baselines3 sb3-contrib tensorboard

# Video recording (optional — training works without it)
pip install imageio imageio-ffmpeg

# Config loading
pip install pyyaml

# Core dependencies (already present)
pip install pygame numpy gym pytest
```

## Verify Setup

```bash
# Run the full test suite
python -m pytest tests/

# Smoke test the training pipeline
python scripts/train_phase1.py --config configs/phase1_fast.yaml --total-steps-override 2048 --eval-interval 1024
```

## Headless (Cloud) Setup

The training environment uses Pygame's `render_mode="rgb_array"` which
does not require a physical display. However, Pygame may still attempt
to open a display window on some systems. Set this environment variable
before running in a headless environment:

### Linux (bash)
```bash
export SDL_VIDEODRIVER=dummy
```

### Windows (PowerShell)
```powershell
$env:SDL_VIDEODRIVER = "dummy"
```

### Windows (cmd)
```cmd
set SDL_VIDEODRIVER=dummy
```

### CUDA Notes

- The CUDA wheel index (`https://download.pytorch.org/whl/cu121`) assumes
  CUDA 12.1 is installed on the cloud host. If your host uses a different
  CUDA version, change the index URL accordingly:
  - CUDA 12.4: `https://download.pytorch.org/whl/cu124`
  - CUDA 11.8: `https://download.pytorch.org/whl/cu118`
  - CPU only: omit `--index-url`

- Verify CUDA is detected:
  ```bash
  python -c "import torch; print(torch.cuda.is_available())"
  ```

## Directory Layout After Setup

```
.
├── configs/
│   └── phase1_fast.yaml
├── scripts/
│   ├── __init__.py
│   └── train_phase1.py
├── src/
│   ├── config_loader.py
│   ├── evaluate.py
│   ├── feature_extractor.py
│   └── video_recorder.py
│   └── ... (existing game modules)
├── rewards/
│   ├── __init__.py
│   ├── sparse.py
│   └── phase1.py
├── tests/
│   ├── test_config_loader.py
│   ├── test_evaluate.py
│   ├── test_feature_extractor.py
│   ├── test_video_recorder.py
│   └── test_training_pipeline.py
│   └── ... (existing test files)
└── docs/
    └── training_dependencies.md
```

## Running Training

```bash
# Fast validation (default config)
python scripts/train_phase1.py --config configs/phase1_fast.yaml

# Resume from checkpoint
python scripts/train_phase1.py --config configs/phase1_fast.yaml --resume runs/phase1_20260702_153000

# Smoke test (quick run to verify setup)
python scripts/train_phase1.py --config configs/phase1_fast.yaml --total-steps-override 2048 --eval-interval 1024
```

## Output Structure

```
runs/phase1_20260702_153000/
├── configs/
│   └── config.yaml
├── checkpoints/
│   ├── latest.zip
│   ├── latest_state.json
│   ├── best_model.zip
│   └── phase_1_1_complete.zip
├── logs/
│   ├── train.log
│   └── phase_11/
│       └── events.out.tfevents.*
├── evaluations/
│   └── phase_1_1/
│       └── step_0025000.json
├── videos/
│   └── phase_1_1/
│       └── step_0025000_seed_000.mp4
└── reports/
    └── phase_1_1_failure.md (only if phase failed)
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `pygame.error: No available video device` | No display in headless env | Set `SDL_VIDEODRIVER=dummy` |
| `CUDA not available` | Wrong PyTorch CUDA version | Reinstall with matching CUDA index |
| `No module named 'imageio_ffmpeg'` | Missing video codec | `pip install imageio-ffmpeg` (optional) |
| `Config hash mismatch` | Config changed since checkpoint | Pass `--override-config` or use original config |
