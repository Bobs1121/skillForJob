---
name: cr60-debug-harness-batch
description: Batch-analyze CR60/arbe rosbag data from an Agent conversation and generate one evidence-backed HTML report per data item plus a batch index. Use when the user provides a prepared data folder, a `cr60-analysis-intake.v1` handoff, or a manifest and asks for rosbag warning precheck, function/frame/target extraction, current arbe source-context analysis, HTML report generation, or report regeneration.
---

# CR60 Debug Harness Batch

This is the downstream Sprint1 skill for the sibling `bosch-data-transfert` skill. Consume the upstream `cr60-analysis-intake.v1` handoff when available; otherwise require the same inputs explicitly. Keep raw extraction deterministic and preserve source/data provenance. Do not infer an object, frame, ROI, vehicle, branch, or parameter profile when the required evidence is missing.

## Upstream/downstream boundary

```text
bosch-data-transfert
  data source → remote prepared data → code/vehicle/build identity
  output: cr60-analysis-intake.v1.json
        ↓
cr60-debug-harness-batch
  handoff → intake-manifest.v1 → remote bag extraction
  output: diagnosis-bundle.v1 → viewer-model.v1 → per-data HTML + batch index
```

The upstream YAML profile and the downstream harness TOML profile are different formats. Do not pass the upstream YAML directly to the harness CLI. Use `downstream.harness_profile` from the handoff or a user-provided harness TOML, and verify that its server/workspace/topic contract matches the handoff.

Read [`references/upstream_handoff.md`](references/upstream_handoff.md) when the input is a handoff. The canonical producer-side contract is the sibling `bosch-data-transfert/references/analysis_handoff.md` in the skill repository.

## Decide the mode

1. If a `cr60-analysis-intake.v1.json` path is supplied, validate and convert it with `scripts/consume_analysis_handoff.py`, then run manifest mode.
2. If the user supplies a data folder, use `folder-analyze`; it recursively discovers files and creates its own intake manifest.
3. If the user supplies a TOML/JSON manifest, use `batch-analyze`.
4. If `cases/*/diagnosis_bundle.json` already exists and the user only wants refreshed HTML, run the report-only rebuild.
5. If no folder, handoff, manifest, or existing batch output is available, ask for the missing path before running anything.

## Required intake

Collect or locate:

- the harness repository root containing `cr60_debug_harness`, `tools/build_html_reports.py`, and `web/`;
- a downstream harness TOML profile with remote host/user/port, remote arbe workspace, ROS setup, topic contract, replay window, vehicle/profile data, and media preference;
- either a `cr60-analysis-intake.v1` handoff, a Linux-accessible data folder, or a manifest whose `bag` paths are readable by the configured remote host;
- a matching `analysis-context.v1` for the current outer arbe and `src/algo_source` state, or explicit permission to create it with read-only `prepare-context --execute`;
- an output directory, normally a new `outputs/<batch-id>` directory.

Do not silently reuse the known `10.190.171.44` profile for another server, repository, branch, COEM, vehicle, or user. If code versions or vehicle profiles differ, split the work into separate output sessions and contexts.

## Consume the upstream handoff

Run the bridge from the harness root or use the installed skill path:

```powershell
python <skill-dir>\scripts\consume_analysis_handoff.py `
  <cr60-analysis-intake.v1.json> `
  --output-manifest <batch-output>\intake_manifest.json
```

If and only if the user accepts an upstream `status=partial` handoff, add `--allow-partial`. The bridge is deterministic and offline: it validates the schema and expands every `bag_paths` entry into one downstream manifest case. It does not SSH, inspect bag contents, checkout code, or mutate arbe.

Preserve these handoff fields in the downstream case: `handoff_id`, upstream case/TR ID, remote bag path, file metadata, `source_selector`, functions hint, customer claim, and preferred radar. If the handoff has multiple bags under one case, use the generated safe case IDs and keep `parent_case_id` for traceability.

## Prepare or verify source context

Prefer the handoff's or user's matching context after checking its source identity. Otherwise, from the harness root:

```powershell
python -m cr60_debug_harness.cli prepare-context `
  --profile <harness-profile.toml> `
  --execute `
  --output-dir <context-dir>
```

This reads the current remote outer repository and `src/algo_source` snapshot, branch/detached state, dirty state, source files, code index, and runtime schema. It must not checkout, fetch, pull, build, start arbe, or attach GDB. A dirty or detached context is a reproducibility warning, not proof of source/binary equivalence.

## Run the deterministic batch

For a converted upstream handoff or an explicit manifest:

```powershell
python -m cr60_debug_harness.cli batch-analyze `
  --profile <harness-profile.toml> `
  --manifest <intake-manifest.json> `
  --context <context-dir>\analysis_context.json `
  --output <batch-output> `
  --html `
  --web-dist web/dist
```

For a folder without a handoff:

```powershell
python -m cr60_debug_harness.cli folder-analyze `
  --profile <harness-profile.toml> `
  --input-dir <linux-data-folder> `
  --context <context-dir>\analysis_context.json `
  --output <batch-output> `
  --html `
  --web-dist web/dist
```

Use `--prepare-context` instead of `--context` only when the active remote source must be refreshed. Use `--customer-claim "..."` or manifest fields to preserve the customer question. Repeated `--function FCTA`/`FCTB` values are code-analysis focus hints; unless the profile explicitly disables it, extraction discovers every warning bit present in each bag.

`--html` performs deterministic extraction first and then projects each bundle into `viewer-model.v1`. It does not run AI, ROS GUI playback, `catkin_make`, or GDB.

## Regenerate HTML only

When bundles already exist or the viewer changed:

```powershell
npm --prefix web run build
python tools/build_html_reports.py `
  --batch-output <batch-output> `
  --web-dist web/dist
```

The report builder reads `cases/*/diagnosis_bundle.json`; it does not re-read rosbag data or refresh source code. It creates one `data/<data-id>/viewer-model.json`, one `data/<data-id>/report.html`, and the batch-level `index.html` and `batch-index.json`.

## Verify before delivery

Check all of the following:

- `batch_summary.json`, `index.html`, and `batch-index.json` exist;
- every ready case has a per-data `report.html` and `viewer-model.json`;
- each case retains `diagnosis_bundle.json`, `runtime_schema.json`, `vscode_handoff.json`, `alarm_events.csv`, and frame/code evidence where available;
- unsupported formats, missing same-radar targets, missing frame IDs, unresolved camera mappings, decode failures, and source-context mismatches remain explicit;
- feature, side, radar ID, warning message index, same-radar LGU message index, `wfAutosarData.frameID`, target ID, raw SGU index, algorithm index, and objectlist index remain separate;
- parameters and ROI values retain source and `observed`/`derived`/`not_available` status; source projection is never presented as a runtime GDB value;
- handoff/source identity is retained so the HTML can be traced to the upstream prepared data and code state.

If the command returns non-zero because any case is blocked or unsupported, inspect the generated output anyway and report ready/blocked/unsupported counts separately. Do not discard valid per-case reports.

## Evidence and AI boundary

The harness owns exact parsing, frame alignment, target association, source token extraction, ROI projection, and breakpoint text. Never substitute a time-near camera object for a radar target. Pi/AI is optional and comes after deterministic artifacts; it may explain a read-only `pi-context.v1` but must not overwrite raw values or silently repair missing evidence.

## Scope boundary

This skill covers Sprint1 batch precheck and HTML delivery. It may produce copyable VS Code/GDB handoff conditions, but it does not perform remote source changes, branch switching, `catkin_make`, `bash start`, `rosbag play`, breakpoint installation, or runtime variable capture. Route those requests to the appropriate arbe build/debug workflow while reusing the bundle's event IDs, target frames, object IDs, and breakpoint pack.
