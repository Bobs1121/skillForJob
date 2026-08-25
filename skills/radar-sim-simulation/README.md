# radar-sim-simulation Skill

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
- `references/tool-contract.md`：MCP 工具、状态、错误和自动准备合同；
- `references/service-profile.json`：部署注入的服务元数据；
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

Skill 的 Python 脚本只使用标准库；SDK/MCP/Connector 由服务端无源码分发。
