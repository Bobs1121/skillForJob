# Claude Code Skills

公共 Claude Code Skill 仓库，提供可复用的团队级 AI 辅助能力。

## 目录结构

```
skills/
├── code-review/          # 自适应代码审查 Skill
│   ├── review.md         # Skill 定义（/review 入口）
│   └── scripts/
│       └── analyze_repo.py  # 代码仓画像构建脚本
docs/
└── usage-guide.md        # 使用指南
```

## 快速开始

### 1. 将 Skill 复制到你的代码仓

```bash
# 在你的代码仓根目录下执行
cp -r /path/to/claude-code-skills/skills/code-review .claude/skills/code-review
```

### 2. 使用

在 VSCode 中打开 Claude Code，输入：

```
/review
```

首次运行会自动构建代码仓画像（约 20-30s），后续运行秒级启动。

## 可用 Skills

| Skill | 命令 | 描述 |
|-------|------|------|
| code-review | `/review` | 自适应三层结构化代码审查 |

## 添加新 Skill

1. 在 `skills/` 下创建新目录
2. 编写 `<skill-name>.md` 定义文件
3. 如有辅助脚本，放入 `scripts/` 子目录
4. 更新本 README 的可用 Skills 表格
5. 提交 PR

## License

Internal Use Only
