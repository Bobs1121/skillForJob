"""Shared helpers for MF4 (ASAM MDF4) ADAS signal analysis.

All signal names, scales and channel patterns come from a JSON profile
(see ../profiles/*.json), so the scripts are not tied to one project.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np

try:
    from asammdf import MDF
except ImportError:  # pragma: no cover
    sys.exit("asammdf is required: pip install asammdf numpy")

SKILL_DIR = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# profile / input handling
# --------------------------------------------------------------------------
def load_profile(name_or_path: str) -> dict:
    p = Path(name_or_path)
    if not p.exists():
        p = SKILL_DIR / "profiles" / (name_or_path if name_or_path.endswith(".json") else name_or_path + ".json")
    if not p.exists():
        sys.exit(f"profile not found: {name_or_path}")
    return json.loads(p.read_text(encoding="utf-8"))


def expand_inputs(items) -> list[Path]:
    """Files, directories (recursive *.mf4) or glob patterns -> sorted file list."""
    out: list[Path] = []
    for it in items:
        p = Path(it)
        if p.is_dir():
            out += [f for f in p.rglob("*") if f.suffix.lower() == ".mf4"]
        elif p.exists():
            out.append(p)
        else:
            out += list(Path(".").glob(it)) if not p.is_absolute() else list(p.parent.glob(p.name))
    return sorted(set(out))


def open_mdf(path) -> MDF:
    return MDF(str(path), memory="minimum")


# --------------------------------------------------------------------------
# signal access
# --------------------------------------------------------------------------
def find_channel(m: MDF, spec):
    """Resolve a spec to (channel_name, group, index) or None.

    spec: "name" | {"name":..., "gi":[group,index]} | {"regex":...}
    Order: explicit gi -> exact name (first occurrence) -> regex (first match).
    """
    if isinstance(spec, str):
        spec = {"name": spec}
    name = spec.get("name")
    if name and name in m.channels_db:
        occ = m.channels_db[name]
        gi = spec.get("gi")
        if gi and tuple(gi) in [tuple(o) for o in occ]:
            return name, gi[0], gi[1]
        return name, occ[0][0], occ[0][1]
    rx = spec.get("regex")
    if rx:
        r = re.compile(rx)
        for n, occ in m.channels_db.items():
            if r.search(n):
                return n, occ[0][0], occ[0][1]
    return None


def _to_text(v: np.ndarray) -> np.ndarray:
    if v.dtype.kind == "S":
        return np.array([x.decode(errors="ignore") for x in v])
    return v


def get_signal(m: MDF, spec, decode=True):
    """Return (t, v, channel_name) or None. Enum/text channels are decoded to str."""
    hit = find_channel(m, spec)
    if hit is None:
        return None
    name, g, i = hit
    s = m.get(name, group=g, index=i)
    t = np.asarray(s.timestamps, dtype=float)
    v = np.asarray(s.samples)
    return t, (_to_text(v) if decode else v), name


def align_nearest(t_src, v_src, t_dst):
    """Sample v_src (at t_src) at t_dst using the nearest earlier/equal sample."""
    j = np.clip(np.searchsorted(t_src, t_dst, side="right") - 1, 0, len(t_src) - 1)
    return np.asarray(v_src)[j]


# --------------------------------------------------------------------------
# ego state
# --------------------------------------------------------------------------
class Ego:
    """Ego speed [m/s], yaw rate [rad/s] and curvature kappa [1/m, +left]."""

    def __init__(self, m: MDF, profile: dict, kappa_source: str = "auto", v_min: float = 2.0):
        cfg = profile["ego"]
        sp = get_signal(m, cfg["speed"], decode=False)
        yw = get_signal(m, cfg["yaw"], decode=False)
        if sp is None or yw is None:
            sys.exit("ego speed/yaw channel not found - check the profile (use mf4_find_channels.py)")
        self.ts, v, self.speed_name = sp[0], np.asarray(sp[1], float) * cfg["speed"].get("scale", 1.0), sp[2]
        self.ty, y, self.yaw_name = yw[0], np.asarray(yw[1], float) * cfg["yaw"].get("scale", 1.0), yw[2]
        self.v, self.yaw = v, y
        self.v_min = v_min
        self.tk = self.k = None
        self.kappa_name = None
        if kappa_source in ("auto", "channel") and "kappa" in cfg:
            kk = get_signal(m, cfg["kappa"], decode=False)
            if kk is not None:
                raw = np.asarray(kk[1])
                scale = cfg["kappa"].get("raw_scale", 1.0) if raw.dtype.kind in "iu" else 1.0
                self.tk, self.k, self.kappa_name = kk[0], raw.astype(float) * scale, kk[2]
        if kappa_source == "channel" and self.k is None:
            sys.exit("kappa channel requested but not found")

    @property
    def duration(self) -> float:
        return float(self.ts[-1] - self.ts[0])

    def speed_at(self, t):
        return np.interp(t, self.ts, self.v)

    def yaw_at(self, t):
        return np.interp(t, self.ty, self.yaw)

    def kappa_at(self, t):
        """Curvature [1/m]; channel value if present, else yaw_rate / max(v, v_min)."""
        if self.k is not None:
            return np.interp(t, self.tk, self.k)
        return self.yaw_at(t) / np.maximum(self.speed_at(t), self.v_min)

    @property
    def kappa_origin(self) -> str:
        return self.kappa_name if self.k is not None else "yaw/v (fallback)"


def kappa_inner(kappa, side: str):
    """Curvature signed so that 'positive' means the evaluated side is the curve's inner side."""
    return -kappa if side == "right" else kappa


def radius(kappa, cap=9999.0):
    k = np.abs(kappa)
    return np.where(k > 1.0 / cap, 1.0 / np.maximum(k, 1e-12), cap)


def interp_clamp(x, x0, y0, x1, y1):
    """Linear interpolation with clamping to [y0, y1] range (x0 != x1)."""
    return np.interp(x, [x0, x1], [y0, y1])


# --------------------------------------------------------------------------
# warning episodes
# --------------------------------------------------------------------------
def on_mask(v: np.ndarray, rule: dict) -> np.ndarray:
    """rule: {"eq":[..]} | {"min": x} | {"off_prefix":["no","off",...]} (text channels)."""
    if "eq" in rule:
        vals = set(rule["eq"])
        return np.array([(x in vals) for x in (v.tolist() if v.dtype.kind in "iuf" else v)])
    if "min" in rule:
        return np.asarray(v, float) >= rule["min"]
    if "off_prefix" in rule:
        pre = tuple(p.lower() for p in rule["off_prefix"])
        return np.array([not str(x).strip().lower().startswith(pre) for x in v])
    raise ValueError(f"bad on-rule {rule}")


def runs(mask: np.ndarray):
    """Yield (i0, i1) inclusive index runs where mask is True."""
    if mask.size == 0:
        return
    d = np.diff(mask.astype(np.int8), prepend=0, append=0)
    for a, b in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1) - 1):
        yield int(a), int(b)


def find_episodes(m: MDF, profile: dict, side: str, source: str = "hmi",
                  on_values=None, merge_gap: float = 0.3, min_dur: float = 0.0):
    """Warning episodes [(t0, t1, max_value)] for a side from the profile's warning channel."""
    cfg = profile["warnings"][side][source]
    sig = get_signal(m, cfg["signal"])
    if sig is None:
        sys.exit(f"warning channel not found for {side}/{source}: {cfg['signal']}")
    t, v, name = sig
    rule = {"eq": on_values} if on_values else cfg["on"]
    mk = on_mask(v, rule)
    eps = []
    for a, b in runs(mk):
        t0, t1 = float(t[a]), float(t[b])
        if eps and t0 - eps[-1][1] <= merge_gap:
            eps[-1][1] = t1
        else:
            eps.append([t0, t1])
    return [(a, b) for a, b in eps if (b - a) >= min_dur], name


# --------------------------------------------------------------------------
# relevant objects (BSD/LCA behaviour state, up to N slots)
# --------------------------------------------------------------------------
class Objects:
    """Per-cycle arrays [n_cycles, n_slots] for the requested fields."""

    def __init__(self, m: MDF, profile: dict, slots=3, fields=None):
        cfg = profile["objects"]
        self.fields = fields or cfg["fields"]
        pre = re.compile(cfg["prefix_regex"])
        slot_rx = re.compile(cfg["slot_regex"])
        used_rx = re.compile(cfg["used_regex"])
        names = [n for n in m.channels_db if pre.search(n)]
        index, used_name = {}, None
        for n in names:
            mm = slot_rx.search(n)
            if mm:
                index[(int(mm.group(1)), mm.group(2))] = n
            elif used_rx.search(n):
                used_name = n
        if not index:
            sys.exit("no relevantObject channels found - check profile objects.prefix_regex/slot_regex")
        self.slots = list(range(slots))
        self.t = None
        self.data = {}
        for f in self.fields:
            cols = []
            for k in self.slots:
                n = index.get((k, f))
                if n is None:
                    cols.append(None)
                    continue
                t, v, _ = get_signal(m, n, decode=False)
                if self.t is None:
                    self.t = t
                v = np.asarray(v, float)
                cols.append(v if len(t) == len(self.t) else align_nearest(t, v, self.t))
            self.data[f] = np.stack([c if c is not None else np.full(len(self.t), np.nan) for c in cols], axis=1)
        self.used = None
        if used_name:
            tu, vu, _ = get_signal(m, used_name, decode=False)
            self.used = align_nearest(tu, np.asarray(vu, float), self.t).astype(int)

    @property
    def dt(self) -> float:
        return float(np.median(np.diff(self.t))) if len(self.t) > 1 else 0.0

    def window(self, t0, t1):
        return np.flatnonzero((self.t >= t0) & (self.t <= t1))


def fmt_hms(t: float) -> str:
    return f"{t:8.2f}s"
