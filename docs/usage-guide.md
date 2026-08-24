# 多 Skill 使用指南

本仓库是**多 Skill 仓库**。通用安装方式见下；每个 skill 的专属配置与操作见其各自 README。

## 安装（通用）

### 方式一：直接复制（推荐）

把 `skills/` 下你需要的 skill 目录复制到你的代码仓：

```bash
# 在你的代码仓根目录下
mkdir -p skills
cp -r /path/to/claude-code-skills/skills/<skill-name> skills/<skill-name>
```

### 方式二：Git Submodule

```bash
# 在你的代码仓根目录下
git submodule add <remote-url> skills/<skill-name>
```

### 方式三：符号链接（本地开发用）

```bash
mkdir -p skills
ln -s /c/claude-code-skills/skills/<skill-name> skills/<skill-name>
```

## 可用 Skills 一览

| Skill | 触发 | 安装/使用 |
|-------|------|-----------|
| code-review | `/review` | [skills/code-review](skills/code-review/) |
| bosch-data-transfert | 数据/arbe 一键 | [skills/bosch-data-transfert/README.md](skills/bosch-data-transfert/README.md) |
| requirement-code-traceability | `$requirement-code-traceability` | [solutions/requirements-code-assistant/README.md](solutions/requirements-code-assistant/README.md) |

## 各 Skill 快速使用

### code-review（自适应代码审查）

在 VSCode 打开 Claude Code，输入 `/review`。首次运行自动做 Repo Profiling（约 20-30s），后续秒级启动。

### bosch-data-transfert（数据 + arbe 环境一键准备）

用于 Bosch 内网 CR60/BYD 项目：把问题单相关 bag 数据拷贝到 Linux 分析服务器，并完成 arbe 环境切分支 → 配车型 CUDA → 应用仿真改动 → 编译 → 启动。

核心用法（在目标服务器上）：

```bash
bash setup_arbe.sh <tag> [<车型>] [--skip-build] [--start]
```

配置差异通过 `profiles/<项目>.yml` 注入；不明确的值会**咨询用户**，AI 推断出的车型/CUDA/tag 也需**用户最终确认**后才执行。

详细见 [skills/bosch-data-transfert/README.md](skills/bosch-data-transfert/README.md)。

### requirement-code-traceability（需求追踪）

需求问答、代码一致性检查与实施方案。需要先按
[solutions/requirements-code-assistant/README.md](solutions/requirements-code-assistant/README.md) 初始化需求 Vault 与 MCP 服务。

## 常见问题

**Q: 每个 skill 都需要安装吗？**
A: 不必。按需复制用到的那个即可，skill 互相独立、自包含。

**Q: Skill 配置放哪？**
A: 每个 skill 内部有 `profiles/`（如有）或参考其 README。配置随 skill 走，复制到代码仓后改本地那份即可。

**Q: 能贡献新 skill 吗？**
A: 可以。按根 README「添加新 Skill」一节，在 `skills/` 下建目录、写 `SKILL.md` + `README.md`，提交 PR。
