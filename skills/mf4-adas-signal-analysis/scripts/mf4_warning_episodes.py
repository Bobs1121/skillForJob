#!/usr/bin/env python
"""List warning episodes (start/end/duration) with the ego state at the time.

  python mf4_warning_episodes.py DATA_DIR_OR_FILES... --side left [--source hmi|can]
         [--on-values 1,2] [--merge-gap 0.3] [--min-dur 0.0] [--json out.json]

Ego columns: v [m/s], kappa [1/m, + = left], R [m] (= 1/|kappa|); kappa source is a channel if
present, otherwise yaw_rate / max(v, 2 m/s).
"""
import argparse
import json

import numpy as np

from mf4_common import Ego, expand_inputs, find_episodes, load_profile, open_mdf, radius


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--profile", default="byd_bsd")
    ap.add_argument("--side", choices=["left", "right"], default="left")
    ap.add_argument("--source", choices=["hmi", "can"], default="hmi")
    ap.add_argument("--on-values", help="comma list of values that count as 'warning on' (numeric channels)")
    ap.add_argument("--merge-gap", type=float, default=0.3)
    ap.add_argument("--min-dur", type=float, default=0.0)
    ap.add_argument("--json")
    a = ap.parse_args()

    prof = load_profile(a.profile)
    on_values = [int(x) for x in a.on_values.split(",")] if a.on_values else None
    result = []
    for f in expand_inputs(a.inputs):
        m = open_mdf(f)
        eps, name = find_episodes(m, prof, a.side, a.source, on_values, a.merge_gap, a.min_dur)
        ego = Ego(m, prof)
        print(f"\n== {f.name}  duration={ego.duration:.0f}s  warning={name.split('.')[-1]}  kappa={ego.kappa_origin.split('.')[-1]}")
        print(f"   {len(eps)} episode(s)")
        for i, (t0, t1) in enumerate(eps):
            tm = np.linspace(t0, t1, max(2, int((t1 - t0) / 0.05)))
            k = ego.kappa_at(tm)
            v = ego.speed_at(tm)
            row = dict(file=str(f), index=i, t0=t0, t1=t1, dur=t1 - t0, v_mean=float(v.mean()),
                       kappa_start=float(ego.kappa_at(t0)), kappa_mean=float(k.mean()),
                       R_mean=float(radius(k.mean())))
            result.append(row)
            print(f"   #{i:<2d} {t0:8.2f}-{t1:8.2f}s ({t1 - t0:5.2f}s) v={row['v_mean']:5.1f}m/s "
                  f"kappa0={row['kappa_start']:+.4f} kappa_mean={row['kappa_mean']:+.4f} R={row['R_mean']:6.1f}m")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1)
        print(f"\nwrote {a.json}")


if __name__ == "__main__":
    main()
