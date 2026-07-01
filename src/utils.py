from src.config import cfg


def grid_to_pixel(x, y):
    return (x - 1) * cfg.CELL_SIZE, cfg.UI_BAR_HEIGHT + (y - 1) * cfg.CELL_SIZE


def grid_center(x, y):
    left, top = grid_to_pixel(x, y)
    return left + cfg.CELL_SIZE // 2, top + cfg.CELL_SIZE // 2


def pixel_to_grid(px, py):
    """
    【BUG修复】原实现未正确处理Y轴UI_BAR_HEIGHT偏移，导致返回的gy错误。
    现在基于几何中心精确转换：格子索引 = round( (像素 - 格子中心偏移) / CELL_SIZE )
    """
    # 格子的中心点像素公式：cx = (gx-1)*CELL_SIZE + CELL_SIZE/2
    # 反向解出：gx = round( (px - CELL_SIZE/2) / CELL_SIZE ) + 1
    gx = round((px - cfg.CELL_SIZE / 2) / cfg.CELL_SIZE) + 1
    # gy 需要减去 UI_BAR_HEIGHT 后再同理计算
    gy = round((py - cfg.UI_BAR_HEIGHT - cfg.CELL_SIZE / 2) / cfg.CELL_SIZE) + 1
    return clamp(gx, 1, cfg.MAP_COLS), clamp(gy, 1, cfg.MAP_ROWS)


def clamp(val, lo, hi):
    return max(lo, min(hi, val))


def sign(x):
    if x > 0:
        return 1.0
    if x < 0:
        return -1.0
    return 0.0


def get_map_width():
    return cfg.CELL_SIZE * cfg.MAP_COLS


def get_map_height():
    return cfg.CELL_SIZE * cfg.MAP_ROWS


def get_window_width():
    return get_map_width()


def get_window_height():
    return get_map_height() + cfg.UI_BAR_HEIGHT


def box_overlap(L1, R1, T1, B1, L2, R2, T2, B2):
    return not (R1 < L2 or R2 < L1 or B1 < T2 or B2 < T1)
