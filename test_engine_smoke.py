# test_engine_smoke.py
from game_engine import GameEngine
engine = GameEngine()
snap = engine.step({"up": False, "down": False, "left": False, "right": False,
                     "action": False, "ignite": False},
                    {"up": False, "down": False, "left": False, "right": False,
                     "action": False, "ignite": False})
assert snap.state == 1  # ROUND_RUNNING
assert len(snap.players) == 2
assert snap.map_grid is not None
print("GameEngine smoke test PASSED")
