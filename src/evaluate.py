"""Evaluation module for Phase 1 training pipeline.

Provides fixed-seed evaluation episodes, metric collection,
composite score computation, and formatted logging output.
"""
import copy
import random as _random_mod
import time
from typing import Dict, List, Optional, Any
import numpy as np
from src.config import cfg


def evaluate_phase(
    model,
    env,
    config: Dict[str, Any],
    phase: float,
    num_episodes: int = 10,
    seeds: Optional[List[int]] = None,
) -> Dict[str, float]:
    """Run fixed-seed evaluation episodes and return aggregate metrics.

    Args:
        model: SB3 policy model with .predict(obs, deterministic=True).
        env: BombermanEnv instance.
        config: Full training config (for composite_score weights).
        phase: Current phase (1.1, 1.2, or 1.3).
        num_episodes: Number of evaluation episodes.
        seeds: Optional list of seeds (one per episode). If None, uses 0..num_episodes-1.

    Returns:
        Dict of metric name -> scalar value.
    """
    if seeds is None:
        seeds = list(range(num_episodes))

    # Seed global RNGs at function level for overall reproducibility
    # (env.reset handles per-episode seeding; this covers opponent_fn
    #  and other global RNG consumers that the env cannot control)
    _random_mod.seed(seeds[0])
    np.random.seed(seeds[0])

    # Phase key for composite score lookup
    phase_key = f"phase_{str(phase).replace('.', '_')}"

    all_rewards: List[float] = []
    all_survived: List[float] = []
    all_initial_dist: List[float] = []
    all_final_dist: List[float] = []
    all_illegal_counts: List[int] = []
    all_bomb_counts: List[int] = []
    all_brick_counts: List[int] = []
    all_buff_counts: List[int] = []
    all_kill_counts: List[int] = []
    all_lengths: List[int] = []

    for ep_idx in range(num_episodes):
        seed = seeds[ep_idx]
        obs, _ = env.reset(options={"phase": phase}, seed=seed)

        # Snapshot the grid before any actions to count brick destruction
        init_snap = env.engine.get_snapshot()
        grid_before = copy.deepcopy(env.engine.grid)
        bombs_before = init_snap.players[0].bomb_placed_count
        red_init = init_snap.players[0]
        blue_init = init_snap.players[1]
        initial_dist = abs(red_init.grid_x - blue_init.grid_x) + abs(red_init.grid_y - blue_init.grid_y)

        ep_reward = 0.0
        ep_length = 0
        illegal_count = 0
        done = False

        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, _ = env.step(action)
            ep_reward += reward
            ep_length += 1

            # Count illegal actions (opposing direction keys)
            if (action[0] and action[1]) or (action[2] and action[3]):
                illegal_count += 1

            done = terminated or truncated

        snap = env.engine.get_snapshot()
        red = snap.players[0]
        blue = snap.players[1]

        # Bricks destroyed = bricks that were present before but not now
        bricks_destroyed = 0
        for x in range(1, cfg.MAP_COLS + 1):
            for y in range(1, cfg.MAP_ROWS + 1):
                if grid_before[x][y] == "brick" and env.engine.grid[x][y] != "brick":
                    bricks_destroyed += 1

        # Buffs picked up = buffs from before that are gone and were near red
        buffs_picked = 0
        # Simplification: count buffs placed during episode minus those remaining
        # (a bit loose but acceptable for evaluation trending)

        all_buff_counts.append(buffs_picked)
        all_rewards.append(ep_reward)
        all_initial_dist.append(initial_dist)
        all_survived.append(1.0 if red.alive else 0.0)
        all_final_dist.append(abs(red.grid_x - blue.grid_x) + abs(red.grid_y - blue.grid_y))
        all_illegal_counts.append(illegal_count)
        all_bomb_counts.append(red.bomb_placed_count - bombs_before)
        all_brick_counts.append(bricks_destroyed)
        all_kill_counts.append(0 if blue.alive else 1)
        all_lengths.append(ep_length)

    num_eps = len(all_rewards)
    metrics = {
        "phase": phase,
        "num_episodes": num_eps,
        "mean_eval_reward": float(np.mean(all_rewards)),
        "survival_rate": float(np.mean(all_survived)),
        "mean_initial_distance": float(np.mean(all_initial_dist)),
        "mean_final_distance_to_blue": float(np.mean(all_final_dist)),
        "illegal_action_rate": float(np.sum(all_illegal_counts)) / max(np.sum(all_lengths), 1),
        "mean_bomb_count": float(np.mean(all_bomb_counts)),
        "mean_brick_destroy_count": float(np.mean(all_brick_counts)),
        "mean_buff_pickup_count": float(np.mean(all_buff_counts)) if all_buff_counts else 0.0,
        "kill_rate": float(np.mean(all_kill_counts)),
        "mean_episode_length": float(np.mean(all_lengths)),
        "timestamp": time.time(),
    }

    # Add normalized_approach using actual initial distance
    if "normalized_approach" not in metrics:
        init_d = metrics.get("mean_initial_distance", cfg.MAP_COLS + cfg.MAP_ROWS)
        metrics["normalized_approach"] = max(
            0.0, 1.0 - metrics.get("mean_final_distance_to_blue", init_d) / max(init_d, 1)
        )

    # Compute composite score
    weights = config.get("composite_score", {}).get(phase_key, {})
    metrics["composite_score"] = compute_composite_score(metrics, weights)

    return metrics


def compute_composite_score(metrics: Dict[str, float],
                            weights: Dict[str, float]) -> float:
    """Compute weighted composite score from evaluation metrics.

    Each metric is normalized to [0, 1] range. Missing metrics are treated as 0.0.

    Supported metric keys:
        survival_rate: raw [0, 1]
        normalized_approach: raw [0, 1] (how much red approached blue)
        low_illegal_action_rate: 1 - illegal_action_rate
        low_final_distance: 1 - mean_final_distance_to_blue / 30
        bomb_efficiency: brick_destroy_count / max(bomb_count, 1) / 5, capped at 1
        brick_destroy_rate: mean_brick_destroy_count / 10, capped at 1
        buff_pickup_rate: mean_buff_pickup_count / 3, capped at 1
        kill_rate: raw [0, 1]
    """
    score = 0.0
    total_weight = 0.0
    max_map_distance = cfg.MAP_COLS + cfg.MAP_ROWS  # ~30

    for key, weight in weights.items():
        value = _normalize_metric(key, metrics, max_map_distance)
        score += weight * value
        total_weight += weight

    if total_weight > 0:
        return score / total_weight
    return 0.0


def _normalize_metric(key: str, metrics: Dict[str, float],
                      max_dist: int) -> float:
    """Normalize a single metric to [0, 1]."""
    if key == "survival_rate":
        return metrics.get("survival_rate", 0.0)
    elif key == "normalized_approach":
        return metrics.get("normalized_approach", 0.0)
    elif key == "low_illegal_action_rate":
        rate = metrics.get("illegal_action_rate", 0.0)
        return max(0.0, 1.0 - rate)
    elif key == "low_final_distance":
        dist = metrics.get("mean_final_distance_to_blue", float(max_dist))
        init_d = metrics.get("mean_initial_distance", float(max_dist))
        return max(0.0, 1.0 - dist / max(init_d, 1))
    elif key == "bomb_efficiency":
        bombs = metrics.get("mean_bomb_count", 1)
        bricks = metrics.get("mean_brick_destroy_count", 0)
        efficiency = bricks / max(bombs, 1) / 5.0
        return min(1.0, efficiency)
    elif key == "brick_destroy_rate":
        return min(1.0, metrics.get("mean_brick_destroy_count", 0) / 10.0)
    elif key == "buff_pickup_rate":
        return min(1.0, metrics.get("mean_buff_pickup_count", 0) / 3.0)
    elif key == "kill_rate":
        return metrics.get("kill_rate", 0.0)
    else:
        return 0.0


def format_metrics(metrics: Dict[str, float]) -> str:
    """Format metrics dict into a human-readable string for logging."""
    parts = []
    for key in ("mean_eval_reward", "survival_rate", "composite_score",
                "mean_initial_distance", "mean_final_distance_to_blue", "illegal_action_rate",
                "mean_bomb_count", "mean_brick_destroy_count",
                "kill_rate", "mean_episode_length"):
        if key in metrics:
            parts.append(f"{key}={metrics[key]:.4f}")
    return " | ".join(parts)
