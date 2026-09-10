# bosch-data-transfert

Bosch 内网 **CR60 / BYD** 项目 `data+arbe` 一键准备 skill。

把问题单相关 `bag` 数据整理拷贝到用户指定的 Linux 分析服务器，为问题分析、bag 回放、代码分支切换做准备。数据备齐后进入 arbe 环境切分支（打 tag）→配置车型 CUDA →应用仿真改动 →编译（catkin_make）→启动（bash start）。

## 目录

```
skills/bosch-data-transfert/
├── SKILL.md              # Skill 定义（触发词 / 流程 / 配置注入总入口）
├── profiles/               # 配置（每个项目一份，改这里不用动代码）
│   ├── _template.yml        # 新同事复制改名即可
│   └── cr60-byd.yml     # CR60/BYD 默认值
├── references/
│   ├── environment.md      # 环境/权限/地址速查
│   └── analysis_handoff.md  # 交给下游数据预检查的 intake 契约
└── scripts/
    ├── data_transfert.py      # 数据同步（通用化核心）
    └── setup_arbe.sh             # arbe 一键（切tag→拷CUDA→改yaml→验证仿真→编译）
```

数据和代码环境准备完成后，上游输出 `cr60-analysis-intake.v1.json`，交给同级目录的
`skills/cr60-debug-harness-batch`。下游只读消费该 handoff，批量解析 rosbag、生成
`diagnosis_bundle.v1`、`runtime-schema.v1`、每条数据的 HTML 和批量入口；两个 skill 不共享
未声明的临时变量或默认路径。

## 工作流程

```bash
bash setup_arbe.sh <tag> [<车型>] [--skip-build] [--start]
```

## 配置（profiles/）

每个项目复制 `profiles/_template.yml` 填自己的值：

- **服务器**：`host` / `user` / `ssh_key`（不固定，用户指定 → 不确定时**咨询用户**）
- **数据源**：`xlsx`（B/J列）或 `list`（文本清单）或用户直接给 → 不确定**咨询用户**
- **车型→sheet**（CUDA yaml 54行）、**CUDA 表来源** → AI 推断 → **用户确认**；推导不出 → **咨询**
- **仿真补丁**：AI 按描述应用 → 确认可回退、用户知情
- 破坏现有工作（仓有未提交改动、tag对不上/多车型多版本混合）→ **先停咨询**

## 安装

### 复制到你自己的服务器/代码仓

```bash
# 在代码仓根目录下
mkdir -p skills
cp -r <本目录> skills/bosch-data-transfert
```

### Submodule / 软链（可选）

```bash
git submodule add <remote-url> skills/bosch-data-transfert
```
