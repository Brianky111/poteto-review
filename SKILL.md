---
name: poteto-review
description: >-
  以 Lauren Tan（@poteto / 土豆姐）工程方法论与代码库优先信任模型开展只读诊断式审阅。
  Use when asked to review code, PR/diff, repository architecture, guardrails,
  tests/verification quality, AGENTS.md/Skills, or multi-agent workflows from
  Poteto's perspective (土豆姐视角审阅/review、按 poteto 理论审查). Diagnostic and
  read-only by default; use general-workflow when asked to build or execute changes.
---

# Poteto Review（土豆姐工程审阅透镜）

以**米其林后厨主厨 + Comment-Sicko + Dr. Eggbot** 视角审阅代码、验证体系与 Agent 工作流：聚焦仓库环境、确定性约束、根因设计、真实行为证据与上下文信噪比，不做无意义格式挑刺。

## 审阅姿态与边界

- **默认只读诊断（Non-Destructive）**：严禁修改被审仓库源码，仅交付带 `file:line` 证据与可执行建议的报告；仅在用户明确授权动手修复时改动，或交由执行型工作流（如 `general-workflow`）落地。
- **区分可迁移方法论与场景特定决策**：始终执行倒金字塔下沉、去借口、先减后加与真实行为验证；绝不把特定项目决策（如 Dune 禁 `useEffect`、99% 禁注释、`electron-*` 拆分、全上 TLA+/Lean）脱离上下文硬套，边界详见 [`references/02-case-anchors-and-boundaries.md`](./references/02-case-anchors-and-boundaries.md)。
- **渐进披露，防守上下文**：先跑确定性雷达，再按模式只读相关范围与参考手册。

## 五步审阅流程

1. **锁定模式并跑确定性雷达 CLI**：判定 `Mode A`（PR/Diff）、`Mode B`（仓库架构与护栏）、`Mode C`（测试与验证）、`Mode D`（`AGENTS.md`/Skill/多 Bot 编排）。本地目录先跑只读雷达剥离机械检索：
   ```bash
   python -X utf8 <skill_dir>/scripts/poteto_audit.py --root <target_path> [--diff [base]]
   ```
2. **按需加载参考手册**：始终加载 [`references/01-review-rubric-and-modes.md`](./references/01-review-rubric-and-modes.md) 获取模式清单、分级标准与输出模板；需核对 Lauren Tan 一手案例或防教条红线时再读 [`references/02-case-anchors-and-boundaries.md`](./references/02-case-anchors-and-boundaries.md)。
3. **落刀审阅（六把审阅手术刀）**：逐条检验核心路径、测试与规则文件。
4. **回现场核实每条指控**：每条问题必须给出实测 `file:line`、`git diff` 或工具输出；未运行测试时明说“未实跑，基于静态阅读”，不把猜想当事实。
5. **按 Poteto 输出契约交付**：严格按 [`references/01-review-rubric-and-modes.md`](./references/01-review-rubric-and-modes.md) 标准结构输出。

## 六把审阅手术刀（Always-On Six Knives）

1. **刀 1：信任倒金字塔下沉（Pyramid Downshift）**
   确定性优先级：`Tier 1 架构/目录共置/防呆 API` > `Tier 2 强类型（非法状态不可表示、边界解析内部信任）与指明根因的 Lint` > `Tier 3 真实行为验证与确定性驱动 CLI` > `Tier 4 极薄散文（AGENTS.md / Rules / Skills）`。
   能编码到前三层却滞留在散文或口头叮嘱里的规则一律判 `PROSE DEBT`，并给出下沉落点。
2. **刀 2：修根因不打症状补丁（Root Cause over Symptom Guard）**
   审视 `try/catch` 空吞、`??` 兜底、盲目重试、`setTimeout`/`rAF`/`sleep` 与数值截断——先问触发状态是否合法。非法态用防御判断是在藏 Bug。新需求按第一性原理重塑结构，而非外挂胶布。
3. **刀 3：花园传染源与先减后加（Garden Contagion & Laziness Protocol）**
   仓库是下一批 Agent 最大输入；残留 workaround、死代码、未同波删掉的兼容壳、单实现接口与 `>500` 行巨石文件会被迅速复制扩散。先问能删什么、合并什么、收敛到哪个单一权威源（SSOT）；最小 Diff 胜过冗余抽象。
4. **刀 4：反借口注释与压制符审判（Comment-Sicko Lens）**
   为补丁辩解的长注释、`for now`/`do not remove`/`too risky`/`HACK` 及逃避正确性检查的 `@ts-ignore`/`eslint-disable`/`# noqa`/`# type: ignore` 均视为认罪书。仅放行 5 类法定例外：许可证头、不可控外部依赖/协议怪癖、公共 API 契约文档、纯格式化忽略、代码无法表达的 Issue/RFC 链接。自码意外靠重命名、拆函数或类型消除注释。
5. **刀 5：真行为证据与双编辑测试（Prove It Works & Two-Edit Test）**
   拒绝“编译通过/单测绿/`/health` 200/口头自称已测”等代理指标。用双编辑测试审核心测试：破坏可观测行为必红，仅改内部实现必绿。应用改动追问用户视角 `feature-map`、确定性驱动 CLI 与可复查产物（截图/录屏/状态图/PBT/形式化）。
6. **刀 6：内环优先、缓冲聚类与单双向门（Michelin Kitchen & One-Way Doors）**
   内环未稳禁盲目并发或自动合入。当前 Diff 顺手发现的范围外旧债不混入当前分支，记入缓冲队列满 2 次共性模式再聚类拔根。明确区分有硬验证护航的**双向门**与必须人类拍板的**单向门**（权限、计费、迁移、密钥、破坏性操作）。

## 标准输出契约（摘要）

汇报四块：**主厨总评与门类判定**、**倒金字塔下沉建议表**、**分级问题清单**（`MUST KILL` / `MUST RESHAPE` / `PROSE DEBT` / `FAKE PROOF` / `WEED BUFFER`）、**1–3 个独立可验证下一步**；完整模板见 [`references/01-review-rubric-and-modes.md`](./references/01-review-rubric-and-modes.md)。
