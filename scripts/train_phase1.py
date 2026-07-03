#!/usr/bin/env python3
"""Phase 1 training pipeline for Bomberman PVP.

Usage:
    python scripts/train_phase1.py --config configs/phase1_fast.yaml
    python scripts/train_phase1.py --config configs/phase1_fast.yaml --resume runs/phase1_20260702_153000
    python scripts/train_phase1.py --config configs/phase1_fast.yaml --total-steps-override 2048 --eval-interval 1024
"""
import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import torch
from stable_baselines3 import PPO

# Ensure the project root is on sys.path so that `import src`, `import rewards` work
# when running the script directly (e.g. `python scripts/train_phase1.py`).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.bomberman_env import BombermanEnv
from src.config_loader import load_config, compute_config_hash
from src.evaluate import evaluate_phase, format_metrics
from src.feature_extractor import ResCnnFeatureExtractor
from src.video_recorder import VideoRecorder
from rewards.phase1 import Phase1Reward

logger = logging.getLogger("train_phase1")


def _stationary_opponent(snapshot, agent_id):
    """Opponent that does nothing (static blue)."""
    return np.zeros(6, dtype=np.int8)


def _patch_env_reset(env, phase):
    """Patch env.reset() to preserve phase when SB3 calls reset without options.

    SB3's BaseAlgorithm.__init__ and set_env() both call env.reset()
    without options, which would reset BombermanEnv._phase back to 1.1.
    This patch ensures optionless resets always use the intended phase.
    Works for both single envs and within SubprocVecEnv workers.
    """
    orig_reset = env.reset

    def _preserve_phase_reset(*, seed=None, options=None):
        if options is not None and ("phase" in options or "grid" in options):
            return orig_reset(seed=seed, options=options)
        return orig_reset(seed=seed, options={"phase": phase})

    env.reset = _preserve_phase_reset
    return env


def _make_phase_aware_env(phase: float, config: Dict[str, Any], seed: int = 42):
    """Create a BombermanEnv for the given phase with a patched reset
    that preserves the phase across SB3-internal env.reset() calls.
    """
    reward_config = {"phase": phase}
    env = BombermanEnv(
        reward_fn=Phase1Reward(reward_config),
        opponent_fn=_stationary_opponent,
        timeout_frames=5400,
    )
    _patch_env_reset(env, phase)
    # First reset: explicitly set the phase
    env.reset(options={"phase": phase}, seed=seed)
    return env


def _make_env_fn(rank: int, phase: float, config: Dict[str, Any], base_seed: int):
    """Return a picklable callable that creates a phase-aware env for a VecEnv worker.

    Each worker gets a unique seed (base_seed + rank) for reproducibility.
    The closure is serialized via cloudpickle inside SubprocVecEnv, so it
    works correctly on Windows (spawn start method).
    """
    import os as _os
    from rewards.phase1 import Phase1Reward  # ensure import in subprocess scope

    # Prevent pygame from attempting display init in subprocesses
    _os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

    def _make():
        env = BombermanEnv(
            render_mode="rgb_array",
            reward_fn=Phase1Reward({"phase": phase}),
            opponent_fn=_stationary_opponent,
            timeout_frames=5400,
        )
        _patch_env_reset(env, phase)
        env.reset(seed=base_seed + rank)
        return env

    return _make


def _build_vec_env(phase: float, config: Dict[str, Any], seed: int):
    """Create a vectorized environment for parallel experience collection.

    If n_envs=1, returns a plain BombermanEnv (backward compatible).
    If n_envs>1, returns a SubprocVecEnv with n_envs worker processes.
    """
    from stable_baselines3.common.vec_env import SubprocVecEnv

    n_envs = config.get("run", {}).get("n_envs", 1)
    if n_envs == 1:
        return _make_phase_aware_env(phase, config, seed)

    env_fns = [_make_env_fn(i, phase, config, seed) for i in range(n_envs)]
    return SubprocVecEnv(env_fns)


def _create_model(env, config: Dict[str, Any], device: str = "auto"):
    """Create SB3 PPO model with custom Res-CNN feature extractor."""
    policy_kwargs = dict(
        features_extractor_class=ResCnnFeatureExtractor,
        features_extractor_kwargs=dict(features_dim=config["network"]["features_dim"]),
        net_arch=dict(pi=[128], vf=[256]),
    )

    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"

    model = PPO(
        "CnnPolicy",
        env,
        learning_rate=config["ppo"]["learning_rate"],
        n_steps=config["ppo"]["n_steps"],
        batch_size=config["ppo"]["batch_size"],
        n_epochs=config["ppo"]["n_epochs"],
        gamma=config["ppo"]["gamma"],
        gae_lambda=config["ppo"]["gae_lambda"],
        clip_range=config["ppo"]["clip_range"],
        ent_coef=config["ppo"]["ent_coef"],
        vf_coef=config["ppo"]["vf_coef"],
        max_grad_norm=config["ppo"]["max_grad_norm"],
        policy_kwargs=policy_kwargs,
        device=device,
        verbose=0,
        tensorboard_log=None,  # set per-phase
    )
    return model


def save_state(state: Dict[str, Any], path: str):
    """Save training state to JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def load_state(path: str) -> Dict[str, Any]:
    """Load training state from JSON file."""
    with open(path, "r") as f:
        return json.load(f)


class TrainingPipeline:
    """Orchestrates curriculum progression, evaluation, checkpointing, and logging."""

    def __init__(self, config: Dict[str, Any], resume_dir: Optional[str] = None,
                 override_config: bool = False):
        self.config = config
        self.config_hash = compute_config_hash(config)
        self.override_config = override_config

        # Create run directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_dir = config["run"]["output_dir"]
        self.run_dir = Path(base_dir) / f"phase1_{timestamp}"
        if resume_dir:
            self.run_dir = Path(resume_dir)

        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "checkpoints").mkdir(exist_ok=True)
        (self.run_dir / "logs").mkdir(exist_ok=True)
        (self.run_dir / "evaluations").mkdir(exist_ok=True)
        (self.run_dir / "videos").mkdir(exist_ok=True)

        # Copy config to run directory
        self._save_config()

        # Training state
        self.current_phase = 1.1
        self.total_timesteps = 0
        self.phase_timesteps = 0
        self.best_composite_score = 0.0
        self.patience_counter = 0
        self.model = None
        self.env = None

        # If resuming, overwrite state from checkpoint
        if resume_dir:
            self._load_from_resume(resume_dir)

        # Setup logging
        self._setup_logging()

        # Heartbeat tracking
        self._last_heartbeat = time.time()
        self._start_wall = time.time()

    def _save_config(self):
        """Save config YAML to run directory."""
        import yaml
        dst = self.run_dir / "configs"
        dst.mkdir(exist_ok=True)
        with open(dst / "config.yaml", "w") as f:
            yaml.dump(self.config, f, default_flow_style=False)

    def _setup_logging(self):
        """Configure file + console logging."""
        log_path = self.run_dir / "logs" / "train.log"
        fmt = "%(asctime)s [%(levelname)s] %(message)s"
        logging.basicConfig(
            level=logging.INFO,
            format=fmt,
            handlers=[
                logging.FileHandler(str(log_path)),
                logging.StreamHandler(sys.stdout),
            ],
        )
        logger.info("=" * 60)
        logger.info("Phase 1 Training Pipeline")
        logger.info(f"Config hash: {self.config_hash}")
        logger.info(f"Run directory: {self.run_dir}")
        logger.info(f"PyTorch version: {torch.__version__}")
        logger.info(f"CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            logger.info(f"CUDA device: {torch.cuda.get_device_name(0)}")
        logger.info(f"SB3: PPO with ResCnnFeatureExtractor")
        logger.info(f"Device: {self.config.get('device', 'auto')}")
        logger.info("=" * 60)

    def _load_from_resume(self, resume_dir: str):
        """Load training state from a previous run directory."""
        resume_path = Path(resume_dir)
        state_path = resume_path / "checkpoints" / "latest_state.json"
        model_path = resume_path / "checkpoints" / "latest.zip"

        if not state_path.exists():
            raise FileNotFoundError(f"Resume state not found: {state_path}")

        state = load_state(str(state_path))
        saved_hash = state.get("config_hash", "")

        # Config hash mismatch check
        if not self.override_config and saved_hash and saved_hash != self.config_hash:
            logger.warning(f"Config hash mismatch: saved={saved_hash}, current={self.config_hash}")
            logger.warning("Pass --override-config to bypass this check.")
            raise ValueError(
                f"Config hash mismatch: saved={saved_hash}, current={self.config_hash}. "
                "Use --override-config to bypass."
            )

        self.current_phase = state.get("current_phase", 1.1)
        self.total_timesteps = state.get("total_timesteps", 0)
        self.phase_timesteps = state.get("phase_timesteps", 0)
        self.best_composite_score = state.get("best_composite_score", 0.0)
        self.patience_counter = state.get("patience_counter", 0)

        if not model_path.exists():
            raise FileNotFoundError(f"Resume model not found: {model_path}")

        # Create env and load model
        self._setup_phase_env()
        self.model = PPO.load(str(model_path), env=self.env)
        logger.info(f"Resumed from {resume_dir}: phase={self.current_phase}, "
                    f"total_steps={self.total_timesteps}, best_score={self.best_composite_score:.4f}")

    def _setup_phase_env(self):
        """Create env for current phase (possibly vectorized)."""
        if self.env is not None:
            self.env.close()
        self.env = _build_vec_env(
            self.current_phase, self.config, self.config["run"]["seed"]
        )

    def _create_phase_model(self):
        """Create fresh PPO model for current phase with adjusted n_steps."""
        device = self.config.get("device", "auto")
        n_envs = self.config.get("run", {}).get("n_envs", 1)
        total_n_steps = self.config["ppo"]["n_steps"]
        per_env_steps = max(1, total_n_steps // n_envs)
        ppo_cfg = dict(self.config["ppo"])
        ppo_cfg["n_steps"] = per_env_steps
        self.model = _create_model(self.env, {**self.config, "ppo": ppo_cfg}, device)
        # Set tensorboard log dir only if tensorboard is available
        # (gracefully degrades for CI / minimal installs)
        tb_log = str(self.run_dir / "logs" / f"phase_{int(self.current_phase * 10)}")
        try:
            import tensorboard  # noqa: F401
            self.model.tensorboard_log = tb_log
        except ImportError:
            logger.info("TensorBoard not available — skipping TB logging")

    def _save_checkpoint(self, name: str = "latest"):
        """Save model weights and training state."""
        ckpt_dir = self.run_dir / "checkpoints"
        model_path = ckpt_dir / f"{name}.zip"
        state_path = ckpt_dir / f"{name}_state.json"

        if self.model is not None:
            self.model.save(str(model_path))

        state = {
            "config_hash": self.config_hash,
            "current_phase": self.current_phase,
            "total_timesteps": self.total_timesteps,
            "phase_timesteps": self.phase_timesteps,
            "best_composite_score": self.best_composite_score,
            "patience_counter": self.patience_counter,
        }
        save_state(state, str(state_path))
        logger.info(f"Checkpoint saved: {name} (step {self.total_timesteps})")

    def _heartbeat(self):
        """Log progress heartbeat at configured interval."""
        now = time.time()
        interval = self.config["logging"]["heartbeat_seconds"]
        if now - self._last_heartbeat < interval:
            return
        self._last_heartbeat = now
        elapsed = now - self._start_wall
        phase_key = int(self.current_phase * 10)
        logger.info(
            f"HEARTBEAT | phase={phase_key} | total_steps={self.total_timesteps} "
            f"| phase_steps={self.phase_timesteps} "
            f"| elapsed={elapsed:.0f}s "
            f"| best_score={self.best_composite_score:.4f}"
        )

    def _evaluate(self) -> Optional[Dict[str, float]]:
        """Run evaluation and return metrics.

        Uses a separate single env (not the training VecEnv) because
        evaluate_phase accesses env.engine.grid directly.
        """
        phase_key = f"phase_{int(self.current_phase * 10)}"
        eval_cfg = self.config["evaluation"]
        num_episodes = eval_cfg["episodes"]
        seeds = [self.config["run"]["seed"] + i for i in range(num_episodes)]

        # Create a single eval env (not vectorized) for evaluate_phase
        eval_env = _make_phase_aware_env(
            self.current_phase, self.config, self.config["run"]["seed"]
        )

        try:
            metrics = evaluate_phase(
                self.model, eval_env, self.config,
                phase=self.current_phase,
                num_episodes=num_episodes,
                seeds=seeds,
            )
        finally:
            eval_env.close()

        metrics["total_timesteps"] = self.total_timesteps
        metrics["phase_timesteps"] = self.phase_timesteps
        metrics["elapsed_time"] = time.time() - self._start_wall

        # Save evaluation JSON
        eval_dir = self.run_dir / "evaluations" / phase_key
        eval_dir.mkdir(parents=True, exist_ok=True)
        eval_path = eval_dir / f"step_{self.total_timesteps:07d}.json"
        with open(eval_path, "w") as f:
            json.dump(metrics, f, indent=2)

        logger.info(f"EVALUATION [{phase_key} step={self.total_timesteps}]: "
                    f"{format_metrics(metrics)}")

        # Record videos for a subset of seeds
        video_eps = eval_cfg.get("video_episodes", 0)
        if video_eps > 0:
            self._record_videos(seeds[:video_eps])

        return metrics

    def _record_videos(self, seeds: list):
        """Record evaluation videos for the given seeds."""
        video_dir = self.run_dir / "videos" / f"phase_{int(self.current_phase * 10)}"
        video_dir.mkdir(parents=True, exist_ok=True)

        recorder = VideoRecorder(str(video_dir), fps=24)

        if not recorder.available:
            logger.warning("Video recording skipped: imageio-ffmpeg not available")
            return

        # Temporarily create a render-capable env
        video_env = BombermanEnv(
            reward_fn=Phase1Reward({"phase": self.current_phase}),
            opponent_fn=_stationary_opponent,
            render_mode="rgb_array",
        )

        step_str = f"step_{self.total_timesteps:07d}"
        for i, seed in enumerate(seeds):
            out_path = video_dir / f"{step_str}_seed_{seed:03d}.mp4"
            success = recorder.record_episode(
                video_env, self.model, seed=seed, path=str(out_path),
                phase=self.current_phase,
            )
            if success:
                logger.info(f"Video saved: {out_path}")
            else:
                logger.warning(f"Video recording failed for seed {seed}")

        video_env.close()

    def _check_phase_progression(self, metrics: Dict[str, float]) -> bool:
        """Check if the agent meets the threshold to advance to the next phase.

        Returns True if the phase advanced.
        """
        threshold = self.config["progression"]["composite_threshold"]
        patience = self.config["progression"]["patience"]

        score = metrics.get("composite_score", 0.0)

        if score > self.best_composite_score:
            self.best_composite_score = score
            self.patience_counter = 0
            self._save_checkpoint("best_model")
            logger.info(f"New best composite score: {score:.4f}")
        else:
            self.patience_counter += 1
            logger.info(f"Composite score {score:.4f} <= best {self.best_composite_score:.4f} "
                        f"(patience {self.patience_counter}/{patience})")

        # Check if we can advance
        phase_min = self.config["phases"][f"{self.current_phase}"]["min_steps"]
        phase_max = self.config["phases"][f"{self.current_phase}"]["max_steps"]

        can_advance = self.phase_timesteps >= phase_min

        if can_advance and score >= threshold:
            self._advance_phase()
            return True
        elif self.phase_timesteps >= phase_max:
            if score >= threshold:
                self._advance_phase()
                return True
            else:
                logger.warning(
                    f"Phase {self.current_phase}: max_steps ({phase_max}) reached "
                    f"with composite score {score:.4f} < threshold {threshold}. "
                    "Marking run as needing review."
                )
                self._write_failure_report(score, threshold)
                self._advance_phase()  # still advance to next phase
                return True

        return False

    def _write_failure_report(self, score: float, threshold: float):
        """Write a failure report when phase max_steps is reached without meeting criteria."""
        report_dir = self.run_dir / "reports"
        report_dir.mkdir(exist_ok=True)
        phase_key = f"phase_{int(self.current_phase * 10)}"
        report_path = report_dir / f"{phase_key}_failure.md"
        with open(report_path, "w") as f:
            f.write(f"# Phase {self.current_phase} Failure Report\n\n")
            f.write(f"- Total timesteps: {self.total_timesteps}\n")
            f.write(f"- Phase timesteps: {self.phase_timesteps}\n")
            f.write(f"- Best composite score: {self.best_composite_score:.4f}\n")
            f.write(f"- Threshold: {threshold}\n")
            f.write(f"- Config hash: {self.config_hash}\n")
            f.write(f"- Timestamp: {datetime.now().isoformat()}\n")
        logger.warning(f"Failure report written: {report_path}")

    def _advance_phase(self):
        """Advance to the next training phase."""
        phases = [1.1, 1.2, 1.3]
        current_idx = phases.index(self.current_phase)
        if current_idx >= len(phases) - 1:
            logger.info("All phases complete!")
            self.current_phase = 2.0  # sentinel past 1.3 so outer loop exits
            return

        next_phase = phases[current_idx + 1]
        logger.info(f"Advancing from phase {self.current_phase} to {next_phase}")

        # Save phase transition checkpoint
        self._save_checkpoint(f"phase_{int(self.current_phase * 10)}_complete")

        # Reset phase-local state FIRST so _setup_phase_env uses the correct phase
        self.current_phase = next_phase
        self.phase_timesteps = 0
        self.best_composite_score = 0.0
        self.patience_counter = 0

        # Create new env for the new phase
        self._setup_phase_env()

        # Update model's env for the new phase
        self.model.set_env(self.env)

        logger.info(f"Phase transition complete. New phase: {self.current_phase}")

    def run(self):
        """Run the full training pipeline with curriculum progression."""
        logger.info("Starting training pipeline run")

        # Initialize phase 1.1
        if self.model is None:
            self._setup_phase_env()
            self._create_phase_model()
            self._save_checkpoint("latest")

        # Main training loop across phases
        while self.current_phase <= 1.3:
            phase_config = self.config["phases"][f"{self.current_phase}"]
            eval_interval = self.config["evaluation"]["interval"]
            ckpt_interval = self.config["checkpoint"]["interval"]

            logger.info(f"Starting phase {self.current_phase}: "
                        f"min={phase_config['min_steps']}, max={phase_config['max_steps']}")

            phase_limit = phase_config["max_steps"]

            # Phase training loop
            while self.phase_timesteps < phase_limit:
                remaining = phase_limit - self.phase_timesteps
                # Train in chunks for responsiveness
                chunk = min(eval_interval, remaining)
                self.model.learn(total_timesteps=chunk, reset_num_timesteps=False,
                                 tb_log_name=f"phase_{int(self.current_phase * 10)}")
                self.total_timesteps += chunk
                self.phase_timesteps += chunk

                # Heartbeat
                self._heartbeat()

                # Evaluate at interval
                if (self.total_timesteps % eval_interval < chunk) or self.phase_timesteps >= phase_limit:
                    eval_metrics = self._evaluate()
                    if eval_metrics:
                        advanced = self._check_phase_progression(eval_metrics)
                        if advanced:
                            break  # phase advanced, restart outer loop

                # Checkpoint at interval
                if self.total_timesteps % ckpt_interval < chunk:
                    self._save_checkpoint("latest")

            # Phase ended (either advanced or max_steps reached without advancing)
            if self.current_phase >= 1.3 and self.phase_timesteps >= phase_limit:
                logger.info("Phase 1.3 complete. Training finished.")
                break

        logger.info("Training pipeline complete.")
        self._save_checkpoint("final")

        # Final evaluation
        if self.model is not None:
            final_metrics = self._evaluate()
            logger.info(f"FINAL EVALUATION: {format_metrics(final_metrics)}")

        if self.env is not None:
            self.env.close()


def main():
    parser = argparse.ArgumentParser(
        description="Phase 1 Bomberman PVP training pipeline"
    )
    parser.add_argument(
        "--config", required=True,
        help="Path to YAML config file"
    )
    parser.add_argument(
        "--resume",
        help="Resume from existing run directory"
    )
    parser.add_argument(
        "--total-steps-override", type=int,
        help="Override max_steps for all phases (smoke testing)"
    )
    parser.add_argument(
        "--eval-interval", type=int,
        help="Override evaluation interval"
    )
    parser.add_argument(
        "--device", default="auto", choices=["auto", "cpu", "cuda"],
        help="Device for PyTorch"
    )
    parser.add_argument(
        "--override-config", action="store_true",
        help="Bypass config hash mismatch check during resume"
    )
    args = parser.parse_args()

    config = load_config(args.config)

    if args.total_steps_override:
        for phase_key in ("1.1", "1.2", "1.3"):
            config["phases"][phase_key]["max_steps"] = args.total_steps_override
            config["phases"][phase_key]["min_steps"] = args.total_steps_override // 2
        config["evaluation"]["interval"] = args.eval_interval or (args.total_steps_override // 2)

    if args.eval_interval:
        config["evaluation"]["interval"] = args.eval_interval

    if args.device != "auto":
        config["device"] = args.device

    pipeline = TrainingPipeline(config, resume_dir=args.resume,
                                 override_config=args.override_config)
    pipeline.run()


if __name__ == "__main__":
    main()
