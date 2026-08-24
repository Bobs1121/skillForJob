#Skills

公共 **多 Skill 仓库**，提供可复用的团队级 AI 辅助能力。每个 skill 独立成目录，自包含（定义 + 脚本 + 配置 + 文档），按需复制到你的代码仓即可使用。

## 仓库结构

```
skills/
├── code-review/                    # 自适应代码审查 Skill
│   ├── review.md                   # Skill 定义（/review 入口）
│   └── scripts/
│       └── analyze_repo.py         # 代码仓画像构建脚本
│
└── bosch-data-transfert/           # 数据 + arbe 环境一键准备 Skill
    ├── SKILL.md                    # Skill 定义（触发词 / 流程 / 配置注入总入口）
    ├── README.md                   # 使用指南
    ├── profiles/                   # 配置（每项目一份，改这里不用动代码）
    │   ├── _template.yml           # 新同事复制改名即可
    │   └── cr60-byd.yml            # CR60/BYD 默认值
    ├── references/
    │   └── environment.md          # 环境/权限/地址速查
    └── scripts/
        ├── data_transfert.py       # 数据同步（通用化核心）
        └── setup_arbe.sh           # arbe 一键（切tag→拷CUDA→改yaml→验证仿真→编译）

solutions/
└── requirements-code-assistant/    # 完整方案：原子需求 Vault + Requirements MCP + Agent Skill
    └── skill/requirement-code-traceability/   # 需求问答、代码一致性检查 Skill

docs/
└── usage-guide.md                  # 多 Skill 通用使用指南
```

## 快速开始

### 1. 将某个 Skill 复制到你的代码仓

```bash
# 在你的代码仓根目录下，把 skills/ 下需要的 skill 复制进来
mkdir -p skills
cp -r /path/to/claude-code-skills/skills/<skill-name> skills/<skill-name>
```

每个 skill 的具体安装/使用/配置，见各自的 README：

| Skill | 文档 |
|-------|------|
| code-review | [skills/code-review](skills/code-review/) |
| bosch-data-transfert | [skills/bosch-data-transfert/README.md](skills/bosch-data-transfert/README.md) |
| requirement-code-traceability | [solutions/requirements-code-assistant](solutions/requirements-code-assistant/README.md) |

### 2. 使用

打开 Claude Code（或你的 Agent），按各 skill 的触发方式调用即可（见下表）。

## 可用 Skills

| Skill | 触发 | 描述 |
|-------|------|------|
| code-review | `/review` | 自适应三层结构化代码审查 |
| bosch-data-transfert | 数据/arbe 一键 | 数据准备 + arbe 切分支/编译/启动 一体化 |
| requirement-code-traceability | `$requirement-code-traceability` | 需求问答、代码一致性检查与实施方案 |

## Solutions

`[solutions/requirements-code-assistant](solutions/requirements-code-assistant/README.md)`：完整的端到端方案（原子需求 Vault、Requirements MCP 服务、作用域化 CodeGraph MCP 与 Agent Skill），比单一 skill 更重，适合需要持久化需求知识库的场景。

## 添加新 Skill

1. 在 `skills/` 下创建新目录，命名用小驼峰 + 连字符（如 `bosch-data-transfert`）
2. 编写 `SKILL.md`（或 `<skill-name>.md`）定义文件，frontmatter 含 `name` + `description`（触发词）
3. 辅助脚本放入 `scripts/`；配置模板放入 `profiles/`；速查放入 `references/`
4. 写一个 `README.md` 作为该 skill 的使用指南
5. 更新本 README 的「可用 Skills」表格
6. 提交 PR

## License

Internal Use Only
