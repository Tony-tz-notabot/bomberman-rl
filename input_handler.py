"""
Input handler — per-player key state tracking with edge detection for action buttons.
"""
import pygame


class InputHandler:
    """Tracks keyboard state for two players and builds action dicts."""

    def __init__(self):
        self.keys = {
            "red": {"W": False, "A": False, "S": False, "D": False, "E": False, "Q": False},
            "blue": {"UP": False, "LEFT": False, "DOWN": False, "RIGHT": False, "DEL": False, "END": False},
        }
        self.prev_action = {"red": False, "blue": False}

    def press(self, key):
        """Call on KEYDOWN to mark a key as pressed."""
        self._set(key, True)

    def release(self, key):
        """Call on KEYUP to mark a key as released."""
        self._set(key, False)

    # ------------------------------------------------------------------
    def _set(self, key, value):
        """Map pygame key constant to internal key name and set its state."""
        if key == pygame.K_w:
            self.keys["red"]["W"] = value
        elif key == pygame.K_a:
            self.keys["red"]["A"] = value
        elif key == pygame.K_s:
            self.keys["red"]["S"] = value
        elif key == pygame.K_d:
            self.keys["red"]["D"] = value
        elif key == pygame.K_e:
            self.keys["red"]["E"] = value
        elif key == pygame.K_q:
            self.keys["red"]["Q"] = value
        elif key == pygame.K_UP:
            self.keys["blue"]["UP"] = value
        elif key == pygame.K_LEFT:
            self.keys["blue"]["LEFT"] = value
        elif key == pygame.K_DOWN:
            self.keys["blue"]["DOWN"] = value
        elif key == pygame.K_RIGHT:
            self.keys["blue"]["RIGHT"] = value
        elif key == pygame.K_DELETE:
            self.keys["blue"]["DEL"] = value
        elif key == pygame.K_END:
            self.keys["blue"]["END"] = value

    # ------------------------------------------------------------------
    def build_actions(self):
        """Return (p1_actions, p2_actions) from current key state.

        Each dict has keys: up, down, left, right, action (edge-triggered),
        ignite.
        """
        p1 = self._player_actions("red")
        p2 = self._player_actions("blue")
        return p1, p2

    def _player_actions(self, color):
        keys = self.keys[color]
        is_red = color == "red"

        cur_action = keys["E"] if is_red else keys["DEL"]
        # Rising-edge trigger: only true when key transitions from released to held
        action_triggered = cur_action and not self.prev_action[color]
        self.prev_action[color] = cur_action

        return {
            "up": keys["W"] if is_red else keys["UP"],
            "down": keys["S"] if is_red else keys["DOWN"],
            "left": keys["A"] if is_red else keys["LEFT"],
            "right": keys["D"] if is_red else keys["RIGHT"],
            "action": action_triggered,
            "ignite": keys["Q"] if is_red else keys["END"],
        }
