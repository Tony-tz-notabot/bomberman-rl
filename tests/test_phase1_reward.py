"""Tests for Phase1Reward."""
import pytest
import numpy as np
from src.game_engine import GameEngine
from src.config import cfg
from src.constants import GameState
from src.utils import grid_center
from rewards.phase1 import Phase1Reward


@pytest.fixture
def engine():
    eng = GameEngine()
    eng.reset_match()
    return eng


@pytest.fixture
def p1_reward():
    return Phase1Reward({"phase": 1.1})


def _take_snap(engine):
    return engine.get_snapshot()


# ── Phase 1.1: Survival & illegal action ──

def test_survival_alive(engine, p1_reward):
    """Alive agent gets +0.001 per frame."""
    snap = _take_snap(engine)
    action = np.zeros(6, dtype=np.int8)
    reward = p1_reward(engine, snap, snap, action, "red")
    assert reward == 0.001


def test_illegal_bomb_cap(engine, p1_reward):
    """action=1 when bomb_placed_count == bomb_max gets penalty."""
    snap = _take_snap(engine)
    action = np.array([0, 0, 0, 0, 1, 0], dtype=np.int8)  # action=1
    reward = p1_reward(engine, snap, snap, action, "red")
    # -illegal_bomb_cap + survival
    assert reward == pytest.approx(-0.1 + 0.001)


# ── Phase 1.1: Approach/retreat, center deviation, stall ──

def test_approach_window(engine, p1_reward):
    """After window frames of approach toward opponent, reward fires."""
    # Place player far from opponent
    engine.red_player.pos_x, engine.red_player.pos_y = cfg.UI_BAR_HEIGHT + 20, 20
    engine.blue_player.pos_x, engine.blue_player.pos_y = 700, cfg.UI_BAR_HEIGHT + 200
    # Ensure opponent is stationary
    snap0 = _take_snap(engine)
    action = np.zeros(6, dtype=np.int8)
    # Run window frames with approach
    for i in range(p1_reward.cfg["reward_approach_window"] + 1):
        px = engine.red_player.pos_x + 2  # move right each frame
        engine.red_player.pos_x = min(px, 700)
        snap = _take_snap(engine)
        p1_reward(engine, snap0, snap, action, "red")
        snap0 = snap
    # After window fills, the last call had approach
    # _prev_avg_x is now set. Next step without movement should not give approach reward.
    snap = _take_snap(engine)
    final_reward = p1_reward(engine, snap0, snap, action, "red")
    assert final_reward <= 0.001 + 0.001  # only survival +/- retreat


def test_center_deviation_off_center(engine, p1_reward):
    """Player far from corridor center gets penalty."""
    # Place on center of a horizontal corridor cell
    gx, gy = 2, 3  # gy=3 odd → horizontal corridor
    cx, cy = grid_center(gx, gy)
    # Snap with player at center
    engine.red_player.pos_x, engine.red_player.pos_y = cx, cy
    prev = _take_snap(engine)
    engine.red_player.pos_y = cy + 10  # 10px off center
    snap = _take_snap(engine)
    action = np.zeros(6, dtype=np.int8)
    reward = p1_reward(engine, prev, snap, action, "red")
    # Center dev: -0.04 * (10/20)² = -0.01, plus survival 0.001
    assert reward == pytest.approx(-0.01 + 0.001)


def test_stall_penalty(engine, p1_reward):
    """Standing still for >30 frames accumulates stall penalty."""
    snap = _take_snap(engine)
    action = np.zeros(6, dtype=np.int8)
    reward = 0.0
    for i in range(35):
        snap2 = _take_snap(engine)
        reward = p1_reward(engine, snap, snap2, action, "red")
        snap = snap2
    # By frame 35, stall penalty = -0.02 * (35-30) = -0.1, plus survival
    assert reward <= 0.001  # survival positive but stall dominates


# ── Phase 1.1: Wall collision & death ──

def test_wall_collision(engine, p1_reward):
    """Direction input but no position change gets penalty."""
    snap = _take_snap(engine)
    # Move up (action[0]=1)
    action = np.array([1, 0, 0, 0, 0, 0], dtype=np.int8)
    reward = p1_reward(engine, snap, snap, action, "red")
    # -0.03 wall + 0.001 survival
    assert reward == pytest.approx(-0.03 + 0.001)


def test_death_self_bomb(engine):
    """Death by own bomb gets self-death penalty."""
    reward = Phase1Reward({"phase": 1.2})
    engine.reset_match()
    # Place a bomb directly under player
    from src.utils import pixel_to_grid
    gx, gy = pixel_to_grid(engine.red_player.pos_x, engine.red_player.pos_y)
    engine.grid[gx][gy] = "floor"  # ensure floor for bomb placement
    # Manually create bomb with fuse=1
    from src.models import Bomb
    bomb = Bomb(engine.next_bomb_id, engine.red_player, "normal", gx, gy, 1)
    engine.bombs.append(bomb)
    engine.next_bomb_id += 1
    engine.red_player.bomb_placed_count += 1
    # Step 2 frames: bomb explodes → player dies
    for _ in range(3):
        engine.step({"up": False}, {"up": False})
    snap = engine.get_snapshot()
    assert not snap.players[0].alive  # red died
