"""Tests for map_generator module."""
import random
import numpy as np
import pytest
from src.map_generator import connected_floor_cells, _safe_spots_for, generate_map
from src.config import cfg


class TestConnectedFloorCells:
    def test_connected_map_high_connectivity(self):
        rng = random.Random(0)
        result = generate_map(1.1, rng)
        grid = result["grid"]
        reachable = connected_floor_cells(grid, 1, 1)
        floor_count = sum(1 for x in range(1, cfg.MAP_COLS + 1)
                          for y in range(1, cfg.MAP_ROWS + 1)
                          if grid[x][y] == "floor")
        assert len(reachable) >= floor_count * 0.9

    def test_brick_wall_disconnects(self):
        """Brick wall fully blocking a corridor: far side is disconnected."""
        # Build a grid with a specific brick wall
        grid = [["floor" for _ in range(cfg.MAP_ROWS + 1)] for _ in range(cfg.MAP_COLS + 1)]
        for x in range(1, cfg.MAP_COLS + 1):
            for y in range(1, cfg.MAP_ROWS + 1):
                if x % 2 == 0 and y % 2 == 0:
                    grid[x][y] = "stone"
                elif (x % 2 == 0) != (y % 2 == 0):
                    grid[x][y] = "brick"  # all corridors blocked
                else:
                    grid[x][y] = "floor"
        # Red at (1,1): connected cells are (1,1), (1,3), (1,5), ..., (3,1), (5,1) ...
        # Keep red's adjacent corridors open, then block the entire y=2 row
        grid[1][2] = "floor"  # keep red's neighbor open
        grid[2][1] = "floor"  # keep red's other neighbor open
        reachable = connected_floor_cells(grid, 1, 1)
        assert (1, 3) in reachable  # vertical corridor still open (1,2) -> (1,3)
        # Block the horizontal corridor at row 2 entirely
        for x in range(3, cfg.MAP_COLS, 2):
            grid[x][2] = "brick"
        reachable2 = connected_floor_cells(grid, 1, 1)
        for x in range(3, cfg.MAP_COLS, 2):
            assert (x, 2) not in reachable2, f"Cell ({x},2) should be brick"

    def test_start_cell_always_in_component(self):
        """The starting cell is always in its own BFS result."""
        rng = random.Random(42)
        result = generate_map(1.2, rng)
        grid = result["grid"]
        reachable = connected_floor_cells(grid, 1, 1)
        assert (1, 1) in reachable


class TestSafeSpots:
    def test_red_safe_spots_correct(self):
        """Red at (1,1): safe spots are (2,1) and (1,2)."""
        spots = _safe_spots_for((1, 1), None)
        assert (2, 1) in spots
        assert (1, 2) in spots
        assert len(spots) == 2

    def test_blue_adds_adjacent_corridor_cells(self):
        """Blue spawn adds its adjacent corridor cells to safe_spots."""
        blue = (17, 9)  # odd, odd — typical floor cell
        spots = _safe_spots_for((1, 1), blue)
        assert (2, 1) in spots  # red
        assert (1, 2) in spots
        # Blue's adjacent corridor cells (one even, one odd)
        assert (16, 9) in spots or (18, 9) in spots  # bx+/-1, by
        assert (17, 8) in spots or (17, 10) in spots  # bx, by+/-1


class TestStandardMap:
    def test_standard_map_structure(self):
        """Phase 1.2 map: has stone pillars, bricks, floor, correct dimensions."""
        rng = random.Random(123)
        result = generate_map(1.2, rng)
        grid = result["grid"]
        assert result["red_spawn"] == (1, 1)
        assert isinstance(result["blue_spawn"], tuple)
        assert len(result["blue_spawn"]) == 2
        assert isinstance(result["safe_spots"], set)
        # Dimensions
        assert len(grid) == cfg.MAP_COLS + 1
        assert len(grid[1]) == cfg.MAP_ROWS + 1
        # Stone pillars at (even, even)
        assert grid[2][2] == "stone"
        assert grid[4][6] == "stone"
        # Floor at (odd, odd)
        assert grid[1][1] == "floor"
        # Has some bricks
        brick_count = sum(1 for x in range(1, cfg.MAP_COLS + 1)
                          for y in range(1, cfg.MAP_ROWS + 1)
                          if grid[x][y] == "brick")
        assert brick_count > 0

    def test_standard_map_blue_on_floor(self):
        """Blue spawn is always on a floor cell."""
        for seed in range(20):
            rng = random.Random(seed)
            result = generate_map(1.2, rng)
            bx, by = result["blue_spawn"]
            assert result["grid"][bx][by] == "floor", f"Blue not on floor seed={seed}"

    def test_standard_map_no_guaranteed_connectivity(self):
        rng = random.Random(456)
        result = generate_map(1.2, rng)
        assert result["blue_spawn"] is not None
        bx, by = result["blue_spawn"]
        assert result["grid"][bx][by] == "floor"

    def test_sample_blue_spawn_fallback(self):
        """Fallback: when no floor candidates exist, picks non-stone cell."""
        from src.map_generator import _sample_blue_spawn
        rng = random.Random(1)
        grid = [["stone" for _ in range(cfg.MAP_ROWS + 1)] for _ in range(cfg.MAP_COLS + 1)]
        grid[1][1] = "floor"  # red spawn only
        grid[2][1] = "brick"  # one non-stone cell for fallback
        result = _sample_blue_spawn(grid, (1, 1), 1.2, rng)
        assert result is not None
        bx, by = result
        assert grid[bx][by] != "stone"


class TestPhase1ConnectedMap:
    def test_connected_map_red_blue_reachable(self):
        """Phase 1.1: blue spawn is reachable from red via floor cells."""
        for seed in range(20):
            rng = random.Random(seed)
            result = generate_map(1.1, rng)
            rx, ry = result["red_spawn"]
            bx, by = result["blue_spawn"]
            reachable = connected_floor_cells(result["grid"], rx, ry)
            assert (bx, by) in reachable, \
                f"Blue {bx,by} unreachable from red seed={seed}"

    def test_connected_map_has_bricks(self):
        """Phase 1.1 has bricks (just fewer than standard)."""
        rng = random.Random(789)
        result = generate_map(1.1, rng)
        brick_count = sum(1 for x in range(1, cfg.MAP_COLS + 1)
                          for y in range(1, cfg.MAP_ROWS + 1)
                          if result["grid"][x][y] == "brick")
        assert brick_count > 0, "Phase 1.1 should still have some bricks"

    def test_connected_map_red_safe_spots_preserved(self):
        """Red's adjacent corridor cells are always floor in Phase 1.1."""
        for seed in range(10):
            rng = random.Random(seed)
            result = generate_map(1.1, rng)
            grid = result["grid"]
            assert grid[1][2] == "floor", f"Red safe spot (1,2) is brick seed={seed}"
            assert grid[2][1] == "floor", f"Red safe spot (2,1) is brick seed={seed}"


class TestEnvIntegration:
    def test_reset_with_phase_options(self):
        """Reset with phase=1.1 creates a valid environment."""
        from src.bomberman_env import BombermanEnv
        env = BombermanEnv()
        obs, info = env.reset(options={"phase": 1.1})
        assert obs.shape == (cfg.MAP_ROWS, cfg.MAP_COLS, 9)
        assert obs.dtype == np.float32

    def test_reset_phase_1_1_blue_reachable(self):
        """After phase=1.1 reset, blue is reachable from red."""
        from src.bomberman_env import BombermanEnv
        from src.map_generator import connected_floor_cells
        env = BombermanEnv()
        for seed in range(5):
            env.reset(seed=seed, options={"phase": 1.1})
            snap = env.engine.get_snapshot()
            red = snap.players[0]
            blue = snap.players[1]
            rx, ry = red.grid_x, red.grid_y
            bx, by = blue.grid_x, blue.grid_y
            grid = [[None for _ in range(cfg.MAP_ROWS + 1)]
                    for _ in range(cfg.MAP_COLS + 1)]
            for x in range(1, cfg.MAP_COLS + 1):
                for y in range(1, cfg.MAP_ROWS + 1):
                    val = env.engine.grid[x][y]
                    if val == "stone":
                        grid[x][y] = "stone"
                    elif val == "brick":
                        grid[x][y] = "brick"
                    else:
                        grid[x][y] = "floor"
            reachable = connected_floor_cells(grid, rx, ry)
            assert (bx, by) in reachable, \
                f"seed={seed}: blue {bx,by} not reachable from red {rx,ry}"

    def test_reset_no_options_fallback(self):
        """Reset without phase uses default engine behavior (fixed blue spawn)."""
        from src.bomberman_env import BombermanEnv
        env = BombermanEnv()
        obs, info = env.reset()
        snap = env.engine.get_snapshot()
        blue = snap.players[1]
        assert blue.grid_x == cfg.MAP_COLS
        assert blue.grid_y == cfg.MAP_ROWS

    def test_reset_with_grid_options_still_works(self):
        """Reset with options={'grid': ...} still works as before."""
        from src.bomberman_env import BombermanEnv
        env = BombermanEnv()
        matrix = np.zeros((cfg.MAP_ROWS, cfg.MAP_COLS), dtype=np.int32)
        matrix[0, 0] = 3
        matrix[cfg.MAP_ROWS - 1, cfg.MAP_COLS - 1] = 4
        obs, info = env.reset(options={"grid": matrix.tolist()})
        snap = env.engine.get_snapshot()
        assert snap.players[0].grid_x == 1
        assert snap.players[0].grid_y == 1
        assert snap.players[1].grid_x == cfg.MAP_COLS
        assert snap.players[1].grid_y == cfg.MAP_ROWS

    def test_reset_phase_1_2_blue_random_position(self):
        """Phase 1.2: blue spawns at different positions across seeds."""
        from src.bomberman_env import BombermanEnv
        env = BombermanEnv()
        positions = set()
        for seed in range(5):
            env.reset(seed=seed, options={"phase": 1.2})
            snap = env.engine.get_snapshot()
            blue = snap.players[1]
            positions.add((blue.grid_x, blue.grid_y))
        assert len(positions) > 1, "Blue should vary across seeds"
