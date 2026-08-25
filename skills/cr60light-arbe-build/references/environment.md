# arbe 切分支/编译 环境参考

## 工作区路径

| 项 | 路径 |
|----|------|
| arbe 工作区根 | `~/CR60LIGHT/cr60_light_arbe/` |
| 外仓（GUI） | `~/CR60LIGHT/cr60_light_arbe/`（git 分支 `develop_LGU_Simulation`） |
| 内仓（算法） | `~/CR60LIGHT/cr60_light_arbe/src/algo_source/`（submodule，detached HEAD） |
| 外仓 Config | `~/CR60LIGHT/cr60_light_arbe/src/arbe_phoenix_radar_driver-master/arbe_gui/Config/` |
| 配置文件 | `Config/launch_config_4radars.yaml` |
| 内仓 CUDA 源 | `~/CR60LIGHT/cr60_light_arbe/src/algo_source/coem/<车型>/tools/container_input/08_CustData/` |
| 启动脚本 | `~/CR60LIGHT/cr60_light_arbe/start` |
| 清理脚本 | `~/CR60LIGHT/cr60_light_arbe/clean`（rm build/devel） |
| 操作指南 | `~/CR60LIGHT/cr60_light_arbe/FCTB_Batch_Replay_Operation_Guide.md` |

## 车型 → 内仓 CUDA 表映射

| 车型目录 | CUDA 表（08_CustData 最新） | 示例版本 |
|----------|------------------------------|----------|
| BYD_UKE | CUDA_BYD_UKE_Bundle_V*.xlsx | V2.0 |
| BYD_SC6H | CUDA_BYD_SC6H_V*.xlsx | V2.0 |
| SERES_E68 | CUDA_SERES_E68_V*.xlsx | V1.1 |
| GAC_T58G | CUDA_GAC_T58G_V*.xlsx | V1.1 |
| GAC_A66 | CUDA_GAC_A66_V*.xlsx | V1.1 |
| JETUR_T1V | CUDA_JETOUR_T1V_V*.xlsx | V1.0 |
| JETUR_T1J | CUDA_JETOUR_T1J_V*.xlsx | V1.1 |
| SGMW_SGU | CUDA_SGMW_SGU_V*.xlsx | V1.0 |
| GEELY_V451K | CUDA_GEELY_V451K_V*.xlsx | V1.1 |

- **注意**：示例版本号仅供参考，**实际要以切 tag 后内仓 `08_CustData` 目录 `ls` 到的文件为准**（版本号随 tag 递增，可能比示例新，也可能某仓是精简版没有该 xlsx，只有 `.hex`）。
- 08_CustData 目录存在：BYD_UKE, SERES_E68, GAC_T58G, JETUR_T1V, GAC_A66, SGMW_SGU, GEELY_V451K, BYD_SC6H, JETUR_T1J
- 拷贝前 `ls` 取目录中最新版本（版本号递增）。

## launch_config_4radars.yaml 关键行

```
53  xlsx_path: "CUDA_<车型>_<版本>.xlsx"   # CUDA 表（拷贝到 Config 的最新文件）
54  xlsx_sheet: "03_QZH"                   # 车型 sheet
75  type: BYD_UKE                          # 车型 type
```

- CUDA xlsx 内 sheet 命名：`dataType, Readme, VersionInfo, 00_SC2E, 01_SA3, 02_PA, 03_QZH, 04_EWE, 05_MR`
- QZH 车型 → `03_QZH`

## 版本 tag（BYD UKE 系列）

| 表格 G 列 | 代码仓 tag |
|-----------|-----------|
| BL03RC02.7_S | BYD_UKE_BL03RC02.7 |
| BL03RC02.8_S | BYD_UKE_BL03RC02.8 |
| BL04RC01.2 | BYD_UKE_BL04RC01.2 |

- 匹配规则：去 `_S` 尾缀，加 `BYD_UKE_` 前缀。
- 内仓本地 tag 488 个，但新 tag 需 `git fetch origin --tags` 才可见。
- 外仓 `develop_LGU_Simulation` 记录的 submodule 指针可能指向其他车型 tag（如 SC6H），内仓手动切 tag 后不一致是正常预期。

## 仿真临时改动

| 文件 | 改动 |
|------|------|
| 外仓 `arbe_gui/src/arbe_visualization_engine/visualization_node.cpp` | `PostProcessMainTI(...)` 末尾 `..., &algo_objGMWInfo, taskTime, taskTime)`（多传 taskTime） |
| 内仓 `algo_source/adas/symmetry/perception/include/paraDefine.h` | `#define BUILDMODEL 2`（原 0；2 = ROS GUI mode） |

## 编译/启动

```bash
cd ~/CR60LIGHT/cr60_light_arbe
source /opt/ros/noetic/setup.bash
catkin_make          # 编译（10-30min）
bash start           # 启动（source devel/setup.bash + roslaunch arbe.launch）
```

- ROS：Noetic。catkin_make 在 `/opt/ros/noetic/bin/catkin_make`。
- GUI 需要显示环境（本地 X / X 转发）。

## 相关

- 数据准备（表格解析、目录、bag 拷贝）：skill `cr60light-data-prep`
- 服务器/权限/代码仓 API：cr60light-data-prep 的 `references/environment.md`
