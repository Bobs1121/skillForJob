#!/usr/bin/env python
"""Find channels in an MF4 file by regex and optionally print basic statistics.

Typical first step on an unknown recording / new project:
  python mf4_find_channels.py FILE.MF4 -r "yaw|speed" -x "Obj\\d|CRC" --stats
"""
import argparse
import re

import numpy as np

from mf4_common import get_signal, open_mdf


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("-r", "--regex", required=True, help="case-insensitive include regex")
    ap.add_argument("-x", "--exclude", help="case-insensitive exclude regex")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--stats", action="store_true", help="read each hit: n, time range, min/max or enum values")
    a = ap.parse_args()

    m = open_mdf(a.file)
    inc = re.compile(a.regex, re.I)
    exc = re.compile(a.exclude, re.I) if a.exclude else None
    hits = [n for n in sorted(m.channels_db) if inc.search(n) and not (exc and exc.search(n))]
    print(f"{len(hits)} match(es) of {len(m.channels_db)} channels (showing {min(len(hits), a.limit)})")
    for n in hits[: a.limit]:
        occ = m.channels_db[n]
        line = f"{n}  gi={[tuple(o) for o in occ[:3]]}{' ...' if len(occ) > 3 else ''}"
        if a.stats:
            sig = get_signal(m, n, decode=False)
            t, v = sig[0], sig[1]
            if len(t) == 0:
                line += "\n    (no samples)"
            elif v.dtype.kind in "fiu":
                line += f"\n    n={len(t)} t=[{t[0]:.2f},{t[-1]:.2f}] min={np.nanmin(v):.4g} max={np.nanmax(v):.4g}"
            else:
                u, c = np.unique(v, return_counts=True)
                u = [x.decode(errors="ignore") if isinstance(x, bytes) else str(x) for x in u]
                line += f"\n    n={len(t)} t=[{t[0]:.2f},{t[-1]:.2f}] values={list(zip(u, c.tolist()))[:12]}"
        print(line)


if __name__ == "__main__":
    main()
