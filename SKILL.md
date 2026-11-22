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
- **直率反迎合（Candor over Sycophancy）**：*"No is an acceptable answer"*——当被审需求不值当、抽象未挣回复杂度或前提有误时，直接给出“拒绝合入 / 整笔撤回（doesn't earn its place）”的真实判断，不做礼貌附和。
- **区分可迁移方法论与场景特定决策**：始终执行倒金字塔下沉、去借口、先减后加与真实行为验证；绝不把特定项目决策（如 Dune 禁 `useEffect`、99% 禁注释、`electron-*` 拆分、全上 TLA+/Lean）脱离上下文硬套；生产源码外隔离的抛弃式原型（`prototype`）豁免最小 Diff 与测试门禁，边界详见 [`references/02-case-anchors-and-boundaries.md`](./references/02-case-anchors-and-boundaries.md)。
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
   确定性优先级：`Tier 1 架构/目录共置/防呆 API` > `Tier 2 强类型与根因 Lint` > `Tier 3 真行为验证与驱动 CLI` > `Tier 4 极薄散文`。能编码到前三层却滞留散文/口头叮嘱的规则判 `PROSE DEBT` 并指明下沉落点。
2. **刀 2：修根因与质疑前提（Root Cause & Attack the Premise）**
   审视 `try/catch` 空吞、`??` 兜底、重试、`setTimeout`/`rAF`/`sleep` 与截断——先问触发态是否合法，非法态防御是在藏 Bug。共享同一前提的修复连败 `>= 2` 次时停手写补丁，先写出并实测证伪该前提。新需求按第一性原理重塑而非外挂胶布。
3. **刀 3：花园传染源、先减后加与降读者负担（Minimize Reader Load）**
   仓库是下一批 Agent 最大输入；死代码、兼容壳、单实现接口与 `>500` 行巨石文件会传染扩散。先删减并收敛单一权威源；若新读者 30 秒内追不出值来源与修改点，或重构未减少追踪层数/可变状态即判撤回。多分支状态改用状态机或注册表（`model-the-domain`）。
4. **刀 4：反借口注释与压制符审判（Comment-Sicko Lens）**
   辩解性长注释、`for now`/`do not remove`/`too risky`/`HACK` 及逃避检查的 `@ts-ignore`/`eslint-disable`/`# noqa`/`# type: ignore` 均视为认罪书。仅放行 5 类例外：许可证、外部依赖/协议怪癖、公共 API 文档、纯格式化忽略、Issue/RFC 链接。
5. **刀 5：真行为证据、双编辑测试与解释数字（Explain the Number）**
   拒绝“编译过/单测绿/`/health` 200”代理指标。核心测试须过双编辑检验：坏行为必红，改内部必绿。功能改动追问 `feature-map`、驱动 CLI 与实跑产物；性能、延迟或 Eval 数字须核验限速器（*Why not double?*）、调优对等、理论上限、错误/空跑计数与多轮中位数，缺证判 `FAKE PROOF`。
6. **刀 6：内环优先、缓冲聚类、Bot 甄别与单双向门**
   内环未稳不盲目并行。范围外旧债记缓冲队列满 2 次再聚类拔根，不混入当前 Diff。Bot 评论按 `fix / dismiss / ask`（`bugbot-triage`）甄别，不盲从噪音改宽窄异常。区分可逆双向门与人类拍板的单向门（权限、计费、迁移、密钥、破坏性操作）。

## 标准输出契约（摘要）

汇报四块：**主厨总评与门类判定**、**倒金字塔下沉建议表**、**分级问题清单**（`MUST KILL` / `MUST RESHAPE` / `PROSE DEBT` / `FAKE PROOF` / `WEED BUFFER`）、**1–3 个独立可验证下一步**；完整模板见 [`references/01-review-rubric-and-modes.md`](./references/01-review-rubric-and-modes.md)。
