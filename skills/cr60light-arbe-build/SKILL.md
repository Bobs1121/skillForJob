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

- G 列版本去掉 `_S` 等尾缀，加**项目前缀**：
  - `BL03RC02.7_S` → `BYD_UKE_BL03RC02.7`
  - `BL04RC01.2` → `BYD_UKE_BL04RC01.2`
  - `BL02V02.2`（SC6H 车系）→ `BYD_SC6H_BL02V02.2`
- **前缀不止 BYD_UKE**：先按版本号全局搜候选，再列给用户确认：
  ```bash
  git ls-remote --tags ssh://git@sourcecode06.dev.bosch.com:7999/cr60_evo/cr60_light.git | grep <版本号>
  ```
  不要只试 `BYD_UKE_` 前缀就下结论"查不到 tag"（SC6E 数据配 SC6H tag 的场景，用户直接指定 `BYD_SC6H_BL02V02.2`）。
- 从代码仓 API 查 tag（见 references/environment.md），或直接在内仓 `git ls-remote --tags origin`。
- **校验 tag 存在**：`git rev-parse -q --verify refs/tags/<tag>`。不存在 → 报错列出候选，咨询用户。
- **多条问题单版本不一致**：先列出所有涉及的版本/tag，咨询用户"按哪个版本切"，或确认分批。
- **无法确定 tag / 版本对不上 / 查不到 → 咨询用户要分支或 tag 信息，不要猜。**

> 全程用实际 arbe 仓根目录替换 `WORKSPACE`（默认 `~/CR60LIGHT/cr60_light_arbe`，亦可能为 `~/repo/arbetest/cr60_light_arbe` 等新副本）。

## 2. 内仓 algo_source 切分支

```bash
cd $WORKSPACE/src/algo_source
git diff > ~/CR60LIGHT/sim_patches/pre_<车型>_$(date +%Y%m%d_%H%M%S).patch   # 先备份未提交改动！
git fetch origin --tags          # 拉最新 tag（本地可能缺新 tag）
git checkout -f <tag>            # 如 BYD_SC6H_BL02V02.2（detached HEAD 是正常预期）
git submodule update --init --recursive   # 子模块指针随 tag 变化，必须同步
git describe --tags              # 验证
```

- **切 tag 前必须备份 dirty diff**（`~/CR60LIGHT/sim_patches/`）：工作区常有前次分析的调试改动（如 `adasFunc.c` 的 `ADAS_STATE_EXTERNAL_MODE` 保护移除、`ADAS_Tools` 子模块指针漂移），checkout 后可用 patch 恢复（见步骤 4b）。
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

**重要：CUDA 表版本号随 tag 变化，一定要在 `git checkout <tag>` 完成之后**，去内仓 `08_CustData` 看那份 tag 下**实际存在**的文件（`ls` 取最新 `CUDA_<车型>_V*.xlsx`），不要照抄 skill 里的固定版本号（如 V1.7 / V2.0 都可能过时）。tag 内也可能没有用户口中的最新表（如 BYD_SC6H_BL02V02.2 tag 只有 V2.1）——**以 tag 内实际文件为准，用 sheetnames 判断够不够用**。

- **内仓最新表（切 tag 后）**：`$WORKSPACE/src/algo_source/coem/<车型>/tools/container_input/08_CustData/`
  - `ls -la` 该目录，取实际最新的 `CUDA_<车型>_V*.xlsx`（也可能带同名 `.hex`）。
  - **用 openpyxl 实测 sheet**：`python3 -c "import openpyxl; print(openpyxl.load_workbook('<xlsx>',read_only=True).sheetnames)"`，确认目标车型 sheet 存在再配 yaml。不要凭"表版本不够新"下结论。
  - 各车型默认映射见 references/environment.md，但**以实际 ls/sheetnames 结果为准**。
- **外仓 Config**：`$WORKSPACE/src/arbe_phoenix_radar_driver-master/arbe_gui/Config/`
- 把内仓最新那份 xlsx `cp` 到外仓 Config（保留旧文件不删，属增量新增）：

```bash
SRC=$WORKSPACE/src/algo_source/coem/BYD_SC6H/tools/container_input/08_CustData
DST=$WORKSPACE/src/arbe_phoenix_radar_driver-master/arbe_gui/Config
ls -la "$SRC"                          # 确认实际最新文件名，如 CUDA_BYD_SC6H_V2.1.xlsx
cp "$SRC/CUDA_BYD_SC6H_V<实际版本>.xlsx" "$DST/"
```

### 3b. yaml 53/54 行

`$WORKSPACE/src/arbe_phoenix_radar_driver-master/arbe_gui/Config/launch_config_4radars.yaml`：

```yaml
53        xlsx_path: "CUDA_BYD_SC6H_V2.1.xlsx"   # ← 改成 3a 拷入的最新文件名
54        xlsx_sheet: "02_SC6E"                   # ← 车型对应 sheet（实测确认）
75        car.type: BYD_SC6H                      # ← 与 tag 的 coem 车型目录一致（影响 CMake 解析 COEM_NAME）
```

- **53 行** `xlsx_path`：填拷贝到 Config 的最新 CUDA 表文件名。
- **54 行** `xlsx_sheet`：车型对应的 sheet 名，**用 3a 的 sheetnames 实测**。QZH 车型 = `03_QZH`（UKE Bundle 表）；SC6E 数据配 SC6H tag = `02_SC6E`（SC6H V2.1 表）。
- 第 75 行 `car.type` **必须与目标 tag 的 coem 车型目录一致**（如 `BYD_SC6H`）：catkin 编译用它动态解析 COEM_NAME 定位 `coem/<车型>/components/AswPerception`，写错会编到错误车型的代码。

## 4. 仿真临时改动（必须，但先核实是否已内置）

**前提（重要）**：部分 arbe 副本自带一套自定义回放/仿真机制（称为 agent-replay，特征：CMakeLists.txt 已改、visualization_node.cpp 已改、且含 `arbe_headless_replay/` 目录、加了 `REPLAY_TRACE_ENABLED` 宏）。这种仓的接口适配**可能已经做好**，直接叠加 skill 的改动会重复/冲突。

**必须先核实（注意：这次实际经验纠正了早先的误判）**：
```bash
cd $WORKSPACE/src/arbe_phoenix_radar_driver-master/arbe_gui/src/arbe_visualization_engine
grep -n "PostProcessMainTI" visualization_node.cpp    # 看调用末参数
# 若调用末参数是 ..., &algo_objGMWInfo, &taskTime);        → 是单指针，与 algo_source 签名（末尾两个 uint8 值）不匹配，编译会报
#     "too few arguments" + "invalid conversion from uint8_t* to uint8_t"，必须改成两个值 → 见下方改动
# 若已是 ..., &algo_objGMWInfo, taskTime, taskTime);      → 已是标准格式，无需再改 visualization_node.cpp
```
- **判断依据是 algo_source 的权威签名**（`funcDefine.h` 里 `PostProcessMainTI` 末尾是否两个 `uint8_t`：`algoTaskTimeMsNet, sysTaskTimeMsNet`）。arbe 侧调用必须对齐它。当前默认 tag `BYD_UKE_BL03RC02.7` 就是两个 uint8 值。
- 若调用是单指针、且即时报"参数不匹配"编译错 → 按下方"多传 taskTime, taskTime"改；**不要误以为 `&taskTime` 是"已适配"**（那会直接编译失败）。
- 若仓已带 `taskTime, taskTime`（标准格式）→ 跳过 visualization_node.cpp 改动，只补 paraDefine.h。

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

改动（10 行 BUILDMODEL、17 行 HILMODEL，sed 按行号改即可）：
```c
// 10 行: 0 = baseband mode, 1 = baseband VS mode, 2 = ROS GUI mode
#define BUILDMODEL 2   // 原为 0
// 17 行: 0 = normal mode, 1 = hil mode, 2 = imu hil mode（受 PF_BUILD_FUNTEST_SGU_INJECTION 宏影响）
#define HILMODEL 0     // 编译前问用户：0=普通（雷达点云仿真回放），2=SGU 仿真注入
```

### 校验

```bash
cd $WORKSPACE && git diff src/arbe_phoenix_radar_driver-master/arbe_gui/src/arbe_visualization_engine/visualization_node.cpp
cd $WORKSPACE/src/algo_source && git diff adas/symmetry/perception/include/paraDefine.h
```

若切换分支后改动丢失，按上面内容重新应用。**应用修改前先备份**：`cp <file> /tmp/<file>.bak_$(date +%s)`，便于回退。

### 4b. 恢复前次调试改动（ADAS_STATE_EXTERNAL_MODE 类 patch）

工作区切 tag 后，用户可能要求恢复之前的调试改动（如 `adasFunc.c` 中移除 `#if defined(ADAS_STATE_EXTERNAL_MODE)` 参数条件编译保护——涉及 ResetBsdRoi/ResetLcaRoi/ResetRctaRoi/ResetDowRoi/ResetRcwRoi/ResetFctaRoi 等函数，共 10+ 处）。

- 备份 patch 在 `~/CR60LIGHT/sim_patches/pre_<车型>_*.patch`（步骤 2 生成）。
- **patch 是按旧 coem 路径做的（如 BYD_UKE），换 tag/换车型后直接 apply 会失败**。处理流程：
  1. 提取目标文件的 diff 段（从 `diff --git a/coem/...` 到下一个 `diff --git`），把路径替换为新 coem 路径（如 `BYD_UKE` → `BYD_SC6H`）；
  2. **去掉 paraDefine.h 的 hunk**（行尾符差异会 FAILED，且该文件已按步骤 4 配好，无需 patch）；
  3. `patch -p1 --fuzz=5 --dry-run` 预检通过后再正式应用（SC6H 与 UKE 的 adasFunc.c 行号有偏移，fuzz=5 可对齐）；
  4. 验证：`git diff --stat` 应显示与备份 patch 等价的改动量；`grep -c 'ADAS_STATE_EXTERNAL_MODE' <adasFunc.c>` 剩余数与原改动一致（改的是移除保护，不是清零所有出现处）。
- **编译的是哪个 adasFunc.c**：catkin 按 yaml `car.type` 解析 COEM_NAME，编译 `coem/<car.type>/components/AswPerception` 下的文件。改错了 coem 目录的文件不会生效也不报错——改前确认 `car.type`。

## 5. 编译（catkin_make）

```bash
cd $WORKSPACE
source /opt/ros/noetic/setup.bash
catkin_make    # 全量编译，不要 --pkg algo_source（它不是 catkin 包，会报 "Packages not found"）
```

- 在工作区根（有 `src/CMakeLists.txt` + `.catkin_workspace`）执行。
- **注意**：arbe_gui 的 CMakeLists 会从 `Config/launch_config_4radars.yaml` 的 `car.type` **动态解析 COEM_NAME**（如 `BYD_SC6H`），用于定位 `coem/<车型>/components/AswPerception`。切车型时确保 yaml 的 `car.type` 与目标车型一致。
- 编译耗时较长（2-15 分钟），用后台 + 日志轮询：
  ```bash
  nohup bash -c 'source /opt/ros/noetic/setup.bash; catkin_make > /tmp/catkin_build.log 2>&1; echo EXIT=$? >> /tmp/catkin_build.log' < /dev/null &
  # 轮询：tail /tmp/catkin_build.log；EXIT=0 且 grep -cE '\berror\b' 为 0 即成功
  ```
- 失败排查：`catkin_make` 输出错误日志，重点看是哪个包报错；改动文件如果报错多为接口不匹配。
- 常见 Warning（不一定致命）：`未找到COEM补丁头文件，将使用默认 perception_public_def.h`，说明 `coem/<车型>/buildscripts/patch/perception_public_def.h` 缺失，编译会回退默认头；若算法接口对不上可能报错，需核对 tag 内仓是否有该补丁头。

## 6. 启动工具（重启 ROS 会话）

**编译后必须先停旧会话再启动**——跑着的 roslaunch 用的还是旧二进制：

```bash
# 1. 查残留：pgrep -af 'roslaunch|rosmaster|arbe_visualization|arbe_gui'
# 2. 停旧会话（pkill 写进脚本 setsid 执行，避免断自己 SSH 连接）：
cat > /tmp/stop_arbe.sh <<'EOF'
#!/bin/bash
pkill -f 'arbe.launch'; sleep 2
pkill -f rosmaster; pkill -f arbe_visualization_engine; pkill -f arbe_gui
exit 0
EOF
setsid nohup /tmp/stop_arbe.sh > /tmp/stop_arbe.log 2>&1 < /dev/null &
# 3. 确认 11311 已释放：ss -tln | grep 11311
# 4. 启动（DISPLAY 沿用旧会话值，可从 /proc/<旧pid>/environ 查；VNC 常为 :10.0）：
setsid nohup bash -c 'export DISPLAY=:10.0; source /opt/ros/noetic/setup.bash; source devel/setup.bash; roslaunch arbe_phoenix_radar_driver arbe.launch' > /tmp/arbe_start.log 2>&1 < /dev/null &
# 5. 25s 后验证：pgrep -c -f arbe_visualization_engine（应 4-5）+ tail /tmp/arbe_start.log
```

- `start` 脚本内容：chmod USB 设备、`source devel/setup.bash`、`roslaunch arbe_phoenix_radar_driver arbe.launch`；等价于上面第 4 步。
- 需要显示环境（GUI）：无头服务器用 VNC display（如 `:10.0`），在服务器本地或带 X 转发运行。
- 启动后 RViz + arbe GUI 出现，即可 Select Folder 选 bag 目录回放。
- 启动日志常见非致命项：tf2 空 frame_id WARN；GUI 与 xcp publisher 的 md5sum 不匹配 ERROR（消息版本差异，不影响 bag 回放主链路）。
- `roslaunch` 进程偶尔杀不干净（rosmaster 残留占 11311），逐个补杀 `pkill -f rosmaster`。

## 脚本

- `scripts/setup_arbe.sh` — 一键脚本：切 tag → 更新 CUDA → 改 yaml → 确认仿真改动 → catkin_make。
  用法：`bash setup_arbe.sh <tag> <车型> [--skip-build]`

## 参考

- 环境/车型/CUDA 表映射：`references/environment.md`
- bag 回放/KPI 模式操作：见 arbe 工作区 `FCTB_Batch_Replay_Operation_Guide.md`
