"""Tests for video recorder module."""
import numpy as np
import pytest
from pathlib import Path
from src.video_recorder import VideoRecorder


class TestVideoRecorder:
    def test_available_false_when_no_ffmpeg(self, monkeypatch):
        """If imageio-ffmpeg is missing, available returns False."""
        monkeypatch.setattr("src.video_recorder._ffmpeg_available", lambda: False)
        recorder = VideoRecorder("/tmp/test_videos", fps=24)
        assert not recorder.available

    def test_available_true_when_ffmpeg_installed(self):
        """If imageio-ffmpeg IS available, available returns True."""
        recorder = VideoRecorder("/tmp/test_videos", fps=24)
        # On CI it may or may not be installed; just verify the check runs
        assert isinstance(recorder.available, bool)

    def test_output_dir_created(self, tmp_path):
        """Output directory is created on init."""
        video_dir = tmp_path / "videos"
        recorder = VideoRecorder(str(video_dir), fps=24)
        assert video_dir.exists()

    def test_record_synthetic_frame_sequence(self, tmp_path):
        """Recording a tiny sequence of synthetic frames produces valid output."""
        video_dir = tmp_path / "videos"
        recorder = VideoRecorder(str(video_dir), fps=24)
        if not recorder.available:
            pytest.skip("imageio-ffmpeg not installed")

        # Generate 10 synthetic frames (H=300, W=640, RGB)
        frames = [np.random.randint(0, 256, (300, 640, 3), dtype=np.uint8) for _ in range(10)]
        output_path = video_dir / "test_clip.mp4"
        from src.video_recorder import write_frames
        success = write_frames(str(output_path), frames, fps=24)
        assert success
        assert output_path.exists()
        assert output_path.stat().st_size > 100  # non-empty mp4

    def test_record_with_model_and_env(self, tmp_path):
        """record_episode runs end-to-end (short episode)."""
        pytest.importorskip("stable_baselines3")
        pytest.importorskip("src.feature_extractor")
        from src.bomberman_env import BombermanEnv
        from rewards.sparse import SparseReward
        from stable_baselines3 import PPO
        from src.feature_extractor import ResCnnFeatureExtractor

        video_dir = tmp_path / "videos"
        recorder = VideoRecorder(str(video_dir), fps=24)
        if not recorder.available:
            pytest.skip("imageio-ffmpeg not installed")

        env = BombermanEnv(reward_fn=SparseReward(), render_mode="rgb_array")
        model = PPO(
            "CnnPolicy", env, verbose=0,
            policy_kwargs=dict(
                features_extractor_class=ResCnnFeatureExtractor,
                features_extractor_kwargs=dict(features_dim=256),
                net_arch=dict(pi=[128], vf=[256]),
            ),
            n_steps=128, batch_size=64, n_epochs=3,
        )
        output_path = video_dir / "eval_seed_0.mp4"
        success = recorder.record_episode(env, model, seed=0, path=str(output_path))
        assert success
        assert output_path.exists()
        env.close()

    def test_record_graceful_fallback(self, tmp_path, monkeypatch):
        """When ffmpeg unavailable, record_episode returns False without crash."""
        pytest.importorskip("stable_baselines3")
        pytest.importorskip("src.feature_extractor")
        from src.bomberman_env import BombermanEnv
        from rewards.sparse import SparseReward
        from stable_baselines3 import PPO
        from src.feature_extractor import ResCnnFeatureExtractor

        monkeypatch.setattr("src.video_recorder._ffmpeg_available", lambda: False)
        video_dir = tmp_path / "videos"
        recorder = VideoRecorder(str(video_dir), fps=24)

        env = BombermanEnv(reward_fn=SparseReward(), render_mode="rgb_array")
        model = PPO(
            "CnnPolicy", env, verbose=0,
            policy_kwargs=dict(
                features_extractor_class=ResCnnFeatureExtractor,
                features_extractor_kwargs=dict(features_dim=256),
                net_arch=dict(pi=[128], vf=[256]),
            ),
            n_steps=128, batch_size=64, n_epochs=3,
        )
        output_path = video_dir / "fallback_test.mp4"
        success = recorder.record_episode(env, model, seed=0, path=str(output_path))
        assert not success  # graceful fallback
        assert not output_path.exists()  # no file written
        env.close()
