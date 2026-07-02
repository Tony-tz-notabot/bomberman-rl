"""Tests for custom Res-CNN feature extractor."""
import numpy as np
import torch
import pytest
from gym import spaces
from src.feature_extractor import ResCnnFeatureExtractor


class TestResCnnFeatureExtractor:
    def test_accepts_env_observation_shape(self):
        """Feature extractor accepts (11, 19, 9) observation and outputs (batch, 256)."""
        obs_space = spaces.Box(low=0.0, high=1.0, shape=(11, 19, 9), dtype=np.float32)
        extractor = ResCnnFeatureExtractor(obs_space, features_dim=256)
        batch = torch.zeros((4, 11, 19, 9), dtype=torch.float32)  # (B, H, W, C)
        features = extractor(batch)
        assert features.shape == (4, 256), f"Expected (4, 256), got {features.shape}"
        assert features.dtype == torch.float32

    def test_single_input_works(self):
        """Batch size 1 works (common in evaluation)."""
        obs_space = spaces.Box(low=0.0, high=1.0, shape=(11, 19, 9), dtype=np.float32)
        extractor = ResCnnFeatureExtractor(obs_space, features_dim=256)
        batch = torch.zeros((1, 11, 19, 9))
        features = extractor(batch)
        assert features.shape == (1, 256)

    def test_output_range_reasonable(self):
        """Features should be in reasonable range after ReLU (non-negative, not huge)."""
        obs_space = spaces.Box(low=0.0, high=1.0, shape=(11, 19, 9), dtype=np.float32)
        extractor = ResCnnFeatureExtractor(obs_space, features_dim=256)
        # Random observation like the real env would produce
        obs = torch.rand((2, 11, 19, 9))
        features = extractor(obs)
        assert features.min() >= -10.0  # Post-ReLU should be >= 0, but allow small neg
        assert features.max() < 500.0  # Sanity: no explosion

    def test_different_features_dim(self):
        """Custom features_dim is respected."""
        obs_space = spaces.Box(low=0.0, high=1.0, shape=(11, 19, 9), dtype=np.float32)
        extractor = ResCnnFeatureExtractor(obs_space, features_dim=128)
        batch = torch.zeros((2, 11, 19, 9))
        features = extractor(batch)
        assert features.shape == (2, 128)

    def test_residual_block_propagates_gradients(self):
        """A forward+backward pass completes without error."""
        obs_space = spaces.Box(low=0.0, high=1.0, shape=(11, 19, 9), dtype=np.float32)
        extractor = ResCnnFeatureExtractor(obs_space, features_dim=256)
        batch = torch.rand((2, 11, 19, 9), requires_grad=True)
        features = extractor(batch)
        loss = features.sum()
        loss.backward()
        # Check gradients flow to input
        assert batch.grad is not None
        assert torch.isfinite(batch.grad).all()

    def test_observation_value_range_preserved(self):
        """Feature extractor handles full [0,1] input range without NaN."""
        obs_space = spaces.Box(low=0.0, high=1.0, shape=(11, 19, 9), dtype=np.float32)
        extractor = ResCnnFeatureExtractor(obs_space, features_dim=256)
        # Edge case: all zeros
        zeros = torch.zeros((2, 11, 19, 9))
        f0 = extractor(zeros)
        assert torch.isfinite(f0).all()
        # Edge case: all ones
        ones = torch.ones((2, 11, 19, 9))
        f1 = extractor(ones)
        assert torch.isfinite(f1).all()
