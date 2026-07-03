# config.py — 全局配置
class Config:
    def __init__(self):
        self.FPS = 24
        self.DT_OVER_DTAU = 1.0 / self.FPS   # dt/dτ 换算率

        self.CELL_SIZE = 40
        self.MAP_COLS = 19
        self.MAP_ROWS = 11
        self.UI_BAR_HEIGHT = 80
        self.BRICK_GEN_PROB = 0.7

        # 速度类 (cells/sec, 通过 DT_OVER_DTAU 换算)
        self.INIT_SPEED = 2.5
        self.SPEED_INCREMENT = 0.5
        self.MAX_SPEED = 6
        self.SPEED_LEVEL_CAP = 7
        self.KICK_INIT_VEL = 6.0
        self.KICK_ACCEL = -2.0

        # 整数类 (直接帧数)
        self.INIT_BOMB_MAX = 1
        self.MAX_BOMB_CAP = 7
        self.INIT_BLAST_RANGE = 2
        self.MAX_BLAST_RANGE = 8
        self.PLAYER_HITBOX_SIZE = 0.6
        self.BOMB_FUSE = 48              # = 2.0 × 24
        self.BOMB_FLICKER_START = 12      # = 0.5 × 24
        self.DEATH_ANIM_DUR = 12          # = 0.5 × 24
        self.SHIELD_INVINCIBLE_DUR = 12   # = 0.5 × 24
        self.WIN_SCORE = 5
        self.ROUND_DELAY = 72             # = 3.0 × 24
        self.BRICK_DROP_PROB = 0.15
        self.BUFF_PROTECTION_TIME = 7     # ≈ 0.3 × 24
        self.REFRESH_INTERVAL = 720       # = 30.0 × 24
        self.WEIGHT_BOMB_PLUS = 0.2
        self.WEIGHT_BLAST_PLUS = 0.2
        self.WEIGHT_SPEED_PLUS = 0.2
        self.WEIGHT_UNKNOWN = 0.4
        self.DURATION_KICK = 720          # = 30.0 × 24
        self.DURATION_REMOTE = 720        # = 30.0 × 24
        self.DURATION_SHIELD = 480        # = 20.0 × 24
        self.DURATION_DIARRHEA = 192      # = 8.0 × 24
        self.DURATION_REVERSE = 240       # = 10.0 × 24
        self.DURATION_FLOAT = 480         # = 20.0 × 24

    def reset_defaults(self):
        self.__init__()

cfg = Config()
