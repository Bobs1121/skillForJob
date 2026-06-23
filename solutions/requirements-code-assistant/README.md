# Requirements-Code Assistant

可复用的“需求事实库 + 代码智能 + Agent 编排”工具：

- 回答功能要求，并返回文档版本、章节和页码；
- 将原子需求与代码逐字段比较；
- 区分候选实现、实现一致和测试验证；
- 根据需求及代码结构生成实施方案；
- 通过两个独立 MCP 供 Codex、Claude Code 或其他 Agent 调用。

本目录不包含客户 PDF、私有需求或代码索引，只提供框架、模板和示例。

## 架构

```text
Requirements Vault                 Source repository
Markdown atomic notes              CodeGraph index
        |                                 |
requirements_mcp.py                 codegraph_mcp_proxy.py
        |                                 |
        +----------- Agent/Skill ---------+
                     |
       Q&A / consistency / implementation plan
```

需求与代码拆成两个接口：

- Requirements MCP 管理规范事实和追踪状态；
- Code MCP 提供代码符号、关系和影响分析；
- Skill 组合证据并推理。

这样可以替换任一底层实现，也避免把 PDF、代码和推理揉成一个巨型知识库。

## 目录

```text
requirements-code-assistant/
├── servers/                 # 两个 stdio MCP
├── src/traceability/        # 需求解析、MCP 和作用域过滤
├── scripts/                 # Vault 初始化、查询和校验
├── templates/vault/         # 可复制的 Obsidian Vault
├── skill/                   # Agent Skill
└── tests/
```

## 环境要求

- Python 3.10+
- 可选：CodeGraph 0.9+，用于代码接口
- Python 部分无第三方依赖

## 1. 创建需求 Vault

```powershell
python scripts/init_vault.py D:\knowledge\my-project-requirements `
  --project "My Project"
```

生成：

```text
my-project-requirements/
├── index.md
├── SCHEMA.md
├── Sources/
├── Features/
├── Requirements/Atomic/
├── Evidence/
└── Templates/
```

Vault 可以由 Obsidian 打开，但 Markdown 才是事实源，Obsidian 不是运行依赖。

## 2. 扩展需求文档

不要把整份 PDF 当成一个知识块。推荐流程：

1. 创建来源文档卡，记录文件、版本、日期和适用产品；
2. 按“一个可判断、可测试的陈述”拆成原子需求；
3. 保留原文页码和章节；
4. 将数值、状态、输入和输出规范化到 `requirement-json`；
5. 初始代码状态设为 `unknown` 或 `candidate`；
6. 人工复核后将 `review_status` 改为 `reviewed`；
7. 运行校验。

```powershell
python scripts/validate_vault.py D:\knowledge\my-project-requirements
```

原子需求核心结构：

```yaml
---
requirement_id: SYS-RCTB-001
feature: RCTB
source_document: RCTAB-SPEC
source_version: A/8
source_pages: [22]
source_sections: ["6.2.2.1"]
review_status: reviewed
implementation_status: candidate
verification_status: unverified
---
```

正文中再放一个机器可读块：

````text
```requirement-json
{
  "requirement_id": "SYS-RCTB-001",
  "feature": "RCTB",
  "kind": "activation",
  "conditions": {"ttc_max_s": 1.6},
  "source": {"document": "RCTAB-SPEC", "version": "A/8", "pages": [22]},
  "code_candidates": [],
  "test_evidence": []
}
```
````

机密文档建议只保存必要的结构化摘要和定位信息。是否保存原文片段应服从组织的数据分级政策。

## 3. 查询需求

```powershell
python scripts/requirements_cli.py `
  --vault D:\knowledge\my-project-requirements list

python scripts/requirements_cli.py `
  --vault D:\knowledge\my-project-requirements search "RCTB TTC"

python scripts/requirements_cli.py `
  --vault D:\knowledge\my-project-requirements get SYS-RCTB-001
```

输出为 UTF-8 JSON。

## 4. 建立 CodeGraph 索引

在代码仓库中：

```powershell
codegraph init .
codegraph index .
codegraph status .
```

多产品 monorepo 必须限制作用域：

```powershell
$env:CODE_REPO="D:\repo\project"
$env:CODE_ALLOWED_ROOTS="coem/TARGET_VARIANT,asw,adas,integration,rte,mmwave"
$env:CODE_VARIANT_ROOT="coem/TARGET_VARIANT"
```

代理会丢弃其他 `coem/*` 结果。其他产品变体不能作为目标产品的实现证据。

## 5. 启动 MCP

两个服务均使用 stdio transport。

### Requirements MCP

```powershell
$env:REQUIREMENTS_VAULT="D:\knowledge\my-project-requirements"
python servers/requirements_mcp.py
```

工具：

- `requirements_search`
- `requirements_get`
- `requirements_list_features`
- `requirements_validate`

### CodeGraph MCP proxy

```powershell
$env:CODE_REPO="D:\repo\project"
$env:CODE_ALLOWED_ROOTS="coem/TARGET_VARIANT,asw,adas,integration,rte,mmwave"
python servers/codegraph_mcp_proxy.py
```

工具：

- `code_search`
- `code_callers`
- `code_callees`
- `code_impact`
- `code_context`

代理只执行查询命令，不修改源码、不重建索引。

如果 `codegraph` 不在 PATH：

```powershell
$env:CODEGRAPH_CMD="D:\tools\codegraph.ps1"
```

## 6. Agent MCP 配置

不同客户端的配置文件位置不同，核心配置一致：

```json
{
  "mcpServers": {
    "project-requirements": {
      "command": "python",
      "args": ["D:/skillForJob/solutions/requirements-code-assistant/servers/requirements_mcp.py"],
      "env": {
        "REQUIREMENTS_VAULT": "D:/knowledge/my-project-requirements"
      }
    },
    "project-code": {
      "command": "python",
      "args": ["D:/skillForJob/solutions/requirements-code-assistant/servers/codegraph_mcp_proxy.py"],
      "env": {
        "CODE_REPO": "D:/repo/project",
        "CODE_ALLOWED_ROOTS": "coem/TARGET_VARIANT,asw,adas,integration,rte,mmwave",
        "CODE_VARIANT_ROOT": "coem/TARGET_VARIANT"
      }
    }
  }
}
```

## 7. 安装 Skill

Codex 示例：

```powershell
Copy-Item -Recurse `
  skill\requirement-code-traceability `
  "$env:USERPROFILE\.codex\skills\requirement-code-traceability"
```

使用示例：

```text
使用 $requirement-code-traceability，告诉我 RCTB 激活要求，
并检查当前目标车型代码是否一致。
```

```text
使用 $requirement-code-traceability，根据新的 BSD 退出速度需求，
结合当前代码给出实施方案和测试矩阵。
```

其他 Agent 只要支持 Skill Markdown 或 MCP，也可复用同样的接口。

## 8. 一致性状态

| 状态 | 含义 |
|---|---|
| `candidate` | 找到语义或符号候选，尚未逐项证明 |
| `matched` | 参数、逻辑和接口有直接代码证据且一致 |
| `mismatch` | 直接代码证据与需求冲突 |
| `missing` | 在正确作用域中未找到实现 |
| `unknown` | 信息不足或实现不可见 |

验证状态独立维护：

- `unverified`
- `partial`
- `verified`
- `failed`

“实现一致但未测试”不能称为完整完成。

## 9. CodeGraph 与 Graphify

默认选择 CodeGraph：它直接支持符号查询、callers/callees、impact、affected、context 和 MCP，适合研发自动化。

Graphify 更适合社区聚类、跨仓库图和可视化探索。两者的 AST 图谱与影响分析存在重叠，不建议同时维护两套全量索引。需要宏观架构探索时再按需运行 Graphify。

## 10. 测试

```powershell
python -m unittest discover -s tests -v
python scripts/validate_vault.py templates/vault
```

## 安全边界

- 不将客户 PDF、受控需求原文或私有源码提交到公共仓库；
- 不保存账号、Token 或密钥；
- MCP 默认只读；
- 其他产品变体不作为目标产品的实现证据；
- AI 产生的映射必须先标记为 `candidate`。
