# radar-sim-simulation Skill

## 作用

这个 Skill 为不同 Agent 对话框提供统一的 Selena 仿真入口：

```text
当前代码环境
  → Skill 发现候选
  → 生成 UserRunConfig 2.0 YAML
  → 向用户确认不确定的业务输入
  → 自动准备 MCP/SDK/Connector 能力
  → MCP 提交仿真 Job
  → 查询进度、诊断、Manifest 和结果
```

用户不需要填写 MCP 地址、Connector 路径、Agent ID、Stage ID、TransferPlan、Runtime Bundle ID 或 Cluster 内部参数。

## 目录

- `SKILL.md`：Agent 加载的主流程和行为约束；
- `agents/openai.yaml`：Skill 展示信息和默认触发提示；
- `references/configuration-policy.md`：代码环境发现、候选选择和 YAML 字段规则；
- `references/tool-contract.md`：MCP 工具输入、输出、错误和外围自动准备规则；
- `scripts/discover_candidates.py`：只读发现 Git、嵌套 Git、编译脚本、Runtime、Selena.exe 和 MF4 候选的标准脚本。

## 在 Agent 中安装

克隆本仓库后，将以下目录注册到 Agent 的 Skill Registry：

```text
skills/radar-sim-simulation
```

支持 Git 子目录安装的 Agent 可以直接使用：

```text
<owner>/<repository>/skills/radar-sim-simulation
```

安装后，在 Agent 对话框中输入：

```text
使用 radar-sim-simulation Skill，基于当前代码仓配置并运行 Selena 仿真；不确定的业务输入先问我，确认后再提交。
```

## 行为约束

- 用户提供完整 YAML 时走快速校验路径，不重复扫描代码仓；
- 缺少字段时只发现相关候选，不读取代码、Runtime、MF4 或结果正文；
- 多个候选不静默选择，必须向用户确认；
- 自动处理 MCP/SDK/Connector 检查、能力检查、任务生命周期和结果下载；
- `partial`、`failed`、`cancelled` 和观察超时必须如实返回；
- 不通过 Web UI，不根据项目名猜测内部参数，不修改用户代码仓。

## 本地验证

在仓库根目录执行：

```bash
python <skill-creator>/scripts/quick_validate.py skills/radar-sim-simulation
python skills/radar-sim-simulation/scripts/discover_candidates.py --root <code-root>
```

Skill 的 Python 脚本只使用标准库；MCP/SDK 是运行仿真时由 Agent 环境提供的外部接口，不包含在本仓库中。
