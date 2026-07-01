"""Pytest fixtures for Bomberman PVP tests.

Must set SDL_VIDEODRIVER=dummy before importing pygame to avoid
opening a real display window during tests.
"""
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import sys
from pathlib import Path

# Ensure the project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
import pygame


@pytest.fixture(scope="session", autouse=True)
def _pygame_init():
    """Initialize pygame once for the whole test session."""
    pygame.init()
    yield
    pygame.quit()


@pytest.fixture(autouse=True)
def _reset_cfg():
    """Reset global config to defaults before each test.

    Many tests implicitly depend on default config values (CELL_SIZE=40,
    MAP_COLS=19, MAP_ROWS=11, etc.).  This fixture guarantees a clean slate.
    """
    from main import cfg
    cfg.reset_defaults()


@pytest.fixture
def cfg():
    """Expose the global config instance (already reset to defaults)."""
    from main import cfg
    return cfg


@pytest.fixture
def game():
    """Create a ready-to-play BombermanGame instance.

    After this fixture the game is in ``ROUND_RUNNING`` state with a
    freshly generated map and both players spawned.
    """
    from main import BombermanGame
    g = BombermanGame()
    return g
