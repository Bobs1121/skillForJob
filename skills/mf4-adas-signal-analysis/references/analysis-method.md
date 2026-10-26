# Analysis method and pitfalls

## Episode extraction
Warning channel (HMI level or raw CAN enum) -> boolean "on" mask via the profile rule -> runs; runs closer than
`--merge-gap` (0.3 s) are merged. HMI level 2 = warning shown, 1 = pre-state (use `--on-values 1,2`).
Raw CAN enums are bytes; the loader decodes them and the `off_prefix` rule treats anything not starting with
no/off/inactive/none/0 as on.

## Ego curvature
- Channel: integer-coded `NormalizedPerMetre0_125` -> `kappa = raw * 0.125 / 32768` [1/m] (profile `raw_scale`,
  applied only when the channel dtype is integer; float channels are used as they are).
- Fallback: `kappa = yaw_rate / max(v, 2 m/s)`.
- Radius `R = 1/|kappa|`. For side-specific analysis `kappa_inner` flips the sign for the right side so that
  positive means "this side is the inner side of the curve". Sign convention (+ = left) was assumed from the
  data (left alarms occur with kappa > 0 in left turns); confirm per project. (待验证)
- Check the dtype on a new recording: `mf4_find_channels.py --stats` on the kappa channel; raw values in the
  10^4 range mean integer coding (physical kappa is below 0.2 1/m).

## Relevant objects
`relevantObjects._m_memory._m_values._{k}_` slots 0..21 plus `_m_usedElements` (valid count); cycle about 66 ms.
`dx/dy` is the front corner of the target nearest to the ego, not the centre; `handle 255` = invalid.
The behaviour instance is shared by left and right; the right side evaluates with dy inverted, so the logged
state after a cycle may belong to the last evaluated side (待验证). The overshoot script therefore multiplies dy
by -1 for `--side right` (override with `--dy-sign`).

## Zone-line what-if (mf4_curvature_overshoot.py)
For each cycle in an episode, valid objects: slot < used, handle != 255, |dx| < 15, |dy| < 6, dy != 0.
- fixed shift s: object counts as alarming if `dy_eval > F + s`
- curvature scheme: `shift(kappa_in) = interp(kappa_in, [1/R_far, 1/R_near], [0, shift_max])` (linear in kappa),
  clamped outside.
- residual = number of cycles with at least one alarming object * cycle time.
- band summary: `n`, sum of residual seconds / number of episodes fully suppressed (residual 0).
Limits: no hysteresis, exit timer, dx/TTC logic or vx suppression; episodes are weighted by object presence, not
by the product warning duration. Only the sign and relative size of the effect are meaningful.
Small clip sets are not statistically meaningful: report counts per band and name the clips.

## Ego-path position (mf4_ego_path.py)
Dead reckoning on a 0.01 s grid: `theta += yaw*dt`, `x += v cos(theta) dt`, `y += v sin(theta) dt`.
Target centre: `(dx - L/2, dy +/- W/2)` (+ on the left side, - on the right), moved to world coordinates with the
ego pose; `lat` = signed distance to the nearest point of the ego's earlier path (+ = left of the path),
`arc` = path length from that point to the ego. Ground speed/heading are finite differences of the centre
and are noisy (use trends, not single values). Drift grows with integration time; keep the start 5-8 s before
the window. Width/length of the target are tracker estimates (often defaults like 1.6 x 4.0).

## General pitfalls
- 100k+ channels: always filter with a regex; do not iterate all groups.
- Same signal name in several groups (e.g. different CAN matrix versions): pin with `gi`.
- Low ego speed makes yaw/v noisy; prefer the kappa channel and ignore v < 1 m/s samples for statistics.
- Mark each conclusion as verified on data or inferred.
