# game_engine.py
import random
import math
from config import cfg
from constants import GameState, COLOR_RED, COLOR_BLUE, \
    CELL_EMPTY, CELL_STONE, CELL_BRICK, CELL_BUFF, CELL_BOMB, CELL_EXPLOSION
from utils import pixel_to_grid, grid_center, sign, \
    box_overlap, get_map_width, get_window_height
from models import Player, Bomb, BuffItem, \
    GameSnapshot, PlayerSnapshot, BombSnapshot, BuffItemSnapshot


class GameEngine:
    def __init__(self):
        self.state = GameState.MENU
        self.grid = [[None for _ in range(cfg.MAP_ROWS + 1)] for _ in range(cfg.MAP_COLS + 1)]
        self.red_player = Player("red", COLOR_RED)
        self.blue_player = Player("blue", COLOR_BLUE)
        self.bombs = []
        self.buffs = []
        self.explosion_cells = set()
        self.round_frame = 0
        self.refresh_timer = cfg.REFRESH_INTERVAL
        self.round_delay_timer = 0
        self.current_winner = ""
        self.next_bomb_id = 0
        self.safe_spots = self.compute_safe_spots()
        self.reset_match()

    def compute_safe_spots(self):
        return {(1, 2), (2, 1), (cfg.MAP_COLS - 1, cfg.MAP_ROWS), (cfg.MAP_COLS, cfg.MAP_ROWS - 1)}

    def reset_match(self):
        self.red_player.wins = 0
        self.blue_player.wins = 0
        self.reset_round()

    def reset_round(self):
        self.generate_map()
        self.red_player.reset(1, 1)
        self.blue_player.reset(cfg.MAP_COLS, cfg.MAP_ROWS)
        self.bombs.clear()
        self.buffs.clear()
        self.explosion_cells.clear()
        self.round_frame = 0
        self.refresh_timer = cfg.REFRESH_INTERVAL
        self.round_delay_timer = 0
        self.current_winner = ""
        self.next_bomb_id = 0
        self.state = GameState.ROUND_RUNNING

    def generate_map(self):
        for x in range(1, cfg.MAP_COLS + 1):
            for y in range(1, cfg.MAP_ROWS + 1):
                if x % 2 == 0 and y % 2 == 0:
                    self.grid[x][y] = "stone"
                elif (x % 2 == 0) != (y % 2 == 0):
                    if (x, y) in self.safe_spots:
                        self.grid[x][y] = "floor"
                    else:
                        self.grid[x][y] = "brick" if random.random() < cfg.BRICK_GEN_PROB else "floor"
                else:
                    self.grid[x][y] = "floor"

    # ── Public API ──

    def step(self, p1_actions, p2_actions):
        """Advance one frame. dtau = 1."""
        self.apply_actions(p1_actions, p2_actions)

        if self.state == GameState.ROUND_RUNNING:
            self.update_round()
        elif self.state == GameState.ROUND_END_DELAY:
            self.update_round_delay()

        return self.get_snapshot()

    def apply_actions(self, p1, p2):
        """Copy action dict into Player input fields."""
        for p, actions in [(self.red_player, p1), (self.blue_player, p2)]:
            p.input_up = actions.get("up", False)
            p.input_down = actions.get("down", False)
            p.input_left = actions.get("left", False)
            p.input_right = actions.get("right", False)
            # action and ignite are per-step, not held state
            # Build them here; player uses them same frame
            p.input_action = actions.get("action", False)
            p.input_ignite = actions.get("ignite", False)

    # ── Round update ──

    def update_round(self):
        """One frame of game logic — no dt param."""
        self.round_frame += 1
        self.update_buff_refresh()
        self.update_buff_protection()
        self.update_player_movement()
        # Diarrhea bomb placement is handled inside movement
        self.update_bomb_timers_and_movement()
        self.process_explosions()
        self.process_player_death()
        self.process_buff_pickups()
        self.update_ability_timers()
        self.check_round_end()

    def update_round_delay(self):
        self.round_delay_timer -= 1
        if self.round_delay_timer <= 0:
            self.reset_round()

    # ── Player movement ──

    def update_player_movement(self):
        for p in (self.red_player, self.blue_player):
            if not p.alive:
                continue
            old_gx, old_gy = pixel_to_grid(p.pos_x, p.pos_y)
            dir_x, dir_y = self._get_input_direction(p)
            if "reverse" in p.abilities:
                dir_x = -dir_x
                dir_y = -dir_y
            speed_val = p.velocity
            if dir_x != 0 and dir_y != 0:
                speed_val *= 0.70710678
            desired_vx = dir_x * speed_val * cfg.CELL_SIZE
            desired_vy = dir_y * speed_val * cfg.CELL_SIZE
            self._move_player(p, desired_vx, desired_vy)

            if "kick" in p.abilities and (dir_x != 0 or dir_y != 0):
                self._try_kick_bomb(p, dir_x, dir_y)

            # Action (place bomb)
            if p.input_action:
                if "remote" in p.abilities:
                    self._place_remote_bomb(p)
                else:
                    self._place_normal_bomb(p)

            if p.input_ignite:
                if "remote" in p.abilities and p.remote_queue:
                    self._detonate_earliest_remote(p)

            # Diarrhea
            self._check_diarrhea_on_move(p, old_gx, old_gy)

    def _get_input_direction(self, p):
        dx, dy = 0, 0
        if p.input_up: dy -= 1
        if p.input_down: dy += 1
        if p.input_left: dx -= 1
        if p.input_right: dx += 1
        count = (p.input_up + p.input_down + p.input_left + p.input_right)
        if count > 2:
            p.dir_x, p.dir_y = 0, 0
            return 0, 0
        p.dir_x, p.dir_y = dx, dy
        return dx, dy

    def _move_player(self, p, vx_ps, vy_ps):
        """vx_ps/vy_ps are in pixels/sec, multiply by DT_OVER_DTAU."""
        old_x, old_y = p.pos_x, p.pos_y
        dt_factor = cfg.DT_OVER_DTAU  # = 1/FPS
        new_x = old_x + vx_ps * dt_factor
        if not self._player_collision_at(p, new_x, old_y, old_x, old_y):
            p.pos_x = new_x
        new_y = old_y + vy_ps * dt_factor
        if not self._player_collision_at(p, p.pos_x, new_y, old_x, old_y):
            p.pos_y = new_y

    def _player_collision_at(self, p, new_x, new_y, old_x, old_y):
        """Same logic as original — pure pixel coords, no dt."""
        half = (cfg.PLAYER_HITBOX_SIZE * cfg.CELL_SIZE) / 2
        L, R = new_x - half, new_x + half
        T, B = new_y - half, new_y + half

        if L < 0 or R > get_map_width() or T < cfg.UI_BAR_HEIGHT or B > get_window_height():
            return True

        if "float" in p.abilities:
            for cell in self._cells_overlapping(L, R, T, B):
                if self.grid[cell[0]][cell[1]] == "stone":
                    return True
        else:
            for cell in self._cells_overlapping(L, R, T, B):
                if self.grid[cell[0]][cell[1]] in ("stone", "brick"):
                    return True

        for other in (self.red_player, self.blue_player):
            if other is p or not other.alive:
                continue
            if box_overlap(L, R, T, B, *other.hitbox()):
                return True

        if "float" not in p.abilities:
            for bomb in self.bombs:
                bgx, bgy = bomb.grid_pos()
                new_gx, new_gy = pixel_to_grid(new_x, new_y)
                old_gx, old_gy = pixel_to_grid(old_x, old_y)
                if (new_gx, new_gy) == (bgx, bgy) and (old_gx, old_gy) != (bgx, bgy):
                    return True
        return False

    def _cells_overlapping(self, L, R, T, B):
        cells = set()
        min_gx = max(1, int(L // cfg.CELL_SIZE) + 1)
        max_gx = min(cfg.MAP_COLS, int((R - 1) // cfg.CELL_SIZE) + 1)
        min_gy = max(1, int((T - cfg.UI_BAR_HEIGHT) // cfg.CELL_SIZE) + 1)
        max_gy = min(cfg.MAP_ROWS, int((B - 1 - cfg.UI_BAR_HEIGHT) // cfg.CELL_SIZE) + 1)
        for gx in range(min_gx, max_gx + 1):
            for gy in range(min_gy, max_gy + 1):
                cells.add((gx, gy))
        return cells

    # ── Bomb placement and kick ──

    def _place_normal_bomb(self, p):
        gx, gy = pixel_to_grid(p.pos_x, p.pos_y)
        if self.grid[gx][gy] != "floor":
            return
        if p.bomb_placed_count >= p.bomb_max:
            return
        # Prevent place on existing bomb
        for b in self.bombs:
            if b.grid_pos() == (gx, gy):
                return
        self._create_bomb(p, "normal", gx, gy, cfg.BOMB_FUSE)

    def _place_remote_bomb(self, p):
        gx, gy = pixel_to_grid(p.pos_x, p.pos_y)
        if self.grid[gx][gy] != "floor":
            return
        if p.bomb_placed_count >= p.bomb_max:
            return
        for b in self.bombs:
            if b.grid_pos() == (gx, gy):
                return
        self._create_bomb(p, "remote", gx, gy, -1)

    def _create_bomb(self, owner, bomb_type, gx, gy, fuse):
        bomb = Bomb(self.next_bomb_id, owner, bomb_type, gx, gy, fuse)
        self.bombs.append(bomb)
        owner.bomb_placed_count += 1
        self.next_bomb_id += 1
        if bomb_type == "remote":
            owner.remote_queue.append(bomb.id)

    def _detonate_earliest_remote(self, p):
        target_id = p.remote_queue.pop(0)
        for bomb in self.bombs:
            if bomb.id == target_id:
                bomb.exploding = True
                break

    def _try_kick_bomb(self, p, dir_x, dir_y):
        for bomb in self.bombs:
            if self._player_touches_bomb(p, bomb):
                self._kick_bomb(bomb, dir_x, dir_y)
                break

    def _player_touches_bomb(self, p, bomb):
        phalf = (cfg.PLAYER_HITBOX_SIZE * cfg.CELL_SIZE) / 2
        br = cfg.CELL_SIZE * 0.35
        return math.hypot(p.pos_x - bomb.pos_x, p.pos_y - bomb.pos_y) < (phalf + br)

    def _kick_bomb(self, bomb, dx, dy):
        bomb.vx = dx * cfg.KICK_INIT_VEL * cfg.CELL_SIZE
        bomb.vy = dy * cfg.KICK_INIT_VEL * cfg.CELL_SIZE

    def count_bombs_owned_by(self, owner):
        return sum(1 for b in self.bombs if b.owner is owner)

    # ── Bomb timers and movement ──

    def update_bomb_timers_and_movement(self):
        for bomb in list(self.bombs):
            if bomb.vx != 0 or bomb.vy != 0:
                self._move_bomb(bomb)
            if bomb.type in ("normal", "converted"):
                if bomb.fuse_frames > 0:
                    bomb.fuse_frames -= 1
                    if bomb.fuse_frames <= 0:
                        bomb.exploding = True
            if bomb.type == "remote" and "remote" not in bomb.owner.abilities:
                bomb.type = "converted"
                bomb.fuse_frames = cfg.BOMB_FUSE

    def _move_bomb(self, bomb):
        dt_factor = cfg.DT_OVER_DTAU
        bomb.vx += sign(bomb.vx) * cfg.KICK_ACCEL * cfg.CELL_SIZE * dt_factor
        bomb.vy += sign(bomb.vy) * cfg.KICK_ACCEL * cfg.CELL_SIZE * dt_factor
        if abs(bomb.vx) < 0.5: bomb.vx = 0
        if abs(bomb.vy) < 0.5: bomb.vy = 0

        new_x = bomb.pos_x + bomb.vx * dt_factor
        new_y = bomb.pos_y + bomb.vy * dt_factor
        if self._bomb_collision_at(bomb, new_x, new_y):
            self._snap_bomb_to_grid_center(bomb)
            bomb.vx = bomb.vy = 0
        else:
            bomb.pos_x = new_x
            bomb.pos_y = new_y

    def _bomb_collision_at(self, bomb, cx, cy):
        """Same as original — pixel coords, no dt."""
        r = cfg.CELL_SIZE * 0.35
        if cx - r < 0 or cx + r > get_map_width() or cy - r < cfg.UI_BAR_HEIGHT or cy + r > get_window_height():
            return True
        gx, gy = pixel_to_grid(cx, cy)
        if self.grid[gx][gy] in ("stone", "brick"):
            return True
        for p in (self.red_player, self.blue_player):
            if not p.alive: continue
            if math.hypot(cx - p.pos_x, cy - p.pos_y) < (cfg.PLAYER_HITBOX_SIZE * cfg.CELL_SIZE / 2 + r):
                return True
        for other in self.bombs:
            if other is bomb: continue
            if math.hypot(cx - other.pos_x, cy - other.pos_y) < 2 * r:
                return True
        return False

    def _snap_bomb_to_grid_center(self, bomb):
        gx, gy = bomb.grid_pos()
        bomb.pos_x, bomb.pos_y = grid_center(gx, gy)

    # ── Explosion BFS ──

    def process_explosions(self):
        queue = []
        for bomb in self.bombs:
            if bomb.exploding and not bomb.exploded:
                queue.append(bomb)
                bomb.exploded = True

        all_cells = set()
        bombs_to_remove = []
        buffs_to_remove = []

        while queue:
            bomb = queue.pop(0)
            cells = self._get_explosion_cells(bomb)
            all_cells.update(cells)
            for gx, gy in cells:
                for other in self.bombs:
                    if not other.exploded and other.grid_pos() == (gx, gy):
                        queue.append(other)
                        other.exploded = True
                        other.exploding = True
                if self.grid[gx][gy] == "brick":
                    self.grid[gx][gy] = "floor"
                    if random.random() < cfg.BRICK_DROP_PROB:
                        self._spawn_buff_at(gx, gy)
                for buff in self.buffs:
                    if buff.grid_pos() == (gx, gy) and buff.protection_timer <= 0:
                        if buff not in buffs_to_remove:
                            buffs_to_remove.append(buff)

        for bomb in self.bombs:
            if bomb.exploded and bomb.exploding:
                bombs_to_remove.append(bomb)
        for bomb in bombs_to_remove:
            for p in (self.red_player, self.blue_player):
                while bomb.id in p.remote_queue:
                    p.remote_queue.remove(bomb.id)
            self.bombs.remove(bomb)

        for buff in buffs_to_remove:
            if buff in self.buffs:
                self.buffs.remove(buff)

        for p in (self.red_player, self.blue_player):
            p.bomb_placed_count = self.count_bombs_owned_by(p)

        self.explosion_cells = all_cells

    def _get_explosion_cells(self, bomb):
        gx, gy = bomb.grid_pos()
        cells = {(gx, gy)}
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for i in range(1, bomb.owner.blast_range + 1):
                nx, ny = gx + dx * i, gy + dy * i
                if nx < 1 or nx > cfg.MAP_COLS or ny < 1 or ny > cfg.MAP_ROWS:
                    break
                cells.add((nx, ny))
                if self.grid[nx][ny] in ("stone", "brick"):
                    break
        return cells

    # ── Player death ──

    def process_player_death(self):
        for p in (self.red_player, self.blue_player):
            if not p.alive: continue
            if p.invincible_timer > 0: continue
            pgx, pgy = pixel_to_grid(p.pos_x, p.pos_y)
            if (pgx, pgy) in self.explosion_cells:
                if "shield" in p.abilities:
                    del p.abilities["shield"]
                    p.invincible_timer = cfg.SHIELD_INVINCIBLE_DUR
                else:
                    p.alive = False
                    p.death_timer = cfg.DEATH_ANIM_DUR

    # ── Buff protection ──

    def update_buff_protection(self):
        for buff in self.buffs:
            if buff.protection_timer > 0:
                buff.protection_timer -= 1

    # ── Buff pickups ──

    def process_buff_pickups(self):
        for p in (self.red_player, self.blue_player):
            if not p.alive: continue
            for buff in self.buffs[:]:
                if math.hypot(p.pos_x - buff.pos_x, p.pos_y - buff.pos_y) < (cfg.PLAYER_HITBOX_SIZE * cfg.CELL_SIZE / 2 + 8):
                    self._apply_buff(p, buff)
                    self.buffs.remove(buff)

    def _apply_buff(self, p, buff):
        if buff.type == "bomb_plus":
            p.perm_bomb_plus += 1
            p.bomb_max = min(cfg.INIT_BOMB_MAX + p.perm_bomb_plus, cfg.MAX_BOMB_CAP)
        elif buff.type == "blast_plus":
            p.perm_blast_plus += 1
            p.blast_range = min(cfg.INIT_BLAST_RANGE + p.perm_blast_plus, cfg.MAX_BLAST_RANGE)
        elif buff.type == "speed_plus":
            p.perm_speed_plus += 1
            p.velocity = min(cfg.INIT_SPEED + p.perm_speed_plus * cfg.SPEED_INCREMENT, cfg.MAX_SPEED)
        elif buff.type == "unknown":
            ability = buff.unknown_subtype
            duration = self._get_ability_duration(ability)
            p.abilities[ability] = duration

    def _get_ability_duration(self, ability):
        return {
            "kick": cfg.DURATION_KICK,
            "remote": cfg.DURATION_REMOTE,
            "shield": cfg.DURATION_SHIELD,
            "diarrhea": cfg.DURATION_DIARRHEA,
            "reverse": cfg.DURATION_REVERSE,
            "float": cfg.DURATION_FLOAT,
        }.get(ability, 10)

    # ── Buff spawn / refresh ──

    def update_buff_refresh(self):
        self.refresh_timer -= 1
        if self.refresh_timer <= 0:
            self._spawn_random_buff()
            self.refresh_timer += cfg.REFRESH_INTERVAL

    def _spawn_random_buff(self):
        for _ in range(100):
            gx = random.randint(1, cfg.MAP_COLS)
            gy = random.randint(1, cfg.MAP_ROWS)
            if (self.grid[gx][gy] == "floor"
                    and not self._is_player_at(gx, gy)
                    and not self._is_bomb_at(gx, gy)
                    and not self._is_buff_at(gx, gy)):
                self._spawn_buff_at(gx, gy)
                return

    def _spawn_buff_at(self, gx, gy):
        r = random.random()
        cum = 0
        weights = [cfg.WEIGHT_BOMB_PLUS, cfg.WEIGHT_BLAST_PLUS, cfg.WEIGHT_SPEED_PLUS, cfg.WEIGHT_UNKNOWN]
        for i, w in enumerate(weights):
            cum += w
            if r < cum:
                if i == 0:
                    self.buffs.append(BuffItem("bomb_plus", "", gx, gy))
                elif i == 1:
                    self.buffs.append(BuffItem("blast_plus", "", gx, gy))
                elif i == 2:
                    self.buffs.append(BuffItem("speed_plus", "", gx, gy))
                else:
                    sub = random.choice(["kick", "remote", "shield", "diarrhea", "reverse", "float"])
                    self.buffs.append(BuffItem("unknown", sub, gx, gy))
                return

    def _is_player_at(self, gx, gy):
        for p in (self.red_player, self.blue_player):
            if p.alive and pixel_to_grid(p.pos_x, p.pos_y) == (gx, gy):
                return True
        return False

    def _is_bomb_at(self, gx, gy):
        for b in self.bombs:
            if b.grid_pos() == (gx, gy):
                return True
        return False

    def _is_buff_at(self, gx, gy):
        for b in self.buffs:
            if b.grid_pos() == (gx, gy):
                return True
        return False

    # ── Ability timers ──

    def update_ability_timers(self):
        for p in (self.red_player, self.blue_player):
            for ability in list(p.abilities.keys()):
                p.abilities[ability] -= 1
                if p.abilities[ability] <= 0:
                    self._remove_ability(p, ability)
            if p.invincible_timer > 0:
                p.invincible_timer -= 1
            if not p.alive and p.death_timer > 0:
                p.death_timer -= 1

    def _remove_ability(self, p, ability):
        if ability not in p.abilities:
            return
        del p.abilities[ability]
        if ability == "remote":
            p.remote_queue.clear()
            for bomb in self.bombs:
                if bomb.owner is p and bomb.type == "remote":
                    bomb.type = "converted"
                    bomb.fuse_frames = cfg.BOMB_FUSE
        elif ability == "float":
            self._handle_float_end(p)

    def _handle_float_end(self, p):
        gx, gy = pixel_to_grid(p.pos_x, p.pos_y)
        needs_evict = (self.grid[gx][gy] == "brick") or self._is_bomb_at(gx, gy)
        if not needs_evict:
            return
        candidates = []
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            nx, ny = gx + dx, gy + dy
            if nx < 1 or nx > cfg.MAP_COLS or ny < 1 or ny > cfg.MAP_ROWS:
                continue
            if self.grid[nx][ny] == "floor" and not self._is_player_at(nx, ny) and not self._is_bomb_at(nx, ny):
                cx, cy = grid_center(nx, ny)
                dist = abs(p.pos_x - cx) + abs(p.pos_y - cy)
                candidates.append((dist, (nx, ny)))
        if candidates:
            candidates.sort(key=lambda x: x[0])
            target_gx, target_gy = candidates[0][1]
            old_gx, old_gy = pixel_to_grid(p.pos_x, p.pos_y)
            p.pos_x, p.pos_y = grid_center(target_gx, target_gy)
            if "diarrhea" in p.abilities:
                self._check_diarrhea_on_move(p, old_gx, old_gy)
        else:
            self._kill_player(p)

    def _check_diarrhea_on_move(self, p, old_gx, old_gy):
        if not p.alive or "diarrhea" not in p.abilities:
            return
        new_gx, new_gy = pixel_to_grid(p.pos_x, p.pos_y)
        if (new_gx, new_gy) != (old_gx, old_gy):
            if self.grid[new_gx][new_gy] == "floor" and not self._is_bomb_at(new_gx, new_gy):
                if p.bomb_placed_count < p.bomb_max:
                    self._create_bomb(p, "normal", new_gx, new_gy, cfg.BOMB_FUSE)

    def _kill_player(self, p):
        p.alive = False
        p.death_timer = 0

    # ── Round end ──

    def check_round_end(self):
        red_alive = self.red_player.alive
        blue_alive = self.blue_player.alive
        if red_alive and blue_alive:
            return

        red_dead = not red_alive
        blue_dead = not blue_alive

        if red_dead and blue_dead:
            self._start_round_delay("")
            return

        if red_dead and blue_alive:
            if self.red_player.death_timer <= 0:
                self.blue_player.wins += 1
                if self.blue_player.wins >= cfg.WIN_SCORE:
                    self.state = GameState.MATCH_END
                else:
                    self._start_round_delay("blue")
        elif blue_dead and red_alive:
            if self.blue_player.death_timer <= 0:
                self.red_player.wins += 1
                if self.red_player.wins >= cfg.WIN_SCORE:
                    self.state = GameState.MATCH_END
                else:
                    self._start_round_delay("red")

    def _start_round_delay(self, winner_id):
        self.current_winner = winner_id
        self.state = GameState.ROUND_END_DELAY
        self.round_delay_timer = cfg.ROUND_DELAY

    # ── Snapshot ──

    def get_snapshot(self):
        """Build a read-only GameSnapshot from current engine state."""
        # Build map_grid (COLS x ROWS)
        map_grid = [[CELL_EMPTY for _ in range(cfg.MAP_ROWS + 1)] for _ in range(cfg.MAP_COLS + 1)]
        for x in range(1, cfg.MAP_COLS + 1):
            for y in range(1, cfg.MAP_ROWS + 1):
                cell = self.grid[x][y]
                if cell == "stone":
                    map_grid[x][y] = CELL_STONE
                elif cell == "brick":
                    map_grid[x][y] = CELL_BRICK
                elif cell == "floor":
                    map_grid[x][y] = CELL_EMPTY

        # Overlay buffs
        for buff in self.buffs:
            gx, gy = buff.grid_pos()
            map_grid[gx][gy] = CELL_BUFF

        # Overlay bombs
        for bomb in self.bombs:
            gx, gy = bomb.grid_pos()
            map_grid[gx][gy] = CELL_BOMB

        # Overlay explosions
        for gx, gy in self.explosion_cells:
            map_grid[gx][gy] = CELL_EXPLOSION

        # Player snapshots
        def _psnap(p):
            gx, gy = pixel_to_grid(p.pos_x, p.pos_y)
            return PlayerSnapshot(
                id=p.id, color=p.color,
                pos_x=p.pos_x, pos_y=p.pos_y,
                grid_x=gx, grid_y=gy,
                alive=p.alive, velocity=p.velocity,
                death_timer=p.death_timer,
                bomb_max=p.bomb_max, bomb_placed_count=p.bomb_placed_count,
                blast_range=p.blast_range, invincible_timer=p.invincible_timer,
                wins=p.wins,
                perm_bomb_plus=p.perm_bomb_plus,
                perm_blast_plus=p.perm_blast_plus,
                perm_speed_plus=p.perm_speed_plus,
                abilities=dict(p.abilities),
                dir_x=p.dir_x, dir_y=p.dir_y,
            )

        # Bomb snapshots
        def _bsnap(b):
            gx, gy = pixel_to_grid(b.pos_x, b.pos_y)
            return BombSnapshot(
                id=b.id, owner=b.owner, type=b.type,
                pos_x=b.pos_x, pos_y=b.pos_y,
                grid_x=gx, grid_y=gy,
                fuse_frames=b.fuse_frames,
                vx=b.vx, vy=b.vy,
            )

        # Buff snapshots
        def _bufsnap(b):
            gx, gy = b.grid_pos()
            return BuffItemSnapshot(
                type=b.type,
                pos_x=b.pos_x, pos_y=b.pos_y,
                grid_x=gx, grid_y=gy,
                # No unknown_subtype
            )

        return GameSnapshot(
            state=self.state,
            round_frame=self.round_frame,
            map_grid=map_grid,
            players=(_psnap(self.red_player), _psnap(self.blue_player)),
            bombs=tuple(_bsnap(b) for b in self.bombs),
            buffs=tuple(_bufsnap(b) for b in self.buffs),
            explosion_cells=tuple(self.explosion_cells),
            scores={"red": self.red_player.wins, "blue": self.blue_player.wins},
            current_winner=self.current_winner,
            round_delay_timer=self.round_delay_timer,
        )
