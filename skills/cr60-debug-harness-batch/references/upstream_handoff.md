# 下游消费 `cr60-analysis-intake.v1`

`bosch-data-transfert` 是上游，负责把问题单数据准备到 Linux、确认 arbe/algo_source 版本和车型/COEM；`cr60-debug-harness-batch` 是下游，负责只读解析 rosbag 并生成诊断包和 HTML。

## 下游必须读取的字段

```text
schema_version = cr60-analysis-intake.v1
status = ready | partial | blocked
handoff_id
environment.server.host/user/port
environment.arbe.workspace
environment.arbe.outer_head/outer_branch/outer_dirty
environment.arbe.algo_submodule/algo_head/algo_branch/algo_dirty
environment.vehicle.coem/model/cuda_sheet
data.root
data.cases[].case_id/tr_id/data_dir/bag_paths[]
data.cases[].source_selector
```

`environment.build`、`checks` 和 `notes` 用于显示准备状态和证据缺口，不等同于算法已经运行或 runtime 变量已经采集。

## 转换规则

| 上游字段 | 下游字段 | 规则 |
|---|---|---|
| `data.cases[].case_id` | `manifest.cases[].case_id` | 单个 bag 时保留；多个 bag 时追加安全化文件 stem |
| `data.cases[].bag_paths[].path` | `manifest.cases[].bag` | 保留远程绝对路径，不在本地 `resolve()` |
| `functions_hint` | `functions` | 仅作为源码关注提示，不遮蔽其他 warning bit |
| `customer_claim` | `customer_claim` | 原样保留到 diagnosis bundle |
| `preferred_radar` | `preferred_radar` | 只作选择提示，不能覆盖数据证据 |
| `source_selector` | `source_selector` | 交给 `BatchAnalyzer` 与 analysis context 做版本 gate |
| 文件 format/size/sha256 | `upstream_provenance.file_metadata` | 只读保留，方便数据完整性追溯 |
| `handoff_id` | `upstream_provenance.handoff_id` | 每个 case 必须保留 |

转换脚本：

```powershell
python <skill-dir>\scripts\consume_analysis_handoff.py `
  <handoff.json> `
  --output-manifest <batch-output>\intake_manifest.json
```

脚本只做 JSON schema/字段检查和 manifest 生成，不连接服务器、不读取 bag、不切换代码。

## Profile 边界

上游 `profiles/*.yml` 面向数据准备和 arbe setup；下游 harness 使用自己的 TOML profile。下游 profile 至少要能表达：

- 远程 SSH host/user/port；
- arbe workspace 和 ROS setup；
- LGU、warning、object、camera topic contract；
- replay warm-up/post window；
- 车型/车辆几何参数和媒体开关。

如果 handoff 中的服务器或 workspace 与下游 TOML 不一致，先阻塞并要求确认，不能把两个 profile 的字段静默拼接。

## 状态控制

- `ready`：可转换并运行 Sprint1。
- `partial`：只在用户明确接受时加 `--allow-partial`；仍需分开报告可用和缺失 case。
- `blocked`：不生成可供分析的 manifest；先回上游补输入。
- `.bag` 是当前 Sprint1 正式支持格式；`.blf`/`.mf4`/`.mcap` 可被发现，但必须标记 `unsupported`，不能按 rosbag 解析。

## 结果回传

下游完成后向用户返回：

```text
batch_output/index.html
batch_output/batch-index.json
batch_output/batch_summary.json
batch_output/data/<data-id>/report.html
```

每条报告和 `diagnosis_bundle.json` 应保留 `handoff_id`、远程 bag 路径、source identity、事件/帧/目标索引和证据缺口。HTML 不是对正报/误报的最终判定；runtime ROI、分支和中间变量仍需后续 DebugSession。
