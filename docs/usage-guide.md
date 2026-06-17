# Code Review Skill 使用指南

## 安装

### 方式一：直接复制（推荐）

将 `skills/code-review/` 目录复制到你的代码仓中：

```bash
# 在你的代码仓根目录下
mkdir -p .claude/skills
cp -r /path/to/claude-code-skills/skills/code-review .claude/skills/
```

### 方式二：Git Submodule

```bash
# 在你的代码仓根目录下
git submodule add <remote-url> .claude/skills-source
ln -s ../.claude/skills-source/skills/code-review .claude/skills/code-review
```

### 方式三：符号链接（本地开发用）

```bash
mkdir -p .claude/skills
ln -s /c/claude-code-skills/skills/code-review .claude/skills/code-review
```

## 使用

在 VSCode 中打开 Claude Code，输入：

```
/review
```

### 首次运行

首次运行时，Skill 会自动执行 **Repo Profiling**：
- 扫描目录结构和构建系统
- 推断代码约定（命名、格式、安全模式）
- 分析 git 历史识别风险热点
- 生成 `.claude/repo_profile.json`

耗时约 20-30 秒（取决于代码仓大小）。

### 后续运行

Profile 会缓存在 `.claude/repo_profile.json`，后续 `/review` 秒级启动。
当代码仓发生重大变化时（50+ commits），会自动增量更新 profile。

## Review 输出说明

Review 结果分为三个级别：

| 级别 | 含义 | 行动 |
|------|------|------|
| 🔴 Critical | 必须修复 | 阻塞合入 |
| 🟡 Warning | 强烈建议修复 | 需回应 |
| 🟢 Suggestion | 可选优化 | 酌情采纳 |

每条 finding 包含：
- 文件和行号定位
- 所属审查层级（代码/逻辑/语义）
- 基于项目约定的具体问题描述
- 修复建议
- 置信度评估

## 自定义

### 补充项目知识

在项目根目录创建或编辑 `CLAUDE.md`，添加 AI 无法自动推断的项目知识：

```markdown
# 项目特定知识

## 业务术语
- FCTA: Front Cross Traffic Alert
- RCTA: Rear Cross Traffic Alert  
- DOW: Door Opening Warning

## 标定流程
所有阈值参数修改必须在 commit message 中标注对应的标定报告编号。

## 已知限制
- ip_ra5 模块为第三方提供，不做 review
- gen/ 目录下的代码由 Selena 工具链自动生成
```

### 调整审查重点

编辑 `.claude/skills/code-review/review.md` 中的检查项，增删改查以适应团队需求。

## 常见问题

**Q: Profiling 太慢怎么办？**
A: 确保安装了 ripgrep (`rg`)，比 grep 快一个数量级。Windows: `choco install ripgrep` / `scoop install ripgrep`

**Q: Profile 需要提交到 git 吗？**
A: 不需要。建议加入 `.gitignore`。每个同事本地生成即可。

**Q: 如何跳过某些目录的 review？**
A: 在 `CLAUDE.md` 中说明，或在 profiling 脚本的 `GENERATED_DIR_PATTERNS` 中添加。

**Q: 支持哪些语言？**
A: C/C++, Python, Java, Rust, Go, TypeScript/JavaScript。Profiling 会自动检测主要语言。
