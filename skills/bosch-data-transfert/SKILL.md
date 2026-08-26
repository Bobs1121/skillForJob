---
name: bosch-data-transfert
description: >
  Bosch 内网 CR60 / BYD 项目数据与 arbe 环境的一键准备工具链。
  用户在 Linux 服务器上需要把问题单相关 bag 数据（来源可能是 Excel 表格 J 列、UNC 路径、
  本地路径或用户直接给出）整理拷贝到服务器目录，或需要切分支（arbe 分析仓 algo_source 子仓）、
  配置车型 CUDA、应用仿真改动、catkin_make 编译并 bash start 启动 arbe 工具时使用。
  服务器地址不固定、由用户指定。本 skill 是"数据准备 + arbe 切分支/编译/启动"的统一入口
  （由 cr60light-data-prep 和 cr60light-arbe-build 两个 skill 合并调度）。
  数据和代码环境准备完成后，可把版本化的 `cr60-analysis-intake.v1` handoff 交给同级
  `cr60-debug-harness-batch` skill 做 Sprint1 数据预检查和 HTML 报告。
  触发词：数据准备、拷贝数据到Linux、问题单、cr60light、arbe、切分支、编译、catkin_make、启动工具。
---

# CR 数据 + arbe 自动编译启动 一体化工具链

把问题单相关 bag 数据（来源：Excel 表格 J 列 **或** 用户直接给的 UNC/本地路径/清单），按 **TR 号**整理拷贝到用户指定的 Linux 分析服务器，为问题分析、bag 回放、代码分支切换做准备。数据备齐后，进入 arbe 环境切分支（打 tag）→ 配车型 CUDA → 应用仿真改动 → 编译（catkin_make）→ 启动（bash start）。

## 总流程

```
用户给数据与服务器
  → 1. 明确服务器（未知 → 咨询用户）
  → 2. 明确数据源类型（Excel / UNC / 本地 / 清单；未知 → 咨询用户）
  → 3. 解析（Excel 读 B列TR号/J列数据路径/G列版本；其他类型引导用户给出结构化清单）
  → 4. 读 TR（问题单，MCP bosch-rsd，补全数据/附件信息）
  → 5. Linux 建目录 data/<车型>/<TR号>/（每 TR 一个二级目录）
  → 6. 从数据源拷数据到对应 TR 目录
  → 7. 校验文件大小一致性
  → 8. 对照 G 列版本，定位代码仓 tag（供下一步切分支用）
  → 9. 输出 `cr60-analysis-intake.v1`（数据路径 + 代码身份 + 车型/COEM + 构建状态）
  → 10. 用户确认后交给 `cr60-debug-harness-batch` 做批量预检查
```

## 输入校验（重要，先做）

**不明确的输入一律咨询用户，不要猜、不要用默认值硬跑。**

### 配置确认原则（关键）

涉及 **车型 / CUDA 参数 / tag / 编译相关** 的配置，一律遵循：
> **AI 先根据数据自行推断 → 列出推断结果与依据 → 必须交用户确认后才能继续进行。**

即使 AI 从表格 E 列、C 列功能、数据目录、G 列版本等推断出了车型/tag，也**不得跳过用户确认**直接沿用默认或单凭推断开工。用户确认后才算定案。

### 必确认输入

| 输入 | 来源 | 处理（AI 先推断 → 用户确认） |
|------|------|-----------|
| **服务器** | 用户指定（ssh 主机 / IP / 用户 / 密钥），如 `10.190.171.44` | 服务器不确定 → **咨询用户**要连哪台；确定后回显确认 |
| **数据源（怎么给数据）** | Excel 表格、UNC 路径、本地路径、或直接给清单 | 不确定 / 源类型混合 → **咨询用户**要什么数据、怎么组织 |
| **目标 tag / 分支** | 表格 G 列版本 → 代码仓 tag | AI 由 G 列推断 → **用户确认**；查不到/对不上/多候选 → 咨询要 tag 或分支 |
| **车型** | 表格 E 列、C 列功能、数据目录 | AI 由这些推断出候选 → **用户确认**；不明确或混合 → 咨询 |
| **CUDA sheet / CUDA 参数** | 车型对应、内仓 08_CustData、yaml 53/54 行 | 车型确认后推导 → **结合车型给用户确认** sheet/参数；推导不出 → 咨询 |
| **数据落盘目录** | 结合服务器工作区 | 不确定 → 咨询用户或按用户习惯，确认后使用 |

### 咨询场景（必须停下）

1. **数据来源类型不确定**：用户没说明数据靠 Excel 还是个别路径，或混合来源无法统一解析 → 咨询用户。
2. **G 列版本 → tag 匹配失败**：表格版本找不到对应 tag，或代码仓 tag 明显不符。列出候选，让用户指定。
3. **同一批问题单多个版本 / 车型混合**：不能用一个 tag/车型覆盖全部。咨询"按哪个版本/车型切？"，或分批处理。
4. **表格没有 G 列 / 车型信息**：咨询用户。
5. **切分支会破坏现有工作**：内仓有未提交改动且非仿真改动、或外仓特殊状态 → 先咨询确认可覆盖。
6. **任何无法从输入推导、且影响编译结果的决策**：咨询。

> 提示：即使 AI 能推断出车型 / tag / CUDA sheet，也**仍要列出来请用户点确认**。这保证了配置不会悄悄用错默认值。

校验（脚本也内置）：tag 不存在 / 车型目录不存在 → 报错并列出候选，不擅自继续。

## 完整流程

```
1. 确定目标 tag：G 列版本 → 代码仓 tag；**AI 先由数据推断出候选 tag 并列出依据 → 必须经用户确认后才算定案**（无 tag 则问用户分支）
2. 内仓 algo_source 切分支/tag
3. 更新 CUDA 表 + 车型配置（两级：大集合文件夹 + 具体车型 sheet）：
   AI 由数据推断出【大集合】与【具体车型】→ 列出推断及依据 → 用户确认后才改 yaml
   - yaml 53 行 xlsx_path：内仓最新 CUDA 表文件名
   - yaml 54 行 xlsx_sheet：具体车型 sheet（如 03_QZH）
   - yaml 75 行 car.type：大集合文件夹名（如 BYD_UKE）
   探索不到 → 咨询用户
4. 应用/确认仿真临时改动（visualization_node.cpp + paraDefine.h；确认为临时，可回退，用户知情）
5. **编译前咨询仿真模式**：paraDefine.h 的 HILMODE（17行）——若配为 2 则为 SGU 仿真模式；编译前必须问用户用哪个模式/值，不猜
6. catkin_make 编译
7. bash start 启动工具
```

## 盘点数据源

数据来源有两种，本 skill 都能处理：

### A. Excel 表格（推荐、可自动解析）

- 用 `openpyxl.read_only` 读：B 列=TR号，J 列=数据路径，G 列=版本。
- 规则：
  - J 列是 UNC（`//…` 或 `\\…`）→ 本地路径映射到 `/mnt/cluster`（`SRC_PREFIX`）。
  - J 列是目录 → 拷贝该目录下所有 `*.bag`/`*.blf`。
  - J 列是单个文件路径（可能无扩展）→ 找到对应 `*.bag`/`*.blf` 拷贝。
  - 跳过非路径文本（"TR 附件"、"需要去 ssec 找数据"）。
  - 幂等：已存在且同尺寸 → skip。拷贝失败重试。

### B. 非 Excel（用户直接给路径/清单）

- 用户可能直接给出若干个 UNC / 本地路径，或一份文本清单。
- 把用户给的内容整理成结构化清单（每行：TR号 → 数据路径），再走同样拷贝逻辑。
- 不确定清单格式 → 咨询用户，请用户给出"TR号 ↔ 数据路径"的对应关系。

## 2. 建目录

在服务器 `~/data/<车型>/<TR号>/` 建目录，与 cr60light-data-prep 一致的风格（具体根目录按用户工作区）。

## 3. 服务器与权限（由用户指定）

- **服务器不固定**，常见 `10.190.171.44`（主机名 `WX-C-001QM`，Ubuntu），以用户指定为准。
- SSH：优先免密密钥（`~/.ssh/id_ed25519`），SSH config 已配可直连部分主机。
- 工作区与数据目录：`~/CR60LIGHT/` 根；数据目录 `~/CR60LIGHT/data/`（可按项目自定义）。
- 数据源 SMB `/mnt/cluster`，UNC 映射 `\\abtvdfs.de.bosch.com\ismdfs\...` → `/mnt/cluster/...`。
- 磁盘 935G 总量，可用约 360G 上下（bag 单个 0.25-1.4GB）。

## 4. 数据拷贝（主流程：Linux 直拷）

数据源挂载到 Linux → **优先服务器端直拷**：

```bash
ssh <用户>@<服务器>
SRC=/mnt/cluster/loc/szh/Isilon2/TestackData/Driving_APP/08_BYD/47_CR60light/02_QZH/06_RCTB
DEST=~/data/qzh
mkdir -p $DEST/<TR号>
cp "$SRC/<子目录>/<file>.bag" "$DEST/<TR号>/"
```

- J 列可能是目录（拷全 `*.bag`/`*.blf`）或单文件路径（可能缺后缀）。
- **推荐用脚本** `scripts/data_transfert.py`（部署到服务器工作区），自动处理 UNC→本地映射、目录/文件解析、幂等跳过、重试、大小校验。
- 大文件从 SMB 拷较慢（约 1GB/min），用 `nohup ... &` 后台跑，轮询进度。

### 兜底（Linux 直拷不可用时）

1. 检查 `/mnt/cluster` 挂载（`mount | grep ismdfs`）；未挂载则尝试 `sudo mount -t cifs //... /mnt/cluster -o ...`。
2. 检查目标 TR 目录已有部分文件（幂等、只补缺）。
3. Windows 兜底：UNC 前缀已映射为 `P:` 盘（资源管理器可访问），从 `P:` 读 → scp/rsync 到服务器。
4. 完全不可达：记入报告提示用户（如 J 列="需要在合规室找数据"）。

## 5. TR 问题单访问（B 列）

- TR 系统 base：`https://rb-tracker.bosch.com/tracker08`，认证 `Authorization: Bearer $BOSCH_TR_KEY`。
  - Windows curl 直连，或用 MCP 工具 `bosch-rsd`：
  - `tr_get_issue`（如 CRGVI-1848）→ 摘要/状态/附件名
  - `tr_get_issue_devstatus` → 关联分支/PR/commit
  - 附件下载（J 列="TR 附件" 时）：`bosch-rsd` 的 `tr_get_issue` 只返回附件名，无下载接口 → HTTP 直连下载：
    1. 附件 id：`fields.attachment[].id`；
    2. 下载 `GET /secure/attachment/<id>/<filename>`（传 id 和文件名）。

## 6. 代码仓与版本（G 列）

- **代码仓**（常见）：`CR60_evo / cr60_light`（Bitbucket，`sourcecode06.dev.bosch.com`）。
- **认证**：`-H "Authorization: Bearer $BOSCH_PR_KEY"`
- **tag 常见**：`BYD_UKE_BL03RC02.7`、`BYD_UKE_BL04RC01.0/1/2` 等；tag 通常 `BYD_UKE_<版本>` 去 `_S` 尾缀。
- **版本匹配**：G 列版本 → tag（非完全一致，模糊匹配）。
- **Linux 直接 git**：`ssh://git@….de:7999/cr60_evo/cr60_light.git`（Linux 可直接连）。

## 7. 校验与纠错

- 拷完检查大小 `stat -c%s` 与源比对。
- 脚本内置：跳过、重试、大小校验、失败统计。
- SMB 拷贝"看似卡住"，用进程轮询确认进程在跑，**不要重复启动同一文件的拷贝**（I/O 竞争）。

## 8. 下游 handoff：交给批量数据预检查

数据准备、版本确认和 arbe 构建状态确认后，生成一个 `cr60-analysis-intake.v1` JSON 文件，作为本 skill 与同级 `cr60-debug-harness-batch` 的唯一交互边界。推荐保存为：

```text
<handoff-dir>/cr60-analysis-intake.v1.json
```

handoff 至少要包含：

- `environment.server`：host、user、port；
- `environment.arbe`：workspace、outer/algo commit、branch 或 detached 状态、dirty 状态、`algo_submodule`；
- `environment.vehicle`：COEM 大集合、车型、CUDA sheet；
- `environment.build`：`catkin_make`、可执行文件和 `bash start` 状态；
- `data.root` 和 `data.cases[]`：`case_id`、TR 号、数据目录、每个 bag 的远程绝对路径、格式、大小和可选 sha256；
- `data.cases[].source_selector`：该数据绑定的 outer/algo commit 或 branch；
- `downstream`：可选的 harness profile、analysis context、输出目录和媒体策略；
- `checks`、`status`、`notes`：缺失数据、版本不匹配、拷贝失败和构建失败必须显式记录。

禁止把 SSH 密钥、密码、Bearer token 或其他凭据写入 handoff。远程 bag 路径可以写入，因为下游需要通过同一 profile 读取它。

交接规则：

1. `status=blocked` 时不启动下游分析；先补齐数据、版本或配置。
2. `status=partial` 只有在用户明确接受部分数据时，才由下游以 `--allow-partial` 消费；ready、blocked、unsupported 必须分别统计。
3. 同一 handoff 内的 case 必须与同一代码版本/车型上下文匹配；混合版本拆成多个 handoff。
4. 下游只读消费 handoff，不切分支、不修改 arbe、不重新解释上游路径；需要刷新源码时由下游另行生成 read-only analysis context。
5. 下游完成后返回 `batch_summary.json`、批量 `index.html` 和每条数据的 `report.html` 路径，并保留 `handoff_id` 与 source identity。

完整字段、状态和示例见 [`references/analysis_handoff.md`](references/analysis_handoff.md)。

## 脚本清单

- `scripts/data_transfert.py` — 全自动同步：解析数据源、UNC→本地、目录/文件解析、拷贝/重试/校验。
  用法：`python3 data_transfert.py <xlsx|清单> [--dry-run] [--src-dir <目录>]`。
- `scripts/setup_arbe.sh` — arbe 一键：切 tag → 拷 CUDA → 改 yaml → 校验仿真 → catkin_make →（可选）start。
  用法：`bash setup_arbe.sh <tag> [<车型>] [--skip-build] [--start]`。
  所有差异通过环境变量/profile 注入（见 profiles/）。

## 详细参考

- 环境/权限/地址速查：`references/environment.md`（含服务器、数据源、tag 规则）。
