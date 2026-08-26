# radar-sim-simulation Skill

当前版本：`0.4.2`

这个 Skill 是 Agent 对话中的 Selena 仿真统一入口。用户把 Skill 交给
Agent 后，通常只需要说明要仿真的数据；MCP/SDK/Connector 的首启、更新、
配置、传输、任务生命周期和结果校验由 Skill 在后台自动完成。

流程：

```text
当前代码/数据环境
  → 恢复或生成 UserRunConfig 2.0
  → 首次只确认真正影响仿真含义的业务歧义
  → 后续自动准备能力、提交、等待、重试、诊断和收集结果
```

用户不需要下载 radar-sim 源码，也不需要填写 MCP 地址、Connector 路径、
Agent ID、Stage ID、TransferPlan、Runtime Bundle ID 或 Cluster 内部参数。

## 运行行为

- 首次配置时，如数据、Selena 来源或 Runtime 候选存在业务歧义，合并询问
  一次；
- 配置确认后不再反复询问 `allow`、更新、Connector、自查、等待或重试；
- Skill 在本机 MCP 的 active profile 中静默保存上次配置、代码仓/产物上下文、
  数据路径、Job ID 和状态，不保存文件正文或凭据；
- 用户说“帮我再仿真一下刚刚的数据”“再跑一次”“我改了这里，重新验证”
  时，自动恢复 active profile；用户给出新数据时只替换数据字段；
- “我改了这里，重新仿”选择当前代码 `build`，实际跳过/增量/全量由后端
  根据分支、代码变化和 Selena 产物证据决定；
- “用现有 Selena/不要编译”保持 `existing`，不编译；
- 中间处理成功时不向用户展示服务地址、版本、本机路径、校验值、安装日志
  或能力自查状态；默认只返回最终结果地址，用户明确要求时才补充 Job、进度、
  诊断或 Manifest。
- 在 VS Code/Copilot 中，首次运行前指导用户完成一次工作区/会话级
  `Bypass Approvals` 配置；之后不重复询问 `Allow`、`Confirm`、`Continue`。
  不默认使用可能自动回答业务问题的 `Autopilot`。
- 仿真完成后默认返回解压好的结果目录；原始 ZIP 只保留在目录内部的 `.radar-sim` 元数据目录中，用于校验和恢复。

- 所有数据、Runtime、构建来源等业务输入必须在仿真前一次收齐；不会运行几段
  Stage 后再追加询问。

## 首启和自动更新

首启由 Agent 内部完成：Skill 会从部署元数据获取服务入口，下载并校验无源码
Agent Tools Bundle，安装 SDK、MCP 和 Skill，并注册本机 stdio MCP。后续启动
自动检查兼容版本并 side-by-side 更新。服务地址不是 Skill 逻辑的一部分，部署
迁移只需替换 provider-owned 元数据。MCP launcher 的人类可读进度写入 stderr，
stdout 保留给 MCP JSON-RPC，不使用 `python -` 交互式入口。

本 Skill 目录包含：

- `SKILL.md`：Agent 主流程和静默执行规则；
- `agents/openai.yaml`：展示信息和默认触发提示；
- `references/configuration-policy.md`：语义配置、重复运行和候选规则；
- `references/copilot-approvals.md`：Copilot/VS Code 审批、终端和 MCP 的一次性配置；
- `references/tool-contract.md`：MCP 工具、状态、错误和自动准备合同；
- `references/service-profile.json`：由安装环境注入的服务元数据，公共版本为空；
- `scripts/discover_candidates.py`：只读环境发现；
- `scripts/bootstrap_agent_tools.py`：首启无源码能力引导；
- `scripts/start_mcp.py`：可作为本机 stdio MCP 的静默启动入口。

## 在 Agent 中安装

将以下目录注册到 Agent 的 Skill Registry：

```text
skills/radar-sim-simulation
```

安装后只需告诉 Agent：

```text
使用 radar-sim-simulation Skill，仿真当前需要验证的数据。
```

Skill 会基于当前代码仓和 active profile 自动补齐其余配置；只有缺少真正的
业务输入时才会询问。

公共分发约束：服务地址、用户、Agent ID、Token、代码仓和结果路径均不得写死；
由 `RADAR_SIM_SERVICE_URL`/`RADAR_SIM_BASE_URL`、本机 MCP 配置和当前用户环境
动态解析。安装时生成的 profile、credentials 和 catalog 不属于公共 Skill。

Skill 的 Python 脚本只使用标准库；SDK/MCP/Connector 由服务端无源码分发。

## 与 Agent 对话：从安装到仿真

以下示例适用于 Copilot、Claude Code 和其他支持 Skill/MCP 的 Agent。用户不需要下载 `radar-sim` 源码；Skill 负责触发服务端 Agent Tools 的下载、校验、安装和更新。

### 首次安装和 MCP 初始化

把 Skill 仓库交给 Agent，并发送：

```text
请安装并启用 radar-sim-simulation Skill：
https://github.com/Bobs1121/skillForJob.git
子目录：skills/radar-sim-simulation

完成首次 MCP 初始化和握手。SDK、MCP、Connector 和更新都从服务提供方的
Agent Tools 服务获取，不要下载 radar-sim 源码。所有常规准备自动完成；只在
仿真业务输入确实不明确时，一次性合并询问，不要中间逐个询问 Allow、Confirm
或 Continue。
```

Copilot 首次出现权限菜单时，将当前工作区/会话从 `Default Approvals` 切换到 `Bypass Approvals`。不建议开启全局 `chat.tools.global.autoApprove`；版本和配置差异见 `references/copilot-approvals.md`。

首次初始化可能需要 Agent 重载一次 MCP 或重新加载窗口。完成后，不要每次仿真重复安装或注册 MCP。

### 首次仿真

最小输入：

```text
使用 radar-sim-simulation Skill，仿真这个数据：
D:/measurements/example.MF4
```

目录输入：

```text
使用 radar-sim-simulation Skill，仿真这个目录：
D:/measurements/example-batch
```

Skill 会从当前代码仓和已有 Agent profile 发现候选，并生成/校验 `UserRunConfig 2.0`。多个 MF4、Runtime、编译脚本或 Selena 产物无法区分时，Agent 会在任何 Connector、传输、编译和提交之前一次性列出合并问题。

### 重复和修改后仿真

```text
用刚刚的数据再仿真一次。
```

```text
我刚修改了当前代码，请用刚刚的数据重新仿真验证。
```

```text
请使用已经配置好的 Selena 产物，不要编译，用这个数据仿真：
D:/measurements/example.MF4
```

Skill 会恢复上次的 active profile。用户说“修改后重新仿真”时使用当前代码 `build`，由后端根据 Selena 分支、代码变化和已有产物证据决定跳过、增量或全量编译；用户不需要在 YAML 中填写这些内部编译模式。

### 正常输出

完成后只需关注本机解压结果目录：

```text
仿真完成
结果地址：<verified local extracted result directory>
```

目录中直接有 MF4、日志和结果文件。原始 ZIP 只保留在目录内部 `.radar-sim` 中用于校验和恢复；MCP 默认返回 `format=directory`。若某个旧 SDK 集成仍需要 ZIP，可显式使用 `extract=false`。

### 用户不需要处理的内容

SDK/MCP/Connector 首启、更新、启动、版本检查、readiness、数据传输、Selena 编译、Job 轮询、可恢复重试、结果下载和解压都由 Skill/MCP/服务端自动完成。对话中不应出现逐步的 `Allow`、`Confirm`、`Continue`、Stage 或 Transfer 操作确认。

只有以下情况才需要用户参与：数据或仿真语义无法判断、显式业务字段互相冲突、宿主强制安全策略拒绝必要操作，或用户主动要求取消/更换执行目标。
