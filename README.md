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
    └── scripts/                    # 环境发现、首启引导和静默启动脚本

solutions/
└── requirements-code-assistant/    # 原子需求 Vault + Requirements MCP + Agent Skill

docs/
└── usage-guide.md                  # 多 Skill 通用使用指南
```

## 快速开始

### 1. 让 Agent 安装 Skill

在目标代码仓中打开 Copilot、Claude Code 或其他支持 Skill 的 Agent，直接发送：

```text
请安装并启用 radar-sim-simulation Skill，来源是：
https://github.com/Bobs1121/skillForJob.git
子目录：skills/radar-sim-simulation

不要下载 radar-sim 源码。SDK、MCP、Connector 和后续更新都从服务提供方的
Agent Tools 服务自动获取。完成首次 MCP 初始化和握手后，再告诉我仿真还缺少
哪些业务输入；不要在中间步骤逐个询问 Allow、Confirm 或 Continue。
```

支持 Git 子目录安装的 Agent 也可以直接注册：

```text
Bobs1121/skillForJob/skills/radar-sim-simulation
```

Skill 的服务地址由安装环境、环境变量或服务提供方的本机配置注入。用户不需要填写服务器内部地址、Agent ID、Stage、TransferPlan 或 Runtime Bundle ID。

### 2. 完成首次 MCP 初始化

首次初始化时，Agent 会自动完成：

- 下载并校验无源码 Agent Tools Bundle；
- 安装版本化 SDK、MCP 和 Skill；
- 注册本机 stdio MCP；
- 检查并按策略更新 MCP/SDK/Skill；
- 检查 Windows Connector，并在受控策略下自动安装或更新。

如果 Copilot 的权限选择器显示 `Default Approvals`，首次使用前将当前会话或当前工作区切换为 `Bypass Approvals`。只需配置一次；不要使用全局自动批准。详细设置见 [Skill 内部 README](skills/radar-sim-simulation/README.md) 和 [Copilot 审批说明](skills/radar-sim-simulation/references/copilot-approvals.md)。

初始化完成后，通常只需要重新加载一次 Agent/MCP 会话，之后仿真流程不再逐阶段点击确认。

### 3. 首次仿真

只提供数据路径即可：

```text
使用 radar-sim-simulation Skill，仿真这个数据：
D:/measurements/example.MF4
```

如果是一个目录：

```text
使用 radar-sim-simulation Skill，仿真这个目录中的数据：
D:/measurements/example-batch
```

Skill 会基于当前代码仓和已有环境发现 Selena、Runtime、编译脚本和数据候选。只有会改变仿真含义的字段无法确定时，才一次性合并询问；不会先运行几段 Stage 再追加询问 Runtime 或 MatFilter。

### 4. 常用对话

代码修改后重新仿真：

```text
我刚修改了当前代码，请用刚刚的数据重新仿真验证。
```

明确要求编译当前代码：

```text
请编译当前 Selena 代码，并用刚刚的数据仿真。
```

使用已经存在的 Selena，不编译：

```text
请使用已经配置好的 Selena 产物，不要编译，用这个数据仿真：
D:/measurements/example.MF4
```

重复上一次任务：

```text
用刚刚的数据再仿真一次。
```

Skill 会恢复上一次确认的代码仓、Selena 来源、Runtime、目标、数据和 Job 上下文。用户给出新数据时，只替换数据字段。

### 5. 用户需要提供什么

通常只需要提供：

- 要仿真的 MF4 文件或目录；
- 是否使用当前代码编译，或使用已有 Selena（如果对话语义已明确则不必单独填写）；
- 多个数据、Runtime、编译脚本或 Selena 产物无法区分时的选择。

以下内容由 Skill/MCP/服务端自动处理，用户不需要填写：

- SDK、MCP、Connector 的安装路径和版本；
- Agent ID、Stage ID、TransferPlan、Runtime Bundle ID；
- Cluster 内部路径、Worker、Gateway、调度和传输参数；
- 增量/全量编译字段；后端根据分支、代码变化和产物证据决定；
- 结果归档、下载和 checksum 校验。

### 6. 完成后的输出

仿真成功后，正常只返回：

```text
仿真完成
结果地址：<本机已校验的解压结果目录>
```

结果目录直接包含 MF4、`result.ini` 等输出文件。原始 ZIP 只保存在结果目录内部的 `.radar-sim` 元数据目录中，用于校验和恢复，不作为用户最终结果地址。

### 7. 异常处理

- MCP 尚未安装：Agent 自动从服务提供方下载、校验并注册；
- MCP 版本不兼容：Agent 自动 side-by-side 更新并重启/重载；
- Connector 未连接：Agent 自动检查并按策略修复；
- 临时网络、传输或 Stage 错误：复用同一 Job 和幂等键进行可恢复重试；
- Cluster readiness 未通过：任务不会盲目提交，Agent 返回一次简短原因；
- 结果 checksum 或解压校验失败：拒绝返回不可信结果，不覆盖已有目录。

正常流程中的中间状态、重试和安装日志保留在隐藏终端/日志中，不刷屏对话。

### 3. 使用其他 Skill

打开 Claude Code 或其他 Agent，按各 Skill 的触发方式调用；具体安装和配置见对应目录的 README。

## 可用 Skills

| Skill | 触发 | 描述 |
|-------|------|------|
| code-review | `/review` | 自适应三层结构化代码审查 |
| bosch-data-transfert | 数据/arbe 一键 | 数据准备 + arbe 切分支/编译/启动一体化 |
| requirement-code-traceability | `$requirement-code-traceability` | 需求问答、代码一致性检查与实施方案 |
| radar-sim-simulation | `$radar-sim-simulation` | 基于当前代码环境静默配置、提交和跟踪 Selena 仿真 |

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
