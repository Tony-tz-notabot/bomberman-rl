"""Two random agents play a headless game and record video."""
import os
import sys
import numpy as np
import gym

# Add project root to path so src/ can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.bomberman_env import BombermanEnv

# Create env with rgb_array render mode for video recording
env = BombermanEnv(render_mode="rgb_array")

# Wrap with gym's RecordVideo
env = gym.wrappers.RecordVideo(
    env,
    video_folder="./videos",
    episode_trigger=lambda e: True,  # record every episode
    name_prefix="random_agents",
)

obs, info = env.reset()
done = False
step_count = 0

while not done and step_count < 1200:  # max ~50s at 24fps
    # Random actions for red; blue is handled by opponent_fn
    action = np.random.randint(0, 2, size=6, dtype=np.int8)
    obs, reward, terminated, truncated, info = env.step(action)
    done = terminated or truncated
    step_count += 1

print(f"Episode finished after {step_count} steps, reward={reward:.2f}")
env.close()
print("Video saved to ./videos/")
