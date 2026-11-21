# 土豆姐（Lauren Tan / `@poteto`）一手案例锚点与防教条红线

本手册只在审阅中需要引用 Lauren Tan 一手实例或核查方法论边界时按需加载。**严禁脱离原始背景生搬硬套，严禁编造未记录的引文、数据或时间戳。**

---

## 一、一手信源索引

- **本地 5 场演讲与访谈逐字稿全景分析**：`C:\Users\z1892\project\poteto-youtube-subtitles\analysis.md`（总计 40,450 英文词，含时间戳索引与 2 份官方文字实录）。
  - `#1` *All Code Is Slop (Except Mine)*（AI Engineer CODE 2026，2026-11-11 演讲 / 11-14 发布）
  - `#2` *LIVE: Poteto (creator of pstack) on shipping 1,000's of PR's a month at SpaceX*（Matt Pocock 直播对谈，2026-10-03）
  - `#3` *We Built Grok Bot. Here Are Our 14 Best Bots*（Peter Yang 专访 Peng Zheng & Lauren Tan，2026-09-27）
  - `#4` *Are Agents About to Replace Software Engineering?*（MTS 访谈 Lauren Tan & Roshan Sadanani，2026-08-13）
  - `#5` *Lauren Tan Reveals How to Build a 21+ Agent GrokBot Team*（Colin 56 分钟屏共享 Q&A，2026-10-17 上传）
- **上游工具链快照**：`vendor/pstack`（来自 `cursor/plugins`，`v0.15.46` @ `aaeb0ea3`），核心含 `correct`、`no-comments`、`architect`、`why`、`reflect`、`recall`、`statechart`、`create/maintain-verification-skill`、`create/maintain-formal-verification-skill`，`comment-sicko` 独立审查员，12 条原则技能与 `eval`/`hillclimb` Playbook。

---

## 二、七个关键案例锚点与迁移边界

### 1. Glass 性能抢救与“人肉代理之耻”（`#2`、`#5`）
- **实情**：在抢救 Cursor Agents Window（`Glass`）卡顿时，她最初每天人工看 Chrome DevTools 火焰图与堆快照再截图贴给 AI，自嘲沦为“Agent 和 DevTools 之间的人肉代理（meat proxy）”。随后据此沉淀出 `control-glass`、按用户视角组织的 `feature-map` 与操控 Electron/CDP 的自定义 CLI。
- **审阅迁移**：凡是审阅中仍要求人类去点页面、复述坐标或手动粘错误截图的环节，一律质疑“为什么还没封装成用户视角的 Feature Map 与可复用 CLI？”，并优先把确定性浏览器/调试操作剥离进脚本。

### 2. Dune 框架用 600+ PR 重构 8 个万行巨石文件（`#1`、`#2`、`#5`）
- **实情**：早期 Vibe Coding 原型长出约 8 个各上万行的巨石文件（god files）。团队用 600 多个原子化 PR 将其重塑为内部桌面框架 Dune：1) 在业务层禁用 `useEffect`，收口到极少数 Dune 底层原语；2) 将 `electron-main` 与 `electron-renderer` 拆成顶级目录并用依赖图 Analyze + Lint 强阻断跨目录导入；3) 在代码内部禁掉 99% 注释，改为会给出根因修复方向的 Lint 报错。
- **迁移边界**：**可迁移的不是“禁用 `useEffect`”或“拆分 `electron-*`”，而是“把需要博士级心智负担才能用对的脚枪 API 隔离收口、用目录名直接表达运行时边界、用报错提示替代死注释”**。如果一个纯后端 Python 工具或普通标准表单组件本就需要合理效果钩子，强套禁令就是教条主义。

### 3. `setTimeout` / `rAF` 补丁注释传染事故（`#1`）
- **实情**：Cursor 中 VS Code 命令式架构与 React 声明式架构冲突，Agent 为求快大量塞入 `setTimeout`、`requestAnimationFrame`、`requestIdleCallback`，触发频繁 GC 与严重卡顿，同时写下长注释“论证为什么这是必要权宜之计”。后续 Agent 看到注释便理直气壮整仓复制扩散。
- **审阅迁移**：在审阅任何“解释为什么要加延时、降级兜底、临时绕过或压制报错”的注释时，绝不接受“态度诚恳”或“暂时先这样”，必须将其视作**全仓毒模范传染源**（`comment-sicko` 视角：`IMPORTANT` / `do not remove` 往往是气味而不是免死金牌，需追查外部依赖真怪癖或直接重塑代码消除意外）。

### 4. GrokBot 报告产量、回退率与 70% 验证预算（`#1`、`#4`、`#5`）
- **实情**：演讲与访谈中报告了团队投入约半年建设基础设施后的结果——10 月团队约 **11,000 PR**（个人 **3,000 PR**）、**227 人**（含 PM、设计师、GTM）参与合入、客户端约每日切一个稳定版、相对回退率降到并稳定在 **约 0.5%**、端到端响应指标优于上线初期；她同时引用同行数据并确认自己大部分 Token 预算同样投入**验证（约 70% 量级）**。
- **迁移边界**：AI Engineer 官方整理明确指出这是其团队在特定环境建设后的**报告结果**，并非受控实验证明所有仓库只要增加 PR 数量就会自动变快变稳。审阅中严禁以“人家都能日合几百 PR”鼓励跳过护栏直接开外环并行；**唯一可迁移的规律是顺序：先收紧内环代码库与验证，最后才放开外环自动合并**。

### 5. 米其林后厨、Git Log 抽样与 Routine 缓冲队列（`#2`）
- **实情**：她反对冰冷低质的“Dark Software Factory”，坚持主厨思维——从单人切菜变成协调副厨，仍靠抽样试菜（晨起看 `git log` 已合并历史）对总品质兜底。定期扫禁止模式时，她**不让 Agent 发现一条就立刻发 PR 乱改**，而是先写入**缓冲汇总清单（Buffer/Queue）**，积攒几天由人类或主管一眼看出“20 条报警其实源自同一个缺口 API”，然后一次治本。
- **审阅迁移**：审阅 PR 时遇到范围外旧债不要当场要求扩散改造范围；审阅自动化巡检工作流时，优先推荐使用 Buffer 汇总模式，避免多路并发 Agent 互相踩踏修表面。

### 6. Dr. Eggbot 与 Matcha 的多 Bot 职责纪律（`#3`）
- **实情**：`Dr. Eggbot` 负责按规范设计新 Bot 并定期审计对话历史——当某个 Bot 上下文杂乱、同时兼任太多无关杂活时，提议拆分出独立 Bot 或抽成 Skill；同时审计哪些每 10 分钟唤醒一次的高频 Routine 白烧 Token。工程主管 Bot `Matcha` 的设定明确要求**自己绝不动手写代码，只负责拆解任务并调度下属工程 Worker Bot（再去拉起云端编码 Agent）**；社交感知 Bot `Poteto` 聚合外部吐槽并把上下文直接交给 `Matcha`，减少人类当复读机。
- **审阅迁移**：审阅多 Agent 系统时，重点抓两类反模式——**主管越位亲自下场敲胶水代码**、**单 Bot 上下文职责混杂却用不断拉长的系统提示词硬撑**。

### 7. Skill 防作弊双盲 Eval 与 Hillclimb 纪律（`#5`、`pstack` playbooks）
- **实情**：在修改 `pstack` 技能前，团队会在刻意隐藏评测意图的**中性命名目录**中并排运行不同模型候选体（Prompt 中绝不出现 `eval`、`test`、`judge`、`rubric`、`score`、`compare`、`benchmark`、`candidate`、`arena` 等字样，也不问候选体“你遵循了哪些原则”），由**另一模型家族的盲评裁判**根据真实代码结构与本地对话轨迹打分。配合 `hillclimb` 做多轮爬坡优化时，必须冻结评测集与回归门禁，每次只合一个过检改动，未显著超越基线噪音即完整回退。
- **审阅迁移**：评审团队自研 Skill/Prompt 迭代流程时，直接把“同模型自吹自擂”“靠 Agent 自述而非查真实产物/轨迹打分”“改动后未跨模型盲测”判定为无效验证（`FAKE PROOF`）。

---

## 三、防教条误用红线（Anti-Dogma Checklist）

在动笔给出最终审阅结论前，自检以下五条红线，任何一条不成立即收回该条批评：

1. **禁止脱离上下文机械套禁令**：禁某 API、目录必须如何命名、全仓零注释、必须上 TLA+/Lean 均以特定痛点与收益成本比为前提；对于核心状态简单的 CRUD 模块或探索原型，应按分级需求给最小恰当约束。
2. **禁止把“单次人类判断”骂成 `PROSE DEBT`**：唯有可确定性表达为结构、类型、Lint、验证脚本的规律，才算散文债；涉及业务取舍、审美调性、高危授权口径或外部沟通边界规则本就应留在极薄文档层。
3. **禁止用“少写几行注释/多加两行 Lint”取代真架构问题**：如果架构自身存在命令式与声明式硬撞或状态分裂，单纯喊“删注释”只能掩盖冲突；优先指出那个导致补丁不断繁殖的一级结构缺陷。
4. **禁止将范围外历史债务塞进当前 PR 阻塞合并**：旧仓推进靠“先划局部净土 + 棘轮锁老债 + 缓冲队列聚类除草”，不能要求一个局部修 Bug 的 PR 先把全仓重构一遍。
5. **禁止以人名压人或编造出处**：不拿“土豆姐说……”替代技术论证；所有观点必须先给出工程因果与代码证据，案例只作同构佐证，且只引用本手册或一手文件核实过的内容。
