---
name: progress-tracking-hotmd
description: Code changes must be recorded in hot.md as meaningful milestones
metadata:
  type: feedback
---

每次完成有意义的代码改动后，必须在 `hot.md` 中更新进展记录。

- 项目根目录下的 `hot.md` 文件跟踪已完成项、当前阶段、下一步计划
- `.claude/settings.json` 中的 PostToolUse hook 在每次 Edit/Write 后提示检查
- 记录粒度：有边界的里程碑（如"完成了碰撞系统重构"），而非微小步骤
- 仅记录实际代码改动（纯讨论不算）

**Why:** 保持正在进行的开发方向透明，方便中断后快速恢复上下文。

**How to apply:** 每次 Edit/Write tool 返回后，检查改动是否代表有意义进展；如果是，更新 hot.md 中的已完成列表或修改下一步计划。
