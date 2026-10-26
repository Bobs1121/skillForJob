#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BLF CAN Data Analysis Tool
Comprehensive analysis for BYD ADAS Corner Radar & Brake Controller logs.
Supports both Public CAN (StandardCANFD) and Private CAN (MPC4 Corner Radars).

Usage:
  python blf_analyze.py explore <blf_file>
  python blf_analyze.py status <blf_file> [--dbc <dbc_file>...]
  python blf_analyze.py warnings <blf_file> [--dbc <dbc_file>...]
  python blf_analyze.py targets <blf_file> [--dbc <dbc_file>...]
  python blf_analyze.py bsd <blf_file> --dbc <dbc_file>
  python blf_analyze.py rctb <blf_file> [--dbc <dbc_file>...]

DBC lookup when --dbc is not given: the BLF directory, its parent, and the directory in env BLF_DBC_DIR.
"""

import can
import cantools
import argparse
import os
import sys
import collections
from collections import defaultdict, Counter

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


def load_all_dbcs(dbc_paths=None, blf_dir='.'):
    """Load all provided or auto-detected DBCs into a unified message mapping."""
    dbcs = []
    if dbc_paths:
        for p in dbc_paths:
            if os.path.exists(p):
                try:
                    db = cantools.database.load_file(p, strict=False)
                    dbcs.append((os.path.basename(p), db))
                except Exception as e:
                    print(f"  Warning: failed to load {p}: {e}")
    else:
        # Search in blf_dir and parent dirs
        search_dirs = [blf_dir, os.path.dirname(blf_dir), os.environ.get('BLF_DBC_DIR', '')]
        for sdir in search_dirs:
            if os.path.exists(sdir):
                for f in os.listdir(sdir):
                    if f.endswith('.dbc'):
                        try:
                            fpath = os.path.join(sdir, f)
                            db = cantools.database.load_file(fpath, strict=False)
                            dbcs.append((f, db))
                        except Exception:
                            pass
    return dbcs


# ============================================================
# COMMAND: explore
# ============================================================
def cmd_explore(args):
    blf_path = args.blf_file
    if not os.path.exists(blf_path):
        print(f"ERROR: BLF file not found: {blf_path}")
        return

    print(f"\n{'='*75}")
    print(f"  BLF EXPLORE: {os.path.basename(blf_path)}")
    print(f"{'='*75}")

    reader = can.BLFReader(blf_path)
    ch_ids = defaultdict(lambda: defaultdict(int))
    first_ts = last_ts = None
    total_msgs = 0

    for msg in reader:
        total_msgs += 1
        if first_ts is None:
            first_ts = msg.timestamp
        last_ts = msg.timestamp
        ch_ids[msg.channel][(msg.arbitration_id, msg.dlc, msg.is_fd)] += 1

    dur = (last_ts - first_ts) if first_ts else 0
    print(f"  Total Messages : {total_msgs:,}")
    print(f"  Duration       : {dur:.2f} s (from {first_ts:.3f} to {last_ts:.3f})")
    print(f"  Active Channels: {list(sorted(ch_ids.keys()))}")

    for ch in sorted(ch_ids.keys()):
        items = ch_ids[ch]
        total_ch_msgs = sum(items.values())
        print(f"\n--- Channel {ch} ({len(items)} unique IDs, {total_ch_msgs:,} msgs) ---")
        sorted_items = sorted(items.items(), key=lambda x: x[0][0])
        for (aid, dlc, is_fd), cnt in sorted_items:
            freq = cnt / dur if dur > 0 else 0
            fd_str = "CAN-FD" if is_fd else "CAN   "
            print(f"  0x{aid:03X} ({aid:5d}) | DLC={dlc:2d} | {fd_str} | {cnt:>7,} msgs ({freq:5.1f} Hz)")


# ============================================================
# COMMAND: status
# ============================================================
def cmd_status(args):
    blf_path = args.blf_file
    dbcs = load_all_dbcs(args.dbc, os.path.dirname(blf_path))
    
    print(f"\n{'='*75}")
    print(f"  RADAR HARDWARE & STATE MACHINE AUDIT: {os.path.basename(blf_path)}")
    print(f"{'='*75}")

    reader = can.BLFReader(blf_path)
    status_summary = defaultdict(lambda: defaultdict(int))
    timeline_changes = defaultdict(list)

    for msg in reader:
        t = msg.timestamp
        aid = msg.arbitration_id
        
        # Try decoding with all DBCs
        for dbc_name, db in dbcs:
            if aid in db._frame_id_to_message:
                mdef = db._frame_id_to_message[aid]
                if any(k in mdef.name for k in ['Status', 'RadarStatus', '20msPDU', '50msPDU', '0x410', '0x450', '0x310', '0x350', '0x418', '0x453']):
                    try:
                        # Pad data if DLC < expected
                        data = msg.data
                        if len(data) < mdef.length:
                            data = data + b'\x00' * (mdef.length - len(data))
                        dec = mdef.decode(data)
                        
                        for sname, sval in dec.items():
                            if any(k in sname for k in ['BLIND', 'Failure', 'Modulation', 'SGUFail', 'System_status', 'SDAState', 'SysSts', 'SysSta', 'SelSts', 'Sys_Status']):
                                status_summary[f'{mdef.name} (0x{aid:03X})'][f'{sname} = {sval}'] += 1
                                last = timeline_changes[sname]
                                if not last or last[-1][1] != sval:
                                    timeline_changes[sname].append((t, sval))
                    except Exception:
                        pass

    if not status_summary:
        print("  No radar status signals found with current DBCs.")
        return

    print("\n>>> Signal Value Distributions:")
    for mname, sig_counts in sorted(status_summary.items()):
        print(f"\n  [Message: {mname}]")
        for sval, cnt in sorted(sig_counts.items()):
            print(f"    - {sval:<50}: {cnt} frames")

    print("\n>>> State Transitions & Anomalies:")
    anomaly_found = False
    for sname, changes in sorted(timeline_changes.items()):
        if len(changes) > 1:
            anomaly_found = True
            print(f"  * {sname} changed {len(changes)} times:")
            for t, val in changes:
                print(f"      t={t:12.3f}s -> {val}")
        else:
            val_str = str(changes[0][1])
            is_bad = any(err in val_str.lower() for err in ['blind', 'fail', 'error', 'high', 'low', 'fault']) and not any(ok in val_str.lower() for ok in ['no ', 'not'])
            if is_bad:
                anomaly_found = True
                print(f"  ! ANOMALY in {sname}: Constant BAD state -> {val_str}")

    if not anomaly_found:
        print("  [OK] All radar nodes & state machines operated stably with NO faults/blindness.")


# ============================================================
# COMMAND: warnings
# ============================================================
def cmd_warnings(args):
    blf_path = args.blf_file
    dbcs = load_all_dbcs(args.dbc, os.path.dirname(blf_path))

    print(f"\n{'='*75}")
    print(f"  FUNCTION WARNINGS & BRAKING AUDIT: {os.path.basename(blf_path)}")
    print(f"{'='*75}")

    reader = can.BLFReader(blf_path)
    warn_summary = defaultdict(lambda: defaultdict(int))
    active_warn_episodes = defaultdict(list)

    for msg in reader:
        t = msg.timestamp
        aid = msg.arbitration_id
        
        for dbc_name, db in dbcs:
            if aid in db._frame_id_to_message:
                mdef = db._frame_id_to_message[aid]
                if any(k in mdef.name for k in ['50msPDU', '20msPDU', '0x418', '0x453', '0x2CA', '0x32D', '0x32F']):
                    try:
                        data = msg.data
                        if len(data) < mdef.length:
                            data = data + b'\x00' * (mdef.length - len(data))
                        dec = mdef.decode(data)
                        
                        for sname, sval in dec.items():
                            if any(k in sname for k in ['Wrnng', 'Warning', 'Warn', 'Req', 'TrgtDcl', 'Braking_Req', 'DecCtrl']):
                                if 'Alive' in sname or 'CRC' in sname or 'SelReq' in sname:
                                    continue
                                warn_summary[f'{mdef.name} (0x{aid:03X})'][f'{sname} = {sval}'] += 1
                                
                                # Track active episodes
                                is_active = False
                                if isinstance(sval, (int, float)):
                                    if 'TrgtDcl' in sname or 'Dec' in sname:
                                        is_active = (abs(sval) > 0.05)
                                    else:
                                        is_active = (sval > 0)
                                elif isinstance(sval, str) and not any(off in sval.lower() for off in ['no', 'off', '0']):
                                    is_active = True
                                    
                                ep_list = active_warn_episodes[sname]
                                if is_active:
                                    if not ep_list or ep_list[-1][1] is not None:
                                        ep_list.append([t, None, sval])
                                else:
                                    if ep_list and ep_list[-1][1] is None:
                                        ep_list[-1][1] = t
                    except Exception:
                        pass

    print("\n>>> Warning & Brake Signal Distributions:")
    for mname, sig_counts in sorted(warn_summary.items()):
        print(f"\n  [Message: {mname}]")
        for sval, cnt in sorted(sig_counts.items()):
            print(f"    - {sval:<50}: {cnt} frames")

    print("\n>>> Warning Trigger Episodes:")
    triggers = 0
    for sname, eps in sorted(active_warn_episodes.items()):
        for ep in eps:
            st = ep[0]
            et = ep[1] if ep[1] is not None else st
            dur = et - st
            if dur > 0.05 or ep[1] is None:
                triggers += 1
                print(f"  * TRIGGER [{sname}]: t={st:12.3f}s ~ {et:12.3f}s (Dur={dur:5.2f}s) | Val={ep[2]}")

    if triggers == 0:
        print("  [OK] Clean recording: NO warning or braking trigger events detected.")


# ============================================================
# COMMAND: targets
# ============================================================
def cmd_targets(args):
    from target_tracker import parse_private_sgu_objects
    blf_path = args.blf_file
    print(f"\n{'='*75}")
    print(f"  RADAR SGU OBJECT TRACKING AUDIT: {os.path.basename(blf_path)}")
    print(f"{'='*75}")

    dbc_rrl = dbc_rfl = None
    for p in args.dbc or []:
        if 'RRL' in p or 'RCR' in p: dbc_rrl = p
        if 'RFL' in p or 'FCR' in p: dbc_rfl = p
    if not (dbc_rrl or dbc_rfl):
        print("ERROR: pass the private-CAN DBC(s) with --dbc (file name containing RRL/RCR and/or RFL/FCR).")
        return

    headers, tracks = parse_private_sgu_objects(blf_path, dbc_rrl, dbc_rfl)

    print("\n>>> Radar SGU Detection Rates:")
    for prefix in ['RFL', 'RFR', 'RRL', 'RRR']:
        info = headers[prefix]
        tot = info['active_frames'] + info['zero_frames']
        rate = (info['active_frames'] / tot * 100) if tot > 0 else 0
        print(f"  {prefix:<4}: Active={info['active_frames']:>4} frames ({rate:5.1f}%), Max Objects={info['max_objects']}")

    print("\n>>> Tracked Target Details:")
    for prefix, id_tracks in sorted(tracks.items()):
        print(f"\n  --- {prefix} Corner Radar Targets ({len(id_tracks)} unique track IDs) ---")
        for obj_id, pts in sorted(id_tracks.items()):
            dur = pts[-1]['ts'] - pts[0]['ts']
            avg_px = sum(p['px'] for p in pts) / len(pts)
            avg_py = sum(p['py'] for p in pts) / len(pts)
            avg_vx = sum(p['vx'] for p in pts) / len(pts)
            avg_vy = sum(p['vy'] for p in pts) / len(pts)
            print(f"    ID {obj_id:3d}: {len(pts):4d} pts ({dur:5.2f}s) | Pos=({avg_px:6.2f}m, {avg_py:6.2f}m) | Vel=({avg_vx:5.2f}m/s, {avg_vy:5.2f}m/s)")


# ============================================================
# Main CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description='BLF CAN Data Analysis Tool (SC6H / UKE / ADAS)',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('command', choices=['explore', 'status', 'warnings', 'targets', 'bsd', 'rctb'],
                        help='Command to execute')
    parser.add_argument('blf_file', help='Path to BLF file')
    parser.add_argument('--dbc', '-d', nargs='+', help='Path to DBC file(s)')

    args = parser.parse_args()

    if args.command == 'explore':
        cmd_explore(args)
    elif args.command == 'status':
        cmd_status(args)
    elif args.command == 'warnings':
        cmd_warnings(args)
    elif args.command == 'targets':
        cmd_targets(args)
    elif args.command == 'bsd':
        from bsd_episodes import analyze_bsd_episodes
        analyze_bsd_episodes(args.blf_file, args.dbc[0] if args.dbc else None)
    elif args.command == 'rctb':
        cmd_warnings(args)


if __name__ == '__main__':
    main()
