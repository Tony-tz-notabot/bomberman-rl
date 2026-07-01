"""Tests for game mechanics — map generation, bombs, explosions,
abilities, buffs, player movement, scoring."""

import pytest

from main import (
    GameState,
    Player,
    Bomb,
    BuffItem,
    BombermanGame,
    grid_center,
    pixel_to_grid,
    cfg as global_cfg,
)


# ====================================================================
# Helper
# ====================================================================

def set_player_at(game, player, gx, gy):
    """Teleport *player* to the centre of grid cell (gx, gy)."""
    player.pos_x, player.pos_y = grid_center(gx, gy)


# ====================================================================
# Map generation
# ====================================================================

class TestMapGeneration:
    def test_stone_at_even_even(self, game, cfg):
        for x in range(2, cfg.MAP_COLS + 1, 2):
            for y in range(2, cfg.MAP_ROWS + 1, 2):
                assert game.grid[x][y] == "stone", f"({x},{y}) should be stone"

    def test_safe_spots_are_floor(self, game):
        for sx, sy in game.safe_spots:
            assert game.grid[sx][sy] == "floor", f"Safe spot ({sx},{sy}) should be floor"

    def test_spawn_points_are_floor(self, game, cfg):
        assert game.grid[1][1] == "floor"
        assert game.grid[cfg.MAP_COLS][cfg.MAP_ROWS] == "floor"

    def test_all_cells_have_valid_type(self, game, cfg):
        for x in range(1, cfg.MAP_COLS + 1):
            for y in range(1, cfg.MAP_ROWS + 1):
                assert game.grid[x][y] in ("floor", "stone", "brick"), \
                    f"Invalid tile at ({x},{y})"

    def test_compute_safe_spots(self, cfg):
        expected = {
            (1, 2), (2, 1),
            (cfg.MAP_COLS - 1, cfg.MAP_ROWS),
            (cfg.MAP_COLS, cfg.MAP_ROWS - 1),
        }
        assert BombermanGame.compute_safe_spots(None) == expected

    def test_custom_map_size(self, cfg, game):
        cfg.MAP_COLS = 13
        cfg.MAP_ROWS = 9
        game.generate_map()
        for x in range(2, cfg.MAP_COLS + 1, 2):
            for y in range(2, cfg.MAP_ROWS + 1, 2):
                assert game.grid[x][y] == "stone"


# ====================================================================
# Player input & spawning
# ====================================================================

class TestPlayerInput:
    def test_opposing_directions_cancel(self, game):
        p = game.red_player
        p.input_up = True
        p.input_down = True
        assert game.get_input_direction(p) == (0, 0)
        p.input_up = p.input_down = False
        p.input_left = p.input_right = True
        assert game.get_input_direction(p) == (0, 0)

    @pytest.mark.parametrize("up,down,left,right,dx,dy", [
        (True, False, False, False, 0, -1),
        (False, True, False, False, 0, 1),
        (False, False, True, False, -1, 0),
        (False, False, False, True, 1, 0),
        (True, False, True, False, -1, -1),
    ])
    def test_direction(self, game, up, down, left, right, dx, dy):
        p = game.red_player
        p.input_up, p.input_down = up, down
        p.input_left, p.input_right = left, right
        assert game.get_input_direction(p) == (dx, dy)

    def test_three_dirs_is_zero(self, game):
        p = game.red_player
        p.input_up = p.input_down = p.input_left = True
        assert game.get_input_direction(p) == (0, 0)

    def test_reverse_inverts_movement(self, game):
        p = game.red_player
        p.input_left = True
        p.abilities["reverse"] = 5.0
        old_x = p.pos_x
        game.update_player_movement(0.016)
        assert p.pos_x > old_x


class TestPlayerSpawning:
    def test_players_at_spawn_points(self, cfg):
        game = BombermanGame()
        rx, ry = pixel_to_grid(game.red_player.pos_x, game.red_player.pos_y)
        assert (rx, ry) == (1, 1)
        bx, by = pixel_to_grid(game.blue_player.pos_x, game.blue_player.pos_y)
        assert (bx, by) == (cfg.MAP_COLS, cfg.MAP_ROWS)

    def test_players_alive(self, game):
        assert game.red_player.alive and game.blue_player.alive


# ====================================================================
# Bomb placement & tracking
# ====================================================================

class TestBombPlacement:
    def test_place_normal_bomb(self, game):
        set_player_at(game, game.red_player, 3, 3)
        game.place_normal_bomb(game.red_player)
        assert len(game.bombs) == 1
        b = game.bombs[0]
        assert b.owner is game.red_player
        assert b.type == "normal"
        assert b.fuse_frames == pytest.approx(48)
        assert game.red_player.bomb_placed_count == 1

    def test_place_remote_bomb(self, game):
        set_player_at(game, game.red_player, 3, 3)
        game.place_remote_bomb(game.red_player)
        assert len(game.bombs) == 1
        b = game.bombs[0]
        assert b.type == "remote"
        assert b.fuse_frames == -1
        assert b.id in game.red_player.remote_queue

    def test_cannot_place_on_bomb(self, game):
        set_player_at(game, game.red_player, 3, 3)
        game.place_normal_bomb(game.red_player)
        game.place_normal_bomb(game.red_player)
        assert len(game.bombs) == 1

    def test_bomb_max_limit(self, game):
        game.red_player.bomb_max = 2
        set_player_at(game, game.red_player, 3, 3)
        game.place_normal_bomb(game.red_player)
        game.red_player.bomb_placed_count = 1
        set_player_at(game, game.red_player, 5, 3)
        game.place_normal_bomb(game.red_player)
        assert len(game.bombs) == 2
        set_player_at(game, game.red_player, 7, 3)
        game.place_normal_bomb(game.red_player)
        assert len(game.bombs) == 2

    def test_bomb_at_cell(self, game):
        set_player_at(game, game.red_player, 5, 5)
        game.place_normal_bomb(game.red_player)
        assert game.is_bomb_at(5, 5) is True
        assert game.is_bomb_at(6, 5) is False

    def test_count_bombs_owned(self, game):
        set_player_at(game, game.red_player, 3, 3)
        set_player_at(game, game.blue_player, 5, 5)
        game.place_normal_bomb(game.red_player)
        game.place_normal_bomb(game.blue_player)
        assert game.count_bombs_owned_by(game.red_player) == 1
        assert game.count_bombs_owned_by(game.blue_player) == 1


class TestRemoteDetonation:
    def test_fifo_detonation(self, game):
        game.red_player.bomb_max = 3
        set_player_at(game, game.red_player, 3, 3)
        game.place_remote_bomb(game.red_player)
        # Move to a different cell before placing second remote
        set_player_at(game, game.red_player, 5, 3)
        game.place_remote_bomb(game.red_player)
        game.red_player.bomb_placed_count = 2
        assert len(game.red_player.remote_queue) == 2
        first_id = game.red_player.remote_queue[0]
        game.detonate_earliest_remote(game.red_player)
        assert len(game.red_player.remote_queue) == 1
        assert first_id not in game.red_player.remote_queue


# ====================================================================
# Explosion
# ====================================================================

class TestExplosionCells:
    def _clear_cells(self, game, cells):
        """Set the given list of (gx,gy) cells to floor."""
        for gx, gy in cells:
            if 1 <= gx < len(game.grid) and 1 <= gy < len(game.grid[0]):
                game.grid[gx][gy] = "floor"

    def test_cross_pattern(self, game):
        # Ensure all cells in the explosion path are floor
        self._clear_cells(game, [
            (5, 5), (5, 4), (5, 3), (5, 6), (5, 7),
            (4, 5), (3, 5), (6, 5), (7, 5),
        ])
        set_player_at(game, game.red_player, 5, 5)
        game.place_normal_bomb(game.red_player)
        b = game.bombs[0]
        b.owner.blast_range = 2
        cells = game.get_explosion_cells(b)
        assert (5, 5) in cells
        assert (5, 3) in cells and (5, 7) in cells
        assert (3, 5) in cells and (7, 5) in cells
        assert (5, 8) not in cells

    def test_stone_stops_explosion(self, game):
        self._clear_cells(game, [(2, 3), (2, 2), (2, 1)])
        game.grid[2][2] = "stone"
        set_player_at(game, game.red_player, 2, 3)
        game.place_normal_bomb(game.red_player)
        b = game.bombs[0]
        b.owner.blast_range = 5
        cells = game.get_explosion_cells(b)
        assert (2, 2) in cells
        assert (2, 1) not in cells

    def test_brick_stops_explosion(self, game):
        # Ensure (5,4) is floor so explosion reaches (5,3)
        self._clear_cells(game, [(5, 5), (5, 4), (5, 3), (5, 2)])
        game.grid[5][3] = "brick"
        set_player_at(game, game.red_player, 5, 5)
        game.place_normal_bomb(game.red_player)
        b = game.bombs[0]
        b.owner.blast_range = 5
        cells = game.get_explosion_cells(b)
        assert (5, 3) in cells
        assert (5, 2) not in cells

    def test_border_clamp(self, game):
        self._clear_cells(game, [(1, 1), (1, 2), (2, 1)])
        set_player_at(game, game.red_player, 1, 1)
        game.place_normal_bomb(game.red_player)
        b = game.bombs[0]
        b.owner.blast_range = 5
        cells = game.get_explosion_cells(b)
        assert (1, 1) in cells
        assert (0, 1) not in cells
        assert (1, 0) not in cells


class TestExplosionProcessing:
    def test_explode_and_remove(self, game):
        set_player_at(game, game.red_player, 5, 5)
        game.place_normal_bomb(game.red_player)
        game.bombs[0].exploding = True
        game.process_explosions()
        assert len(game.bombs) == 0
        assert len(game.explosion_cells) > 0

    def test_chain_reaction(self, game):
        set_player_at(game, game.red_player, 5, 5)
        game.place_normal_bomb(game.red_player)
        b2 = Bomb(game.next_bomb_id, game.red_player, "normal", 5, 6, 2.0)
        b2.pos_x, b2.pos_y = grid_center(5, 6)
        game.next_bomb_id += 1
        game.bombs.append(b2)
        game.bombs[0].exploding = True
        game.process_explosions()
        assert len(game.bombs) == 0

    def test_explosion_destroys_brick(self, game):
        game.grid[5][4] = "brick"
        set_player_at(game, game.red_player, 5, 5)
        game.place_normal_bomb(game.red_player)
        game.bombs[0].exploding = True
        game.process_explosions()
        assert game.grid[5][4] == "floor"


# ====================================================================
# Player death & shield
# ====================================================================

class TestPlayerDeath:
    def test_shield_blocks_death(self, game):
        set_player_at(game, game.red_player, 3, 3)
        game.red_player.abilities["shield"] = 10.0
        game.place_normal_bomb(game.red_player)
        game.bombs[0].exploding = True
        game.process_explosions()
        game.process_player_death()
        assert game.red_player.alive is True
        assert "shield" not in game.red_player.abilities
        assert game.red_player.invincible_timer > 0

    def test_dies_without_shield(self, game):
        set_player_at(game, game.red_player, 3, 3)
        game.place_normal_bomb(game.red_player)
        game.bombs[0].exploding = True
        game.process_explosions()
        game.process_player_death()
        assert game.red_player.alive is False
        assert game.red_player.death_timer > 0

    def test_invincible_ignores_explosion(self, game):
        set_player_at(game, game.red_player, 3, 3)
        game.red_player.invincible_timer = 1.0
        game.place_normal_bomb(game.red_player)
        game.bombs[0].exploding = True
        game.process_explosions()
        game.process_player_death()
        assert game.red_player.alive is True


# ====================================================================
# Buffs / pickups
# ====================================================================

class TestBuffs:
    def test_spawn_buff(self, game):
        game.spawn_buff_at(7, 7)
        assert len(game.buffs) == 1
        assert game.buffs[0].type in ("bomb_plus", "blast_plus", "speed_plus", "unknown")

    def test_pickup_bomb_plus(self, game, cfg):
        red = game.red_player
        red.bomb_max = cfg.INIT_BOMB_MAX
        game.buffs.append(BuffItem("bomb_plus", "", 3, 3))
        set_player_at(game, red, 3, 3)
        game.process_buff_pickups()
        assert red.bomb_max == cfg.INIT_BOMB_MAX + 1
        assert len(game.buffs) == 0

    def test_pickup_blast_plus(self, game):
        red = game.red_player
        red.blast_range = 2
        game.buffs.append(BuffItem("blast_plus", "", 3, 3))
        set_player_at(game, red, 3, 3)
        game.process_buff_pickups()
        assert red.blast_range == 3

    def test_pickup_speed_plus(self, game, cfg):
        red = game.red_player
        red.velocity = cfg.INIT_SPEED
        game.buffs.append(BuffItem("speed_plus", "", 3, 3))
        set_player_at(game, red, 3, 3)
        game.process_buff_pickups()
        assert red.velocity == pytest.approx(cfg.INIT_SPEED + cfg.SPEED_INCREMENT)

    def test_pickup_unknown_gives_ability(self, game, cfg):
        red = game.red_player
        game.buffs.append(BuffItem("unknown", "shield", 3, 3))
        set_player_at(game, red, 3, 3)
        game.process_buff_pickups()
        assert "shield" in red.abilities
        assert red.abilities["shield"] == pytest.approx(cfg.DURATION_SHIELD)

    def test_apply_buff_respects_max_caps(self, game, cfg):
        red = game.red_player
        red.bomb_max = cfg.MAX_BOMB_CAP
        red.perm_bomb_plus = cfg.MAX_BOMB_CAP - cfg.INIT_BOMB_MAX
        game.buffs.append(BuffItem("bomb_plus", "", 3, 3))
        set_player_at(game, red, 3, 3)
        game.process_buff_pickups()
        assert red.bomb_max == cfg.MAX_BOMB_CAP

    def test_protected_buff_survives_explosion(self, game):
        game.spawn_buff_at(5, 5)
        game.buffs[0].protection_timer = 1.0
        set_player_at(game, game.red_player, 5, 5)
        game.place_normal_bomb(game.red_player)
        game.bombs[0].exploding = True
        game.process_explosions()
        assert len(game.buffs) >= 1

    def test_unprotected_buff_destroyed(self, game):
        # Use a cell on the edge where explosion won't hit other cells' brick drops
        game.grid[1][1] = "floor"
        game.spawn_buff_at(1, 1)
        assert len(game.buffs) == 1, "Buff should be created"
        game.buffs[0].protection_timer = 0.0
        assert game.buffs[0].protection_timer <= 0
        set_player_at(game, game.red_player, 1, 1)
        game.place_normal_bomb(game.red_player)
        game.bombs[0].exploding = True
        game.process_explosions()
        assert len(game.buffs) == 0, f"Buff should be destroyed by explosion, got {len(game.buffs)}"


# ====================================================================
# Abilities
# ====================================================================

class TestAbilityTimers:
    def test_countdown(self, game):
        game.red_player.abilities["kick"] = 5.0
        game.update_ability_timers(1.0)
        assert game.red_player.abilities["kick"] == pytest.approx(4.0)

    def test_expiry(self, game):
        game.red_player.abilities["kick"] = 0.5
        game.update_ability_timers(1.0)
        assert "kick" not in game.red_player.abilities


class TestRemoteAbility:
    def test_remote_bomb_converts_on_expiry(self, game, cfg):
        set_player_at(game, game.red_player, 3, 3)
        game.place_remote_bomb(game.red_player)
        game.red_player.abilities["remote"] = 0.5
        game.update_ability_timers(1.0)
        assert "remote" not in game.red_player.abilities
        assert game.bombs[0].type == "converted"
        assert game.bombs[0].fuse_frames == pytest.approx(cfg.BOMB_FUSE)

    def test_remote_queue_cleared(self, game):
        set_player_at(game, game.red_player, 3, 3)
        game.place_remote_bomb(game.red_player)
        game.red_player.abilities["remote"] = 0.5
        game.update_ability_timers(1.0)
        assert game.red_player.remote_queue == []


class TestFloatAbility:
    def test_floor_no_eviction(self, game):
        set_player_at(game, game.red_player, 5, 5)
        game.red_player.abilities["float"] = 0.5
        game.update_ability_timers(1.0)
        assert game.red_player.alive is True
        cx, cy = grid_center(5, 5)
        assert game.red_player.pos_x == cx
        assert game.red_player.pos_y == cy

    def test_evict_from_brick(self, game):
        set_player_at(game, game.red_player, 5, 5)
        game.grid[5][5] = "brick"
        game.grid[5][6] = "floor"
        game.red_player.abilities["float"] = 0.5
        game.update_ability_timers(1.0)
        assert game.red_player.alive is True
        cx, cy = grid_center(5, 5)
        assert (game.red_player.pos_x, game.red_player.pos_y) != (cx, cy)

    def test_no_safe_tile_dies(self, game, cfg):
        game.grid[3][3] = "brick"
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            nx, ny = 3 + dx, 3 + dy
            if 1 <= nx <= cfg.MAP_COLS and 1 <= ny <= cfg.MAP_ROWS:
                if game.grid[nx][ny] != "stone":
                    game.grid[nx][ny] = "stone"
        set_player_at(game, game.red_player, 3, 3)
        game.red_player.abilities["float"] = 0.5
        game.update_ability_timers(1.0)
        assert game.red_player.alive is False


class TestKickAbility:
    def test_kick_sets_velocity(self, game):
        set_player_at(game, game.red_player, 5, 5)
        game.place_normal_bomb(game.red_player)
        game.kick_bomb(game.bombs[0], 1, 0)
        assert game.bombs[0].vx > 0
        assert game.bombs[0].vy == 0.0

    def test_player_touches_bomb(self, game):
        set_player_at(game, game.red_player, 5, 5)
        game.place_normal_bomb(game.red_player)
        assert game.player_touches_bomb(game.red_player, game.bombs[0]) is True

    def test_player_not_touching_distant_bomb(self, game):
        set_player_at(game, game.red_player, 3, 3)
        game.place_normal_bomb(game.red_player)
        set_player_at(game, game.red_player, 8, 8)
        assert game.player_touches_bomb(game.red_player, game.bombs[0]) is False


class TestDiarrheaAbility:
    def test_places_bomb_on_crossing_cell(self, game):
        # Ensure target cell is floor
        game.grid[6][5] = "floor"
        set_player_at(game, game.red_player, 5, 5)
        game.red_player.abilities["diarrhea"] = 5.0
        game.red_player.bomb_max = 3
        game.red_player.bomb_placed_count = 0
        set_player_at(game, game.red_player, 6, 5)
        game.check_diarrhea_on_move(game.red_player, 5, 5)
        assert game.is_bomb_at(6, 5) is True

    def test_no_bomb_if_at_capacity(self, game):
        set_player_at(game, game.red_player, 5, 5)
        game.red_player.abilities["diarrhea"] = 5.0
        game.red_player.bomb_placed_count = game.red_player.bomb_max
        set_player_at(game, game.red_player, 6, 5)
        game.check_diarrhea_on_move(game.red_player, 5, 5)
        assert game.is_bomb_at(6, 5) is False

    def test_no_bomb_if_same_cell(self, game):
        set_player_at(game, game.red_player, 5, 5)
        game.red_player.abilities["diarrhea"] = 5.0
        game.check_diarrhea_on_move(game.red_player, 5, 5)
        assert game.is_bomb_at(5, 5) is False


# ====================================================================
# Scoring & rounds
# ====================================================================

class TestScoring:
    def test_red_scores_when_blue_dies(self, game):
        game.blue_player.alive = False
        game.blue_player.death_timer = 0.0
        game.check_round_end()
        assert game.red_player.wins == 1
        assert game.state == GameState.ROUND_END_DELAY

    def test_blue_scores_when_red_dies(self, game):
        game.red_player.alive = False
        game.red_player.death_timer = 0.0
        game.check_round_end()
        assert game.blue_player.wins == 1
        assert game.state == GameState.ROUND_END_DELAY

    def test_simultaneous_death_no_score(self, game):
        game.red_player.alive = False
        game.blue_player.alive = False
        game.check_round_end()
        assert game.red_player.wins == 0
        assert game.blue_player.wins == 0

    def test_match_ends_at_win_score(self, game, cfg):
        game.blue_player.wins = cfg.WIN_SCORE - 1
        game.red_player.alive = False
        game.red_player.death_timer = 0.0
        game.check_round_end()
        assert game.blue_player.wins == cfg.WIN_SCORE
        assert game.state == GameState.MATCH_END

    def test_both_alive_no_action(self, game):
        game.check_round_end()
        assert game.state == GameState.ROUND_RUNNING

    def test_death_animating_not_scored(self, game):
        game.blue_player.alive = False
        game.blue_player.death_timer = 0.3
        game.check_round_end()
        assert game.red_player.wins == 0


class TestRoundDelay:
    def test_delay_then_reset(self, game):
        game.state = GameState.ROUND_END_DELAY
        game.round_delay_timer = 0.5
        game.update_round_delay(1.0)
        assert game.state == GameState.ROUND_RUNNING
        assert game.red_player.alive and game.blue_player.alive


class TestMatchReset:
    def test_reset_match_clears_scores(self, game):
        game.red_player.wins = 3
        game.blue_player.wins = 2
        game.reset_match()
        assert game.red_player.wins == 0
        assert game.blue_player.wins == 0

    def test_reset_round_clears_state(self, game):
        game.red_player.abilities["shield"] = 5.0
        game.blue_player.perm_bomb_plus = 3
        game.reset_round()
        assert game.red_player.abilities == {}
        assert game.blue_player.perm_bomb_plus == 0
        assert len(game.bombs) == 0
        assert len(game.buffs) == 0


# ====================================================================
# Collision
# ====================================================================

class TestPlayerCollision:
    def test_map_boundary(self, game):
        p = game.red_player
        assert game.player_collision_at(p, -1, p.pos_y, p.pos_x, p.pos_y) is True

    def test_player_blocks_player(self, game):
        set_player_at(game, game.red_player, 5, 5)
        set_player_at(game, game.blue_player, 5, 6)
        p = game.red_player
        nx, ny = grid_center(5, 6)
        assert game.player_collision_at(p, nx, ny, p.pos_x, p.pos_y) is True

    def test_bomb_blocks_entry(self, game):
        set_player_at(game, game.red_player, 5, 5)
        game.place_normal_bomb(game.red_player)
        set_player_at(game, game.red_player, 5, 6)
        p = game.red_player
        nx, ny = grid_center(5, 5)
        assert game.player_collision_at(p, nx, ny, p.pos_x, p.pos_y) is True

    def test_leaving_bomb_not_blocked(self, game):
        # Ensure both cells are floor
        game.grid[5][5] = "floor"
        game.grid[5][6] = "floor"
        set_player_at(game, game.red_player, 5, 5)
        game.place_normal_bomb(game.red_player)
        p = game.red_player
        nx, ny = grid_center(5, 6)
        assert game.player_collision_at(p, nx, ny, p.pos_x, p.pos_y) is False

    def test_floating_ignores_bomb(self, game):
        set_player_at(game, game.red_player, 5, 5)
        game.place_normal_bomb(game.red_player)
        game.red_player.abilities["float"] = 10.0
        set_player_at(game, game.red_player, 5, 6)
        p = game.red_player
        nx, ny = grid_center(5, 5)
        assert game.player_collision_at(p, nx, ny, p.pos_x, p.pos_y) is False
