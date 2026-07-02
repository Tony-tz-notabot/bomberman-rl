"""Map generation utilities for Phase 1 training pipeline.

Provides phase-aware map generation and blue spawn sampling,
independent of GameEngine's built-in generate_map().
"""
import random
from typing import Optional
from src.config import cfg


def generate_map(phase: float, rng: random.Random,
                 red_spawn: tuple = (1, 1)) -> dict:
    """Generate map and spawn positions for the given phase.

    Args:
        phase: 1.1, 1.2, or 1.3
        rng: Seeded RNG for reproducibility.
        red_spawn: (gx, gy), defaults to (1, 1).

    Returns:
        dict with keys:
            grid: list[list[str]] — 2D grid indexed [gx][gy],
                   values "floor" / "brick" / "stone"
            red_spawn: (int, int)
            blue_spawn: (int, int)
            safe_spots: set of (int, int)
    """
    if int(phase * 10) == 11:  # Phase 1.1
        return _generate_connected_map(rng, red_spawn)
    return _generate_standard_map(rng, red_spawn)


def connected_floor_cells(grid: list, gx: int, gy: int) -> set:
    """BFS: return all floor cells reachable from (gx, gy)."""
    visited = set()
    queue = [(gx, gy)]
    visited.add((gx, gy))
    while queue:
        cx, cy = queue.pop(0)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = cx + dx, cy + dy
            if (1 <= nx <= cfg.MAP_COLS and 1 <= ny <= cfg.MAP_ROWS
                    and (nx, ny) not in visited
                    and grid[nx][ny] == "floor"):
                visited.add((nx, ny))
                queue.append((nx, ny))
    return visited


def _safe_spots_for(red_spawn: tuple,
                    blue_spawn: Optional[tuple] = None) -> set:
    """Compute corridor cells that must stay floor for spawn access.

    Corridor cells are those where one coordinate is odd and the other even,
    i.e. (odd, even) or (even, odd). These are the cells that can be bricks.
    """
    spots = set()
    for spawn in [red_spawn, blue_spawn]:
        if spawn is None:
            continue
        sx, sy = spawn
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = sx + dx, sy + dy
            if 1 <= nx <= cfg.MAP_COLS and 1 <= ny <= cfg.MAP_ROWS:
                if (nx % 2) != (ny % 2):  # corridor cell
                    spots.add((nx, ny))
    return spots


def _empty_grid() -> list:
    """Create a MAP_COLS x MAP_ROWS grid, all floor.

    Indexed as grid[x][y] where x in [1,MAP_COLS], y in [1,MAP_ROWS].
    Index 0 is unused (dummy), matching GameEngine convention.
    """
    return [["floor" for _ in range(cfg.MAP_ROWS + 1)]
            for _ in range(cfg.MAP_COLS + 1)]


def _populate_grid(grid: list, brick_prob: float, safe_spots: set,
                   rng: random.Random):
    """Fill a pre-allocated empty grid with stone, brick, and floor cells."""
    for x in range(1, cfg.MAP_COLS + 1):
        for y in range(1, cfg.MAP_ROWS + 1):
            if x % 2 == 0 and y % 2 == 0:
                grid[x][y] = "stone"
            elif (x % 2 == 0) != (y % 2 == 0):
                grid[x][y] = ("floor" if (x, y) in safe_spots
                              else "brick" if rng.random() < brick_prob
                              else "floor")
            else:
                grid[x][y] = "floor"


def _sample_blue_spawn(grid: list, red_spawn: tuple,
                       phase: float, rng: random.Random) -> tuple:
    """Pick a random floor cell for blue spawn.

    Phase 1.1: must be in same connected component as red.
    Phase 1.2/1.3: any floor cell (no connectivity check).
    """
    rx, ry = red_spawn
    if int(phase * 10) == 11:  # Phase 1.1
        component = connected_floor_cells(grid, rx, ry)
        candidates = [(x, y) for (x, y) in component if (x, y) != (rx, ry)]
    else:
        candidates = [(x, y) for x in range(1, cfg.MAP_COLS + 1)
                      for y in range(1, cfg.MAP_ROWS + 1)
                      if grid[x][y] == "floor" and (x, y) != (rx, ry)]
    if not candidates:
        # Fallback — any non-stone cell
        candidates = [(x, y) for x in range(1, cfg.MAP_COLS + 1)
                      for y in range(1, cfg.MAP_ROWS + 1)
                      if grid[x][y] != "stone" and (x, y) != (rx, ry)]
    return rng.choice(candidates)


def _generate_standard_map(rng: random.Random,
                           red_spawn: tuple = (1, 1)) -> dict:
    """Standard Phase 1.2/1.3 map — BRICK_GEN_PROB=0.7, no connectivity required."""
    grid = _empty_grid()
    _populate_grid(grid, cfg.BRICK_GEN_PROB, _safe_spots_for(red_spawn), rng)
    blue_spawn = _sample_blue_spawn(grid, red_spawn, 1.2, rng)
    # Compute final safe_spots with blue known
    safe = _safe_spots_for(red_spawn, blue_spawn)
    for (sx, sy) in safe:
        grid[sx][sy] = "floor"
    return {
        "grid": grid,
        "red_spawn": red_spawn,
        "blue_spawn": blue_spawn,
        "safe_spots": safe,
    }


def _generate_connected_map(rng: random.Random,
                            red_spawn: tuple = (1, 1)) -> dict:
    """Phase 1.1 connected map — reduced brick probability, BFS-verified.

    Uses BRICK_GEN_PROB=0.3 and retries if the connected component of red
    has fewer than 100 candidate floor cells for blue spawn. Falls back to
    a fully open map after 30 failed attempts.
    """
    brick_prob = 0.3
    for _attempt in range(30):
        grid = _empty_grid()
        _populate_grid(grid, brick_prob, _safe_spots_for(red_spawn), rng)
        reachable = connected_floor_cells(grid, red_spawn[0], red_spawn[1])
        candidates = [(x, y) for (x, y) in reachable if (x, y) != red_spawn]
        if len(candidates) >= 100:
            blue_spawn = rng.choice(candidates)
            safe = _safe_spots_for(red_spawn, blue_spawn)
            for (sx, sy) in safe:
                grid[sx][sy] = "floor"
            return {
                "grid": grid,
                "red_spawn": red_spawn,
                "blue_spawn": blue_spawn,
                "safe_spots": safe,
            }
    # Fallback: fully open map (all corridors floor)
    grid = _empty_grid()
    _populate_grid(grid, 0.0, _safe_spots_for(red_spawn), rng)
    floor_cells = [(x, y) for x in range(1, cfg.MAP_COLS + 1)
                   for y in range(1, cfg.MAP_ROWS + 1)
                   if grid[x][y] == "floor" and (x, y) != red_spawn]
    blue_spawn = rng.choice(floor_cells) if floor_cells else (3, 3)
    safe = _safe_spots_for(red_spawn, blue_spawn)
    for (sx, sy) in safe:
        grid[sx][sy] = "floor"
    return {
        "grid": grid,
        "red_spawn": red_spawn,
        "blue_spawn": blue_spawn,
        "safe_spots": safe,
    }
