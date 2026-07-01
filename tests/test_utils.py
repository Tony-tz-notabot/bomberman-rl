"""Tests for Config, coordinate utilities, and data-structure constructors."""

import pytest
import math


# ====================================================================
# Config
# ====================================================================

class TestConfig:
    """Global Config singleton — default values and reset behaviour."""

    def test_default_values(self, cfg):
        assert cfg.CELL_SIZE == 40
        assert cfg.MAP_COLS == 19
        assert cfg.MAP_ROWS == 11
        assert cfg.UI_BAR_HEIGHT == 80
        assert cfg.INIT_SPEED == pytest.approx(2.5)
        assert cfg.INIT_BOMB_MAX == 1
        assert cfg.INIT_BLAST_RANGE == 2
        assert cfg.BOMB_FUSE == pytest.approx(48)
        assert cfg.WIN_SCORE == 5
        assert cfg.DURATION_KICK == pytest.approx(720)

    def test_reset_defaults_restores_defaults(self, cfg):
        cfg.CELL_SIZE = 99
        cfg.WIN_SCORE = 999
        cfg.reset_defaults()
        assert cfg.CELL_SIZE == 40
        assert cfg.WIN_SCORE == 5


# ====================================================================
# Coordinate utilities
# ====================================================================

class TestGridToPixel:
    """grid_to_pixel(gx, gy) → (left, top) pixel coordinates."""

    def test_origin(self, cfg):
        from main import grid_to_pixel
        # Cell (1,1) top-left → (0, UI_BAR_HEIGHT)
        x, y = grid_to_pixel(1, 1)
        assert x == 0
        assert y == cfg.UI_BAR_HEIGHT

    def test_last_cell(self, cfg):
        from main import grid_to_pixel
        x, y = grid_to_pixel(cfg.MAP_COLS, cfg.MAP_ROWS)
        expected_x = (cfg.MAP_COLS - 1) * cfg.CELL_SIZE
        expected_y = cfg.UI_BAR_HEIGHT + (cfg.MAP_ROWS - 1) * cfg.CELL_SIZE
        assert x == expected_x
        assert y == expected_y


class TestGridCenter:
    """grid_center(gx, gy) → pixel center of a grid cell."""

    def test_center_of_origin(self, cfg):
        from main import grid_center
        cx, cy = grid_center(1, 1)
        assert cx == cfg.CELL_SIZE // 2
        assert cy == cfg.UI_BAR_HEIGHT + cfg.CELL_SIZE // 2

    def test_center_of_last_cell(self, cfg):
        from main import grid_center
        cx, cy = grid_center(cfg.MAP_COLS, cfg.MAP_ROWS)
        expected_cx = (cfg.MAP_COLS - 1) * cfg.CELL_SIZE + cfg.CELL_SIZE // 2
        expected_cy = cfg.UI_BAR_HEIGHT + (cfg.MAP_ROWS - 1) * cfg.CELL_SIZE + cfg.CELL_SIZE // 2
        assert cx == expected_cx
        assert cy == expected_cy


class TestPixelToGrid:
    """pixel_to_grid(px, py) → (gx, gy)  (1-indexed, clamped).

    Note: uses ``round()`` — at exact .5 boundaries Python 3's banker's
    rounding may lean toward the even integer.  This is existing behaviour;
    tests document it rather than asserting "intuitive" rounding.
    """

    def test_from_center_roundtrips(self, cfg):
        """The center of every grid cell round-trips correctly."""
        from main import grid_center, pixel_to_grid
        for gx in (1, 2, cfg.MAP_COLS // 2, cfg.MAP_COLS):
            for gy in (1, 2, cfg.MAP_ROWS // 2, cfg.MAP_ROWS):
                px, py = grid_center(gx, gy)
                rx, ry = pixel_to_grid(px, py)
                assert (rx, ry) == (gx, gy), f"Failed at cell ({gx}, {gy})"

    def test_px_outside_map_clamps(self, cfg):
        """Coordinates outside the grid are clamped to [1, COLS/ROWS]."""
        from main import pixel_to_grid
        # Far below/left
        gx, gy = pixel_to_grid(-999, -999)
        assert gx == 1
        assert gy == 1
        # Far beyond top-right
        gx, gy = pixel_to_grid(99999, 99999)
        assert gx == cfg.MAP_COLS
        assert gy == cfg.MAP_ROWS

    def test_top_left_corner_of_cell_2_2(self, cfg):
        """The pixel coordinate that is the top-left corner of cell (2,2)
        should, via grid_to_pixel, give (2,2) — or very close."""
        from main import grid_to_pixel, pixel_to_grid
        # Top-left pixel of cell (2,2)
        px, py = grid_to_pixel(2, 2)
        gx, gy = pixel_to_grid(px, py)
        # Note: pixel_to_grid uses round(), and exact midpoints may round
        # either way.  The result should be within 1 cell of (2,2).
        assert 1 <= gx <= 2
        assert 1 <= gy <= 2


class TestWindowHelpers:
    def test_dimensions(self, cfg):
        from main import get_map_width, get_map_height, get_window_width, get_window_height
        assert get_map_width() == cfg.MAP_COLS * cfg.CELL_SIZE
        assert get_map_height() == cfg.MAP_ROWS * cfg.CELL_SIZE
        assert get_window_width() == get_map_width()
        assert get_window_height() == get_map_height() + cfg.UI_BAR_HEIGHT


# ====================================================================
# Clamp & Sign
# ====================================================================

class TestClamp:
    def test_within_range(self):
        from main import clamp
        assert clamp(5, 1, 10) == 5

    def test_below_min(self):
        from main import clamp
        assert clamp(0, 1, 10) == 1

    def test_above_max(self):
        from main import clamp
        assert clamp(15, 1, 10) == 10


class TestSign:
    def test_positive(self):
        from main import sign
        assert sign(42) == 1.0
        assert sign(0.1) == 1.0

    def test_negative(self):
        from main import sign
        assert sign(-3) == -1.0

    def test_zero(self):
        from main import sign
        assert sign(0) == 0.0


# ====================================================================
# Data structures
# ====================================================================

class TestPlayer:
    """Player constructor, reset(), hitbox()"""

    def test_constructor(self, cfg):
        from models import Player
        from constants import COLOR_RED
        p = Player("red", COLOR_RED)
        assert p.id == "red"
        assert p.color == COLOR_RED
        assert p.alive is True
        assert p.wins == 0
        assert p.abilities == {}
        assert p.remote_queue == []

    def test_reset_restores_defaults(self, cfg):
        from models import Player
        from constants import COLOR_RED
        from utils import grid_center
        p = Player("red", COLOR_RED)
        p.wins = 3
        p.abilities["shield"] = 10.0
        p.bomb_max = 99

        p.reset(1, 1)
        assert p.wins == 3          # wins persist across rounds
        assert p.abilities == {}    # abilities cleared
        assert p.bomb_max == cfg.INIT_BOMB_MAX
        assert p.velocity == cfg.INIT_SPEED
        assert p.pos_x == grid_center(1, 1)[0]
        assert p.pos_y == grid_center(1, 1)[1]

    def test_hitbox_dimensions(self, cfg):
        from models import Player
        from constants import COLOR_RED
        p = Player("red", COLOR_RED)
        p.pos_x = 100.0
        p.pos_y = 200.0
        half = (cfg.PLAYER_HITBOX_SIZE * cfg.CELL_SIZE) / 2
        L, R, T, B = p.hitbox()
        assert L == pytest.approx(100.0 - half)
        assert R == pytest.approx(100.0 + half)
        assert T == pytest.approx(200.0 - half)
        assert B == pytest.approx(200.0 + half)


class TestBomb:
    def test_construction(self, cfg):
        from models import Bomb
        b = Bomb(0, "red", "normal", 3, 5, 48)  # 48 frames = 2s at 24fps
        assert b.id == 0
        assert b.owner == "red"
        assert b.type == "normal"
        assert b.fuse_frames == 48
        assert b.vx == 0.0
        assert b.vy == 0.0
        assert b.exploding is False
        assert b.exploded is False

    def test_grid_pos_roundtrip(self, cfg):
        from models import Bomb
        b = Bomb(1, "red", "remote", 7, 4, -1)
        gx, gy = b.grid_pos()
        assert gx == 7
        assert gy == 4

    def test_remote_bomb_has_minus_one_fuse(self, cfg):
        from models import Bomb
        b = Bomb(2, "blue", "remote", 1, 1, -1)
        assert b.fuse_frames == -1


class TestBuffItem:
    def test_construction(self, cfg):
        from models import BuffItem
        b = BuffItem("bomb_plus", "", 5, 3)
        assert b.type == "bomb_plus"
        assert b.unknown_subtype == ""
        assert b.protection_timer == cfg.BUFF_PROTECTION_TIME

    def test_grid_pos(self, cfg):
        from models import BuffItem
        b = BuffItem("unknown", "kick", 10, 7)
        gx, gy = b.grid_pos()
        assert gx == 10
        assert gy == 7

    def test_protection_timer_decays(self, cfg):
        from models import BuffItem
        b = BuffItem("speed_plus", "", 1, 1)
        b.protection_timer -= 0.1
        assert b.protection_timer == pytest.approx(7 - 0.1)  # 7 frames ≈ 0.3s


class TestGameState:
    def test_enum_values(self):
        from main import GameState
        assert GameState.MENU == 0
        assert GameState.ROUND_RUNNING == 1
        assert GameState.ROUND_END_DELAY == 2
        assert GameState.MATCH_END == 3
        assert GameState.SETTINGS == 4
        assert GameState.SETTINGS_PAUSED == 5


# ====================================================================
# Collision helper
# ====================================================================

class TestBoxOverlap:
    def test_overlapping(self):
        from utils import box_overlap
        assert box_overlap(0, 10, 0, 10, 5, 15, 5, 15) is True

    def test_non_overlapping_x(self):
        from utils import box_overlap
        assert box_overlap(0, 10, 0, 10, 20, 30, 0, 10) is False

    def test_non_overlapping_y(self):
        from utils import box_overlap
        assert box_overlap(0, 10, 0, 10, 0, 10, 20, 30) is False

    def test_touching_edge_counts_as_overlap(self):
        from utils import box_overlap
        # Current code: R1 == L2 → not (R1 < L2) → True (counts as overlap)
        assert box_overlap(0, 10, 0, 10, 10, 20, 0, 10) is True

    def test_containment(self):
        from utils import box_overlap
        assert box_overlap(0, 100, 0, 100, 25, 75, 25, 75) is True
