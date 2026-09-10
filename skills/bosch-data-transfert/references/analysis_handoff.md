# `cr60-analysis-intake.v1`：数据准备到数据预检查的交接契约

这个文件是 `bosch-data-transfert`（上游）和同级 `cr60-debug-harness-batch`（下游）的唯一业务交接边界。
上游负责数据可用性、代码版本/车型和 arbe 环境准备；下游负责只读的 rosbag 预检查、源码投影、断点 handoff 和 HTML 报告。

## 生命周期

```text
数据源 / 问题单
    ↓
bosch-data-transfert
    ↓  数据目录、bag 路径、代码身份、车型/COEM、构建状态
cr60-analysis-intake.v1.json
    ↓
cr60-debug-harness-batch
    ↓  intake-manifest.v1 + analysis-context.v1
diagnosis-bundle.v1 / viewer-model.v1 / report.html / batch index
```

上游可以在数据拷贝完成后生成 handoff，也可以在 arbe 切 tag、CUDA 配置和编译完成后补充 `environment.build`。不允许用未记录的聊天上下文替代 handoff 中的字段。

## 最小结构

```json
{
  "schema_version": "cr60-analysis-intake.v1",
  "handoff_id": "CRGVI-1829-<timestamp-or-uuid>",
  "status": "ready",
  "producer": {
    "skill": "bosch-data-transfert",
    "workflow": "data-prep-and-arbe-build",
    "created_at": "2026-08-26T12:00:00+08:00"
  },
  "environment": {
    "server": {"host": "<user-confirmed-host>", "user": "<user>", "port": 22},
    "arbe": {
      "workspace": "<remote arbe workspace>",
      "outer_head": "<commit>",
      "outer_branch": "<branch-or-detached>",
      "outer_dirty": false,
      "algo_submodule": "src/algo_source",
      "algo_head": "<commit>",
      "algo_branch": "<branch-or-detached>",
      "algo_dirty": false
    },
    "ros": {"distro": "noetic", "setup": "/opt/ros/noetic/setup.bash"},
    "vehicle": {
      "coem": "<coem directory>",
      "model": "<vehicle model>",
      "cuda_sheet": "<confirmed sheet>"
    },
    "build": {
      "catkin_make": "success|not_run|failed",
      "executable": "<optional executable path>",
      "start": "running|not_started|failed"
    }
  },
  "data": {
    "root": "<remote prepared data root>",
    "source_kind": "prepared_remote_folder|prepared_manifest|user_path",
    "cases": [
      {
        "case_id": "CRGVI-1829",
        "tr_id": "CRGVI-1829",
        "data_dir": "<remote case directory>",
        "bag_paths": [
          {
            "path": "<remote absolute bag path>",
            "format": "bag",
            "size_bytes": 123,
            "sha256": "<optional>"
          }
        ],
        "functions_hint": ["FCTA", "FCTB"],
        "customer_claim": "<optional claim>",
        "preferred_radar": "auto",
        "source_selector": {
          "outer_commit": "<optional>",
          "outer_branch": "<optional>",
          "algo_submodule_commit": "<optional>",
          "algo_submodule_branch": "<optional>"
        }
      }
    ]
  },
  "downstream": {
    "harness_profile": "<optional local TOML profile>",
    "analysis_context": "<optional local analysis-context.v1>",
    "output_dir": "<optional local output directory>",
    "extract_camera": true
  },
  "checks": [],
  "notes": []
}
```

## 字段规则

| 字段 | 上游责任 | 下游用法 |
|---|---|---|
| `status` | 数据、版本和必要配置的整体状态 | `blocked` fail closed；`partial` 需用户明确允许 |
| `environment.server` | 记录用户确认的远程访问目标 | 选择 SSH profile，不从默认值猜服务器 |
| `environment.arbe` | 记录 outer arbe 和 algo submodule 身份 | 校验 analysis context 是否匹配 |
| `environment.vehicle` | 记录已确认的 COEM/车型/CUDA sheet | 绑定参数/ROI 解释，禁止跨车型复用 |
| `environment.build` | 记录是否编译/启动以及产物 | 仅作证据和后续 debug 前置检查，不由 Sprint1 自动启动 |
| `data.cases[].bag_paths` | 给出远程可读的 bag 路径、格式和校验信息 | 每个 bag 展开为下游一个 manifest case |
| `source_selector` | 表示数据绑定的代码版本 | 传给 `BatchAnalyzer` 做 source-context gate |
| `downstream` | 可选地给出下游已有 profile/context/output | 下游优先复用，缺失时按用户授权补建 |
| `checks` / `notes` | 记录缺口和校验结果 | 保留在批量结果和每条报告的 provenance 中 |

## 禁止事项

- 不写入 SSH 私钥、密码、Bearer token 或其他凭据。
- 不把 `message_index`、`wfAutosarData.frameID`、warning message index、objectlist index 和 algorithm index 混成一个 `frame` 或 `index`。
- 不把 `catkin_make` 成功等同于算法运行时变量已经可见；运行时 ROI/中间变量仍需 Sprint2 debug trace。
- 不把数据准备 skill 内部的临时 shell 变量当作下游接口。
- 不在不同 `algo_head`、车型、COEM 或参数 profile 的 case 之间共用同一个未验证 context。

## 下游转换

下游使用其 skill 中的 `consume_analysis_handoff.py` 将 `data.cases[].bag_paths` 转成 `intake-manifest.v1`。一个 case 只有一个 bag 时保留 `case_id`；一个 case 有多个 bag 时追加安全化的文件 stem，确保每个报告一一对应一个数据文件。

随后执行：

```powershell
python -m cr60_debug_harness.cli batch-analyze `
  --profile <harness-profile.toml> `
  --manifest <generated-intake-manifest.json> `
  --context <analysis-context.json> `
  --output <batch-output> `
  --html `
  --web-dist web/dist
```

`diagnosis-bundle.v1` 中必须保留 `handoff_id`、上游环境身份和原始 bag 路径，方便从 HTML 追溯回数据准备步骤。
