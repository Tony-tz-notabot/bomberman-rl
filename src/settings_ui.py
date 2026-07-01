# settings_ui.py — settings overlay panel

import pygame
from src.config import cfg
from src.constants import COLOR_TEXT
from src.utils import get_window_width, get_window_height


class SettingsUI:
    def __init__(self):
        self.font = pygame.font.Font(None, 30)
        self.font_small = pygame.font.Font(None, 18)
        self.scroll = 0
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
            ("BOMB_FUSE", "int", 12, 240),
            ("BOMB_FLICKER_START", "int", 2, 120),
            ("KICK_INIT_VEL", "float", 1.0, 10.0),
            ("KICK_ACCEL", "float", -5.0, -0.1),
            ("DEATH_ANIM_DUR", "int", 2, 48),
            ("SHIELD_INVINCIBLE_DUR", "int", 2, 48),
            ("WIN_SCORE", "int", 1, 20),
            ("ROUND_DELAY", "int", 24, 240),
            ("BRICK_DROP_PROB", "float", 0.0, 1.0),
            ("BUFF_PROTECTION_TIME", "int", 1, 120),
            ("REFRESH_INTERVAL", "int", 120, 1440),
            ("WEIGHT_BOMB_PLUS", "float", 0.0, 1.0),
            ("WEIGHT_BLAST_PLUS", "float", 0.0, 1.0),
            ("WEIGHT_SPEED_PLUS", "float", 0.0, 1.0),
            ("WEIGHT_UNKNOWN", "float", 0.0, 1.0),
            ("DURATION_KICK", "int", 120, 1440),
            ("DURATION_REMOTE", "int", 120, 1440),
            ("DURATION_SHIELD", "int", 120, 1440),
            ("DURATION_DIARRHEA", "int", 120, 1440),
            ("DURATION_REVERSE", "int", 120, 1440),
            ("DURATION_FLOAT", "int", 120, 1440),
        ]

    def draw(self, screen, engine):
        """Draw settings overlay."""
        panel = pygame.Surface((get_window_width(), get_window_height()), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 220))
        screen.blit(panel, (0, 0))
        y = 20
        for name, typ, lo, hi in self.param_list:
            if y > get_window_height() - 100:
                break
            val = getattr(cfg, name)
            text = self.font.render(
                f"{name}: {val:.2f}" if typ == "float" else f"{name}: {int(val)}",
                True, COLOR_TEXT)
            screen.blit(text, (50, y))
            y += 30
        # Hints
        hint = self.font_small.render(
            "Press P to close settings. Click anywhere to RESET defaults.",
            True, COLOR_TEXT)
        screen.blit(hint, (50, get_window_height() - 80))

    def handle_click(self, pos, engine):
        """Reset defaults on click."""
        cfg.reset_defaults()
        engine.safe_spots = engine.compute_safe_spots()
        engine.reset_match()
