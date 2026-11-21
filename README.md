# Poteto Review（土豆姐视角工程审阅技能）

将 Lauren Tan（`@poteto`）在 AI Engineer CODE 2026、Matt Pocock 直播对谈、GrokBot 团队分享与 `pstack` 中的核心工程审阅方法论提炼为独立跨端只读审阅 Skill，支持 Claude Code、Cursor、Codex CLI、Agents 通用目录与 Pi。

> **与 `general-workflow` 的分工**：`general-workflow` 负责从零或接手项目并**执行开发与护栏搭建**；`poteto-review` 聚焦**只读诊断式审阅（Review / Audit）**，可在**任意仓库**（无论是否接入 `.guardrails/`）独立运行，默认不修改被审源文件。

## 目录结构

```text
poteto-review/
├── SKILL.md                                    # 主入口：审阅姿态、五步流程与六把审阅手术刀
├── README.md
├── agents/openai.yaml                          # Codex 等宿主显示元数据
├── references/
│   ├── 01-review-rubric-and-modes.md           # 四大审阅模式、分级标签与标准输出模板
│   └── 02-case-anchors-and-boundaries.md       # 一手案例锚点与防教条误用红线
├── scripts/
│   ├── poteto_audit.py                         # 离线只读确定性审阅雷达（支持全仓与 --diff）
│   └── install.py                              # 五端跨宿主安装、校验与卸载脚本
└── tests/
    ├── test_poteto_audit.py
    └── test_install_and_skill.py
```

## 四大审阅模式

1. **Mode A — PR / Diff 审阅**：聚焦原子序列、唯一状态拥有者、边界解析与内部信任、Comment-Sicko 反借口与双编辑测试。
2. **Mode B — 仓库架构与代码库健康度体检**：参照 Dune 五层防线检查目录边界、脚枪 API 收口、依赖阻断、花园杂草传染源与信任阶梯卡点。
3. **Mode C — 验证与测试套件审阅**：用双编辑测试猎杀虚绿与同义反复测试，审计 `feature-map`/驱动 CLI 剥离度与高风险区形式化需求。
4. **Mode D — Agent 工作流 / `AGENTS.md` / Skill / 多 Bot 编排审阅**：以 Dr. Eggbot 视角审计散文肥胖、上下文溢出、主管职责纯粹性、Routine 缓冲队列与双盲 Eval 防作弊。

## 确定性雷达脚本 `poteto_audit.py`

审阅前先运行雷达 CLI，把计数、行号与气味检索从 LLM 上下文中剥离出去：

```bash
# 全仓体检（人读摘要）
python -X utf8 scripts/poteto_audit.py --root /path/to/repo

# 仅聚焦相对 main（或 HEAD）改动及未跟踪文件，输出 JSON
python -X utf8 scripts/poteto_audit.py --root /path/to/repo --diff main --json
```

脚本仅使用 Python 3 标准库、严格只读目标仓库，输出四层雷达信号：巨石文件（`>500` 行）、屏蔽/压制符、借口注释与连篇注释说教、症状补丁（裸定时器/阻塞 sleep/空异常吞错）、测试气味（重度 Mock/跳过/永真断言）以及 `AGENTS.md`/`SKILL.md` 散文膨胀指标。

## 安装、校验与测试

```bash
# 预览五端安装（claude / cursor / codex / agents / pi）
python -X utf8 scripts/install.py --target all --dry-run

# 执行安装与内置校验
python -X utf8 scripts/install.py --target all

# 卸载已安装版本
python -X utf8 scripts/install.py --target all --uninstall

# 运行单元测试与文件完整性校验
python -X utf8 -B -m unittest discover -s tests -p "test_*.py" -v
```
