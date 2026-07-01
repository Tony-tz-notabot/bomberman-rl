"""
bomberman version 2.0.2
"""
import pygame
import random
import sys

from config import Config, cfg

from utils import (
    grid_to_pixel, grid_center, pixel_to_grid, clamp, sign,
    get_map_width, get_map_height, get_window_width, get_window_height,
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
from models import Player, Bomb, BuffItem
from game_engine import GameEngine

# ==================== 主游戏类 ====================
class BombermanGame:
    def __init__(self):
        pygame.init()
        self.engine = GameEngine()
        self.screen = pygame.display.set_mode((get_window_width(), get_window_height()), pygame.RESIZABLE)
        pygame.display.set_caption("炸弹人 双人PVP v2.8")
        self.clock = pygame.time.Clock()
        self.running = True
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
        # Previous references kept as properties for backward compat
        self.state = self.engine.state

    # ── Forward game state to engine ──

    @property
    def grid(self): return self.engine.grid

    @property
    def red_player(self): return self.engine.red_player

    @property
    def blue_player(self): return self.engine.blue_player

    @property
    def bombs(self): return self.engine.bombs

    @property
    def buffs(self): return self.engine.buffs

    @property
    def explosion_cells(self): return self.engine.explosion_cells

    @property
    def state(self): return self.engine.state

    @state.setter
    def state(self, val): self.engine.state = val

    @property
    def round_time(self): return self.engine.round_frame

    @property
    def round_delay_timer(self): return self.engine.round_delay_timer

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

    def handle_key(self, key, pressed):
        if self.state == GameState.MENU:
            if pressed and key == pygame.K_RETURN:
                self.engine.reset_match()
            return
        if self.state == GameState.MATCH_END:
            if pressed and key == pygame.K_r:
                self.engine.reset_match()
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
    def update(self, _dt_unused=None):
        # Build action dicts from keyboard state
        p1_actions = self._build_red_actions()
        p2_actions = self._build_blue_actions()
        self.engine.step(p1_actions, p2_actions)
        # Update prev_action for edge detection next frame
        self.red_player.prev_action = p1_actions.get("action", False)
        self.blue_player.prev_action = p2_actions.get("action", False)

    def _build_red_actions(self):
        return {
            "up": self.keys_red['W'],
            "down": self.keys_red['S'],
            "left": self.keys_red['A'],
            "right": self.keys_red['D'],
            "action": self.keys_red['E'] and not self.red_player.prev_action,
            "ignite": self.keys_red['Q'],
        }

    def _build_blue_actions(self):
        return {
            "up": self.keys_blue['UP'],
            "down": self.keys_blue['DOWN'],
            "left": self.keys_blue['LEFT'],
            "right": self.keys_blue['RIGHT'],
            "action": self.keys_blue['DEL'] and not self.blue_player.prev_action,
            "ignite": self.keys_blue['END'],
        }

    # Forwarder used by rendering (draw_player looks at input direction)
    def get_input_direction(self, p):
        return self.engine._get_input_direction(p)

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
                flicker = (bomb.type in ("normal", "converted") and bomb.fuse_frames <= cfg.BOMB_FLICKER_START)
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
        if flicker and int(bomb.fuse_frames * 10) % 2 == 0:
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
            self.engine.safe_spots = self.engine.compute_safe_spots()
            self.engine.reset_match()

    def handle_settings_click(self, pos):
        cfg.reset_defaults()
        self.engine.safe_spots = self.engine.compute_safe_spots()
        self.engine.reset_match()

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
