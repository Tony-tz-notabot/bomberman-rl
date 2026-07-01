# Phase 1 课程学习设计：基础操作与生存

> 基于 2026-07-01 讨论定稿

## 一、三阶段学习策略总览

| 阶段 | 名称 | 目标 |
|------|------|------|
| **Stage 1** | 基础操作与生存（本文档） | 学会走中线、推进、放炸弹炸砖、基本 Buff 拾取 |
| **Stage 2** | 生成对抗式轨迹模仿（GAIL） | 人类 vs Stage 1 AI 对战采集轨迹 → BC 预热 → GAIL 精调 |
| **Stage 3** | 自主双智能体对战（稀疏奖励） | 自博弈，+1/-1/0 稀疏奖励最终优化 |

### 设计原则

- **每阶段的奖励函数独立**，仅用于学习该阶段目标
- **子阶段过渡**：前一阶段奖励项权重减半保留，新奖励项以显式权重加入
- **对手**：每轮随机初始化位置，每轮内固定不动

---

## 二、地图结构（重申）

```
行11(奇):  F  ?  F  ?  F  ?  F  ?  F  ?  F  ?  F  ?  F  ?  F  ?  F
行10(偶):  ?  S  ?  S  ?  S  ?  S  ?  S  ?  S  ?  S  ?  S  ?  S  ?
行 9(奇):  F  ?  F  ?  F  ?  F  ?  F  ?  F  ?  F  ?  F  ?  F  ?  F
行 8(偶):  ?  S  ?  S  ?  S  ?  S  ?  S  ?  S  ?  S  ?  S  ?  S  ?
行 7(奇):  F  ?  F  ?  F  ?  F  ?  F  ?  F  ?  F  ?  F  ?  F  ?  F
行 6(偶):  ?  S  ?  S  ?  S  ?  S  ?  S  ?  S  ?  S  ?  S  ?  S  ?
行 5(奇):  F  ?  F  ?  F  ?  F  ?  F  ?  F  ?  F  ?  F  ?  F  ?  F
行 4(偶):  ?  S  ?  S  ?  S  ?  S  ?  S  ?  S  ?  S  ?  S  ?  S  ?
行 3(奇):  F  ?  F  ?  F  ?  F  ?  F  ?  F  ?  F  ?  F  ?  F  ?  F
行 2(偶):  ?  S  ?  S  ?  S  ?  S  ?  S  ?  S  ?  S  ?  S  ?  S  ?
行 1(奇):  F  ?  F  ?  F  ?  F  ?  F  ?  F  ?  F  ?  F  ?  F  ?  F
```

- F: 地板（奇-奇坐标）
- S: 石墙（偶-偶坐标，不可破坏）
- ?: 砖块（概率 0.7）或地板（奇-偶/偶-奇坐标）
- 尺寸：19×11（默认），CELL_SIZE=40px，碰撞盒=32px（0.8×），每侧 4px 容差

### 中线偏离计算

玩家当前所在格子 (gx, gy)：
- 该格子的中心像素坐标 (cx, cy) 由 `grid_center` 得到
- 走廊方向判断：
  - 若 gy 为奇数（水平走廊），中线为 y = cy，偏离距离 = |pos_y - cy|
  - 若 gx 为奇数（垂直走廊），中线为 x = cx，偏离距离 = |pos_x - cx|
  - 若 gx、gy 均为奇数（交叉口），偏离距离 = max(|pos_x - cx|, |pos_y - cy|)
  - gx、gy 均为偶数的格子（石墙）不会出现
- 归一化尺度：half_cell = CELL_SIZE / 2 = 20px

---

## 三、Phase 1 子阶段设计

### Phase 1.1：纯走廊生存（~10K 步）

**地图配置**：`BRICK_GEN_PROB = 0`，全场无砖块，仅奇-奇走廊+石柱

**目标**：学会沿走廊中线行进，持续朝向对手位置推进

| 类 | 奖励项 | 值 | 说明 |
|----|--------|----|------|
| 🟢 | 曼哈顿距缩小 | +0.1 / 格 | 与上一帧比较，缩短则加分 |
| 🔴 | 曼哈顿距增大 | -0.05 / 格 | 远离对手则惩罚 |
| 🔴 | 中线偏离惩罚 | -0.04 × (dist/20)² | 偏离走廊中心线，二次型加重偏大值 |
| 🔴 | 连续 30 帧（≈1.25s）无净推进 | -0.02/帧，叠至 -0.5 上限 | 防止原地徘徊或来回走；推进判定为曼哈顿距缩小 >0 |
| 🔴 | 撞墙 | -0.03/轴 | 有方向输入但坐标未变 |
| 🔴 | 撞对手 | -0.02 | 被对方阻挡 |
| 🟢 | 存活 | +0.01/帧 | 每帧基本分 |
| 🔴 | 非法操作-炸弹上限 | -0.1 | action=1 但已达 bomb_max |
| 🔴 | 非法操作-脚下不可放弹 | -0.05 | action=1 但脚下非 floor |
| 🔴 | 非法操作-无效 ignite | -0.05 | ignite=1 但无遥控能力或队列空 |
| 🔴 | 非法操作-超 2 方向 | -0.05 | count>2 |
| 🔴 | 被自己炸弹炸死 | -1.0 | 区分于对手 |
| 🔴 | 被对手炸弹炸死 | -0.5 |  |

### Phase 1.2：砖块爆破与开路（~50K 步）

**地图配置**：恢复 `BRICK_GEN_PROB = 0.7`

**新增奖励**（1.1 所有项权重减半保留）：

| 类 | 奖励项 | 值 | 说明 |
|----|--------|----|------|
| 🟢 | 成功放置炸弹 | +0.1 | action=1 且合法放置 |
| 🟢 | 自己炸弹炸毁砖块 | +0.5/块 | 一次性，砖块永久消失 |

### Phase 1.3：Buff 引入（~30K 步）

**新增奖励**（1.1+1.2 所有项权重减半保留）：

| 类 | 奖励项 | 值 | 说明 |
|----|--------|----|------|
| 🟢 | 拾取任意 Buff | +0.2 | 所有类型 |
| 🟢 | 拾取未知道具 | +0.3 | 区别于永久增强 |

### Phase 1.4：融合评估（~10K 步）

不做训练，仅评估。在最终环境配置下评测：

- 平均生存帧数
- 场均炸弹数 & 场均有效炸砖数
- 胜率 vs 随机对手（100 局）
- 场均非法操作数
- 中线偏离均值

---

## 四、量级估算（每 60s 回合，~1440 帧）

### Phase 1.1 — 训练较好的 Agent

| 奖励项 | 单次值 | 每局频次 | 小计 | 占比 |
|--------|--------|----------|------|------|
| 存活 | +0.01/帧 | 1440 帧 | +14.40 | 41% |
| 曼哈顿距缩小 | +0.1/格 | ~80 次净缩小 | +8.00 | 23% |
| 曼哈顿距增大 | -0.05/格 | ~50 次净增大 | -2.50 | -7% |
| 中线偏离 | -0.04×(d/20)² | 均值 d=5px → -0.0025/帧 | -3.60 | -10% |
| 连续无推进 | -0.02→封顶-0.5 | ~3 次激活 | -1.50 | -4% |
| 撞墙 | -0.03/轴 | ~15 次 | -0.45 | -1% |
| 撞对手 | -0.02 | ~3 次 | -0.06 | <1% |
| 非法操作 | -0.05~-0.1 | ~25 次 | -2.00 | -6% |
| 死亡 | -0.5~-1.0 | 1 次 | -0.50 | -1% |
| **合计** | | | **+11.79** | **100%** |

### Phase 1.1 — 训练较差的 Agent

| 项 | 值 | 说明 |
|----|-----|------|
| 中心偏离严重 (d=12px) | -20.74 | 中线惩罚主导为负 |
| 净缩小仅 40 次 | +4.00 | → 推进不足 |
| 非法操作多 (40 次) | -3.50 | → 上浮 |
| **合计** | **-13.30** | 负数 → 驱动 Agent 快速改善中线行走 |

→ 中线偏离惩罚是**最主要的质量判别信号**，好 Agent 此项约 -3.6，差 Agent 此项达 -20.7。

### Phase 1.2（1.1 项减半 + 炸弹新增）

| 来源 | 值 |
|------|----|
| Phase 1.1 减半小计 | +5.64 |
| 放炸弹 (25 次 × +0.1) | +2.50 |
| 炸砖块 (12 块 × +0.5) | +6.00 |
| **合计** | **+14.14** |

→ 炸弹/炸砖贡献约 60%，运动/生存约 40%。

### Phase 1.3（Buff 新增）

| 来源 | 值 |
|------|----|
| 拾取 Buff (~3 次 × +0.2) | +0.60 |
| 未知道具 (~1 次 × +0.3) | +0.30 |
| Buff 合计占比 | ~4% |

→ Buff 仅为轻量引导，不影响主体优化方向。

---

## 五、奖励函数架构

### 接口定义

使用现有的 `rewards/` 架构，所有参数通过构造函数注入，**不硬编码**：

```python
class Phase1Reward(RewardFunction):
    def __init__(self, config: dict = None):
        cfg = config or {}
        self.reward_alive = cfg.get("reward_alive", 0.01)
        self.reward_approach = cfg.get("reward_approach", 0.1)
        self.penalty_retreat = cfg.get("penalty_retreat", -0.05)
        self.penalty_center_dev = cfg.get("penalty_center_dev", -0.04)
        self.reward_bomb_place = cfg.get("reward_bomb_place", 0.1)
        self.reward_brick_destroy = cfg.get("reward_brick_destroy", 0.5)
        self.reward_buff_pickup = cfg.get("reward_buff_pickup", 0.2)
        self.penalty_illegal_action = cfg.get("penalty_illegal_action", -0.1)
        self.penalty_wall_collision = cfg.get("penalty_wall_collision", -0.03)
        self.penalty_death_self = cfg.get("penalty_death_self", -1.0)
        self.penalty_death_opp = cfg.get("penalty_death_opp", -0.5)
        self.stagnation_frames = cfg.get("stagnation_frames", 30)
        self.stagnation_penalty = cfg.get("stagnation_penalty", -0.02)
        self.stagnation_cap = cfg.get("stagnation_cap", -0.5)
        # sub-phase scaling
        self.ph11_scale = cfg.get("ph11_scale", 1.0)   # Phase 1.1 weight
        self.ph12_scale = cfg.get("ph12_scale", 0.5)   # Phase 1.2 multiplier on 1.1
        self.ph13_scale = cfg.get("ph13_scale", 0.25)  # Phase 1.3 multiplier on 1.1
```

### 非法操作检测

`engine.step()` 中已经包含了动作的静默忽略逻辑。Reward 函数通过对比 `prev_snap` 和 `snap` 中的玩家状态来推算操作是否有效：

| 非法操作 | 检测方式 |
|----------|----------|
| 已达上限放炸弹 | action["action"]=1 且 bomb_placed_count 未增加 |
| 脚下非法放炸弹 | action["action"]=1 且 bomb_placed_count 未增加 |
| 无效 ignite | action["ignite"]=1 且 remote_queue 长度无变化 |
| 撞墙 | 有方向输入但对应轴坐标无变化 |
| 撞对手 | 有方向输入但坐标未变 + 被对方阻挡 |

### 环境集成

```python
# 创建 Phase 1.1 环境
reward_fn = Phase1Reward({
    "ph11_scale": 1.0, "ph12_scale": 0.0, "ph13_scale": 0.0,
})
env = BombermanEnv(reward_fn=reward_fn)

# 创建 Phase 1.2 环境
reward_fn = Phase1Reward({
    "ph11_scale": 0.5, "ph12_scale": 1.0, "ph13_scale": 0.0,
})
env = BombermanEnv(reward_fn=reward_fn)
```

---

## 六、已知风险与缓解

| 风险 | 缓解方案 |
|------|----------|
| Agent 学到"靠近但不推进"的摆烂态 | 连续 N 帧无净推进惩罚 + "曼哈顿缩小"仅奖励增量 |
| Agent 放完炸弹就跑角落 | 放炸弹收益(+0.1)远小于"远离对手"的惩罚 |
| 撞墙 + 中线偏离 双罚叠加过渡惩罚 | 惩罚值均为轻量级，叠加后最大 -0.07/帧，仍在合理范围 |
| 砖块炸完后的探索真空期 | "向对手走"为主信号，不受砖块数量影响 |
