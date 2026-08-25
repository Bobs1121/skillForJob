# Skills

公共多 Skill 仓库，提供可复用的团队级 AI 辅助能力。每个 Skill 独立成目录，自包含定义、脚本、配置和文档，按需复制或注册到 Agent 中使用。

## 仓库结构

```text
skills/
├── code-review/                    # 自适应代码审查 Skill
│   ├── review.md                   # Skill 定义（/review 入口）
│   └── scripts/
│       └── analyze_repo.py         # 代码仓画像构建脚本
├── bosch-data-transfert/           # 数据 + arbe 环境一键准备 Skill
│   ├── SKILL.md
│   ├── README.md
│   ├── profiles/
│   ├── references/
│   └── scripts/
└── radar-sim-simulation/           # Selena 雷达仿真 Skill
    ├── SKILL.md                    # Agent Skill 主入口
    ├── README.md                   # Skill 内部使用说明
    ├── VERSION                     # Skill 版本
    ├── agents/                     # Agent 展示和触发信息
    ├── references/                 # YAML/MCP 合同和配置规则
    └── scripts/                    # 只读环境发现脚本

solutions/
└── requirements-code-assistant/    # 原子需求 Vault + Requirements MCP + Agent Skill

docs/
└── usage-guide.md                  # 多 Skill 通用使用指南
```

## 快速开始

### 1. 将 Skill 注册到 Agent

```bash
git clone https://github.com/Bobs1121/skillForJob.git
```

在 Agent 支持的 Skill Registry 中注册需要的目录，例如：

```text
skills/radar-sim-simulation
```

支持 Git 子目录安装的 Agent 可以直接使用：

```text
Bobs1121/skillForJob/skills/radar-sim-simulation
```

### 2. 使用雷达仿真 Skill

在任意 Agent 对话框中输入：

```text
使用 radar-sim-simulation Skill，基于当前代码仓配置并运行 Selena 仿真；不确定的业务输入先问我，确认后再提交。
```

Skill 会根据当前代码仓发现 Git、嵌套 Selena 子仓、编译脚本、Runtime、Selena 产物和 MF4 候选，生成 `UserRunConfig 2.0` YAML，并自动处理 MCP/SDK/Connector 检查、任务提交、进度、诊断、Manifest 和结果下载。

用户不需要下载 radar-sim 源码或填写内部 Agent、Stage、Transfer、Runtime Bundle 和 Cluster 参数。

### 3. 使用其他 Skill

打开 Claude Code 或其他 Agent，按各 Skill 的触发方式调用；具体安装和配置见对应目录的 README。

## 可用 Skills

| Skill | 触发 | 描述 |
|-------|------|------|
| code-review | `/review` | 自适应三层结构化代码审查 |
| bosch-data-transfert | 数据/arbe 一键 | 数据准备 + arbe 切分支/编译/启动一体化 |
| requirement-code-traceability | `$requirement-code-traceability` | 需求问答、代码一致性检查与实施方案 |
| radar-sim-simulation | `$radar-sim-simulation` | 基于当前代码环境配置、提交和跟踪 Selena 仿真 |

## Solutions

[`solutions/requirements-code-assistant`](solutions/requirements-code-assistant/README.md) 是完整的端到端方案，包含原子需求 Vault、Requirements MCP、作用域化 CodeGraph MCP 与 Agent Skill，适合需要持久化需求知识库的场景。

## 添加新 Skill

1. 在 `skills/` 下创建独立目录，目录名使用小写字母、数字和连字符；
2. 编写 `SKILL.md`，frontmatter 必须包含 `name` 和 `description`；
3. 将确定性辅助脚本放入 `scripts/`；
4. 将详细合同和大段参考信息放入 `references/`；
5. 添加内部 `README.md`，说明安装、使用和验证方式；
6. 更新本 README 的可用 Skills 表格；
7. 使用 Skill validator 验证后提交 PR。

## License

Internal Use Only
