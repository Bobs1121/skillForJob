---
name: blf-can-analysis
description: Use when analyzing CAN bus BLF log files, especially for BYD Corner Radar (CR60 / MPC4 / StandardCANFD), ADAS debugging (BSD/LCA, DOW, RCTA, RCW, RCTB, FCTA, FCTB), radar hardware status, state machine transitions, and target tracking (SGU / 0x291 / 0x36F).
---

# BLF CAN Data Analysis Skill

## Overview

A unified toolchain for analyzing automotive CAN / CAN FD BLF (Binary Logging Format) data.
Supports both **BYD Public CAN Matrix** (StandardCANFD) and **MPC4 Corner Radar Private CAN Matrix** (RRL/RRR & RFL/RFR).

## Core Capabilities

1. **BLF Exploration (`explore`)**: Channel breakdown, CAN FD vs Classical CAN, message frequency, DLC distribution, and DBC matching.
2. **Radar Hardware & State Machine Audit (`status`)**: Sensor blindness (`BLIND`), internal failures (`Failure_Status`), RF modulation / time sync (`Modulation_Status`), SGU failures (`SGUFail`), and calibration state (`SDAState`).
3. **Function Warning & Braking Audit (`warnings` / `bsd` / `rctb`)**: Audits BSD/LCA, DOW, RCTA, RCW, RCTB, FCTA, and FCTB warning signals, trigger episodes, durations, and braking deceleration requests.
4. **Target Tracking & SGU Audit (`targets`)**: Extracts header statistics (`NumValidObjects`), active trajectory tracks, positions $(P_x, P_y)$, relative velocities $(V_x, V_y)$, and measurement status.

Requires `pip install python-can cantools`. For MF4 recordings use the `mf4-adas-signal-analysis` skill instead.

---

## CAN Matrix & Architecture Reference

### 1. BYD MPC4 Corner Radar Private CAN (Private Bus)

| Channel / ID | Node / Message | Key Signals & Function |
|---|---|---|
| **Ch2 0x410** | `RRL_RadarStatus` | 左后雷达底层状态: `RRL_Status_BLIND`, `RRL_Status_Failure_Status`, `RRL_Status_Modulation_Status`, `RRL_Status_SGUFail` |
| **Ch2 0x450** | `RRR_RadarStatus` | 右后雷达底层状态: `RRR_Status_BLIND`, `RRR_Status_Failure_Status`, `RRR_Status_Modulation_Status`, `RRR_Status_SGUFail` |
| **Ch2 0x560** | `RRL_20msPDU` | RCTB故障状态 `RRL_RCTBSysFltSts`, 自标定状态 `RRL_SDAState` |
| **Ch2 0x561** | `RRL_50msPDU` | 功能状态机: `RRL_BSDSelSts`, `RRL_DOWSelSts`, `RRL_RCTSysSelSts`, `RRL_RCWSelSts`, `RRL_RCTBSysSta`<br>功能报警: `RRL_LBSDAndLCAWrnng`, `RRL_LDOWWrnng`, `RRL_LRCTAWrnng`, `RRL_RCWWrnng`, `RRL_RCTBReq`, `RRL_RCTBTrgtDcl` |
| **Ch2 0x054** | `RRR_HU_SelReq` | 车机开关请求: `RRR_BSDSelReq`, `RRR_DOWSelReq`, `RRR_LCASelReq`, `RRR_RCWSelReq`, `RRR_RCTSysSelReq` |
| **Ch2 0x414~0x434** | `RRL_SGU01~32` | 左后雷达 SGU 目标流（Header + 32个目标）: 包含 $P_x, P_y, V_x, V_y$, `MeasurementStatus`, `ExistProb` |
| **Ch2 0x454~0x474** | `RRR_SGU01~32` | 右后雷达 SGU 目标流（Header + 32个目标） |
| **Ch3 0x310 / 0x350** | `RFL / RFR_RadarStatus` | 前角雷达底层状态机 |
| **Ch3 0x314~0x334** | `RFL_SGU01~32` | 左前雷达 SGU 目标流 |
| **Ch3 0x354~0x374** | `RFR_SGU01~32` | 右前雷达 SGU 目标流 |

### 2. BYD Public CAN Matrix (StandardCANFD)

| CAN ID | Message Name | Key Signals |
|---|---|---|
| **0x0418** | `RCR_R_0x418` | `R_BSD_Warning_Left_S`, `R_BSD_Warning_Right_S`, `Right_Radar_RCTB_Status_S`, `Right_Radar_RCTB_Braking_Req_S`, `RCTBTargetDecel_S` |
| **0x0453** | `RCR_R_0x453` | `RCTA_Assemble_Status_S`, `RCTB_Assemble_Status_S`, `BSD_Assemble_Status_S`, `DOW_Assemble_Status_S` |
| **0x0291** | `RCR_R_0x291` | Multiplexed targets (0~2): $d_x, d_y, v_x, v_y$, `Target_Warning`, `Target_State_B1` |
| **0x0322** | `IPB_0x322` | `RCTB_active`, `RCTB_Available` (制动系统执行端) |
| **0x0121 / 0x10C** | `IPB_0x121 / 0x10C` | `IPB_Vehicle_Speed_S` / `VehicleSpeed_Status`, `AEB_Dec_Active_S` |
| **0x0342** | `VCU_0x342` | `VCU_Goal_Gear_S`, `VCU_Vehicle_Run_Mode_S` |

---

## CLI Commands & Usage

All scripts are located in `scripts/`:

```bash
# 1. 快速概览 BLF 总线通道、报文数量与频率
python scripts/blf_analyze.py explore <path_to_blf>

# 2. 审查雷达硬件自检与底层状态机 (BLIND, Failure, SGUFail, Modulation)
python scripts/blf_analyze.py status <path_to_blf> [--dbc <dbc_files>...]

# 3. 审查 ADAS 功能报警与制动请求信号
python scripts/blf_analyze.py warnings <path_to_blf> [--dbc <dbc_files>...]

# 4. SGU 目标流与目标轨迹追踪分析（需 --dbc 给出私有 CAN 的 DBC，文件名含 RRL/RCR 或 RFL/FCR）
python scripts/blf_analyze.py targets <path_to_blf> --dbc <dbc_files>...

# 5. BSD / LCA 预警事件分段分析
python scripts/bsd_episodes.py <path_to_blf> --dbc <dbc_file>
```

未传 `--dbc` 时，`status` / `warnings` 会在 BLF 所在目录、其上一级目录以及环境变量 `BLF_DBC_DIR` 指向的目录中查找 `*.dbc`。

---

## Common Diagnostic Patterns

1. **误报警分析 (False Positive Analysis)**:
   * 运行 `warnings` 查看预警发生的起始与结束时间戳。
   * 运行 `targets` 检查预警期间是否有 SGU 目标进入警戒区（$P_y$ 横向距离 0.5~3.5m，$P_x$ 纵向处于盲区覆盖范围）。
   * 检查目标 `MeasurementStatus` 是否为 `Measured`，`ExistProb` 是否稳定。

2. **硬件/通信异常排查**:
   * 运行 `status`，如果 `RRL_Status_BLIND != 0` 说明雷达被遮挡。
   * 如果 `Failure_Status` 出现 `Misalignment_elevation` 或 `azimuth`，说明雷达安装失准。
   * 如果 `SDAState` 长期处于 `Ongoing` 或 `Fail`，说明自标定过程异常。
