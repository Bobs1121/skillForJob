---
name: cr60light-arbe-build
description: >
  CR60 Light arbe 分析工作区切分支 + 编译 + 启动工具链。当用户在 10.190.171.44 服务器上需要
  把 cr60_light_arbe 的 algo_source 子仓切到问题单 G 列对应的版本 tag、配置 CUDA/车型、
  应用仿真临时改动、执行 catkin_make 编译并 bash start 启动时使用。由 cr60light-data-prep
  skill 统一调度（数据准备完成后，进入本 skill 的切分支/编译阶段）。用户提到"切分支"、
  "编译 arbe"、"catkin_make"、"algo_source 分支"、"启动工具"、"仿真" 时使用。
---

# CR60 Light arbe 切分支 / 编译 / 启动

数据准备（`cr60light-data-prep`）完成 bag 数据拷贝后，本 skill 负责把 arbe 分析环境
切到对应版本并编译启动，供 bag 回放分析。

## 前置

- 服务器 `10.190.171.44`（`hoz2wx@10.190.171.44`，SSH 免密）
- **arbe 工作区路径不固定**：默认 `~/CR60LIGHT/cr60_light_arbe/`，但可能存在新副本（如 `~/repo/arbetest/cr60_light_arbe/`）。**必须先向用户确认本次的目标路径**，不要默认固定路径。
- 已从问题单表格拿到：`G列版本`（如 BL03RC02.7_S）、`车型`（如 QZH / BYD_UKE）
- 问题单表格 xlsx 在服务器 `~/CR60LIGHT/data/` 下（data-prep 已拷贝）
- 本 skill 命令示例以默认路径 `~/CR60LIGHT/cr60_light_arbe` 书写，实际使用时用目标路径替换；下文以 `WORKSPACE` 表示该根目录。

## 0. 输入校验与咨询（重要，先做这一步）

**在执行任何切分支/编译动作之前，先确认输入是否明确。不明确的输入一律向用户咨询，不要猜测、不要用默认值硬跑。**

### 0.1 必确认的输入

| 输入 | 来源 | 不明确时的处理 |
|------|------|----------------|
| **arbe 工作区路径** | 用户指定 | 不明确 / 有多个候选 → **咨询用户**要切哪个仓（可能已有新副本如 `~/repo/arbetest/cr60_light_arbe`） |
| **目标 tag / 分支** | 表格 G 列版本 → tag | 无法确定 tag（查不到/对不上/多个候选）→ **咨询用户**要 tag 或分支名 |
| **车型** | 表格 E 列、C 列功能、数据目录 | 车型不明确或混合 → **咨询用户** |
| **CUDA sheet** | 车型对应 | 车型确认后自动推导（QZH→03_QZH），推导不出 → 咨询 |
| **数据目录** | data-prep 阶段确定 | 缺失 → 先回 data-prep skill 补 |

### 0.2 咨询的场景（必须停下来问）

1. **G 列版本 → tag 匹配失败**：表格版本查不到对应 tag，或版本与代码仓 tag 明显不一致。列出候选 tag，让用户指定。
2. **同一批问题单有多个不同版本/车型**：不能用一个 tag 覆盖全部。咨询用户"按哪个版本/车型切？"，或分批处理。
3. **表格中没有 G 列 / 车型信息**：咨询用户。
4. **切分支会破坏现有工作**：内仓当前有未提交改动且不是仿真改动（见步骤4），或外仓有特殊状态，先咨询用户确认可覆盖。
5. **任何无法从输入推导、且影响编译结果的决策**：咨询。

### 0.3 校验流程（脚本也内置）

```bash
# 先检查关键输入是否齐全
[ -z "$TAG" ] && echo "缺少目标 tag/分支，需要咨询用户" && exit 1
[ -z "$MODEL" ] && echo "缺少车型，需要咨询用户" && exit 1
```

脚本 `setup_arbe.sh` 在 tag 不存在、车型目录不存在时会报错并列出候选，**不会擅自继续**。

## 完整流程

```
1. 确定目标 tag：G列版本 → 代码仓 tag（无 tag 则问用户分支）
2. 内仓 algo_source 切分支/切 tag
3. 更新 CUDA 表：内仓 08_CustData 最新表 → 外仓 Config，改 yaml 53/54行
4. 确认/应用仿真临时改动（visualization_node.cpp + paraDefine.h）
5. catkin_make 编译
6. bash start 启动工具
```

## 1. 确定目标 tag（G 列版本 → tag）

- G 列版本去掉 `_S` 等尾缀，加 `BYD_UKE_` 前缀：
  - `BL03RC02.7_S` → `BYD_UKE_BL03RC02.7`
  - `BL04RC01.2` → `BYD_UKE_BL04RC01.2`
- 从代码仓 API 查 tag（见 references/environment.md），或直接在内仓 `git ls-remote --tags origin`。
- **校验 tag 存在**：`git rev-parse -q --verify refs/tags/<tag>`。不存在 → 报错列出候选，咨询用户。
- **多条问题单版本不一致**：先列出所有涉及的版本/tag，咨询用户"按哪个版本切"，或确认分批。
- **无法确定 tag / 版本对不上 / 查不到 → 咨询用户要分支或 tag 信息，不要猜。**

> 全程用实际 arbe 仓根目录替换 `WORKSPACE`（默认 `~/CR60LIGHT/cr60_light_arbe`，亦可能为 `~/repo/arbetest/cr60_light_arbe` 等新副本）。

## 2. 内仓 algo_source 切分支

```bash
cd $WORKSPACE/src/algo_source
git fetch origin --tags          # 拉最新 tag（本地可能缺新 tag）
git checkout <tag>               # 如 BYD_UKE_BL03RC02.7（detached HEAD 是正常预期）
git describe --tags              # 验证
```

- **注意**：外仓 `develop_LGU_Simulation` 分支保持不变，内仓直接 checkout tag（detached HEAD）。
  外仓 submodule 指针可能与本仓 HEAD 不一致（`git status` 显示 `src/algo_source (新提交)`），这是预期状态，不要 revert。
- 当前默认目标：问题单都是 BYD UKE 车型 → tag `BYD_UKE_BL03RC02.7`（BL03RC02.7_S）。
- 切完后确认 `git describe --tags` 输出目标 tag。

## 3. 更新 CUDA / 车型配置

**先确认车型**：车型是配置 CUDA 表来源（08_CustData 目录）和 yaml 54 行 sheet 的关键。
- 表格 E 列通常给出车型（QZHCX→BYD_UKE、SC6H→BYD_SC6H、EM2E 等）。
- 车型不明确 / 表格多个车型混合 / 车型目录在 `coem/` 下找不到 → **咨询用户**，列出 `coem/` 下存在的车型目录（见下）。

两个文件要动：

### 3a. CUDA 表（xlsx）

**重要：CUDA 表版本号随 tag 变化，一定要在 `git checkout <tag>` 完成之后**，去内仓 `08_CustData` 看那份 tag 下**实际存在**的文件（`ls` 取最新 `CUDA_<车型>_Bundle_V*.xlsx`），不要照抄 skill 里的固定版本号（如 V1.7 / V2.0 都可能过时）。

- **内仓最新表（Aft切 tag）**：`$WORKSPACE/src/algo_source/coem/<车型>/tools/container_input/08_CustData/`
  - `ls -la` 该目录，取实际最新的 `CUDA_<车型>_Bundle_V*.xlsx`（也可能带同名 `.hex`）。
  - 各车型默认映射见 references/environment.md，但**以实际 ls 结果为准**。
- **外仓 Config**：`$WORKSPACE/src/arbe_phoenix_radar_driver-master/arbe_gui/Config/`
- 把内仓最新那份 xlsx `cp` 到外仓 Config（保留旧文件不删，属增量新增）：

```bash
SRC=$WORKSPACE/src/algo_source/coem/BYD_UKE/tools/container_input/08_CustData
DST=$WORKSPACE/src/arbe_phoenix_radar_driver-master/arbe_gui/Config
ls -la "$SRC"                          # 确认实际最新文件名，如 CUDA_BYD_UKE_Bundle_V2.0.xlsx
cp "$SRC/CUDA_BYD_UKE_Bundle_<实际版本>.xlsx" "$DST/"
```

### 3b. yaml 53/54 行

`$WORKSPACE/src/arbe_phoenix_radar_driver-master/arbe_gui/Config/launch_config_4radars.yaml`：

```yaml
53        xlsx_path: "CUDA_BYD_UKE_Bundle_V1.5.xlsx"   # ← 改成 3a 拷入的最新文件名
54        xlsx_sheet: "03_QZH"                          # ← 车型对应 sheet（通常保持）
```

- **53 行** `xlsx_path`：填拷贝到 Config 的最新 CUDA 表文件名。
- **54 行** `xlsx_sheet`：车型对应的 sheet 名。QZH 车型 = `03_QZH`。
  常见映射：`00_SC2E`/`01_SA3`/`02_PA`/`03_QZH`/`04_EWE`/`05_MR`。
- 第 75 行 `car.type: BYD_UKE` 是车型 type，通常保持。

## 4. 仿真临时改动（必须，但先核实是否已内置）

**前提（重要）**：部分 arbe 副本自带一套自定义回放/仿真机制（称为 agent-replay，特征：CMakeLists.txt 已改、visualization_node.cpp 已改、且含 `arbe_headless_replay/` 目录、加了 `REPLAY_TRACE_ENABLED` 宏）。这种仓的接口适配**可能已经做好**，直接叠加 skill 的改动会重复/冲突。

**必须先核实**：
```bash
cd $WORKSPACE/src/arbe_phoenix_radar_driver-master/arbe_gui/src/arbe_visualization_engine
grep -n "PostProcessMainTI" visualization_node.cpp    # 看调用末参数
# 如果已是 ..., &algo_objGMWInfo, &taskTime);  → 接口已适配，不要按下面"多传 taskTime, taskTime"改
# 如果是 ..., &algo_objGMWInfo, taskTime, taskTime); → 已是 skill 标准格式
```
- 若该仓已适配（如 arbetest 用 `&taskTime` 单指针），**跳过 visualization_node.cpp 改动，只补 paraDefine.h**。
- 若是最原始的标准仓（调用仍是单 `taskTime`），才按下面补。

### 外仓 `visualization_node.cpp`（仅当未内置时）

路径：`src/arbe_phoenix_radar_driver-master/arbe_gui/src/arbe_visualization_engine/visualization_node.cpp`

改动：`PostProcessMainTI(...)` 调用末尾多传一个 `taskTime`：
```cpp
// 原:
..., &algo_objESSInfo, &algo_objGMWInfo, &taskTime);
// 改:
..., &algo_objESSInfo, &algo_objGMWInfo, taskTime, taskTime);
```
（为 GUI 仿真适配算法接口。）

### 内仓 `paraDefine.h`（总是补）

路径：`src/algo_source/adas/symmetry/perception/include/paraDefine.h`

改动：`BUILDMODEL` 从 `0` 改为 `2`：
```c
// 0 = baseband mode, 1 = baseband VS mode, 2 = ROS GUI mode
#define BUILDMODEL 2   // 原为 0
```

### 校验

```bash
cd $WORKSPACE && git diff src/arbe_phoenix_radar_driver-master/arbe_gui/src/arbe_visualization_engine/visualization_node.cpp
cd $WORKSPACE/src/algo_source && git diff adas/symmetry/perception/include/paraDefine.h
```

若切换分支后改动丢失，按上面内容重新应用。**应用修改前先备份**：`cp <file> /tmp/<file>.bak_$(date +%s)`，便于回退。

## 5. 编译（catkin_make）

```bash
cd $WORKSPACE
source /opt/ros/noetic/setup.bash
catkin_make
```

- 在工作区根（有 `src/CMakeLists.txt` + `.catkin_workspace`）执行。
- **注意**：arbe_gui 的 CMakeLists 会从 `Config/launch_config_4radars.yaml` 的 `car.type` **动态解析 COEM_NAME**（如 `BYD_UKE`），用于定位 `coem/<车型>/components/AswPerception`。切车型时确保 yaml 的 `car.type` 与目标车型一致。
- 编译耗时较长（10-30 分钟），用 `nohup ... &` 后台 + 日志轮询，或前台等待。
- 失败排查：`catkin_make` 输出错误日志，重点看是哪个包报错；改动文件如果报错多为接口不匹配。
- 常见 Warning（不一定致命）：`未找到COEM补丁头文件，将使用默认 perception_public_def.h`，说明 `coem/<车型>/buildscripts/patch/perception_public_def.h` 缺失，编译会回退默认头；若算法接口对不上可能报错，需核对 tag 内仓是否有该补丁头。

## 6. 启动工具（bash start）

```bash
cd $WORKSPACE
bash start
```

- `start` 内容：chmod USB 设备、`source devel/setup.bash`、`roslaunch arbe_phoenix_radar_driver arbe.launch`
- 需要显示环境（GUI），在服务器本地或带 X 转发运行。
- 启动后 RViz + arbe GUI 出现，即可 Select Folder 选 bag 目录回放。

## 脚本

- `scripts/setup_arbe.sh` — 一键脚本：切 tag → 更新 CUDA → 改 yaml → 确认仿真改动 → catkin_make。
  用法：`bash setup_arbe.sh <tag> <车型> [--skip-build]`

## 参考

- 环境/车型/CUDA 表映射：`references/environment.md`
- bag 回放/KPI 模式操作：见 arbe 工作区 `FCTB_Batch_Replay_Operation_Guide.md`
