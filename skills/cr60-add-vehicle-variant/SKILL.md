---
name: cr60-add-vehicle-variant
description: >
  CR60 Light (BYD_SC6H / BYD_UKE) 车型相关需求全流程：新增车型配置、特殊驾驶模式抑制、
  左右舵、新旧 UI、本地编译验证、commit 信息格式、提 PR（先编译截图再提 PR、截图放评论区）。
  用户提到"新增车型"、"新增 index"、"车型配置"、"左舵/右舵"、"欧标/非欧标/韩标"、
  "特殊驾驶模式"、"驾驶模式抑制"、"新旧UI"、"新UI"、"提PR"、"建PR"、"commit"、
  "variant index"、"VEH_VARIANT"、"编码表"、"BYD_Support_variants"、"SHH"、"SC6H"、
  "EM2E"、"CNHEU" 时使用。
---

# CR60 Light 车型需求全流程（配置新增 / 特殊驾驶模式 / 编译 / 提交 / PR）

## 目标

处理 CR60 Light 车型相关的两类需求，并按固定流程完成编译验证与 PR 提交：

1. **新增车型配置**：把用户给出的车型列表（每个 Index 的 左舵/右舵、标准）落到代码中，只做配置新增，不加逻辑
2. **特殊驾驶模式抑制**：在 `ADAS_HMI.c` 的 `ADAS_DrvMod_Disable()` 中按车型接入驾驶模式信号 → 抑制策略映射

## 铁律：提 PR 前必须先本地编译（用户明确要求）

**顺序固定，不可跳步：**

1. 跑本地编译脚本，编译**必须成功**
2. 拿到编译成功的截图（日志末尾成功输出）
3. 再提 PR
4. **把截图放到 PR 评论区**（不是 PR 描述里）

即使 PR 已提前建好（补流程场景），也要编译成功后把截图补到评论区。

### 本地编译命令

真正的工作路径是 `D:\cr60_light`（不是 ZCode 会话的临时 worktree）。编译按工程分脚本：

| 工程 | 脚本 | cfg（KL30/SYMMETRY/周期/标准） |
|---|---|---|
| BYD_UKE | `coem/BYD_UKE/buildscripts/build_ENCAP.bat` | KL30 / SYMMETRY / T66MS / ENCAP |
| BYD_UKE | `coem/BYD_UKE/buildscripts/build_NORMAL.bat` | KL30 / SYMMETRY / T66MS / NORMAL |
| BYD_SC6H | `coem/BYD_SC6H/buildscripts/build.bat` | KL30 / SYMMETRY / T50MS / ENCAP |

- 改了哪个 `coem/<VEH>` 工程，就跑哪个工程的脚本；两个工程都改了就都跑
- 日志重定向到仓库根目录的 `_build_<veh>_<ticket>.log`，成功判定看退出码 0 + 日志末尾无 error
- 截图取日志末尾成功段（链接完成 / Build succeeded / exit 0）
- 编译会跑 ConfigGen → genMCAL → RTA-CAR genBsw → patch → scons 全链路，耗时较长，用后台执行
- 两个工程顺序编译，不要并行（共享生成目录会冲突）

### git 环境注意

- `D:\cr60_light` 是主 worktree；ZCode 会话可能创建临时 worktree（`D:\data\New folder\.zcode\worktrees\`），同一分支不能被两个 worktree 同时检出
- 临时 worktree 删除遇 Permission denied 时：`git worktree prune` 清注册信息即可，残留目录让用户稍后手动删
- 切分支前先看 `git status`；主 worktree 常有用户未提交改动（如 14952 分支的 10 个文件），处理方式：无重叠时 `git stash push -m "wip-<分支>-auto-stash"` 再切，不要直接丢弃

## 需求一：新增车型配置

### 输入（先向用户确认缺失项）

- 车型名与 Index 列表，例如 `Index1,左舵,欧标`
- 每个 Index 的 7 字节车型编码（前 7 字节，第 8 字节由规则计算）。缺失时必须先向用户索取，不要猜测
- 标准到配置模板的映射（已确认过的默认映射见下文）
- 新 UI 还是旧 UI（影响开关策略确认，当前默认全是新 UI：`ADCMode_UI_Status = ADC_UI_NEW`）

### 步骤

#### 1. 找枚举（以 `coem/<VEH>/components/diag/DiaWdbi/inc/DiaWdbi.h` 为准）

- 查找 `VEH_VARIANT_<VEH>_INDEX_*`，确认是否已有该车型枚举
- 确认 `VEH_VARIANT_<VEH>_INDEX_MIN/MAX` 宏覆盖全部 Index
- 枚举顺序必须与编码表顺序一致
- `VEH_VARIANT_INDEX_MAX` 在枚举末尾，新增行后不要手动改它

#### 2. 编码表与诊断分支（`coem/<VEH>/components/diag/DiaWdbi/src/DiaWdbi.c`）

- `BYD_Support_variants[VEH_VARIANT_INDEX_MAX][8]` 每个枚举值一行，顺序一一对应
- 第 8 字节校验规则：`byte7 = ((byte0+...+byte6) & 0xFF) ^ 0x55`
- 确认 `DiaRdbi.c` 的 `ReadFunc_0xF194/0xF195/0xFF94/0xFF95` 对新 Index 有 case 或范围覆盖
- `DiaUserRunnable.c` 的 `VEH_VARIANT_<VEH>_INDEX_MAX` 范围判断需覆盖新增 Index

#### 3. ADAS 配置（`coem/<VEH>/components/AswIf/ASW_ADAS/ADAS_Cfg.c`）

- `ADAS_GetVariantDriveSide()`：左舵 `driveSide = 1u`，右舵 `driveSide = 2u`，把新 Index 加入对应 case 组
- `ADAS_FacCfg_ppst[]`（工厂）与 `ADAS_PonCfg_ppst[]`（上电）：每个 Index 一个 `[VEH_VARIANT_...] = {...}` 条目
- 数组长度为 `VEH_VARIANT_INDEX_MAX + 1`，缺失条目会被零初始化（所有开关 OFF），必须补齐

#### 4. RCTB 重量表（`coem/<VEH>/components/AswIf/ASW_OUT/ASWOUT_OutCalc.c`）

- `RctbHalfLoadWeightTable[VEH_VARIANT_INDEX_MAX]` 只填写有实测车重的车型
- 未出现在表中的 Index 值为 0，`GetVehHalfLoadWeight()` 判断 `> 0.0f` 失败后自动回退 `RCTB_DEFAULT_WEIGHT`，因此默认车重的车型**不要**逐行写入 `= RCTB_DEFAULT_WEIGHT`
- 只有用户提供了具体车重时才新增一行

#### 5. 其他检查

- `coem/BYD_UKE` 的 ADAS 逻辑在 `ADAS_HMI.c` 的 `ADAS_GetVariantIndex()` 中用 switch 直接映射，BYD_SC6H 不使用该 switch，而是依赖 `ADAS_Cfg.c`。先确认目标车型所在工程使用哪一套
- 灰化配置 `g_ADAS_VariantGrayCfg_ast`（仅 BYD_UKE）默认不加，除非用户明确要求灰化

### 标准到配置模板的映射（已确认）

| 标准 | ADAS_Cfg 模板（工厂 / 上电） |
|---|---|
| 欧标 | SC6E_3（ENCAP） |
| 非欧标 | SC6E_1（No ENCAP） |
| 韩标 | SC6E_2（KNCAP） |

注意：SC6E_3 上电表的 `BSDLCWCfgSts_u8` 为 `ADAS_CFG_NVM_ENCAP_en`，其他模板为 `ADAS_CFG_NVM_en`，照模板复制即可。

## 需求二：特殊驾驶模式抑制

### 框架位置（以 BYD_UKE 为例，BYD_SC6H 同构）

全部在 `coem/<VEH>/components/AswIf/ASW_ADAS/ADAS_HMI.c` 的 `ADAS_DrvMod_Disable()`（20ms 周期调用）：

1. **车型判定链**：`findVehVariantIndex()`（匹配 `DiaWdbi.c` 编码表）→ Index 范围 → `VehicleType` 枚举。新车型在枚举加 `VEHICLE_TYPE_<VEH>`，在判定链加 `else if` 范围判断
2. **信号来源**：`RteComMapping_Rx.c` 已把 CAN 信号读进 `AdasStM`（结构体在 `ASWIN_AdasState.h`）。常用信号：`VCU_Vehicle_Run_Mode_S`、`Tar_drv_mod_S`、`Act_drv_mod`、拖车组（`TrailerSts`/`DragModSts`/`Dragging_Method_S`/`Actual_Trailer_Type_*`）、`CCO_Active`、`TAB_Ctrl_Sts`。新信号才需要加映射和字段
3. **策略选择**：按车型分支写信号条件 → `ADAS_SUPPRESSION_STRATEGY_*`
4. **策略 → 功能请求**（函数末尾公共 switch，自动生效，通常不用改）：
   - `STRATEGY_1/3`：不置任何请求
   - `STRATEGY_2`：FCTB 灰化+关闭、RCTB 灰化+被动
   - `STRATEGY_2_VARIANT_1/6`：+BSD_LCW/DOW/RCW/RCTA 全灰化被动
   - `STRATEGY_2_VARIANT_5`：仅后向组（BSD_LCW/DOW/RCW/RCTA/RCTB）
   - `STRATEGY_2_VARIANT_3/4`：FCTA/FCTB + 后向组

### 已确认的车型映射（勿重复询问）

| 车型 | 信号 | 映射 |
|---|---|---|
| EM2E（CRGVBYDPF-14968） | `VCU_Vehicle_Run_Mode_S` | 1/2 → 策略1，3 → 策略2，其他不抑制 |
| EW | `VCU_Vehicle_Run_Mode_S` | 1/2 → 策略1，3 → 策略2 |
| SR | `Tar_drv_mod_S` | 1-3 → 策略1，4-8 → 策略2 |
| SC6H/SHH | `Act_drv_mod` | 0-3 → 策略1，4-6 → 策略2 |

### 注意

- 用户给的映射可能和 TR ticket 描述不一致（如 ticket 写"仅策略2"但用户给了完整映射）：以用户最新说法为准，但要点名差异让用户确认
- 生效范围注意是整个车系（INDEX_MIN~MAX）还是特定 Index，ticket 里写具体车型代号（如 EM2ECHDH）时要问清对应哪个 Index
- 注释按用户要求：不加说明性注释（用户明确说了"注释不要"）

## 校验（必须执行，结果写入回复）

1. 数量：枚举数量、编码行数、驱动侧 case 数、工厂表条目数、上电表条目数应一致（重量表只需确认新车型未被误写 `= RCTB_DEFAULT_WEIGHT`）
2. 编码校验和：逐行验证 `byte7`，并检查无重复行
3. 左右舵：驱动侧 case 集合与用户列表逐项比对
4. 编辑器错误：对改动文件调用 `get_errors`

校验命令示例（Python 3.10 完整路径，PATH 中可能没有 python）：

```
& "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe" -c 'import re;L=open(r"<DiaWdbi.c 路径>",encoding="utf-8",errors="ignore").read().splitlines();s=[i for i,l in enumerate(L) if l.strip()=="//<VEH>"][0];e=[i for i,l in enumerate(L) if "// " in l and i>s][0];rows=[l for l in L[s+1:e] if "{0x" in l];[print(n+1, "calc=0x%02X" % ((sum(int(x,16) for x in re.findall(r"0x([0-9A-Fa-f]{2})",r)[:7]) & 0xFF) ^ 0x55), "got=0x"+re.findall(r"0x([0-9A-Fa-f]{2})",r)[7]) for n,r in enumerate(rows)];print("rows",len(rows),"unique",len(set(rows)))'
```

注意：PowerShell 中含单引号或制表符的内联脚本容易卡在续行，优先用单行命令或临时 `.ps1` 文件。

## commit 信息格式（已确认）

- 格式：`<TICKET> <一句话改动描述>`，多个任务分开 commit，一个 commit 一个任务
- 示例：
  - `CRGVBYDPF-14968 EM2E special drive mode suppression: VCU_Vehicle_Run_Mode_S 1/2 strategy 1, 3 strategy 2`
  - `Add CNHEU variant ADAS config: Index1 LHD / Index2 RHD, ENCAP template`
- ticket 号从分支名（`feature/<TICKET>-<描述>`）或 TR 取；独立配置新增任务没有 ticket 号时可省略前缀

## PR 流程（已确认）

1. **先本地编译成功 + 截图**（见顶部铁律）
2. commit 并 push 到 feature 分支
3. 用 `bb_create_pull_request` 建 PR：source = feature 分支，target = master
4. PR 描述：概述改动点（分工程列出）、注明基于 Master 的 commit
5. **截图贴到 PR 评论区**（Bitbucket 评论，不是描述）
6. PR 建好后用 `bb_get_commit_builds` 监控 4 个 Jenkins job：`CR60_Light`（主编译）、`CR60_Light_review_check`、`CR60_Light_quality_check`、`CR60_Light_AI_PR_Review`
7. TR ticket 的 devstatus 会自动关联分支与 PR

## 注意事项

- 已存在的车型条目（如 SHH Index1/2）不要改动；如果其配置与模板不一致，只报告，不擅自修改
- 不修改与本车型无关的文件；不做超出配置新增的逻辑改动
- 未经用户要求不提交、不推送、不建 PR
- 无法编译验证时，明确说明仅做了静态检查
- 搜索代码用精准关键词一次到位（如 `grep -rn "CNHEU" coem/<VEH> --include="*.c" --include="*.h"`），避免反复试探
