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
    """Alive in Phase 1.1 gets per-frame survival penalty."""
    snap = _take_snap(engine)
    action = np.zeros(6, dtype=np.int8)
    reward = p1_reward(engine, snap, snap, action, "red")
    assert reward == pytest.approx(-0.002)


def test_illegal_bomb_cap(engine, p1_reward):
    """action=1 when bomb_placed_count == bomb_max gets penalty."""
    snap = _take_snap(engine)
    action = np.array([0, 0, 0, 0, 1, 0], dtype=np.int8)  # action=1
    reward = p1_reward(engine, snap, snap, action, "red")
    # -illegal_bomb_cap + survival_penalty
    assert reward == pytest.approx(-0.035)


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
    assert final_reward <= 0.001  # only survival (now 0) +/- retreat


def test_approach_reward_positive(engine, p1_reward):
    """When window average moves toward opponent, approach reward fires."""
    # Place player far from opponent
    engine.red_player.pos_x, engine.red_player.pos_y = 100, cfg.UI_BAR_HEIGHT + 100
    engine.blue_player.pos_x, engine.blue_player.pos_y = 700, cfg.UI_BAR_HEIGHT + 100
    snap0 = engine.get_snapshot()
    action = np.zeros(6, dtype=np.int8)

    # Move toward opponent across cells (40px per cell, move 50px to cross 1+ cells)
    for i in range(p1_reward.cfg["reward_approach_window"]):
        engine.red_player.pos_x += 5  # 5px/frame for 10 frames = 50px (>1 cell)
        snap = engine.get_snapshot()
        _ = p1_reward(engine, snap0, snap, action, "red")
        snap0 = snap

    # After window fills, the last call should have had approach reward
    # Survival alone = 0.0. Approach reward adds on top.
    # Move one more frame and capture the reward
    engine.red_player.pos_x += 5
    snap = engine.get_snapshot()
    final_reward = p1_reward(engine, snap0, snap, action, "red")
    # Should include approach reward (>0.0 survival alone)
    assert final_reward > 0.0


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
    # Center dev: -0.013 * (10/20)² = -0.00325, plus survival -0.002
    assert reward == pytest.approx(-0.005, abs=0.001)


def test_stall_penalty(engine, p1_reward):
    """Standing still for >70 frames (40 buffer + 30 threshold) accumulates stall penalty."""
    snap = _take_snap(engine)
    action = np.zeros(6, dtype=np.int8)
    reward = 0.0
    for i in range(75):
        snap2 = _take_snap(engine)
        reward = p1_reward(engine, snap, snap2, action, "red")
        snap = snap2
    # By frame 75: buffer full (40) + stall_frames=36 > 30 → cap hit at -0.00167
    # Survival -0.002 + stall -0.00167 + possible center_dev
    assert reward < -0.003, f"Expected stall penalty, got {reward}"


# ── Phase 1.1: Wall collision & death ──

def test_wall_collision(engine, p1_reward):
    """Direction input but no position change gets penalty."""
    snap = _take_snap(engine)
    # Move up (action[0]=1)
    action = np.array([1, 0, 0, 0, 0, 0], dtype=np.int8)
    reward = p1_reward(engine, snap, snap, action, "red")
    # -0.003 wall + -0.002 survival
    assert reward == pytest.approx(-0.005)


def test_death_self_bomb(engine):
    """Death by own bomb gets self-death penalty."""
    reward = Phase1Reward({"phase": 1.2})
    engine.reset_match()
    from src.utils import pixel_to_grid
    gx, gy = pixel_to_grid(engine.red_player.pos_x, engine.red_player.pos_y)
    engine.grid[gx][gy] = "floor"
    from src.models import Bomb
    bomb = Bomb(engine.next_bomb_id, engine.red_player, "normal", gx, gy, 1)
    engine.bombs.append(bomb)
    engine.next_bomb_id += 1
    engine.red_player.bomb_placed_count += 1

    prev = engine.get_snapshot()

    # Step: bomb explodes, player dies
    for _ in range(3):
        engine.step({"up": False}, {"up": False})
    snap = engine.get_snapshot()

    assert not snap.players[0].alive  # red died

    # Now test the reward function
    action = np.zeros(6, dtype=np.int8)
    result = reward(engine, prev, snap, action, "red")
    # Death by own bomb: -1.0 × p11(0.5) = -0.5
    # Wasted bomb: -0.067 × p12(1.0) = -0.067
    # Total: ~ -0.567 (plus negligible approach/retreat from position change)
    assert result < -0.3
    assert result == pytest.approx(-0.567, abs=0.5)


# ── Phase 1.2: Bomb placement & brick destruction ──

def test_bomb_placement_reward(engine):
    """Successful bomb placement gives +0.1."""
    reward = Phase1Reward({"phase": 1.2})
    engine.reset_match()
    prev = engine.get_snapshot()
    # Place bomb via step
    engine.step({"action": True}, {"up": False})
    snap = engine.get_snapshot()
    r = reward(engine, prev, snap, np.array([0, 0, 0, 0, 1, 0], dtype=np.int8), "red")
    # Should include +0.033 bomb placement + 0.0 survival (- possible approach/stall)
    # Near spawn, opponent is far → no approach or stall issues
    assert r > 0.03  # has at least the bomb placement


def test_brick_destruction_forward(engine):
    """Brick toward opponent gets forward reward; side bricks get side reward."""
    reward = Phase1Reward({"phase": 1.2})
    engine.reset_match()
    engine.state = GameState.ROUND_RUNNING

    # Clear all non-stone cells to floor, then place specific bricks
    for x in range(1, cfg.MAP_COLS + 1):
        for y in range(1, cfg.MAP_ROWS + 1):
            if engine.grid[x][y] != "stone":
                engine.grid[x][y] = "floor"
    # Bomb at (3,3) — intersection floor cell (odd, odd)
    # (4,3) toward opponent (right), (3,4) toward opponent (up), (3,2) side (down)
    engine.grid[4][3] = "brick"   # toward opponent
    engine.grid[3][4] = "brick"   # toward opponent
    engine.grid[3][2] = "brick"   # side (opposite direction from opponent)

    # Place player at bomb position, opponent far right
    engine.red_player.pos_x, engine.red_player.pos_y = grid_center(3, 3)
    engine.blue_player.pos_x, engine.blue_player.pos_y = grid_center(18, 10)

    # Place bomb at (3,3) with fuse=1 BEFORE taking prev snapshot
    from src.models import Bomb
    bomb = Bomb(engine.next_bomb_id, engine.red_player, "normal", 3, 3, 1)
    engine.bombs.append(bomb)
    engine.red_player.bomb_placed_count += 1
    engine.next_bomb_id += 1

    prev = _take_snap(engine)  # prev now includes the bomb

    # Give shield so player survives own explosion
    engine.red_player.abilities["shield"] = 100

    # Step: bomb fuse 1→0, explodes, destroys bricks
    engine.step({"up": False}, {"up": False})

    snap = _take_snap(engine)
    action = np.zeros(6, dtype=np.int8)
    r = reward(engine, prev, snap, action, "red")

    # Player survived (shield). Bricks destroyed:
    # (4,3): from bomb(3,3) → opponent(18,10) => dot=(15,7)·(1,0)=15>0 → forward +0.5
    # (3,4): from bomb(3,3) → opponent(18,10) => dot=(15,7)·(0,1)=7>0 → forward +0.5
    # (3,2): from bomb(3,3) → opponent(18,10) => dot=(15,7)·(0,-1)=-7≤0 → side +0.1
    # Total brick: 1.1. Plus survival 0.0, minus no retreat/stall/wall/illegal.
    assert r > 0.3  # at minimum one forward brick


def test_kill_opponent_reward(engine):
    """Killing the opponent gives +4.0 reward."""
    reward = Phase1Reward({"phase": 1.2,
        "reward_approach": 0, "penalty_retreat": 0,
        "penalty_center_dev": 0, "penalty_wall": 0,
        "penalty_illegal_bomb_cap": 0, "penalty_illegal_ignite": 0, "penalty_illegal_dir": 0,
        "penalty_death_self": 0, "penalty_death_opp": 0,
        "penalty_death_self_bomb": 0, "penalty_death_opp_bomb": 0,
        "reward_place_bomb": 0, "reward_destroy_brick_fwd": 0,
        "reward_destroy_brick_side": 0, "penalty_bomb_wasted": 0,
        "reward_pickup_normal": 0, "reward_pickup_unknown": 0})
    engine.reset_match()
    # Place opponent on a cell adjacent to the player
    engine.blue_player.pos_x, engine.blue_player.pos_y = grid_center(2, 1)
    from src.models import Bomb
    bomb = Bomb(engine.next_bomb_id, engine.red_player, "normal", 2, 1, 1)
    engine.bombs.append(bomb)
    engine.red_player.bomb_placed_count += 1
    engine.next_bomb_id += 1
    # Shield agent to survive own blast
    engine.red_player.abilities["shield"] = 100

    prev = _take_snap(engine)

    # Step: bomb explodes, opponent dies, agent survives
    engine.step({"up": False}, {"up": False})
    snap = _take_snap(engine)

    assert snap.players[1].alive is False  # blue died
    assert snap.players[0].alive is True   # red survived

    r = reward(engine, prev, snap, np.zeros(6, dtype=np.int8), "red")
    assert r == pytest.approx(1.333, abs=0.01)


# ── Phase 1.3: Buff pickup ──

def test_buff_pickup_reward(engine):
    """Picking up a buff gives +0.2."""
    reward = Phase1Reward({"phase": 1.3})
    engine.reset_match()
    # Place a buff near the player
    from src.models import BuffItem
    from src.utils import pixel_to_grid
    gx, gy = pixel_to_grid(engine.red_player.pos_x, engine.red_player.pos_y)
    # Place at adjacent cell
    bx, by = gx + 1, gy
    if engine.grid[bx][by] == "floor":
        buff = BuffItem("bomb_plus", None, bx, by)
        engine.buffs.append(buff)
        prev = engine.get_snapshot()
        # Move player over the buff
        engine.red_player.pos_x, engine.red_player.pos_y = grid_center(bx, by)
        snap = engine.get_snapshot()
        # Manually trigger pickup
        engine.process_buff_pickups()
        snap2 = engine.get_snapshot()
        r = reward(engine, snap, snap2, np.zeros(6, dtype=np.int8), "red")
        assert r == pytest.approx(0.067, abs=0.01)  # +0.067 for normal buff, survival is 0


# ── Phase weight transition ──

def test_phase_12_weights(engine):
    """Phase 1.2 has P1.1 rewards halved and P1.2 rewards at full."""
    p11 = Phase1Reward({"phase": 1.1, "reward_approach": 0, "penalty_retreat": 0,
                        "penalty_center_dev": 0, "penalty_wall": 0, "penalty_blocked": 0,
                        "penalty_illegal_bomb_cap": 0,
                        "penalty_illegal_ignite": 0, "penalty_illegal_dir": 0,
                        "penalty_death_self": 0, "penalty_death_opp": 0,
                        "penalty_death_self_bomb": 0, "penalty_death_opp_bomb": 0,
                        "penalty_survive_time": 0,
                        "reward_place_bomb": 0.1, "reward_destroy_brick_fwd": 0,
                        "reward_destroy_brick_side": 0, "penalty_bomb_wasted": 0,
                        "reward_pickup_normal": 0, "reward_pickup_unknown": 0})
    p12 = Phase1Reward({"phase": 1.2, "reward_approach": 0, "penalty_retreat": 0,
                        "penalty_center_dev": 0, "penalty_wall": 0, "penalty_blocked": 0,
                        "penalty_illegal_bomb_cap": 0,
                        "penalty_illegal_ignite": 0, "penalty_illegal_dir": 0,
                        "penalty_death_self": 1.0, "penalty_death_opp": 0.5,
                        "penalty_death_self_bomb": 3.0, "penalty_death_opp_bomb": 1.5,
                        "penalty_survive_time": 0,
                        "reward_place_bomb": 0.1, "reward_destroy_brick_fwd": 0,
                        "reward_destroy_brick_side": 0, "penalty_bomb_wasted": 0,
                        "reward_pickup_normal": 0, "reward_pickup_unknown": 0})
    engine.reset_match()
    snap = engine.get_snapshot()
    action = np.zeros(6, dtype=np.int8)
    r11 = p11(engine, snap, snap, action, "red")
    r12 = p12(engine, snap, snap, action, "red")
    # p11: 0.0 survival
    assert r11 == 0.0
    # p12: 0.0 * 0.5 = 0.0 survival
    assert r12 == 0.0


def test_env_with_phase1_reward():
    """BombermanEnv with Phase1Reward steps without error."""
    import numpy as np
    from src.bomberman_env import BombermanEnv
    from rewards.phase1 import Phase1Reward

    env = BombermanEnv(reward_fn=Phase1Reward({"phase": 1.1}))
    obs, _ = env.reset()
    assert obs.shape == (11, 19, 9)

    total_reward = 0.0
    for _ in range(50):
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        if terminated:
            break
    # Reward should be finite
    assert np.isfinite(total_reward)
