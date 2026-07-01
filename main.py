"""
bomberman version 2.0.2
"""
import pygame
import random
import math
import sys

from config import Config, cfg

from utils import (
    grid_to_pixel, grid_center, pixel_to_grid, clamp, sign,
    get_map_width, get_map_height, get_window_width, get_window_height,
    box_overlap,
)
from constants import (
    COLOR_BG, COLOR_FLOOR, COLOR_STONE, COLOR_BRICK,
    COLOR_RED, COLOR_BLUE, COLOR_BOMB_BODY, COLOR_BOMB_FUSE,
    COLOR_EXPLOSION, COLOR_TEXT, COLOR_UI_BAR_BG, COLOR_SHIELD,
    BUFF_BOMB_COLOR, BUFF_BLAST_COLOR, BUFF_SPEED_COLOR, BUFF_UNKNOWN_COLOR,
    ABILITY_KICK_COLOR, ABILITY_REMOTE_COLOR, ABILITY_SHIELD_COLOR,
    ABILITY_DIARRHEA_COLOR, ABILITY_REVERSE_COLOR, ABILITY_FLOAT_COLOR,
    GameState,
)

# ==================== 数据结构 ====================
class Player:
    def __init__(self, pid, color):
        self.id = pid          # "red" or "blue"
        self.color = color
        self.pos_x = 0.0
        self.pos_y = 0.0
        self.velocity = cfg.INIT_SPEED
        self.bomb_max = cfg.INIT_BOMB_MAX
        self.bomb_placed_count = 0
        self.blast_range = cfg.INIT_BLAST_RANGE
        self.alive = True
        self.death_timer = 0.0
        self.invincible_timer = 0.0
        self.wins = 0
        self.perm_bomb_plus = 0
        self.perm_blast_plus = 0
        self.perm_speed_plus = 0
        self.abilities = {}        # {ability_name: remaining_seconds}
        self.remote_queue = []     # list of bomb IDs (FIFO)
        # 输入
        self.input_up = False
        self.input_down = False
        self.input_left = False
        self.input_right = False
        self.input_action = False
        self.prev_action = False
        self.vx = 0.0
        self.vy = 0.0

    def reset(self, spawn_x, spawn_y):
        self.pos_x, self.pos_y = grid_center(spawn_x, spawn_y)
        self.velocity = cfg.INIT_SPEED
        self.bomb_max = cfg.INIT_BOMB_MAX
        self.bomb_placed_count = 0
        self.blast_range = cfg.INIT_BLAST_RANGE
        self.alive = True
        self.death_timer = 0.0
        self.invincible_timer = 0.0
        self.perm_bomb_plus = 0
        self.perm_blast_plus = 0
        self.perm_speed_plus = 0
        self.abilities.clear()
        self.remote_queue.clear()
        self.vx = 0.0
        self.vy = 0.0
        self.input_up = self.input_down = self.input_left = self.input_right = False
        self.input_action = False
        self.input_ignite = False
        self.prev_action = False

    def hitbox(self):
        half = (cfg.PLAYER_HITBOX_SIZE * cfg.CELL_SIZE) / 2
        return (self.pos_x - half, self.pos_x + half,
                self.pos_y - half, self.pos_y + half)

class Bomb:
    def __init__(self, bid, owner, bomb_type, grid_x, grid_y, timer):
        self.id = bid
        self.owner = owner
        self.type = bomb_type          # "normal", "remote", "converted"
        self.pos_x, self.pos_y = grid_center(grid_x, grid_y)
        self.timer = timer             # -1 for remote untimed
        self.vx = 0.0
        self.vy = 0.0
        self.exploding = False
        self.exploded = False

    def grid_pos(self):
        return pixel_to_grid(self.pos_x, self.pos_y)

class BuffItem:
    def __init__(self, buff_type, sub_type, gx, gy):
        self.type = buff_type           # "bomb_plus", "blast_plus", "speed_plus", "unknown"
        self.unknown_subtype = sub_type # 当type为unknown时有效
        self.pos_x, self.pos_y = grid_center(gx, gy)
        self.protection_timer = cfg.BUFF_PROTECTION_TIME

    def grid_pos(self):
        return pixel_to_grid(self.pos_x, self.pos_y)

# ==================== 主游戏类 ====================
class BombermanGame:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((get_window_width(), get_window_height()), pygame.RESIZABLE)
        pygame.display.set_caption("炸弹人 双人PVP v2.8")
        self.clock = pygame.time.Clock()
        self.running = True
        self.state = GameState.MENU
        self.grid = [[None for _ in range(cfg.MAP_ROWS + 1)] for _ in range(cfg.MAP_COLS + 1)]
        self.red_player = Player("red", COLOR_RED)
        self.blue_player = Player("blue", COLOR_BLUE)
        self.bombs = []
        self.buffs = []
        self.explosion_cells = set()
        self.round_time = 0.0
        self.refresh_timer = cfg.REFRESH_INTERVAL
        self.round_delay_timer = 0.0
        self.current_winner = ""   # "red", "blue", "" for tie
        self.next_bomb_id = 0
        self.keys_red = {'W': False, 'A': False, 'S': False, 'D': False, 'E': False,'Q':False}
        self.keys_blue = {'UP': False, 'LEFT': False, 'DOWN': False, 'RIGHT': False, 'DEL': False,'END':False}
        # 设置面板
        self.show_settings = False
        self.settings_pause_state = None
        self.settings_buttons = []
        self.settings_scroll = 0
        self.init_settings_ui()
        # 字体
        self.font_small = pygame.font.Font(None, 18)
        self.font_medium = pygame.font.Font(None, 24)
        self.font_big = pygame.font.Font(None, 48)
        # 安全格子
        self.safe_spots = self.compute_safe_spots()
        # 开始
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
        self.round_time = 0.0
        self.refresh_timer = cfg.REFRESH_INTERVAL
        self.round_delay_timer = 0.0
        self.current_winner = ""
        self.next_bomb_id = 0
        self.state = GameState.ROUND_RUNNING

    def generate_map(self):
        for x in range(1, cfg.MAP_COLS + 1):
            for y in range(1, cfg.MAP_ROWS + 1):
                if x % 2 == 0 and y % 2 == 0:
                    self.grid[x][y] = "stone"
                elif (x % 2 == 0) != (y % 2 == 0):  # 一奇一偶
                    if (x, y) in self.safe_spots:
                        self.grid[x][y] = "floor"
                    else:
                        self.grid[x][y] = "brick" if random.random() < cfg.BRICK_GEN_PROB else "floor"
                else:
                    self.grid[x][y] = "floor"

    # ==================== 输入处理 ====================
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self.handle_key(event.key, True)
            elif event.type == pygame.KEYUP:
                self.handle_key(event.key, False)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if self.state in (GameState.SETTINGS, GameState.SETTINGS_PAUSED):
                    self.handle_settings_click(event.pos)
        self.sync_input()

    def handle_key(self, key, pressed):
        if self.state == GameState.MENU:
            if pressed and key == pygame.K_RETURN:
                self.reset_match()
            return
        if self.state == GameState.MATCH_END:
            if pressed and key == pygame.K_r:
                self.reset_match()
            return
        if self.state in (GameState.SETTINGS, GameState.SETTINGS_PAUSED):
            if pressed and key == pygame.K_p:
                self.toggle_settings()
            return

        if pressed and key == pygame.K_p:
            self.toggle_settings()
            return

        # 红方
        if key == pygame.K_w: self.keys_red['W'] = pressed
        elif key == pygame.K_a: self.keys_red['A'] = pressed
        elif key == pygame.K_s: self.keys_red['S'] = pressed
        elif key == pygame.K_d: self.keys_red['D'] = pressed
        elif key == pygame.K_e: self.keys_red['E'] = pressed
        elif key == pygame.K_q: self.keys_red['Q'] = pressed
        # 蓝方
        elif key == pygame.K_UP: self.keys_blue['UP'] = pressed
        elif key == pygame.K_LEFT: self.keys_blue['LEFT'] = pressed
        elif key == pygame.K_DOWN: self.keys_blue['DOWN'] = pressed
        elif key == pygame.K_RIGHT: self.keys_blue['RIGHT'] = pressed
        elif key == pygame.K_DELETE: self.keys_blue['DEL'] = pressed
        elif key == pygame.K_END: self.keys_blue['END'] = pressed

    def sync_input(self):
        p = self.red_player
        p.input_up = self.keys_red['W']
        p.input_down = self.keys_red['S']
        p.input_left = self.keys_red['A']
        p.input_right = self.keys_red['D']
        p.prev_action = p.input_action
        p.input_action = self.keys_red['E'] and not p.prev_action
        p.input_ignite = self.keys_red['Q']

        p = self.blue_player
        p.input_up = self.keys_blue['UP']
        p.input_down = self.keys_blue['DOWN']
        p.input_left = self.keys_blue['LEFT']
        p.input_right = self.keys_blue['RIGHT']
        p.prev_action = p.input_action
        p.input_action = self.keys_blue['DEL'] and not p.prev_action
        p.input_ignite = self.keys_blue['END']

    def toggle_settings(self):
        if self.state in (GameState.SETTINGS, GameState.SETTINGS_PAUSED):
            if self.settings_pause_state is not None:
                self.state = self.settings_pause_state
                self.settings_pause_state = None
            else:
                self.state = GameState.ROUND_RUNNING
        else:
            if self.state == GameState.ROUND_RUNNING:
                self.settings_pause_state = GameState.ROUND_RUNNING
            else:
                self.settings_pause_state = None
            self.state = GameState.SETTINGS

    # ==================== 游戏更新 ====================
    def update(self, dt):
        if self.state == GameState.ROUND_RUNNING:
            self.update_round(dt)
        elif self.state == GameState.ROUND_END_DELAY:
            self.update_round_delay(dt)

    def update_round(self, dt):
        self.round_time += 1.0
        self.update_buff_refresh(dt)
        self.update_buff_protection(dt)
        self.update_player_movement(dt)
        self.update_bomb_timers_and_movement(dt)
        self.process_explosions()
        self.process_player_death()
        self.process_buff_pickups()
        self.update_ability_timers(dt)
        self.check_round_end()

    # ---------- 玩家移动 ----------
    def update_player_movement(self, dt):
        for p in (self.red_player, self.blue_player):
            if not p.alive:
                continue
            old_gx, old_gy = pixel_to_grid(p.pos_x, p.pos_y)
            dir_x, dir_y = self.get_input_direction(p)
            if "reverse" in p.abilities:
                dir_x = -dir_x
                dir_y = -dir_y
            speed = p.velocity
            if dir_x != 0 and dir_y != 0:
                speed *= 0.70710678  # 1/sqrt(2)
            desired_vx = dir_x * speed * cfg.CELL_SIZE
            desired_vy = dir_y * speed * cfg.CELL_SIZE
            self.move_player(p, desired_vx, desired_vy, dt)

            # 踢炸弹
            if "kick" in p.abilities and (dir_x != 0 or dir_y != 0):
                self.try_kick_bomb(p, dir_x, dir_y)

            # 动作键
            if p.input_action:
                if "remote" in p.abilities:
                        self.place_remote_bomb(p)
                        
                else:
                    self.place_normal_bomb(p)
                p.input_action = False

            if p.input_ignite:
                if "remote" in p.abilities:
                    if p.remote_queue:
                        self.detonate_earliest_remote(p)

            # 腹泻
            self.check_diarrhea_on_move(p, old_gx, old_gy)

    def get_input_direction(self, p):
        dx, dy = 0, 0
        if p.input_up: dy -= 1
        if p.input_down: dy += 1
        if p.input_left: dx -= 1
        if p.input_right: dx += 1
        count = (p.input_up + p.input_down + p.input_left + p.input_right)
        if count > 2:
            return 0, 0
        return dx, dy

    def move_player(self, p, vx_ps, vy_ps, dt):
        old_x, old_y = p.pos_x, p.pos_y
        # X 轴
        new_x = old_x + vx_ps * dt
        if not self.player_collision_at(p, new_x, old_y, old_x, old_y):
            p.pos_x = new_x
        # Y 轴
        new_y = old_y + vy_ps * dt
        if not self.player_collision_at(p, p.pos_x, new_y, old_x, old_y):
            p.pos_y = new_y

    def player_collision_at(self, p, new_x, new_y, old_x, old_y):
        half = (cfg.PLAYER_HITBOX_SIZE * cfg.CELL_SIZE) / 2
        L, R = new_x - half, new_x + half
        T, B = new_y - half, new_y + half

        # 边界
        if L < 0 or R > get_map_width() or T < cfg.UI_BAR_HEIGHT or B > get_window_height():
            return True

        # 地形
        if "float" in p.abilities:
            for cell in self.cells_overlapping(L, R, T, B):
                if self.grid[cell[0]][cell[1]] == "stone":
                    return True
        else:
            for cell in self.cells_overlapping(L, R, T, B):
                if self.grid[cell[0]][cell[1]] in ("stone", "brick"):
                    return True

        # 玩家碰撞
        for other in (self.red_player, self.blue_player):
            if other is p or not other.alive:
                continue
            if box_overlap(L, R, T, B, *other.hitbox()):
                return True

        # 炸弹：可以离开不能进入（悬浮忽略）
        if "float" not in p.abilities:
            for bomb in self.bombs:
                bgx, bgy = bomb.grid_pos()
                new_gx, new_gy = pixel_to_grid(new_x, new_y)
                old_gx, old_gy = pixel_to_grid(old_x, old_y)
                if (new_gx, new_gy) == (bgx, bgy) and (old_gx, old_gy) != (bgx, bgy):
                    return True
        return False

    def cells_overlapping(self, L, R, T, B):
        cells = set()
        min_gx = max(1, int(L // cfg.CELL_SIZE) + 1)
        max_gx = min(cfg.MAP_COLS, int((R - 1) // cfg.CELL_SIZE) + 1)
        min_gy = max(1, int((T - cfg.UI_BAR_HEIGHT) // cfg.CELL_SIZE) + 1)
        max_gy = min(cfg.MAP_ROWS, int((B - 1 - cfg.UI_BAR_HEIGHT) // cfg.CELL_SIZE) + 1)
        for gx in range(min_gx, max_gx + 1):
            for gy in range(min_gy, max_gy + 1):
                cells.add((gx, gy))
        return cells

    # ---------- 踢炸弹 ----------
    def try_kick_bomb(self, p, dir_x, dir_y):
        for bomb in self.bombs:
            if self.player_touches_bomb(p, bomb):
                self.kick_bomb(bomb, dir_x, dir_y)
                break

    def player_touches_bomb(self, p, bomb):
        phalf = (cfg.PLAYER_HITBOX_SIZE * cfg.CELL_SIZE) / 2
        br = cfg.CELL_SIZE * 0.35
        return math.hypot(p.pos_x - bomb.pos_x, p.pos_y - bomb.pos_y) < (phalf + br)

    def kick_bomb(self, bomb, dx, dy):
        bomb.vx = dx * cfg.KICK_INIT_VEL * cfg.CELL_SIZE
        bomb.vy = dy * cfg.KICK_INIT_VEL * cfg.CELL_SIZE

    # ---------- 放置炸弹 ----------
    def place_normal_bomb(self, p):
        if p.bomb_placed_count >= p.bomb_max:
            return
        gx, gy = pixel_to_grid(p.pos_x, p.pos_y)
        if self.is_bomb_at(gx, gy):
            return
        self.create_bomb(p, "normal", gx, gy, cfg.BOMB_FUSE)

    def place_remote_bomb(self, p):
        if p.bomb_placed_count >= p.bomb_max:
            return
        gx, gy = pixel_to_grid(p.pos_x, p.pos_y)
        if self.is_bomb_at(gx, gy):
            return
        bomb = self.create_bomb(p, "remote", gx, gy, -1.0)
        p.remote_queue.append(bomb.id)

    def create_bomb(self, owner, bomb_type, gx, gy, timer):
        bomb = Bomb(self.next_bomb_id, owner, bomb_type, gx, gy, timer)
        self.next_bomb_id += 1
        self.bombs.append(bomb)
        owner.bomb_placed_count = self.count_bombs_owned_by(owner)
        return bomb

    def detonate_earliest_remote(self, p):
        if not p.remote_queue:
            return
        bid = p.remote_queue.pop(0)
        for bomb in self.bombs:
            if bomb.id == bid and bomb.owner is p:
                bomb.exploding = True
                break

    def is_bomb_at(self, gx, gy):
        for bomb in self.bombs:
            if bomb.grid_pos() == (gx, gy):
                return True
        return False

    def count_bombs_owned_by(self, owner):
        return sum(1 for b in self.bombs if b.owner is owner)

    # ---------- 炸弹计时与移动 ----------
    def update_bomb_timers_and_movement(self, dt):
        for bomb in self.bombs:
            if bomb.vx != 0 or bomb.vy != 0:
                self.move_bomb(bomb, dt)
            if bomb.type in ("normal", "converted"):
                if bomb.timer > 0:
                    bomb.timer -= 1.0
                    if bomb.timer <= 0:
                        bomb.exploding = True
            if bomb.type == "remote" and "remote" not in bomb.owner.abilities:
                bomb.type = "converted"
                bomb.timer = cfg.BOMB_FUSE

    def move_bomb(self, bomb, dt):
        bomb.vx += sign(bomb.vx) * cfg.KICK_ACCEL * cfg.CELL_SIZE * dt
        bomb.vy += sign(bomb.vy) * cfg.KICK_ACCEL * cfg.CELL_SIZE * dt
        if abs(bomb.vx) < 0.5: bomb.vx = 0
        if abs(bomb.vy) < 0.5: bomb.vy = 0

        new_x = bomb.pos_x + bomb.vx * dt
        new_y = bomb.pos_y + bomb.vy * dt
        if self.bomb_collision_at(bomb, new_x, new_y):
            self.snap_bomb_to_grid_center(bomb)
            bomb.vx = bomb.vy = 0
        else:
            bomb.pos_x = new_x
            bomb.pos_y = new_y

    def bomb_collision_at(self, bomb, cx, cy):
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

    def snap_bomb_to_grid_center(self, bomb):
        gx, gy = bomb.grid_pos()
        bomb.pos_x, bomb.pos_y = grid_center(gx, gy)

    # ---------- 爆炸处理（BFS）----------
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
            cells = self.get_explosion_cells(bomb)
            all_cells.update(cells)
            for gx, gy in cells:
                # 连锁其他炸弹
                for other in self.bombs:
                    if not other.exploded and other.grid_pos() == (gx, gy):
                        queue.append(other)
                        other.exploded = True
                        other.exploding = True
                # 破坏砖块
                if self.grid[gx][gy] == "brick":
                    self.grid[gx][gy] = "floor"
                    if random.random() < cfg.BRICK_DROP_PROB:
                        self.spawn_buff_at(gx, gy)
                # 摧毁不受保护的Buff
                for buff in self.buffs:
                    if buff.grid_pos() == (gx, gy) and buff.protection_timer <= 0:
                        if buff not in buffs_to_remove:
                            buffs_to_remove.append(buff)

        # 清理炸弹
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

    def get_explosion_cells(self, bomb):
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

    # ---------- 玩家死亡 ----------
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

    # ---------- Buff拾取 ----------
    def update_buff_protection(self, dt):
        for buff in self.buffs:
            if buff.protection_timer > 0:
                buff.protection_timer -= 1.0

    def process_buff_pickups(self):
        for p in (self.red_player, self.blue_player):
            if not p.alive: continue
            for buff in self.buffs[:]:
                if math.hypot(p.pos_x - buff.pos_x, p.pos_y - buff.pos_y) < (cfg.PLAYER_HITBOX_SIZE * cfg.CELL_SIZE / 2 + 8):
                    self.apply_buff(p, buff)
                    self.buffs.remove(buff)

    def apply_buff(self, p, buff):
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
            duration = self.get_ability_duration(ability)
            p.abilities[ability] = duration

    def get_ability_duration(self, ability):
        return {
            "kick": cfg.DURATION_KICK,
            "remote": cfg.DURATION_REMOTE,
            "shield": cfg.DURATION_SHIELD,
            "diarrhea": cfg.DURATION_DIARRHEA,
            "reverse": cfg.DURATION_REVERSE,
            "float": cfg.DURATION_FLOAT,
        }.get(ability, 10)

    # ---------- Buff刷新 ----------
    def update_buff_refresh(self, dt):
        self.refresh_timer -= 1.0
        if self.refresh_timer <= 0:
            self.spawn_random_buff()
            self.refresh_timer += cfg.REFRESH_INTERVAL

    def spawn_random_buff(self):
        for _ in range(100):
            gx = random.randint(1, cfg.MAP_COLS)
            gy = random.randint(1, cfg.MAP_ROWS)
            if self.grid[gx][gy] == "floor" and not self.is_player_at(gx, gy) and not self.is_bomb_at(gx, gy) and not self.is_buff_at(gx, gy):
                self.spawn_buff_at(gx, gy)
                return

    def spawn_buff_at(self, gx, gy):
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

    def is_player_at(self, gx, gy):
        for p in (self.red_player, self.blue_player):
            if p.alive and pixel_to_grid(p.pos_x, p.pos_y) == (gx, gy):
                return True
        return False

    def is_buff_at(self, gx, gy):
        for b in self.buffs:
            if b.grid_pos() == (gx, gy):
                return True
        return False

    # ---------- 能力计时器与过期 ----------
    def update_ability_timers(self, dt):
        for p in (self.red_player, self.blue_player):
            for ability in list(p.abilities.keys()):
                p.abilities[ability] -= 1.0
                if p.abilities[ability] <= 0:
                    self.remove_ability(p, ability)
            if p.invincible_timer > 0:
                p.invincible_timer -= 1.0
            if not p.alive and p.death_timer > 0:
                p.death_timer -= 1.0

    def remove_ability(self, p, ability):
        if ability not in p.abilities:
            return
        del p.abilities[ability]
        if ability == "remote":
            p.remote_queue.clear()
            for bomb in self.bombs:
                if bomb.owner is p and bomb.type == "remote":
                    bomb.type = "converted"
                    bomb.timer = cfg.BOMB_FUSE
        elif ability == "float":
            self.handle_float_end(p)

    def handle_float_end(self, p):
        gx, gy = pixel_to_grid(p.pos_x, p.pos_y)
        needs_evict = (self.grid[gx][gy] == "brick") or self.is_bomb_at(gx, gy)
        if not needs_evict:
            return
        candidates = []
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):  # 上,下,左,右
            nx, ny = gx + dx, gy + dy
            if nx < 1 or nx > cfg.MAP_COLS or ny < 1 or ny > cfg.MAP_ROWS:
                continue
            if self.grid[nx][ny] == "floor" and not self.is_player_at(nx, ny) and not self.is_bomb_at(nx, ny):
                cx, cy = grid_center(nx, ny)
                dist = abs(p.pos_x - cx) + abs(p.pos_y - cy)
                candidates.append((dist, (nx, ny)))
        if candidates:
            candidates.sort(key=lambda x: x[0])
            target_gx, target_gy = candidates[0][1]
            old_gx, old_gy = pixel_to_grid(p.pos_x, p.pos_y)
            p.pos_x, p.pos_y = grid_center(target_gx, target_gy)
            if "diarrhea" in p.abilities:
                self.check_diarrhea_on_move(p, old_gx, old_gy)
        else:
            self.kill_player(p)

    def check_diarrhea_on_move(self, p, old_gx, old_gy):
        if not p.alive or "diarrhea" not in p.abilities:
            return
        new_gx, new_gy = pixel_to_grid(p.pos_x, p.pos_y)
        if (new_gx, new_gy) != (old_gx, old_gy):
            if self.grid[new_gx][new_gy] == "floor" and not self.is_bomb_at(new_gx, new_gy):
                if p.bomb_placed_count < p.bomb_max:
                    self.create_bomb(p, "normal", new_gx, new_gy, cfg.BOMB_FUSE)

    def kill_player(self, p):
        p.alive = False
        p.death_timer = 0.0

    # ---------- 回合结束 ----------
    def check_round_end(self):
        red_alive = self.red_player.alive
        blue_alive = self.blue_player.alive
        if red_alive and blue_alive:
            return

        red_dead = not red_alive
        blue_dead = not blue_alive

        if red_dead and blue_dead:
            self.start_round_delay("")
            return

        if red_dead and blue_alive:
            if self.red_player.death_timer <= 0:
                self.blue_player.wins += 1
                if self.blue_player.wins >= cfg.WIN_SCORE:
                    self.state = GameState.MATCH_END
                else:
                    self.start_round_delay("blue")
        elif blue_dead and red_alive:
            if self.blue_player.death_timer <= 0:
                self.red_player.wins += 1
                if self.red_player.wins >= cfg.WIN_SCORE:
                    self.state = GameState.MATCH_END
                else:
                    self.start_round_delay("red")

    def start_round_delay(self, winner_id):
        self.current_winner = winner_id
        self.state = GameState.ROUND_END_DELAY
        self.round_delay_timer = cfg.ROUND_DELAY

    def update_round_delay(self, dt):
        self.round_delay_timer -= 1.0
        if self.round_delay_timer <= 0:
            self.reset_round()

    # ==================== 渲染 ====================
    def render(self):
        self.screen.fill(COLOR_BG)
        if self.state in (GameState.SETTINGS, GameState.SETTINGS_PAUSED):
            self.draw_settings_panel()
        else:
            self.draw_map()
            for buff in self.buffs:
                self.draw_buff(buff)
            for bomb in self.bombs:
                flicker = (bomb.type in ("normal", "converted") and bomb.timer <= cfg.BOMB_FLICKER_START)
                self.draw_bomb(bomb, flicker)
            for cell in self.explosion_cells:
                self.draw_explosion_cell(cell)
            self.draw_player(self.red_player)
            self.draw_player(self.blue_player)
            self.draw_ui_bar()
            if self.state == GameState.MATCH_END:
                self.draw_victory_screen()
            elif self.state == GameState.ROUND_END_DELAY:
                self.draw_round_delay_overlay()
        pygame.display.flip()

    # ---------- 地图 ----------
    def draw_map(self):
        for x in range(1, cfg.MAP_COLS + 1):
            for y in range(1, cfg.MAP_ROWS + 1):
                left, top = grid_to_pixel(x, y)
                rect = pygame.Rect(left, top, cfg.CELL_SIZE, cfg.CELL_SIZE)
                if self.grid[x][y] == "floor":
                    pygame.draw.rect(self.screen, COLOR_FLOOR, rect)
                    pygame.draw.rect(self.screen, (160, 160, 160), rect, 1)
                elif self.grid[x][y] == "stone":
                    pygame.draw.rect(self.screen, COLOR_STONE, rect)
                    cx, cy = left + cfg.CELL_SIZE // 2, top + cfg.CELL_SIZE // 2
                    pygame.draw.line(self.screen, (60,60,60), (cx-10, cy), (cx+10, cy), 2)
                    pygame.draw.line(self.screen, (60,60,60), (cx, cy-10), (cx, cy+10), 2)
                elif self.grid[x][y] == "brick":
                    pygame.draw.rect(self.screen, COLOR_BRICK, rect)
                    pygame.draw.rect(self.screen, (180,100,40), rect, 2)
                    mid_y = top + cfg.CELL_SIZE//2
                    pygame.draw.line(self.screen, (180,100,40), (left, mid_y), (left+cfg.CELL_SIZE, mid_y), 2)
                    third = cfg.CELL_SIZE // 3
                    pygame.draw.line(self.screen, (180,100,40), (left+third, top), (left+third, mid_y), 2)
                    pygame.draw.line(self.screen, (180,100,40), (left+2*third, mid_y), (left+2*third, top+cfg.CELL_SIZE), 2)

    # ---------- Buff ----------
    def draw_buff(self, buff):
        gx, gy = buff.grid_pos()
        cx, cy = grid_center(gx, gy)
        size = int(cfg.CELL_SIZE * 0.35)
        if buff.type == "bomb_plus":
            col = BUFF_BOMB_COLOR
        elif buff.type == "blast_plus":
            col = BUFF_BLAST_COLOR
        elif buff.type == "speed_plus":
            col = BUFF_SPEED_COLOR
        else:
            col = BUFF_UNKNOWN_COLOR
        pygame.draw.circle(self.screen, (*col, 180), (cx, cy), size + 2)
        pygame.draw.circle(self.screen, (255, 255, 255, 200), (cx, cy), size)
        if buff.type == "bomb_plus":
            br = int(size * 0.45)
            pygame.draw.circle(self.screen, (40, 40, 40), (cx, cy - 1), br)
            pygame.draw.circle(self.screen, (80, 80, 80), (cx - br//3, cy - br//3 - 1), br//3)
            pygame.draw.line(self.screen, (255, 200, 0), (cx, cy - br), (cx, cy - br - 5), 2)
            plus = int(size * 0.5)
            pygame.draw.line(self.screen, (255,255,255), (cx - plus//2, cy), (cx + plus//2, cy), 2)
            pygame.draw.line(self.screen, (255,255,255), (cx, cy - plus//2), (cx, cy + plus//2), 2)
        elif buff.type == "blast_plus":
            L = int(size * 0.6)
            W = int(size * 0.2)
            for dx, dy in ((0,-1),(0,1),(-1,0),(1,0)):
                if dx == 0:
                    r = pygame.Rect(cx - W//2, cy - L if dy == -1 else cy, W, L)
                else:
                    r = pygame.Rect(cx - L if dx == -1 else cx, cy - W//2, L, W)
                pygame.draw.rect(self.screen, BUFF_BLAST_COLOR, r)
            pygame.draw.circle(self.screen, BUFF_BLAST_COLOR, (cx, cy), W)
        elif buff.type == "speed_plus":
            ah = int(size * 0.7)
            aw = int(size * 0.6)
            top_y = cy - ah//2
            bot_y = cy + ah//2
            left_x = cx - aw//2
            right_x = cx + aw//2
            pts = [(cx, top_y), (right_x, top_y + int(ah*0.4)),
                   (cx + int(aw*0.2), top_y + int(ah*0.4)),
                   (cx + int(aw*0.2), bot_y), (cx - int(aw*0.2), bot_y),
                   (cx - int(aw*0.2), top_y + int(ah*0.4)),
                   (left_x, top_y + int(ah*0.4))]
            pygame.draw.polygon(self.screen, BUFF_SPEED_COLOR, pts)
        else:
            font = pygame.font.Font(None, int(size * 1.8))
            text = font.render("?", True, (80, 80, 80))
            text_rect = text.get_rect(center=(cx, cy))
            self.screen.blit(text, text_rect)

    # ---------- 炸弹 ----------
    def draw_bomb(self, bomb, flicker):
        if flicker and int(bomb.timer * 10) % 2 == 0:
            return  # 闪烁效果
        cx, cy = int(bomb.pos_x), int(bomb.pos_y)
        r = int(cfg.CELL_SIZE * 0.35)
        pygame.draw.circle(self.screen, COLOR_BOMB_BODY, (cx, cy), r)
        pygame.draw.circle(self.screen, (60, 60, 60), (cx - r//3, cy - r//3), r//3)
        fuse_start = (cx, cy - r)
        fuse_end = (cx, cy - r - 8)
        pygame.draw.line(self.screen, COLOR_BOMB_FUSE, fuse_start, fuse_end, 3)
        spark_dx = random.randint(-2, 2)
        spark_dy = random.randint(-2, 2)
        pygame.draw.circle(self.screen, (255, 255, 0), (cx + spark_dx, cy - r - 10 + spark_dy), 3)

    # ---------- 爆炸 ----------
    def draw_explosion_cell(self, cell):
        gx, gy = cell
        left, top = grid_to_pixel(gx, gy)
        rect = pygame.Rect(left, top, cfg.CELL_SIZE, cfg.CELL_SIZE)
        intensity = random.random()
        r, g, b = 255, min(200, int(100 + 100 * intensity)), 0
        pygame.draw.rect(self.screen, (r, g, b), rect)
        pygame.draw.rect(self.screen, (200, 80, 0), rect, 2)

    # ---------- 玩家 ----------
    def draw_player(self, p):
        if not p.alive and p.death_timer > 0:
            progress = 1 - (p.death_timer / cfg.DEATH_ANIM_DUR)
            alpha = int(255 * (1 - progress))
            r = int(cfg.CELL_SIZE * 0.38 * (1 - progress))
            if r > 0 and alpha > 0:
                surf = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
                pygame.draw.circle(surf, (100, 100, 100, alpha), (r, r), r)
                self.screen.blit(surf, (int(p.pos_x - r), int(p.pos_y - r)))
            return
        if not p.alive:
            return

        color = p.color
        r = int(cfg.CELL_SIZE * 0.38)
        cx, cy = int(p.pos_x), int(p.pos_y)
        pygame.draw.circle(self.screen, color, (cx, cy), r)

        if "shield" in p.abilities:
            shield_r = r + 4
            if p.abilities["shield"] <= 2.0 * cfg.FPS and int(p.abilities["shield"] / cfg.FPS * 10) % 2 == 0:
                pass  # 闪烁时跳过绘制光环
            else:
                alpha_surf = pygame.Surface((shield_r*2, shield_r*2), pygame.SRCALPHA)
                pygame.draw.circle(alpha_surf, (*COLOR_SHIELD, 100), (shield_r, shield_r), shield_r)
                self.screen.blit(alpha_surf, (cx - shield_r, cy - shield_r))

        dir_x, dir_y = self.get_input_direction(p)
        if "reverse" in p.abilities:
            dir_x, dir_y = -dir_x, -dir_y
        eye_r = r // 3
        eye_offset = r // 2
        if dir_x > 0:
            left_eye = (cx + eye_offset, cy - eye_offset)
            right_eye = (cx + eye_offset, cy + eye_offset)
        elif dir_x < 0:
            left_eye = (cx - eye_offset, cy - eye_offset)
            right_eye = (cx - eye_offset, cy + eye_offset)
        elif dir_y < 0:
            left_eye = (cx - eye_offset, cy - eye_offset)
            right_eye = (cx + eye_offset, cy - eye_offset)
        else:
            left_eye = (cx - eye_offset, cy + eye_offset)
            right_eye = (cx + eye_offset, cy + eye_offset)

        pygame.draw.circle(self.screen, (255, 255, 255), left_eye, eye_r)
        pygame.draw.circle(self.screen, (255, 255, 255), right_eye, eye_r)
        pupil_r = eye_r // 2
        pygame.draw.circle(self.screen, (0, 0, 0), left_eye, pupil_r)
        pygame.draw.circle(self.screen, (0, 0, 0), right_eye, pupil_r)

    # ---------- 状态栏 ----------
    def draw_ui_bar(self):
        bar_rect = pygame.Rect(0, 0, get_map_width(), cfg.UI_BAR_HEIGHT)
        pygame.draw.rect(self.screen, COLOR_UI_BAR_BG, bar_rect)
        mid_x = get_map_width() // 2
        pygame.draw.line(self.screen, COLOR_TEXT, (mid_x, 10), (mid_x, cfg.UI_BAR_HEIGHT - 10), 2)

        # 红方
        red_text = self.font_big.render(f"Red: {self.red_player.wins}", True, COLOR_RED)
        self.screen.blit(red_text, (20, 8))
        bomb_start_x = 20 + red_text.get_width() + 15
        self.draw_bomb_indicators(bomb_start_x, 12, self.red_player.bomb_max, self.red_player.bomb_placed_count, True)
        ability_x = bomb_start_x + self.red_player.bomb_max * 16 + 15
        self.draw_ability_icons(ability_x, 10, self.red_player.abilities, True)

        # 蓝方
        blue_text = self.font_big.render(f"Blue: {self.blue_player.wins}", True, COLOR_BLUE)
        blue_rect = blue_text.get_rect(topright=(get_map_width() - 20, 8))
        self.screen.blit(blue_text, blue_rect)
        bomb_width = self.blue_player.bomb_max * 16
        bomb_start_x_right = blue_rect.left - bomb_width - 15
        self.draw_bomb_indicators(bomb_start_x_right, 12, self.blue_player.bomb_max, self.blue_player.bomb_placed_count, False)
        ability_x_right = bomb_start_x_right - 15
        self.draw_ability_icons(ability_x_right, 10, self.blue_player.abilities, False)

        timer_text = self.font_big.render(f"{int(self.round_time / cfg.FPS)}", True, COLOR_TEXT)
        timer_rect = timer_text.get_rect(center=(mid_x, cfg.UI_BAR_HEIGHT // 2))
        self.screen.blit(timer_text, timer_rect)

    def draw_bomb_indicators(self, start_x, y, bomb_max, bomb_placed, left_to_right):
        bomb_r = 6
        spacing = 16
        for i in range(bomb_max):
            idx = i if left_to_right else (bomb_max - 1 - i)
            cx = start_x + idx * spacing + bomb_r if left_to_right else start_x - idx * spacing - bomb_r
            cy = y + bomb_r
            if i < bomb_placed:
                pygame.draw.circle(self.screen, (80, 80, 80), (cx, cy), bomb_r)
            else:
                pygame.draw.circle(self.screen, (200, 200, 200), (cx, cy), bomb_r, 2)

    def draw_ability_icons(self, start_x, y, abilities, left_to_right):
        icon_size = 10
        spacing = 26
        ab_list = list(abilities.items())
        for i, (ability, remain) in enumerate(ab_list):
            idx = i if left_to_right else -i
            cx = start_x + idx * spacing + 11 if left_to_right else start_x + idx * spacing - 11
            cy = y + 12
            self.draw_ability_icon_graphic(cx, cy, ability, icon_size)
            time_str = f"{remain:.0f}s"
            time_surf = self.font_small.render(time_str, True, COLOR_TEXT)
            time_rect = time_surf.get_rect(center=(cx, cy + 16))
            self.screen.blit(time_surf, time_rect)

    def draw_ability_icon_graphic(self, cx, cy, ability, icon_size):
        col_map = {
            "kick": ABILITY_KICK_COLOR, "remote": ABILITY_REMOTE_COLOR,
            "shield": ABILITY_SHIELD_COLOR, "diarrhea": ABILITY_DIARRHEA_COLOR,
            "reverse": ABILITY_REVERSE_COLOR, "float": ABILITY_FLOAT_COLOR
        }
        col = col_map.get(ability, (255,255,255))
        pygame.draw.circle(self.screen, (*col, 180), (cx, cy), icon_size + 2)
        pygame.draw.circle(self.screen, (255, 255, 255, 220), (cx, cy), icon_size)

        if ability == "kick":
            pygame.draw.rect(self.screen, (180,40,40), (cx - icon_size*0.7, cy + icon_size*0.1, icon_size*1.4, icon_size*0.25), border_radius=2)
            pygame.draw.ellipse(self.screen, (220,80,80), (cx - icon_size*0.6, cy - icon_size*0.5, icon_size*1.2, icon_size*0.7))
            pygame.draw.line(self.screen, (255,255,255), (cx - icon_size*0.2, cy - icon_size*0.2), (cx + icon_size*0.2, cy - icon_size*0.2), 1)
            pygame.draw.line(self.screen, (255,255,255), (cx - icon_size*0.2, cy), (cx + icon_size*0.2, cy), 1)
        elif ability == "remote":
            pygame.draw.rect(self.screen, (50,100,180), (cx - icon_size*0.4, cy - icon_size*0.6, icon_size*0.8, icon_size*0.7), border_radius=3)
            cw = icon_size*0.4
            pygame.draw.rect(self.screen, (100,150,220), (cx - cw//2, cy - icon_size*0.4, cw, icon_size*0.5))
            pygame.draw.rect(self.screen, (100,150,220), (cx - icon_size*0.3, cy - cw//2 - icon_size*0.15, icon_size*0.6, cw))
            pygame.draw.circle(self.screen, (200,50,50), (cx + icon_size*0.3, cy - icon_size*0.4), int(icon_size*0.15))
        elif ability == "shield":
            pts = [(cx, cy - icon_size*0.7), (cx + icon_size*0.55, cy - icon_size*0.4),
                   (cx + icon_size*0.55, cy + icon_size*0.2), (cx, cy + icon_size*0.7),
                   (cx - icon_size*0.55, cy + icon_size*0.2), (cx - icon_size*0.55, cy - icon_size*0.4)]
            pygame.draw.polygon(self.screen, (30,180,100), pts)
            check_pts = [(cx - icon_size*0.25, cy), (cx - icon_size*0.05, cy + icon_size*0.2), (cx + icon_size*0.3, cy - icon_size*0.15)]
            pygame.draw.lines(self.screen, (255,255,255), False, check_pts, 2)
        elif ability == "diarrhea":
            pts = [(cx - icon_size*0.4, cy - icon_size*0.1), (cx - icon_size*0.5, cy + icon_size*0.4),
                   (cx - icon_size*0.2, cy + icon_size*0.7), (cx + icon_size*0.2, cy + icon_size*0.7),
                   (cx + icon_size*0.5, cy + icon_size*0.4), (cx + icon_size*0.4, cy - icon_size*0.1)]
            pygame.draw.polygon(self.screen, (100,60,20), pts)
            pygame.draw.circle(self.screen, (139,90,43), (cx, cy + int(icon_size*0.1)), int(icon_size*0.45))
            pygame.draw.circle(self.screen, (255,255,255), (cx - int(icon_size*0.15), cy + int(icon_size*0.05)), int(icon_size*0.1))
            pygame.draw.circle(self.screen, (255,255,255), (cx + int(icon_size*0.15), cy + int(icon_size*0.05)), int(icon_size*0.1))
        elif ability == "reverse":
            aw, ah = icon_size*0.7, icon_size*0.5
            l_pts = [(cx - icon_size*0.25, cy - ah/2), (cx - icon_size*0.65, cy), (cx - icon_size*0.25, cy + ah/2)]
            pygame.draw.polygon(self.screen, (150,70,220), l_pts)
            r_pts = [(cx + icon_size*0.25, cy - ah/2), (cx + icon_size*0.65, cy), (cx + icon_size*0.25, cy + ah/2)]
            pygame.draw.polygon(self.screen, (150,70,220), r_pts)
        else:  # float
            cloud_color = (200,200,200)
            pygame.draw.circle(self.screen, cloud_color, (cx - icon_size*0.3, cy + icon_size*0.1), int(icon_size*0.35))
            pygame.draw.circle(self.screen, cloud_color, (cx + icon_size*0.3, cy + icon_size*0.1), int(icon_size*0.35))
            pygame.draw.circle(self.screen, cloud_color, (cx, cy - icon_size*0.15), int(icon_size*0.45))
            pygame.draw.circle(self.screen, cloud_color, (cx, cy + icon_size*0.25), int(icon_size*0.3))

    # ---------- 比赛结束画面 ----------
    def draw_victory_screen(self):
        overlay = pygame.Surface((get_window_width(), get_window_height()), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))
        font = pygame.font.Font(None, 72)
        if self.red_player.wins >= cfg.WIN_SCORE:
            text = font.render("RED WINS!", True, COLOR_RED)
        else:
            text = font.render("BLUE WINS!", True, COLOR_BLUE)
        text_rect = text.get_rect(center=(get_window_width()//2, get_window_height()//2 - 40))
        self.screen.blit(text, text_rect)
        small_font = pygame.font.Font(None, 36)
        restart_text = small_font.render("Press R to restart", True, COLOR_TEXT)
        restart_rect = restart_text.get_rect(center=(get_window_width()//2, get_window_height()//2 + 40))
        self.screen.blit(restart_text, restart_rect)

    def draw_round_delay_overlay(self):
        overlay = pygame.Surface((get_window_width(), get_window_height()), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.screen.blit(overlay, (0, 0))
        font = pygame.font.Font(None, 48)
        text = font.render(f"Next round in {int(round(self.round_delay_timer / cfg.FPS))}...", True, COLOR_TEXT)
        text_rect = text.get_rect(center=(get_window_width()//2, get_window_height()//2))
        self.screen.blit(text, text_rect)

    # ==================== 设置面板 ====================
    def init_settings_ui(self):
        self.param_list = [
            ("CELL_SIZE", "int", 20, 80),
            ("MAP_COLS", "int", 13, 25),
            ("MAP_ROWS", "int", 9, 15),
            ("BRICK_GEN_PROB", "float", 0.0, 1.0),
            ("INIT_SPEED", "float", 0.5, 5.0),
            ("SPEED_INCREMENT", "float", 0.1, 1.0),
            ("MAX_SPEED", "float", 2.0, 10.0),
            ("INIT_BOMB_MAX", "int", 1, 10),
            ("MAX_BOMB_CAP", "int", 1, 15),
            ("INIT_BLAST_RANGE", "int", 1, 10),
            ("MAX_BLAST_RANGE", "int", 1, 15),
            ("BOMB_FUSE", "float", 1.0, 10.0),
            ("BOMB_FLICKER_START", "float", 0.1, 5.0),
            ("KICK_INIT_VEL", "float", 1.0, 10.0),
            ("KICK_ACCEL", "float", -5.0, -0.1),
            ("DEATH_ANIM_DUR", "float", 0.1, 2.0),
            ("SHIELD_INVINCIBLE_DUR", "float", 0.1, 2.0),
            ("WIN_SCORE", "int", 1, 20),
            ("ROUND_DELAY", "float", 1.0, 10.0),
            ("BRICK_DROP_PROB", "float", 0.0, 1.0),
            ("BUFF_PROTECTION_TIME", "float", 0.1, 5.0),
            ("REFRESH_INTERVAL", "float", 5.0, 60.0),
            ("WEIGHT_BOMB_PLUS", "float", 0.0, 1.0),
            ("WEIGHT_BLAST_PLUS", "float", 0.0, 1.0),
            ("WEIGHT_SPEED_PLUS", "float", 0.0, 1.0),
            ("WEIGHT_UNKNOWN", "float", 0.0, 1.0),
            ("DURATION_KICK", "float", 5.0, 60.0),
            ("DURATION_REMOTE", "float", 5.0, 60.0),
            ("DURATION_SHIELD", "float", 5.0, 60.0),
            ("DURATION_DIARRHEA", "float", 5.0, 60.0),
            ("DURATION_REVERSE", "float", 5.0, 60.0),
            ("DURATION_FLOAT", "float", 5.0, 60.0),
        ]
        self.settings_buttons = []

    def draw_settings_panel(self):
        panel = pygame.Surface((get_window_width(), get_window_height()), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 220))
        self.screen.blit(panel, (0, 0))
        font = pygame.font.Font(None, 30)
        y = 20
        for name, typ, lo, hi in self.param_list:
            if y > get_window_height() - 100:
                break
            val = getattr(cfg, name)
            text = font.render(f"{name}: {val:.2f}" if typ == "float" else f"{name}: {int(val)}", True, COLOR_TEXT)
            self.screen.blit(text, (50, y))
            y += 30
        hint = self.font_small.render("Press P to close settings. Click anywhere to RESET defaults.", True, COLOR_TEXT)
        self.screen.blit(hint, (50, get_window_height() - 80))
        if pygame.mouse.get_pressed()[0]:
            cfg.reset_defaults()
            self.safe_spots = self.compute_safe_spots()
            self.reset_match()

    def handle_settings_click(self, pos):
        cfg.reset_defaults()
        self.safe_spots = self.compute_safe_spots()
        self.reset_match()

    # ==================== 主循环 ====================
    def run(self):
        while self.running:
            dt = self.clock.tick(cfg.FPS) / 1000.0
            self.handle_events()
            if self.state not in (GameState.SETTINGS, GameState.SETTINGS_PAUSED):
                self.update(dt)
            self.render()
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    game = BombermanGame()
    game.run()
