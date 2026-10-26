---
name: mf4-adas-signal-analysis
description: Analyze ADAS/radar MF4 (ASAM MDF4) recordings with asammdf scripts - find channels by regex, list warning episodes (BSD/LCA, AEB, etc.) with ego speed/yaw/curvature, dump per-cycle tracked objects in a time window, evaluate warning-zone line shifts against curvature (what-if overshoot analysis), and reconstruct a target's position relative to the ego past path. Use whenever the user mentions MF4/MDF recordings, Gen5 bags, false/missing warnings in recorded data, "which signals are in this MF4", ego curvature or turning radius vs alarms, relevantObjects, or wants to validate a warning-logic change with real drive data. Profile-driven (JSON), so it also works for other projects or signal names.
---

# MF4 ADAS signal analysis

Scripts in `scripts/` share `mf4_common.py`; signal names, scales and warning rules live in a JSON profile
(`profiles/byd_bsd.json` is the reference one). Run with a Python that has `asammdf` and `numpy`
(`pip install asammdf numpy`). Recordings are large (1-3 GB, 100k+ channels): files are opened with
`memory="minimum"`, and each script reads only the channels it needs.

## Workflow

1. **Discover channels** (new project / unknown naming):
   `python scripts/mf4_find_channels.py FILE -r "yaw|speed" [-x "CRC|Obj\d"] --stats`
   Shows `gi=[(group, index)]`. Duplicated channel groups are common; put the `gi` you want into the profile.
2. **List warning episodes** with ego state:
   `python scripts/mf4_warning_episodes.py DIR_OR_FILES --side left|right [--source hmi|can] [--on-values 1,2] [--json out.json]`
3. **Inspect one episode** (per-cycle objects + ego v/kappa/R):
   `python scripts/mf4_object_trace.py FILE --episode N --side left --pad 0.5` or `--t0 --t1`
4. **Quantify a zone-line change against curvature** (what-if):
   `python scripts/mf4_curvature_overshoot.py DIR --side left --line-f 0.8828 --fixed-shifts 0.1,0.3,0.5,0.7 --scheme-r-near 30 --scheme-r-far 60 --scheme-max 0.7`
   Prints per-episode residual alarm time, curvature histogram and a per-radius-band summary. Check that the
   large-R / outer-side bands (true overtakers) are unchanged.
5. **Is the target really in my lane while I turn?** (optional)
   `python scripts/mf4_ego_path.py FILE --t0 .. --t1 .. --handle H --integ-from t0-7`

Use `--help` on any script. Times are MF4 timestamps (seconds, file may not start at 0).

## Adapting to another project

Copy `profiles/byd_bsd.json` and change: `ego.speed|yaw|kappa` (name / `gi` / `regex`, `scale` to SI,
`raw_scale` for integer-coded channels), `warnings.<side>.<hmi|can>.signal` and `on` rule
(`{"eq":[..]}`, `{"min":x}`, `{"off_prefix":[..]}` for enum text), `objects.*` regexes and field list,
`zone.line_f_m`. Pass it with `--profile path/to/file.json`. If no kappa channel exists, kappa falls back to
`yaw_rate / max(v, 2 m/s)` (noisy at low speed).

## Interpretation rules and pitfalls

Formulas and caveats are in [references/analysis-method.md](references/analysis-method.md); read it before
drawing conclusions from step 4 or 5. Key points:
- Output of step 4 is an object-level approximation (no hysteresis/exit timer): use it for ranking and sizing.
- Sign of kappa (+ = left) and the right-side dy inversion are assumptions; verify on a known clip.
- Enum channels come as bytes (decoded to text automatically); some channels have several groups.
- State and conclusions should say what was verified on data and what is inferred.
