"""Example: train a PPO agent on BombermanEnv using Stable-Baselines3.

Usage:
    python examples/train_with_sb3.py

Dependencies:
    pip install gymnasium stable-baselines3 numpy
"""
import sys
from pathlib import Path

# Add project root to path so imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from sb3_contrib import MaskablePPO
from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.callbacks import EvalCallback

from bomberman_env import BombermanEnv
from rewards.sparse import SparseReward


# ── Custom opponent strategies ──

def random_opponent(snapshot, agent_id):
    """Random baseline opponent."""
    return np.random.randint(0, 2, size=6, dtype=np.int8)


def stationary_opponent(snapshot, agent_id):
    """Opponent that does nothing."""
    return np.zeros(6, dtype=np.int8)


# ── Training setup ──

def main():
    # Create environment with random opponent
    env = BombermanEnv(
        reward_fn=SparseReward(),
        opponent_fn=random_opponent,
        penalty_opposing=-0.01,
    )

    # Validate environment (optional, for debugging)
    # check_env(env)  # Uncomment to verify gym API compliance

    # Create PPO agent
    # MultiBinary action space → use MultiInputPolicy or MlpPolicy
    # For CNN-friendly observation (image-like Box), CnnPolicy works
    model = PPO(
        "CnnPolicy",
        env,
        learning_rate=3e-4,
        n_steps=2048,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,
        verbose=1,
        tensorboard_log="./tb_logs/",
    )

    # Train
    print("Starting training (1000 timesteps for demo)...")
    model.learn(total_timesteps=1000)

    # Save
    model.save("./models/bomberman_ppo_demo")
    print("Model saved to ./models/bomberman_ppo_demo")

    # ── Evaluation loop ──

    print("\nRunning evaluation...")
    env = BombermanEnv(
        reward_fn=SparseReward(),
        opponent_fn=random_opponent,
    )
    obs, _ = env.reset()
    total_reward = 0.0
    for _ in range(200):
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, _ = env.step(action)
        total_reward += reward
        if terminated or truncated:
            break
    print(f"Evaluation total reward: {total_reward:.2f}")


if __name__ == "__main__":
    main()
