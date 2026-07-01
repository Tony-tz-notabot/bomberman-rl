"""
bomberman version 2.0.2
"""
import pygame
import sys

from config import cfg

from utils import (
    get_window_width, get_window_height,
)
from constants import (
    COLOR_BG, COLOR_TEXT,
    GameState,
)
from game_engine import GameEngine
from renderer import Renderer
from input_handler import InputHandler

# ==================== 主游戏类 ====================
class BombermanGame:
    def __init__(self):
        pygame.init()
        self.engine = GameEngine()
        self.screen = pygame.display.set_mode((get_window_width(), get_window_height()), pygame.RESIZABLE)
        pygame.display.set_caption("炸弹人 双人PVP v2.8")
        self.renderer = Renderer(self.screen)
        self.clock = pygame.time.Clock()
        self.running = True
        self.input_handler = InputHandler()
        # 设置面板
        self.show_settings = False
        self.settings_pause_state = None
        self.settings_buttons = []
        self.settings_scroll = 0
        self.init_settings_ui()
        # 字体 (settings panel uses self.font_small)
        self.font_small = pygame.font.Font(None, 18)

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

    # ==================== 输入处理 ====================
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self.input_handler.press(event.key)
                self._check_menu_key(event.key)
            elif event.type == pygame.KEYUP:
                self.input_handler.release(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if self.state in (GameState.SETTINGS, GameState.SETTINGS_PAUSED):
                    self.handle_settings_click(event.pos)

    def _check_menu_key(self, key):
        """Handle state-transition keys (ENTER, R, P)."""
        if self.state == GameState.MENU:
            if key == pygame.K_RETURN:
                self.engine.reset_match()
            return
        if self.state == GameState.MATCH_END:
            if key == pygame.K_r:
                self.engine.reset_match()
            return
        if self.state in (GameState.SETTINGS, GameState.SETTINGS_PAUSED):
            if key == pygame.K_p:
                self.toggle_settings()
            return

        if key == pygame.K_p:
            self.toggle_settings()
            return

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
        p1_actions, p2_actions = self.input_handler.build_actions()
        self.engine.step(p1_actions, p2_actions)

    # ==================== 渲染 ====================
    def render(self):
        self.screen.fill(COLOR_BG)
        if self.state in (GameState.SETTINGS, GameState.SETTINGS_PAUSED):
            self.draw_settings_panel()
        else:
            snapshot = self.engine.get_snapshot()
            self.renderer.draw(snapshot)
        pygame.display.flip()

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
