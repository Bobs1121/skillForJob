#!/usr/bin/env python
"""Dump the relevant objects per cycle inside a time window together with the ego state.

  python mf4_object_trace.py FILE --t0 266 --t1 268.5 [--slots 3] [--every 1]
  python mf4_object_trace.py FILE --episode 2 --side left --pad 0.5

Values are as logged (dx/dy = target front corner in ego coordinates; for the right side the
behaviour evaluates with dy inverted - check the sign before comparing against a line).
"""
import argparse

from mf4_common import Ego, Objects, find_episodes, load_profile, open_mdf, radius


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--profile", default="byd_bsd")
    ap.add_argument("--t0", type=float)
    ap.add_argument("--t1", type=float)
    ap.add_argument("--episode", type=int, help="take the window from warning episode N")
    ap.add_argument("--side", choices=["left", "right"], default="left")
    ap.add_argument("--source", choices=["hmi", "can"], default="hmi")
    ap.add_argument("--pad", type=float, default=0.5, help="seconds around the episode")
    ap.add_argument("--slots", type=int, default=3)
    ap.add_argument("--every", type=int, default=1, help="print every n-th cycle")
    a = ap.parse_args()

    prof = load_profile(a.profile)
    m = open_mdf(a.file)
    if a.episode is not None:
        eps, _ = find_episodes(m, prof, a.side, a.source)
        t0, t1 = eps[a.episode]
        t0, t1 = t0 - a.pad, t1 + a.pad
        print(f"episode {a.episode}: {t0 + a.pad:.2f}-{t1 - a.pad:.2f}s")
    elif a.t0 is not None and a.t1 is not None:
        t0, t1 = a.t0, a.t1
    else:
        ap.error("give --t0/--t1 or --episode")

    ego = Ego(m, prof)
    obj = Objects(m, prof, slots=a.slots)
    idx = obj.window(t0, t1)
    print(f"{len(idx)} cycles, dt={obj.dt * 1000:.0f} ms, kappa={ego.kappa_origin.split('.')[-1]}")
    for n, j in enumerate(idx):
        if n % a.every:
            continue
        t = obj.t[j]
        k = float(ego.kappa_at(t))
        used = int(obj.used[j]) if obj.used is not None else a.slots
        line = f"t={t:8.3f} v={float(ego.speed_at(t)):5.2f} k={k:+.4f} R={float(radius(k)):6.1f} used={used}"
        for s in range(min(used, a.slots)):
            d = {f: obj.data[f][j, s] for f in obj.fields}
            line += (f" | s{s} h={int(d['handle'])} dx={d['dx']:+.2f} dy={d['dy']:+.2f} vx={d['vx']:+.2f} "
                     f"vy={d['vy']:+.2f} w={d['width']:.2f} l={d['length']:.2f}")
        print(line)


if __name__ == "__main__":
    main()
