---
name: bosch-data-transfert
description: >
  Bosch 内网 CR60 / BYD 项目数据与 arbe 环境的一键准备工具链。
  用户在 Linux 服务器上需要把问题单相关 bag 数据（来源可能是 Excel 表格 J 列、UNC 路径、
  本地路径或用户直接给出）整理拷贝到服务器目录，或需要切分支（arbe 分析仓 algo_source 子仓）、
  配置车型 CUDA、应用仿真改动、catkin_make 编译并 bash start 启动 arbe 工具时使用。
  服务器地址不固定、由用户指定。本 skill 是"数据准备 + arbe 切分支/编译/启动"的统一入口
  （由 cr60light-data-prep 和 cr60light-arbe-build 两个 skill 合并调度）。
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
2. 内仓 algo_source 切分支/tag（强制覆盖前：`git diff > 备份.patch` 存到 ~/CR60LIGHT/sim_patches/）
3. 更新 CUDA 表 + 车型配置：
   - **先切 tag 再找 CUDA 表**：`ls coem/<车型>/tools/container_input/08_CustData/`，用该 tag 下**实际存在**的最新 `CUDA_<项目>_V*.xlsx`（tag 内不一定有用户口中的最新版本，如 BL02V02.2 tag 只有 V2.1，但 V2.1 已含 02_SC6E sheet——**切 tag 后用 openpyxl 列 sheetnames 找车型 sheet，不要凭表版本下结论**）
   - 拷 xlsx 到外仓 GUI Config：`cp ... ~/CR60LIGHT/cr60_light_arbe/src/arbe_phoenix_radar_driver-master/arbe_gui/Config/`
   - 改 `arbe_gui/Config/launch_config_4radars.yaml`：
     - 53 行 xlsx_path：拷入的表文件名
     - 54 行 xlsx_sheet：车型对应 sheet（如 02_SC6E；用 sheetnames 实测确认）
     - 75 行 car.type：与 tag 的 coem 车型目录一致（如 BYD_SC6H）
   探索不到 → 咨询用户
4. 应用/确认仿真临时改动（paraDefine.h BUILDMODEL=2；ADAS_STATE_EXTERNAL_MODE 相关见 cr60light-arbe-build skill；应用前先备份 dirty diff）
5. **编译前咨询仿真模式**：paraDefine.h 的 HILMODEL（17行）——0=普通（雷达点云仿真），2=SGU 仿真注入（受 PF_BUILD_FUNTEST_SGU_INJECTION 宏影响）；编译前必须问用户用哪个模式/值，不猜
6. catkin_make 编译（**不要 `--pkg algo_source`**——algo_source 不是 catkin 包，直接全量 `catkin_make`）
7. 启动：先停旧 ROS 会话再 roslaunch（见下"启动与会话"）
```

## 盘点数据源

数据来源有两种，本 skill 都能处理：

### A. Excel 表格（推荐、可自动解析）

- 用 `openpyxl` 读（文件有 200 个空行时 `read_only=True` 的 `max_row` 不可信，直接 `iter_rows` 逐行读）：B 列=TR号，J 列=数据路径，G 列=版本，E 列=车型。
- **筛选范围以用户口径为准，先澄清再拷**：
  - 用户说"只要 SC6E 的"可能指 **sheet 名**（SC6E sheet）而非 E 列车型 —— sheet 内会混排其他车型行（SC6E sheet 里就有 E 列=SC6H 的 CRGVI-1928）。**按 sheet 过滤，不要只按 E 列车型过滤**；拿不准时列出行清单让用户圈定。
  - 用户补说"倒数第二个也要拷"之类，按 sheet 行序定位，拷前先 `ls` 源目录并 `stat -c%s` 校验。
- 规则：
  - J 列是 UNC（`//…` 或 `\\…`）→ 本地路径映射到 `/mnt/cluster`（`SRC_PREFIX`）。
  - J 列是目录 → 拷贝该目录下所有 `*.bag`/`*.blf`。
  - J 列是单个文件路径（可能无扩展）→ 找到对应 `*.bag`/`*.blf` 拷贝。
  - 跳过非路径文本（"TR 附件"、"需要去 ssec 找数据"、"见TR"、tracker URL）：
    - "TR 附件"/"见TR" → 走 TR 附件下载（见下），下载后 scp 上传到该 TR 目录。
    - J 列是目录（无文件名）→ `ls` 源目录，拷目录下所有 `*.bag`/`*.blf`。
  - 幂等：已存在且同尺寸 → skip。拷贝失败重试。

### B. 非 Excel（用户直接给路径/清单）

- 用户可能直接给出若干个 UNC / 本地路径，或一份文本清单。
- 把用户给的内容整理成结构化清单（每行：TR号 → 数据路径），再走同样拷贝逻辑。
- 不确定清单格式 → 咨询用户，请用户给出"TR号 ↔ 数据路径"的对应关系。

## 2. 建目录

在服务器 `~/CR60LIGHT/data/<车型小写>/<TR号>/` 建目录（如 `~/CR60LIGHT/data/qzh/CRGVI-1842/`、`~/CR60LIGHT/data/sc6e/CRGVI-1899/`；与 cr60light-data-prep 一致的风格，具体根目录按用户工作区）。
每 TR 一个二级目录；一 TR 多行数据共用同一目录。

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
- **SSH 会话里跑长命令要防超时**：拷贝/编译一律 `nohup bash -c '...' > /tmp/xxx.log 2>&1 < /dev/null &`（`< /dev/null` 防 stdin 挂起），然后短命令轮询日志。
- **`pkill -f` 会切断自己的 SSH 连接**（匹配到 sshd 会话链，exit 255）：停 ROS/arbe 进程时，把 pkill 写进远端脚本 `setsid nohup /tmp/stop_arbe.sh &` 执行，不要在交互 SSH 命令里直接 pkill。

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
- **tag 常见**：`BYD_UKE_BL03RC02.7`、`BYD_UKE_BL04RC01.0/1/2`、`BYD_SC6H_BL02V02.2` 等；tag 通常 `<项目>_<版本>` 去 `_S` 尾缀。
- **版本匹配**：G 列版本 → tag（非完全一致，模糊匹配）。
- **tag 前缀不止 BYD_UKE**：SC6H 车系用 `BYD_SC6H_` 前缀（如 BL02V02.2→`BYD_SC6H_BL02V02.2`）。**候选集要先 `git ls-remote --tags | grep <版本号>` 按版本号全局搜**，再按前缀分组列给用户确认——不要只试 BYD_UKE 前缀就下结论"查不到 tag"。
- **Linux 直接 git**：`git ls-remote --tags ssh://git@sourcecode06.dev.bosch.com:7999/cr60_evo/cr60_light.git`（Windows 侧 Git Bash 可直连 22 端口）。

## 7. 校验与纠错

- 拷完检查大小 `stat -c%s` 与源比对。
- 脚本内置：跳过、重试、大小校验、失败统计。
- SMB 拷贝"看似卡住"，用进程轮询确认进程在跑，**不要重复启动同一文件的拷贝**（I/O 竞争）。

## 脚本清单

- `scripts/data_transfert.py` — 全自动同步：解析数据源、UNC→本地、目录/文件解析、拷贝/重试/校验。
  用法：`python3 data_transfert.py <xlsx|清单> [--dry-run] [--src-dir <目录>]`。
- `scripts/setup_arbe.sh` — arbe 一键：切 tag → 拷 CUDA → 改 yaml → 校验仿真 → catkin_make →（可选）start。
  用法：`bash setup_arbe.sh <tag> [<车型>] [--skip-build] [--start]`。
  所有差异通过环境变量/profile 注入（见 profiles/）。

## 详细参考

- 环境/权限/地址速查：`references/environment.md`（含服务器、数据源、tag 规则）。

## 启动与会话（重要）

服务器常有**旧 ROS 会话残留**（前次分析的 roscore/roslaunch/多个 `arbe_visualization_engine`），直接启动会节点名冲突。启动前：

```bash
# 1. 查残留：pgrep -af 'roslaunch|rosmaster|arbe_visualization|arbe_gui'
# 2. 停旧会话（不要在 SSH 命令里直接 pkill，会断自己连接）：
cat > /tmp/stop_arbe.sh <<'EOF'
#!/bin/bash
pkill -f 'arbe.launch'; sleep 2
pkill -f rosmaster; pkill -f arbe_visualization_engine; pkill -f arbe_gui
exit 0
EOF
setsid nohup /tmp/stop_arbe.sh > /tmp/stop_arbe.log 2>&1 < /dev/null &
# 3. 确认 11311 端口已释放：ss -tln | grep 11311
# 4. 启动（DISPLAY 用旧会话的值，可从 /proc/<旧pid>/environ 查；VNC 常为 :10.0）：
setsid nohup bash -c 'export DISPLAY=:10.0; source /opt/ros/noetic/setup.bash; source devel/setup.bash; roslaunch arbe_phoenix_radar_driver arbe.launch' > /tmp/arbe_start.log 2>&1 < /dev/null &
# 5. 25s 后验证：pgrep -c -f arbe_visualization_engine（应为 4-5）+ tail 启动日志
```

- 编译后**必须重启会话**才加载新二进制（跑着的 roslaunch 用的还是旧产物）。
- 启动日志常见非致命项：tf2 空 frame_id WARN；GUI 与 xcp publisher 的 md5sum 不匹配 ERROR（消息版本差异，不影响 bag 回放主链路）。