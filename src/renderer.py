# renderer.py — all drawing logic, consumes GameSnapshot only

import pygame
import random
import math
from src.config import cfg
from src.constants import (
    COLOR_BG, COLOR_FLOOR, COLOR_STONE, COLOR_BRICK,
    COLOR_RED, COLOR_BLUE, COLOR_BOMB_BODY, COLOR_BOMB_FUSE,
    COLOR_EXPLOSION, COLOR_TEXT, COLOR_UI_BAR_BG, COLOR_SHIELD,
    BUFF_BOMB_COLOR, BUFF_BLAST_COLOR, BUFF_SPEED_COLOR, BUFF_UNKNOWN_COLOR,
    ABILITY_KICK_COLOR, ABILITY_REMOTE_COLOR, ABILITY_SHIELD_COLOR,
    ABILITY_DIARRHEA_COLOR, ABILITY_REVERSE_COLOR, ABILITY_FLOAT_COLOR,
    GameState,
    CELL_EMPTY, CELL_STONE, CELL_BRICK, CELL_BUFF, CELL_BOMB, CELL_EXPLOSION,
)
from src.utils import grid_to_pixel, grid_center, get_map_width, get_window_height
from src.models import GameSnapshot


class Renderer:
    """Read-only renderer. Consumes GameSnapshot, draws to screen."""

    def __init__(self, screen):
        self.screen = screen
        self.font_small = pygame.font.Font(None, 18)
        self.font_medium = pygame.font.Font(None, 24)
        self.font_big = pygame.font.Font(None, 48)

    # ── Main draw entry point ──

    def draw(self, snap):
        """Main draw call — reads GameSnapshot only. Caller handles pygame.display.flip()."""
        self._draw_map(snap)
        self._draw_buffs(snap)
        self._draw_bombs(snap)
        self._draw_explosions(snap)
        self._draw_players(snap)
        self._draw_ui_bar(snap)
        if snap.state == GameState.MATCH_END:
            self._draw_victory_screen(snap)
        elif snap.state == GameState.ROUND_END_DELAY:
            self._draw_round_delay_overlay(snap)

    # ── Map terrain ──

    def _draw_map(self, snap):
        for gx in range(1, cfg.MAP_COLS + 1):
            for gy in range(1, cfg.MAP_ROWS + 1):
                left, top = grid_to_pixel(gx, gy)
                rect = pygame.Rect(left, top, cfg.CELL_SIZE, cfg.CELL_SIZE)
                cell = snap.map_grid[gx][gy]
                if cell == CELL_EMPTY:
                    pygame.draw.rect(self.screen, COLOR_FLOOR, rect)
                    pygame.draw.rect(self.screen, (160, 160, 160), rect, 1)
                elif cell == CELL_STONE:
                    pygame.draw.rect(self.screen, COLOR_STONE, rect)
                    cx, cy = left + cfg.CELL_SIZE // 2, top + cfg.CELL_SIZE // 2
                    pygame.draw.line(self.screen, (60, 60, 60), (cx - 10, cy), (cx + 10, cy), 2)
                    pygame.draw.line(self.screen, (60, 60, 60), (cx, cy - 10), (cx, cy + 10), 2)
                elif cell == CELL_BRICK:
                    pygame.draw.rect(self.screen, COLOR_BRICK, rect)
                    pygame.draw.rect(self.screen, (180, 100, 40), rect, 2)
                    mid_y = top + cfg.CELL_SIZE // 2
                    pygame.draw.line(self.screen, (180, 100, 40), (left, mid_y),
                                     (left + cfg.CELL_SIZE, mid_y), 2)
                    third = cfg.CELL_SIZE // 3
                    pygame.draw.line(self.screen, (180, 100, 40), (left + third, top),
                                     (left + third, mid_y), 2)
                    pygame.draw.line(self.screen, (180, 100, 40),
                                     (left + 2 * third, mid_y),
                                     (left + 2 * third, top + cfg.CELL_SIZE), 2)

    # ── Buff items ──

    def _draw_buffs(self, snap):
        for buff in snap.buffs:
            cx, cy = buff.pos_x, buff.pos_y
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
                pygame.draw.circle(self.screen, (80, 80, 80), (cx - br // 3, cy - br // 3 - 1), br // 3)
                pygame.draw.line(self.screen, (255, 200, 0), (cx, cy - br), (cx, cy - br - 5), 2)
                plus = int(size * 0.5)
                pygame.draw.line(self.screen, (255, 255, 255), (cx - plus // 2, cy),
                                 (cx + plus // 2, cy), 2)
                pygame.draw.line(self.screen, (255, 255, 255), (cx, cy - plus // 2),
                                 (cx, cy + plus // 2), 2)
            elif buff.type == "blast_plus":
                L = int(size * 0.6)
                W = int(size * 0.2)
                for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                    if dx == 0:
                        r = pygame.Rect(cx - W // 2, cy - L if dy == -1 else cy, W, L)
                    else:
                        r = pygame.Rect(cx - L if dx == -1 else cx, cy - W // 2, L, W)
                    pygame.draw.rect(self.screen, BUFF_BLAST_COLOR, r)
                pygame.draw.circle(self.screen, BUFF_BLAST_COLOR, (cx, cy), W)
            elif buff.type == "speed_plus":
                ah = int(size * 0.7)
                aw = int(size * 0.6)
                top_y = cy - ah // 2
                bot_y = cy + ah // 2
                left_x = cx - aw // 2
                right_x = cx + aw // 2
                pts = [
                    (cx, top_y),
                    (right_x, top_y + int(ah * 0.4)),
                    (cx + int(aw * 0.2), top_y + int(ah * 0.4)),
                    (cx + int(aw * 0.2), bot_y),
                    (cx - int(aw * 0.2), bot_y),
                    (cx - int(aw * 0.2), top_y + int(ah * 0.4)),
                    (left_x, top_y + int(ah * 0.4)),
                ]
                pygame.draw.polygon(self.screen, BUFF_SPEED_COLOR, pts)
            else:
                font = pygame.font.Font(None, int(size * 1.8))
                text = font.render("?", True, (80, 80, 80))
                text_rect = text.get_rect(center=(cx, cy))
                self.screen.blit(text, text_rect)

    # ── Bombs ──

    def _draw_bombs(self, snap):
        for bomb in snap.bombs:
            flicker = (bomb.type in ("normal", "converted") and bomb.fuse_frames <= cfg.BOMB_FLICKER_START)
            if flicker and int(bomb.fuse_frames * 10) % 2 == 0:
                continue  # Flicker: skip drawing this frame
            cx, cy = int(bomb.pos_x), int(bomb.pos_y)
            r = int(cfg.CELL_SIZE * 0.35)
            pygame.draw.circle(self.screen, COLOR_BOMB_BODY, (cx, cy), r)
            pygame.draw.circle(self.screen, (60, 60, 60), (cx - r // 3, cy - r // 3), r // 3)
            fuse_start = (cx, cy - r)
            fuse_end = (cx, cy - r - 8)
            pygame.draw.line(self.screen, COLOR_BOMB_FUSE, fuse_start, fuse_end, 3)
            spark_dx = random.randint(-2, 2)
            spark_dy = random.randint(-2, 2)
            pygame.draw.circle(self.screen, (255, 255, 0), (cx + spark_dx, cy - r - 10 + spark_dy), 3)

    # ── Explosions ──

    def _draw_explosions(self, snap):
        for gx, gy in snap.explosion_cells:
            left, top = grid_to_pixel(gx, gy)
            rect = pygame.Rect(left, top, cfg.CELL_SIZE, cfg.CELL_SIZE)
            intensity = random.random()
            r, g, b = 255, min(200, int(100 + 100 * intensity)), 0
            pygame.draw.rect(self.screen, (r, g, b), rect)
            pygame.draw.rect(self.screen, (200, 80, 0), rect, 2)

    # ── Players ──

    def _draw_players(self, snap):
        for ps in snap.players:
            if not ps.alive and ps.death_timer > 0:
                progress = 1 - (ps.death_timer / cfg.DEATH_ANIM_DUR)
                alpha = int(255 * (1 - progress))
                r = int(cfg.CELL_SIZE * 0.38 * (1 - progress))
                if r > 0 and alpha > 0:
                    surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                    pygame.draw.circle(surf, (100, 100, 100, alpha), (r, r), r)
                    self.screen.blit(surf, (int(ps.pos_x - r), int(ps.pos_y - r)))
                continue
            if not ps.alive:
                continue

            color = ps.color
            r = int(cfg.CELL_SIZE * 0.38)
            cx, cy = int(ps.pos_x), int(ps.pos_y)
            pygame.draw.circle(self.screen, color, (cx, cy), r)

            # Shield aura
            if "shield" in ps.abilities:
                shield_r = r + 4
                if ps.abilities["shield"] <= 2.0 * cfg.FPS and int(ps.abilities["shield"] / cfg.FPS * 10) % 2 == 0:
                    pass  # Blink: skip aura this frame
                else:
                    alpha_surf = pygame.Surface((shield_r * 2, shield_r * 2), pygame.SRCALPHA)
                    pygame.draw.circle(alpha_surf, (*COLOR_SHIELD, 100), (shield_r, shield_r), shield_r)
                    self.screen.blit(alpha_surf, (cx - shield_r, cy - shield_r))

            # Direction eyes: use stored direction (reverse applied here)
            dir_x, dir_y = ps.dir_x, ps.dir_y
            if "reverse" in ps.abilities:
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

    # ── UI bar ──

    def _draw_ui_bar(self, snap):
        bar_rect = pygame.Rect(0, 0, get_map_width(), cfg.UI_BAR_HEIGHT)
        pygame.draw.rect(self.screen, COLOR_UI_BAR_BG, bar_rect)
        mid_x = get_map_width() // 2
        pygame.draw.line(self.screen, COLOR_TEXT, (mid_x, 10), (mid_x, cfg.UI_BAR_HEIGHT - 10), 2)

        # Red player (index 0)
        red_ps = snap.players[0]
        red_text = self.font_big.render(f"Red: {snap.scores['red']}", True, COLOR_RED)
        self.screen.blit(red_text, (20, 8))
        bomb_start_x = 20 + red_text.get_width() + 15
        self._draw_bomb_indicators(bomb_start_x, 12, red_ps.bomb_max, red_ps.bomb_placed_count, True)
        ability_x = bomb_start_x + red_ps.bomb_max * 16 + 15
        self._draw_ability_icons(ability_x, 10, red_ps.abilities, True)

        # Blue player (index 1)
        blue_ps = snap.players[1]
        blue_text = self.font_big.render(f"Blue: {snap.scores['blue']}", True, COLOR_BLUE)
        blue_rect = blue_text.get_rect(topright=(get_map_width() - 20, 8))
        self.screen.blit(blue_text, blue_rect)
        bomb_width = blue_ps.bomb_max * 16
        bomb_start_x_right = blue_rect.left - bomb_width - 15
        self._draw_bomb_indicators(bomb_start_x_right, 12, blue_ps.bomb_max, blue_ps.bomb_placed_count, False)
        ability_x_right = bomb_start_x_right - 15
        self._draw_ability_icons(ability_x_right, 10, blue_ps.abilities, False)

        # Timer
        timer_text = self.font_big.render(f"{int(snap.round_frame / cfg.FPS)}", True, COLOR_TEXT)
        timer_rect = timer_text.get_rect(center=(mid_x, cfg.UI_BAR_HEIGHT // 2))
        self.screen.blit(timer_text, timer_rect)

    # ── Bomb indicator dots ──

    def _draw_bomb_indicators(self, start_x, y, bomb_max, bomb_placed, left_to_right):
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

    # ── Ability icons in UI bar ──

    def _draw_ability_icons(self, start_x, y, abilities, left_to_right):
        icon_size = 10
        spacing = 26
        ab_list = list(abilities.items())
        for i, (ability, remain) in enumerate(ab_list):
            idx = i if left_to_right else -i
            cx = start_x + idx * spacing + 11 if left_to_right else start_x + idx * spacing - 11
            cy = y + 12
            self._draw_ability_icon_graphic(cx, cy, ability, icon_size)
            time_str = f"{remain:.0f}s"
            time_surf = self.font_small.render(time_str, True, COLOR_TEXT)
            time_rect = time_surf.get_rect(center=(cx, cy + 16))
            self.screen.blit(time_surf, time_rect)

    def _draw_ability_icon_graphic(self, cx, cy, ability, icon_size):
        col_map = {
            "kick": ABILITY_KICK_COLOR, "remote": ABILITY_REMOTE_COLOR,
            "shield": ABILITY_SHIELD_COLOR, "diarrhea": ABILITY_DIARRHEA_COLOR,
            "reverse": ABILITY_REVERSE_COLOR, "float": ABILITY_FLOAT_COLOR,
        }
        col = col_map.get(ability, (255, 255, 255))
        pygame.draw.circle(self.screen, (*col, 180), (cx, cy), icon_size + 2)
        pygame.draw.circle(self.screen, (255, 255, 255, 220), (cx, cy), icon_size)

        if ability == "kick":
            pygame.draw.rect(self.screen, (180, 40, 40),
                             (cx - icon_size * 0.7, cy + icon_size * 0.1,
                              icon_size * 1.4, icon_size * 0.25), border_radius=2)
            pygame.draw.ellipse(self.screen, (220, 80, 80),
                                (cx - icon_size * 0.6, cy - icon_size * 0.5,
                                 icon_size * 1.2, icon_size * 0.7))
            pygame.draw.line(self.screen, (255, 255, 255),
                             (cx - icon_size * 0.2, cy - icon_size * 0.2),
                             (cx + icon_size * 0.2, cy - icon_size * 0.2), 1)
            pygame.draw.line(self.screen, (255, 255, 255),
                             (cx - icon_size * 0.2, cy),
                             (cx + icon_size * 0.2, cy), 1)
        elif ability == "remote":
            pygame.draw.rect(self.screen, (50, 100, 180),
                             (cx - icon_size * 0.4, cy - icon_size * 0.6,
                              icon_size * 0.8, icon_size * 0.7), border_radius=3)
            cw = icon_size * 0.4
            pygame.draw.rect(self.screen, (100, 150, 220),
                             (cx - cw // 2, cy - icon_size * 0.4, cw, icon_size * 0.5))
            pygame.draw.rect(self.screen, (100, 150, 220),
                             (cx - icon_size * 0.3, cy - cw // 2 - icon_size * 0.15,
                              icon_size * 0.6, cw))
            pygame.draw.circle(self.screen, (200, 50, 50),
                               (cx + icon_size * 0.3, cy - icon_size * 0.4),
                               int(icon_size * 0.15))
        elif ability == "shield":
            pts = [(cx, cy - icon_size * 0.7),
                   (cx + icon_size * 0.55, cy - icon_size * 0.4),
                   (cx + icon_size * 0.55, cy + icon_size * 0.2),
                   (cx, cy + icon_size * 0.7),
                   (cx - icon_size * 0.55, cy + icon_size * 0.2),
                   (cx - icon_size * 0.55, cy - icon_size * 0.4)]
            pygame.draw.polygon(self.screen, (30, 180, 100), pts)
            check_pts = [(cx - icon_size * 0.25, cy),
                         (cx - icon_size * 0.05, cy + icon_size * 0.2),
                         (cx + icon_size * 0.3, cy - icon_size * 0.15)]
            pygame.draw.lines(self.screen, (255, 255, 255), False, check_pts, 2)
        elif ability == "diarrhea":
            pts = [(cx - icon_size * 0.4, cy - icon_size * 0.1),
                   (cx - icon_size * 0.5, cy + icon_size * 0.4),
                   (cx - icon_size * 0.2, cy + icon_size * 0.7),
                   (cx + icon_size * 0.2, cy + icon_size * 0.7),
                   (cx + icon_size * 0.5, cy + icon_size * 0.4),
                   (cx + icon_size * 0.4, cy - icon_size * 0.1)]
            pygame.draw.polygon(self.screen, (100, 60, 20), pts)
            pygame.draw.circle(self.screen, (139, 90, 43), (cx, cy + int(icon_size * 0.1)),
                               int(icon_size * 0.45))
            pygame.draw.circle(self.screen, (255, 255, 255),
                               (cx - int(icon_size * 0.15), cy + int(icon_size * 0.05)),
                               int(icon_size * 0.1))
            pygame.draw.circle(self.screen, (255, 255, 255),
                               (cx + int(icon_size * 0.15), cy + int(icon_size * 0.05)),
                               int(icon_size * 0.1))
        elif ability == "reverse":
            ah = icon_size * 0.5
            l_pts = [(cx - icon_size * 0.25, cy - ah / 2),
                     (cx - icon_size * 0.65, cy),
                     (cx - icon_size * 0.25, cy + ah / 2)]
            pygame.draw.polygon(self.screen, (150, 70, 220), l_pts)
            r_pts = [(cx + icon_size * 0.25, cy - ah / 2),
                     (cx + icon_size * 0.65, cy),
                     (cx + icon_size * 0.25, cy + ah / 2)]
            pygame.draw.polygon(self.screen, (150, 70, 220), r_pts)
        else:  # float
            cloud_color = (200, 200, 200)
            pygame.draw.circle(self.screen, cloud_color,
                               (cx - icon_size * 0.3, cy + icon_size * 0.1),
                               int(icon_size * 0.35))
            pygame.draw.circle(self.screen, cloud_color,
                               (cx + icon_size * 0.3, cy + icon_size * 0.1),
                               int(icon_size * 0.35))
            pygame.draw.circle(self.screen, cloud_color,
                               (cx, cy - icon_size * 0.15),
                               int(icon_size * 0.45))
            pygame.draw.circle(self.screen, cloud_color,
                               (cx, cy + icon_size * 0.25),
                               int(icon_size * 0.3))

    # ── Victory screen overlay ──

    def _draw_victory_screen(self, snap):
        overlay = pygame.Surface((get_window_width(), get_window_height()), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))
        font = pygame.font.Font(None, 72)
        if snap.scores['red'] >= cfg.WIN_SCORE:
            text = font.render("RED WINS!", True, COLOR_RED)
        else:
            text = font.render("BLUE WINS!", True, COLOR_BLUE)
        text_rect = text.get_rect(center=(get_window_width() // 2, get_window_height() // 2 - 40))
        self.screen.blit(text, text_rect)
        small_font = pygame.font.Font(None, 36)
        restart_text = small_font.render("Press R to restart", True, COLOR_TEXT)
        restart_rect = restart_text.get_rect(center=(get_window_width() // 2, get_window_height() // 2 + 40))
        self.screen.blit(restart_text, restart_rect)

    # ── Round delay overlay ──

    def _draw_round_delay_overlay(self, snap):
        overlay = pygame.Surface((get_window_width(), get_window_height()), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.screen.blit(overlay, (0, 0))
        font = pygame.font.Font(None, 48)
        text = font.render(
            f"Next round in {int(round(snap.round_delay_timer / cfg.FPS))}...",
            True, COLOR_TEXT,
        )
        text_rect = text.get_rect(center=(get_window_width() // 2, get_window_height() // 2))
        self.screen.blit(text, text_rect)
