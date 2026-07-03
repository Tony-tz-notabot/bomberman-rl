"""
bomberman version 2.0.2
"""
import pygame
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import cfg

from src.utils import (
    get_window_width, get_window_height,
)
from src.constants import (
    COLOR_BG,
    GameState,
)
from src.game_engine import GameEngine
from src.renderer import Renderer
from src.input_handler import InputHandler
from src.settings_ui import SettingsUI

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
        self.settings_pause_state = None
        self.settings_ui = SettingsUI()

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
                if self.engine.state in (GameState.ROUND_RUNNING, GameState.ROUND_END_DELAY):
                    self.input_handler.press(event.key)
                self._check_menu_key(event.key)
            elif event.type == pygame.KEYUP:
                if self.engine.state in (GameState.ROUND_RUNNING, GameState.ROUND_END_DELAY):
                    self.input_handler.release(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if self.state in (GameState.SETTINGS, GameState.SETTINGS_PAUSED):
                    self.settings_ui.handle_click(event.pos, self.engine)

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
            self.settings_ui.draw(self.screen, self.engine)
        else:
            snapshot = self.engine.get_snapshot()
            self.renderer.draw(snapshot)
        pygame.display.flip()

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
