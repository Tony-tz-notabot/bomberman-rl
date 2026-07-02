"""Custom Res-CNN feature extractor for Bomberman grid observations.

Architecture (from spec):
  input: 11 x 19 x 9, HWC float32
  transpose: HWC -> CHW

  Conv2d 9 -> 32, kernel=3, stride=1, padding=1
  ReLU
  Conv2d 32 -> 32, kernel=3, stride=1, padding=1
  ReLU
  ResidualBlock, channels=32
  Conv2d 32 -> 64, kernel=3, stride=1, padding=1
  ReLU
  Conv2d 64 -> 64, kernel=3, stride=1, padding=1
  ReLU
  Flatten
  Linear -> features_dim
  ReLU

Policy/value heads (handled by SB3):
  actor:  256 -> 128 -> MultiBinary(6)
  critic: 256 -> 256 -> scalar value
"""
import torch
import torch.nn as nn
from gym import spaces
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor


class ResidualBlock(nn.Module):
    """3x3 conv -> ReLU -> 3x3 conv, skip connection + ReLU."""

    def __init__(self, channels: int):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, kernel_size=3, stride=1, padding=1)
        self.relu1 = nn.ReLU()
        self.conv2 = nn.Conv2d(channels, channels, kernel_size=3, stride=1, padding=1)
        self.relu2 = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        identity = x
        out = self.conv1(x)
        out = self.relu1(out)
        out = self.conv2(out)
        out = out + identity
        out = self.relu2(out)
        return out


class ResCnnFeatureExtractor(BaseFeaturesExtractor):
    """Res-CNN feature extractor for (H, W, C) grid observations.

    Compatible with SB3's CnnPolicy. The input should be (B, H, W, C);
    this extractor transposes to (B, C, H, W) internally.
    """

    def __init__(self, observation_space: spaces.Box, features_dim: int = 256):
        super().__init__(observation_space, features_dim)
        n_input_channels = observation_space.shape[2]  # C from (H, W, C)

        self.cnn = nn.Sequential(
            nn.Conv2d(n_input_channels, 32, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.Conv2d(32, 32, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            ResidualBlock(32),
            nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.Conv2d(64, 64, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.Flatten(),
        )

        # Compute flattened dimension
        with torch.no_grad():
            sample = torch.zeros(1, n_input_channels,
                                 observation_space.shape[0],  # H
                                 observation_space.shape[1])  # W
            n_flatten = self.cnn(sample).shape[1]

        self.linear = nn.Sequential(
            nn.Linear(n_flatten, features_dim),
            nn.ReLU(),
        )
        self._features_dim = features_dim

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        """Extract features from (B, H, W, C) observations.

        Args:
            observations: (batch, height, width, channels)

        Returns:
            (batch, features_dim) feature vector
        """
        # SB3's CnnPolicy does NOT auto-transpose HWC -> CHW,
        # so we do it here: (B, H, W, C) -> (B, C, H, W)
        observations = observations.permute(0, 3, 1, 2)
        cnn_out = self.cnn(observations)
        return self.linear(cnn_out)
