#!/usr/bin/env python
"""Curvature statistics + 'what if line F were shifted outward' evaluation for BSD/LCA warnings.

For every warning episode the script looks at the relevant objects that are active during the alarm
and counts how long at least one of them is still beyond the inner vertical line F when F is shifted
outward by a fixed amount, or by a curvature-dependent amount (small radius -> larger shift).

  python mf4_curvature_overshoot.py DATA_DIR_OR_FILES... --side left --line-f 0.8828 \
      --fixed-shifts 0.1,0.3,0.5,0.7 --scheme-r-near 30 --scheme-r-far 60 --scheme-max 0.7

Reading the result
  * residual = time (s) in the episode with an object beyond F+shift.
  * 'suppressed' = residual 0 although the episode had >0 s without shift.
  * A good scheme suppresses episodes in the small-radius bands and leaves the large-radius / outer
    side episodes (real overtakers) untouched -> check the band summary at the end.
  * This is an object-level approximation (it ignores hysteresis, the exit timer, TTC/dx handling of
    line F and vx suppression), so use it for ranking and sizing, not as a final proof.
"""
import argparse
from collections import defaultdict

import numpy as np

from mf4_common import (Ego, Objects, expand_inputs, find_episodes, interp_clamp, kappa_inner,
                        load_profile, open_mdf, radius)

INVALID_HANDLE = 255


def band_of(k_in, edges):
    if k_in <= 1.0 / 9999:
        return "outer/straight"
    r = 1.0 / k_in
    lo = 0.0
    for e in edges:
        if r < e:
            return f"R {lo:.0f}-{e:.0f}"
        lo = e
    return f"R >= {lo:.0f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--profile", default="byd_bsd")
    ap.add_argument("--side", choices=["left", "right"], default="left")
    ap.add_argument("--source", choices=["hmi", "can"], default="hmi")
    ap.add_argument("--on-values")
    ap.add_argument("--line-f", type=float, help="line F dy [m]; default from profile zone.line_f_m")
    ap.add_argument("--fixed-shifts", default="0.1,0.3,0.5,0.7")
    ap.add_argument("--scheme-r-near", type=float, help="radius with full shift [m]")
    ap.add_argument("--scheme-r-far", type=float, help="radius with zero shift [m]")
    ap.add_argument("--scheme-max", type=float, help="full shift [m]")
    ap.add_argument("--r-bands", default="30,60,100", help="band edges [m] used for the summary")
    ap.add_argument("--slots", type=int, default=3)
    ap.add_argument("--dy-sign", type=int, choices=[-1, 1], help="multiply logged dy (default +1 left, -1 right)")
    ap.add_argument("--max-dx", type=float, default=15.0)
    ap.add_argument("--max-dy", type=float, default=6.0)
    ap.add_argument("--v-min", type=float, default=1.0, help="m/s, driving threshold for the kappa histogram")
    a = ap.parse_args()

    prof = load_profile(a.profile)
    F = a.line_f if a.line_f is not None else prof["zone"]["line_f_m"]
    shifts = [float(x) for x in a.fixed_shifts.split(",") if x]
    sign = a.dy_sign if a.dy_sign else (-1 if a.side == "right" else 1)
    edges = [float(x) for x in a.r_bands.split(",") if x]
    scheme = None
    if a.scheme_r_near and a.scheme_r_far and a.scheme_max is not None:
        scheme = (1.0 / a.scheme_r_far, 1.0 / a.scheme_r_near, a.scheme_max)
        print(f"scheme: shift 0 at R>={a.scheme_r_far:g} m ... {a.scheme_max:g} m at R<={a.scheme_r_near:g} m "
              f"(linear in kappa {scheme[0]:.4f}..{scheme[1]:.4f})")
    print(f"line F = {F:.4f} m, side={a.side}, dy sign={sign:+d}, objects limited to |dx|<{a.max_dx:g}, |dy|<{a.max_dy:g}")

    hist = defaultdict(float)  # band -> seconds
    drive_total = 0.0
    rows = []

    for f in expand_inputs(a.inputs):
        m = open_mdf(f)
        ego = Ego(m, prof)
        obj = Objects(m, prof, slots=a.slots)
        dt = obj.dt

        # curvature histogram over driving time
        k_all = kappa_inner(ego.kappa_at(obj.t), a.side)
        v_all = ego.speed_at(obj.t)
        for k, v in zip(k_all[v_all > a.v_min], v_all[v_all > a.v_min]):
            hist[band_of(k, edges)] += dt
        drive_total += float((v_all > a.v_min).sum()) * dt

        eps, _ = find_episodes(m, prof, a.side, a.source, [int(x) for x in a.on_values.split(",")] if a.on_values else None)
        print(f"\n== {f.name}: {len(eps)} episode(s), cycle {dt * 1000:.0f} ms")
        hdr = f"   {'#':>2} {'t0':>8} {'dur':>5} {'v':>5} {'R':>6} {'dyMax':>6} {'base':>5}"
        hdr += "".join(f" {'+%.1f' % s:>5}" for s in shifts) + (f" {'scheme':>6}" if scheme else "")
        print(hdr)
        for i, (t0, t1) in enumerate(eps):
            idx = obj.window(t0, t1)
            if len(idx) == 0:
                continue
            dy = sign * obj.data["dy"][idx]
            dx = obj.data["dx"][idx]
            hd = obj.data["handle"][idx]
            used = obj.used[idx] if obj.used is not None else np.full(len(idx), a.slots)
            slot_ok = np.arange(a.slots)[None, :] < used[:, None]
            valid = slot_ok & (hd != INVALID_HANDLE) & (np.abs(dy) < a.max_dy) & (np.abs(dx) < a.max_dx) & (dy != 0)
            tt = obj.t[idx]
            k_in = kappa_inner(ego.kappa_at(tt), a.side)
            dy_max = float(np.where(valid, dy, -99).max())
            base = float((valid & (dy > F)).any(axis=1).sum()) * dt
            res = []
            for s in shifts:
                res.append(float((valid & (dy > F + s)).any(axis=1).sum()) * dt)
            sch = None
            if scheme:
                sh = interp_clamp(k_in, scheme[0], 0.0, scheme[1], scheme[2])
                sch = float((valid & (dy > (F + sh)[:, None])).any(axis=1).sum()) * dt
            k_mean = float(k_in.mean())
            R = float(radius(k_mean)) if k_mean > 1.0 / 9999 else float("inf")
            band = band_of(k_mean, edges)
            rows.append(dict(file=f.name, i=i, band=band, base=base, res=res, sch=sch, dur=t1 - t0))
            line = f"   {i:>2} {t0:8.2f} {t1 - t0:5.2f} {float(ego.speed_at(t0)):5.1f} {R:6.1f} {dy_max:+6.2f} {base:5.2f}"
            line += "".join(f" {r:5.2f}" for r in res) + (f" {sch:6.2f}" if scheme else "")
            print(line)

    print("\n== driving time by curvature band (inner side of the evaluated side)")
    for b, sec in sorted(hist.items(), key=lambda kv: -kv[1]):
        print(f"   {b:<16} {sec:8.1f}s  {100 * sec / max(drive_total, 1e-9):5.1f}%")

    print("\n== episode summary by band (object-based residual alarm time)")
    cols = [("base", lambda r: r["base"])] + [(f"+{s:g}", (lambda r, n=n: r["res"][n])) for n, s in enumerate(shifts)]
    if scheme:
        cols.append(("scheme", lambda r: r["sch"]))
    print(f"   {'band':<16} {'n':>3} " + " ".join(f"{c:>12}" for c, _ in cols) + "   (sum s / suppressed)")
    for b in sorted({r["band"] for r in rows}):
        rs = [r for r in rows if r["band"] == b and r["base"] > 0]
        if not rs:
            continue
        cells = []
        for _, fn in cols:
            tot = sum(fn(r) for r in rs)
            sup = sum(1 for r in rs if fn(r) == 0)
            cells.append(f"{tot:6.2f}/{sup:<3d}")
        print(f"   {b:<16} {len(rs):>3} " + " ".join(f"{c:>12}" for c in cells))


if __name__ == "__main__":
    main()
