"""Video recording for training evaluation episodes.

Records mp4 files from rgb_array frames. Gracefully degrades when
imageio-ffmpeg is not installed.
"""
from pathlib import Path
from typing import List
import numpy as np


def _ffmpeg_available() -> bool:
    """Check if imageio-ffmpeg codec is available."""
    try:
        import imageio_ffmpeg  # noqa: F401
        return True
    except ImportError:
        return False


def write_frames(path: str, frames: List[np.ndarray], fps: int = 24) -> bool:
    """Write a sequence of RGB frames to an mp4 file.

    Args:
        path: Output file path.
        frames: List of (H, W, 3) uint8 numpy arrays.
        fps: Frames per second.

    Returns:
        True if successful, False if codec is unavailable.
    """
    try:
        import imageio
    except ImportError:
        return False

    if not _ffmpeg_available():
        return False

    try:
        imageio.mimsave(path, frames, fps=fps)
        return True
    except Exception:
        return False


class VideoRecorder:
    """Records evaluation episodes to mp4 files.

    Usage:
        recorder = VideoRecorder("runs/my_run/videos", fps=24)
        if recorder.available:
            recorder.record_episode(env, model, seed=0, path="ep_0.mp4")
    """

    def __init__(self, output_dir: str, fps: int = 24):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.fps = fps
        self._available = _ffmpeg_available()

    @property
    def available(self) -> bool:
        return self._available

    def record_episode(self, env, model, seed: int, path: str) -> bool:
        """Run one deterministic evaluation episode and record video.

        Args:
            env: BombermanEnv with render_mode="rgb_array".
            model: SB3 policy model.
            seed: Environment seed for reproducibility.
            path: Full output path for the mp4 file.

        Returns:
            True if video was written, False if unavailable or failed.
        """
        if not self._available:
            return False

        frames: List[np.ndarray] = []
        obs, _ = env.reset(options={"phase": 1.1}, seed=seed)
        frame = env.render()
        if frame is not None:
            frames.append(frame)

        done = False
        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, _, terminated, truncated, _ = env.step(action)
            frame = env.render()
            if frame is not None:
                frames.append(frame)
            done = terminated or truncated

        if not frames:
            return False

        return write_frames(path, frames, self.fps)
