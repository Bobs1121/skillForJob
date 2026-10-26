#!/usr/bin/env python
"""Where is a tracked target relative to the ego's *past path* (not just the ego x axis)?

The ego pose is integrated from speed and yaw rate; the target's front-corner position (dx, dy) is
turned into a centre point, moved to world coordinates and compared with the ego's earlier path.
This answers "is the vehicle behind me still in my lane while I am turning?".

  python mf4_ego_path.py FILE --t0 321 --t1 324 --handle 2 [--side left] [--integ-from 314]

Output columns: lateral offset to the ego past path (lat, + = left of the path), arc distance along the
path (arc), target ground speed (spd) and heading difference to the ego (hd, deg).

Assumptions: (dx, dy) is the target's front corner nearest to the ego, so the centre is
(dx - L/2, dy + W/2) on the left side and (dx - L/2, dy - W/2) on the right side. Dead-reckoning drift
grows with time: keep --integ-from only a few seconds before --t0.
"""
import argparse

import numpy as np

from mf4_common import Ego, Objects, load_profile, open_mdf


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--profile", default="byd_bsd")
    ap.add_argument("--t0", type=float, required=True)
    ap.add_argument("--t1", type=float, required=True)
    ap.add_argument("--handle", type=int, required=True, help="object handle to follow")
    ap.add_argument("--side", choices=["left", "right"], default="left")
    ap.add_argument("--integ-from", type=float, help="start of ego dead reckoning (default t0-7)")
    ap.add_argument("--slots", type=int, default=3)
    ap.add_argument("--step", type=float, default=0.01, help="integration step [s]")
    a = ap.parse_args()

    prof = load_profile(a.profile)
    m = open_mdf(a.file)
    ego = Ego(m, prof)
    obj = Objects(m, prof, slots=a.slots)

    ti = a.integ_from if a.integ_from is not None else a.t0 - 7.0
    dt = a.step
    tg = np.arange(ti, a.t1 + dt, dt)
    v = ego.speed_at(tg)
    y = ego.yaw_at(tg)
    th = np.cumsum(y) * dt
    px = np.cumsum(v * np.cos(th)) * dt
    py = np.cumsum(v * np.sin(th)) * dt
    lat_sign = 1.0 if a.side == "left" else -1.0

    print("t, dx, dy, W, L, yawAngle | centre(x,y) | lat, arc, spd, hd")
    prev = None
    for j in obj.window(a.t0, a.t1):
        used = int(obj.used[j]) if obj.used is not None else a.slots
        for s in range(min(used, a.slots)):
            if int(obj.data["handle"][j, s]) != a.handle:
                continue
            g = {f: float(obj.data[f][j, s]) for f in obj.fields}
            cx = g["dx"] - g["length"] / 2.0
            cy = g["dy"] + lat_sign * g["width"] / 2.0
            i = int(round((obj.t[j] - ti) / dt))
            c, sn = np.cos(th[i]), np.sin(th[i])
            wx, wy = px[i] + c * cx - sn * cy, py[i] + sn * cx + c * cy
            n = int(np.argmin((px[: i + 1] - wx) ** 2 + (py[: i + 1] - wy) ** 2))
            lat = -np.sin(th[n]) * (wx - px[n]) + np.cos(th[n]) * (wy - py[n])
            arc = float(np.sum(v[n: i + 1]) * dt)
            spd = hd = float("nan")
            if prev is not None and obj.t[j] - prev[0] > 1e-3:
                vxw, vyw = (wx - prev[1]) / (obj.t[j] - prev[0]), (wy - prev[2]) / (obj.t[j] - prev[0])
                spd = float(np.hypot(vxw, vyw))
                hd = float((np.degrees(np.arctan2(vyw, vxw) - th[i]) + 180) % 360 - 180)
            prev = (obj.t[j], wx, wy)
            print(f"{obj.t[j]:.2f}, {g['dx']:+.2f}, {g['dy']:+.2f}, {g['width']:.2f}, {g['length']:.2f}, "
                  f"{g['yawAngle']:+.2f} | c=({cx:.2f},{cy:.2f}) | lat={lat:+.2f} arc={arc:.2f} spd={spd:.2f} hd={hd:+.1f}")


if __name__ == "__main__":
    main()
