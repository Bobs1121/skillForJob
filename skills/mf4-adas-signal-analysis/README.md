# mf4-adas-signal-analysis

从 ADAS / 雷达的 MF4（ASAM MDF4）实车录制数据里，抽取并分析信号的一套脚本。典型用途：定位某个报警（如 BSD/LCA）在什么时刻、什么工况下触发，并用真实数据验证报警逻辑的修改是否有效。

信号名、换算系数、报警判定规则都放在 JSON profile 里，脚本本身不绑定具体项目。仓库自带 BYD CR60 / Gen5 的 profile（`profiles/byd_bsd.json`），换项目只需复制并修改它。

## 能做什么

| 脚本 | 作用 |
|------|------|
| `mf4_find_channels.py` | 用正则在 10 万级通道里找信号，`--stats` 给出采样数、时间范围、取值范围 |
| `mf4_warning_episodes.py` | 列出报警段（起止、时长），附带自车速度、曲率 κ、转弯半径 R |
| `mf4_object_trace.py` | 按周期打印某个时间窗内的相关目标（dx、dy、vx、vy、宽、长）和自车状态 |
| `mf4_curvature_overshoot.py` | 曲率统计，并评估"把内侧线 F 外移 s 米"后各半径区间里报警会少多少 |
| `mf4_ego_path.py` | 用速度和横摆角速度积分自车轨迹，算目标相对自车走过路径的横向偏移 |

## 安装

需要 Python 3.9 及以上，以及两个依赖：

```bash
pip install asammdf numpy
```

数据文件 1-3 GB 属正常，脚本以 `memory="minimum"` 打开，只读用到的通道，内存占用不大，但首次打开一个文件需要几十秒建立通道索引。

## 快速上手

在 `scripts/` 目录下运行（每个脚本都支持 `--help`）。

```bash
# 1. 找通道：自车速度、横摆角速度
python mf4_find_channels.py D:/data/clip.MF4 -r "Yaw_Rate|Vehicle_Speed" --stats

# 2. 列出左侧报警段（可以传文件、目录，目录会递归找 *.mf4）
python mf4_warning_episodes.py D:/data/clips --side left

# 3. 看第 2 个报警段前后 0.5 s 的目标轨迹
python mf4_object_trace.py D:/data/clip.MF4 --episode 2 --side left --pad 0.5

# 4. 评估 F 线外移：固定外移量 + 随曲率变化的方案
python mf4_curvature_overshoot.py D:/data/clips --side left --line-f 0.8828 \
    --fixed-shifts 0.1,0.3,0.5,0.7 \
    --scheme-r-near 30 --scheme-r-far 60 --scheme-max 0.7

# 5. 某个目标是否还在自车走过的路径上
python mf4_ego_path.py D:/data/clip.MF4 --t0 616.3 --t1 617.2 --handle 2 --integ-from 610
```

### 输出示例（报警段列表）

```text
== clip.MF4  duration=85s  warning=_m_bsdlcaWarnLValue  kappa=_m_value
   3 episode(s)
   #0    615.64-  616.47s ( 0.84s) v=  4.4m/s kappa0=+0.0541 kappa_mean=+0.0534 R=  18.7m
```

## 术语

- **报警段（episode）**：报警信号连续为"开"的一段时间；间隔小于 0.3 s 的相邻段会合并。
- **κ（kappa）**：自车行驶轨迹曲率，单位 1/m，正号表示左转；转弯半径 R = 1/|κ|。
- **相关目标（relevantObjects）**：BSD 行为模块实际用来判断报警的目标列表，每周期最多 22 个槽位，周期约 66 ms。
- **F 线**：BSD 报警区域的内侧纵向边界，默认 0.8828 m（来自参数，换参数集要改 `--line-f` 或 profile 里的 `zone.line_f_m`）。
- **dx / dy**：目标最近前角在自车坐标系下的纵向、横向位置，不是目标中心。

## 适配其他项目

复制 `profiles/byd_bsd.json`，按需修改后用 `--profile 路径` 指定：

| 字段 | 含义 |
|------|------|
| `ego.speed / yaw / kappa` | 通道名（或 `regex`、`gi`），`scale` 换算到 SI 单位，整型编码通道用 `raw_scale` |
| `warnings.<left/right>.<hmi/can>` | 报警通道及"开"的判定：`{"eq":[2]}`、`{"min":1}` 或枚举文本用 `{"off_prefix":[...]}` |
| `objects` | 相关目标通道的正则和字段列表 |
| `zone.line_f_m` | F 线横向位置 |

没有曲率通道时，κ 自动退化为 `横摆角速度 / max(车速, 2 m/s)`，低速下噪声较大。

## 使用时要注意

- **what-if 结果只是近似**：`mf4_curvature_overshoot.py` 在目标层面判断，不包含迟滞、退出计时、TTC 逻辑和 vx 抑制，用于排序和估量级，不能当作最终结论。
- **符号约定未在全部数据上验证**：κ 正号为左转，以及右侧评估时 dy 取反，是根据已有数据假设的，换数据时先用一个已知片段核对。
- **样本量**：几个片段不具备统计意义，汇报时写清楚每个半径区间的段数和片段名。
- **同名通道多组**：不同 CAN 矩阵版本会出现同名通道，用 `gi` 在 profile 里固定。
- **路径积分有漂移**：`--integ-from` 建议只取窗口前 5-8 s；目标宽长常是跟踪器默认值，目标对地速度噪声大，只看趋势。

公式、判定规则和更多坑见 [references/analysis-method.md](references/analysis-method.md)。给 Agent 使用时的触发说明见 [SKILL.md](SKILL.md)。

## 目录

```text
mf4-adas-signal-analysis/
├── SKILL.md                      # Agent 入口（触发描述 + 工作流）
├── README.md
├── profiles/byd_bsd.json         # BYD CR60 / Gen5 信号配置
├── references/analysis-method.md # 方法、公式、注意事项
└── scripts/
    ├── mf4_common.py             # 公共：读通道、自车状态、报警段、目标
    ├── mf4_find_channels.py
    ├── mf4_warning_episodes.py
    ├── mf4_object_trace.py
    ├── mf4_curvature_overshoot.py
    └── mf4_ego_path.py
```

## 验证状态

在 `CRGVBYDPF-14486` 的一个约 85 s 的片段（时间戳 600-685 s）上，5 个脚本均可运行：曲率通道的整型缩放自动识别正确（R≈18-20 m），报警段、目标轨迹、F 线 what-if、路径积分都有输出。尚未做多文件目录的批量运行，也未测试右侧报警。
