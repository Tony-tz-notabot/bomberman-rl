"""SparseReward: +1 win, -1 lose, 0 draw, 0 otherwise."""
from rewards import RewardFunction
from src.constants import GameState


class SparseReward(RewardFunction):
    """赢+1, 输-1, 平局0, 其余帧0"""

    def __call__(self, engine, prev, snap, action, agent):
        if snap.state == GameState.ROUND_END_DELAY or snap.state == GameState.MATCH_END:
            opp = "blue" if agent == "red" else "red"
            my_score = snap.scores.get(agent, 0)
            opp_score = snap.scores.get(opp, 0)
            if my_score > opp_score:
                return 1.0
            elif my_score < opp_score:
                return -1.0
            else:
                return 0.0  # draw
        return 0.0
