"""Phase 1 curriculum reward: basic operations and survival learning."""
import math
from typing import Optional, Dict, Any
from src.config import cfg
from src.constants import CELL_STONE, CELL_BRICK
from src.utils import pixel_to_grid, grid_center
from rewards import RewardFunction


class Phase1Reward(RewardFunction):
    _DEFAULT_CFG = {
        "reward_approach": 0.033, "reward_approach_window": 10,
        "penalty_retreat": 0.007,
        "penalty_center_dev": 0.013,
        "penalty_stall_threshold": 30, "penalty_stall_init": 0.007, "penalty_stall_cap": 0.167,
        "penalty_wall": 0.01,
        "reward_survive": 0.0,  # was 0.0003
        "penalty_survive_time": 0.002,  # Phase 1.1 only: per-frame drain to create urgency
        "penalty_illegal_bomb_cap": 0.033,
        "penalty_illegal_ignite": 0.017, "penalty_illegal_dir": 0.017,
        "penalty_death_self": 0.333, "penalty_death_opp": 0.167,
        "penalty_death_self_bomb": 1.0, "penalty_death_opp_bomb": 0.5,
        "reward_place_bomb": 0.033,
        "reward_kill_opponent": 1.333,
        "reward_destroy_brick_fwd": 0.167, "reward_destroy_brick_side": 0.033,
        "penalty_bomb_wasted": 0.067,
        "reward_pickup_normal": 0.067, "reward_pickup_unknown": 0.1,
        "phase": 1.1,
    }
    _PHASE_WEIGHTS = {
        1.1: {"p11": 1.0, "p12": 0.0, "p13": 0.0},
        1.2: {"p11": 0.5, "p12": 1.0, "p13": 0.0},
        1.3: {"p11": 0.25, "p12": 0.5, "p13": 1.0},
    }
    def __init__(self, config=None):
        self.cfg = dict(self._DEFAULT_CFG)
        if config:
            self.cfg.update(config)
        self.reset()
    def reset(self, episode_info=None):
        self._frame = 0
        self._pos_buffer = []
        self._prev_avg_x = self._prev_avg_y = None
        self._prev_mdist = None
        self._stall_frames = 0
    def __call__(self, engine, prev_snap, snap, action, agent_id):
        self._frame += 1
        w = self._PHASE_WEIGHTS.get(self.cfg["phase"], self._PHASE_WEIGHTS[1.1])
        curr_self = snap.players[0] if snap.players[0].id == agent_id else snap.players[1]
        opp = snap.players[1] if curr_self is snap.players[0] else snap.players[0]
        prev_self = prev_snap.players[0] if prev_snap.players[0].id == agent_id else prev_snap.players[1]
        gx, gy = pixel_to_grid(curr_self.pos_x, curr_self.pos_y)
        opp_gx, opp_gy = opp.grid_x, opp.grid_y
        curr_mdist = abs(gx - opp_gx) + abs(gy - opp_gy)
        reward = 0.0
        reward += w["p11"] * self._survival(curr_self.alive)
        reward += w["p11"] * self._approach_and_retreat(gx, gy, opp_gx, opp_gy, curr_mdist)
        reward += w["p11"] * self._center_deviation(curr_self)
        reward += w["p11"] * self._stall(curr_mdist)
        reward += w["p11"] * self._wall_collision(action[:4], prev_self, curr_self)
        reward += w["p11"] * self._illegal_action(action[4], action[5], action[:4], prev_self, curr_self)
        reward += w["p11"] * self._death(prev_self, prev_snap, snap, agent_id)
        if w["p12"] > 0:
            reward += w["p12"] * self._bomb_placement(prev_self, curr_self)
            reward += w["p12"] * self._brick_destruction(prev_snap, snap, agent_id)
            reward += w["p12"] * self._wasted_bomb(prev_snap, snap, agent_id)
            reward += w["p12"] * self._kill_opponent(prev_snap, snap, agent_id)
        if w["p13"] > 0:
            reward += w["p13"] * self._buff_pickup(prev_snap, snap, agent_id)
        self._prev_mdist = curr_mdist
        return reward

    # ── Phase 1.1: Basic survival & movement ──

    def _survival(self, alive: bool) -> float:
        if not alive:
            return 0.0
        # Phase 1.1: no bombs, can't die — per-frame penalty creates urgency to reach blue
        if int(self.cfg.get("phase", 1.1) * 10) == 11:
            return -self.cfg.get("penalty_survive_time", 0.002)
        return self.cfg.get("reward_survive", 0.0)

    def _approach_and_retreat(self, gx, gy, opp_gx, opp_gy, curr_mdist) -> float:
        reward = 0.0
        window = self.cfg["reward_approach_window"]
        self._pos_buffer.append((gx, gy))
        if len(self._pos_buffer) > window:
            self._pos_buffer.pop(0)
        # Per-frame retreat penalty
        if self._prev_mdist is not None and curr_mdist > self._prev_mdist:
            reward -= self.cfg["penalty_retreat"] * (curr_mdist - self._prev_mdist)
        # Windowed approach reward (every `window` frames)
        if len(self._pos_buffer) == window:
            avg_x = sum(p[0] for p in self._pos_buffer) / window
            avg_y = sum(p[1] for p in self._pos_buffer) / window
            if self._prev_avg_x is not None:
                prev_avg_dist = abs(self._prev_avg_x - opp_gx) + abs(self._prev_avg_y - opp_gy)
                curr_avg_dist = abs(avg_x - opp_gx) + abs(avg_y - opp_gy)
                if curr_avg_dist < prev_avg_dist:
                    reward += self.cfg["reward_approach"] * (prev_avg_dist - curr_avg_dist)
            self._prev_avg_x, self._prev_avg_y = avg_x, avg_y
        return reward

    def _center_deviation(self, player) -> float:
        gx, gy = player.grid_x, player.grid_y
        if gx % 2 == 0 and gy % 2 == 0:
            return 0.0  # stone cell — shouldn't occur
        cx, cy = grid_center(gx, gy)
        if gx % 2 == 1 and gy % 2 == 1:
            dev = min(abs(player.pos_x - cx), abs(player.pos_y - cy))
        elif gy % 2 == 1:
            dev = abs(player.pos_y - cy)  # horizontal corridor: Y deviation
        else:
            dev = abs(player.pos_x - cx)  # vertical corridor: X deviation
        norm = dev / (cfg.CELL_SIZE / 2)
        return -self.cfg["penalty_center_dev"] * (norm * norm)

    def _stall(self, curr_mdist) -> float:
        if self._prev_mdist is not None and curr_mdist < self._prev_mdist:
            self._stall_frames = 0
        else:
            self._stall_frames += 1
        threshold = self.cfg["penalty_stall_threshold"]
        if self._stall_frames > threshold:
            penalty = self.cfg["penalty_stall_init"] * (self._stall_frames - threshold)
            return -min(penalty, self.cfg["penalty_stall_cap"])
        return 0.0

    def _wall_collision(self, dir4, prev_self, curr_self) -> float:
        reward = 0.0
        if (dir4[2] or dir4[3]) and abs(curr_self.pos_x - prev_self.pos_x) < 0.001:
            reward -= self.cfg["penalty_wall"]
        if (dir4[0] or dir4[1]) and abs(curr_self.pos_y - prev_self.pos_y) < 0.001:
            reward -= self.cfg["penalty_wall"]
        return reward

    def _illegal_action(self, action_val, ignite_val, dir4, prev_self, curr_self) -> float:
        reward = 0.0
        if action_val and curr_self.bomb_placed_count == prev_self.bomb_placed_count:
            reward -= self.cfg["penalty_illegal_bomb_cap"]
        if ignite_val:
            reward -= self.cfg["penalty_illegal_ignite"]
        if sum(dir4) > 2:
            reward -= self.cfg["penalty_illegal_dir"]
        return reward

    def _death(self, prev_self, prev_snap, snap, agent_id) -> float:
        # Did the agent die this frame?
        curr_self = snap.players[0] if snap.players[0].id == agent_id else snap.players[1]
        if not (prev_self.alive and not curr_self.alive):
            return 0.0
        death_cell = (curr_self.grid_x, curr_self.grid_y)
        our_expired = {b.id for b in prev_snap.bombs if b.owner == agent_id}
        remain = {b.id for b in snap.bombs}
        exploded_ids = our_expired - remain
        self_death = False
        for b in prev_snap.bombs:
            if b.id in exploded_ids:
                player_snap = prev_snap.players[0] if prev_snap.players[0].id == agent_id else prev_snap.players[1]
                cells = self._explosion_cells_set(b.grid_x, b.grid_y, prev_snap.map_grid, player_snap.blast_range)
                if death_cell in cells:
                    self_death = True
                    break
        is_p12 = self.cfg.get("phase", 1.1) >= 1.2
        if self_death:
            return -self.cfg["penalty_death_self_bomb" if is_p12 else "penalty_death_self"]
        return -self.cfg["penalty_death_opp_bomb" if is_p12 else "penalty_death_opp"]

    @staticmethod
    def _explosion_cells_set(gx, gy, map_grid, blast_range):
        cells = {(gx, gy)}
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for i in range(1, blast_range + 1):
                nx, ny = gx + dx * i, gy + dy * i
                if nx < 1 or nx > cfg.MAP_COLS or ny < 1 or ny > cfg.MAP_ROWS:
                    break
                cells.add((nx, ny))
                if map_grid[nx][ny] in (CELL_STONE, CELL_BRICK):
                    break
        return cells

    # ── Phase 1.2: Bomb & brick interaction ──

    def _bomb_placement(self, prev_self, curr_self) -> float:
        if curr_self.bomb_placed_count > prev_self.bomb_placed_count:
            return self.cfg["reward_place_bomb"]
        return 0.0

    def _brick_destruction(self, prev_snap, snap, agent_id) -> float:
        destroyed = []
        for x in range(1, cfg.MAP_COLS + 1):
            for y in range(1, cfg.MAP_ROWS + 1):
                if prev_snap.map_grid[x][y] == CELL_BRICK and snap.map_grid[x][y] != CELL_BRICK:
                    destroyed.append((x, y))
        if not destroyed:
            return 0.0
        our_exploded = [b for b in prev_snap.bombs
                        if b.owner == agent_id and not any(sb.id == b.id for sb in snap.bombs)]
        if not our_exploded:
            return 0.0
        # Precompute explosion cells for each of our bombs
        player_state = prev_snap.players[0] if prev_snap.players[0].id == agent_id else prev_snap.players[1]
        bomb_cells = {}
        for b in our_exploded:
            bomb_cells[b.id] = self._explosion_cells_set(b.grid_x, b.grid_y, prev_snap.map_grid, player_state.blast_range)
        opp = snap.players[1] if snap.players[0].id == agent_id else snap.players[0]
        opp_gx, opp_gy = opp.grid_x, opp.grid_y
        reward = 0.0
        for bx, by in destroyed:
            best_dist = float('inf')
            bomb_pos = None
            for b in our_exploded:
                if (bx, by) in bomb_cells[b.id]:
                    d = abs(bx - b.grid_x) + abs(by - b.grid_y)
                    if d < best_dist:
                        best_dist = d
                        bomb_pos = (b.grid_x, b.grid_y)
            if bomb_pos is not None:
                dot = (opp_gx - bomb_pos[0]) * (bx - bomb_pos[0]) + (opp_gy - bomb_pos[1]) * (by - bomb_pos[1])
                reward += self.cfg["reward_destroy_brick_fwd"] if dot > 0 else self.cfg["reward_destroy_brick_side"]
        return reward

    def _wasted_bomb(self, prev_snap, snap, agent_id) -> float:
        our_exploded = [b for b in prev_snap.bombs
                        if b.owner == agent_id and not any(sb.id == b.id for sb in snap.bombs)]
        if not our_exploded:
            return 0.0
        bricks_destroyed = 0
        for x in range(1, cfg.MAP_COLS + 1):
            for y in range(1, cfg.MAP_ROWS + 1):
                if prev_snap.map_grid[x][y] == CELL_BRICK and snap.map_grid[x][y] != CELL_BRICK:
                    bricks_destroyed += 1
        if bricks_destroyed == 0:
            return -self.cfg["penalty_bomb_wasted"] * len(our_exploded)
        return 0.0

    def _kill_opponent(self, prev_snap, snap, agent_id) -> float:
        """+4.0 when the opponent dies this frame (agent survives)."""
        opp_snap = snap.players[1] if snap.players[0].id == agent_id else snap.players[0]
        prev_opp = prev_snap.players[1] if prev_snap.players[0].id == agent_id else prev_snap.players[0]
        if prev_opp.alive and not opp_snap.alive:
            return self.cfg["reward_kill_opponent"]
        return 0.0

    # ── Phase 1.3: Buff pickup ──

    def _buff_pickup(self, prev_snap, snap, agent_id) -> float:
        prev_buffs = {(b.grid_x, b.grid_y, b.type) for b in prev_snap.buffs}
        curr_buffs = {(b.grid_x, b.grid_y, b.type) for b in snap.buffs}
        disappeared = [b for b in prev_snap.buffs if (b.grid_x, b.grid_y, b.type) not in curr_buffs]
        if not disappeared:
            return 0.0
        curr_self = snap.players[0] if snap.players[0].id == agent_id else snap.players[1]
        pickup_range = (cfg.PLAYER_HITBOX_SIZE * cfg.CELL_SIZE) / 2 + 8
        reward = 0.0
        for buff in disappeared:
            dx = curr_self.pos_x - buff.pos_x
            dy = curr_self.pos_y - buff.pos_y
            if math.hypot(dx, dy) < pickup_range:
                reward += self.cfg["reward_pickup_unknown"] if buff.type == "unknown" else self.cfg["reward_pickup_normal"]
        return reward
