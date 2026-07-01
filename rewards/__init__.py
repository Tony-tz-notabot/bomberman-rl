"""RewardFunction base class — pluggable reward adapter for BombermanEnv."""
from abc import ABC, abstractmethod


class RewardFunction(ABC):
    """奖励策略基类。完全可插拔，无硬编码于环境。

    子类只需实现 __call__()，可选覆写 reset()。
    """

    def reset(self, episode_info: dict):
        """每回合开始时调用，重置内部跟踪状态。"""
        pass

    @abstractmethod
    def __call__(
        self,
        engine,
        prev_snapshot,
        snapshot,
        action,  # np.ndarray(6,) — [up, down, left, right, action, ignite]
        agent_id: str,  # "red" | "blue"
    ) -> float:
        """返回该帧的奖励值。"""
        raise NotImplementedError
