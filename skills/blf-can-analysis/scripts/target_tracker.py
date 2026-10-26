#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Target Tracker for Radar CAN Data
Supports both Private CAN (SGU Objects: 0x314-0x334, 0x354-0x374, 0x414-0x434, 0x454-0x474)
and Public CAN (Multiplexed Objects: 0x291, 0x36F, 0x295, 0x374).
"""

import can
import cantools
import os
import sys
from collections import defaultdict, Counter


def parse_private_sgu_objects(blf_path, dbc_rrl_path=None, dbc_rfl_path=None, min_prob=0):
    """
    Parse SGU Objects from Private CAN channels (RRL, RRR, RFL, RFR).
    Returns summary statistics and active target tracks.
    """
    db_rrl = cantools.database.load_file(dbc_rrl_path, strict=False) if dbc_rrl_path and os.path.exists(dbc_rrl_path) else None
    db_rfl = cantools.database.load_file(dbc_rfl_path, strict=False) if dbc_rfl_path and os.path.exists(dbc_rfl_path) else None

    reader = can.BLFReader(blf_path)
    
    radar_headers = defaultdict(lambda: {'zero_frames': 0, 'active_frames': 0, 'max_objects': 0})
    tracks = defaultdict(lambda: defaultdict(list))  # [radar][obj_id] -> [(ts, px, py, vx, vy, prob, meas)]
    
    for msg in reader:
        t = msg.timestamp
        ch = msg.channel
        aid = msg.arbitration_id
        
        db = db_rrl if ch == 2 else (db_rfl if ch == 3 else None)
        if not db or aid not in db._frame_id_to_message:
            continue
            
        mdef = db._frame_id_to_message[aid]
        mname = mdef.name
        
        # Header message
        if 'header' in mname.lower() or 'hdr' in mname.lower():
            try:
                dec = mdef.decode(msg.data)
                prefix = mname[:3]
                num_obj = dec.get(f'{prefix}_ObjHdr_NumValidObjects', 0)
                if num_obj > 0:
                    radar_headers[prefix]['active_frames'] += 1
                    radar_headers[prefix]['max_objects'] = max(radar_headers[prefix]['max_objects'], num_obj)
                else:
                    radar_headers[prefix]['zero_frames'] += 1
            except Exception:
                pass
                
        # SGU Object message
        elif '_SGU' in mname:
            try:
                dec = mdef.decode(msg.data)
                prefix = mname[:3]
                obj_slot = mname[7:]
                
                meas = str(dec.get(f'{prefix}_Obj{obj_slot}_MeasurementStatus', ''))
                prob = dec.get(f'{prefix}_Obj{obj_slot}_ExistProb', 0)
                
                if 'Invalid' not in meas and (prob is None or prob >= min_prob):
                    obj_id = dec.get(f'{prefix}_Obj{obj_slot}_ObjId', int(obj_slot))
                    px = dec.get(f'{prefix}_Obj{obj_slot}_Px', 0.0)
                    py = dec.get(f'{prefix}_Obj{obj_slot}_Py', 0.0)
                    vx = dec.get(f'{prefix}_Obj{obj_slot}_Vx', 0.0)
                    vy = dec.get(f'{prefix}_Obj{obj_slot}_Vy', 0.0)
                    
                    tracks[prefix][obj_id].append({
                        'ts': t, 'px': px, 'py': py, 'vx': vx, 'vy': vy,
                        'prob': prob, 'meas': meas
                    })
            except Exception:
                pass
                
    return radar_headers, tracks


def parse_public_mux_targets(blf_path, dbc_path):
    """
    Parse multiplexed targets from Public CAN matrix (0x291 / 0x36F / 0x295 / 0x374).
    """
    if not os.path.exists(dbc_path):
        return {}
        
    db = cantools.database.load_file(dbc_path, strict=False)
    reader = can.BLFReader(blf_path)
    
    mux_targets = defaultdict(lambda: defaultdict(list))
    
    for msg in reader:
        t = msg.timestamp
        aid = msg.arbitration_id
        
        if aid in [0x291, 0x36F, 0x295, 0x374] and aid in db._frame_id_to_message:
            try:
                dec = db.decode_message(aid, msg.data, decode_choices=False)
                # Check for child slot
                for slot in (1, 2, 3, 4):
                    type_sig = f'Target_Type_{aid:03X}s{slot}_S' if f'Target_Type_{aid:03X}s{slot}_S' in dec else f'Target_State_B1_{aid:03X}s{slot}_S'
                    if type_sig in dec:
                        dx = dec.get(f'Lock_Target_Ordinate_{aid:03X}s{slot}_S', 0.0)
                        dy = dec.get(f'Lock_Target_Abscissa_{aid:03X}s{slot}_S', 0.0)
                        vx = dec.get(f'Goal_Length_Absolute_Spd_{aid:03X}s{slot}_S', 0.0)
                        vy = dec.get(f'Goal_Late_Absolute_Spd_{aid:03X}s{slot}_S', 0.0)
                        warn = dec.get(f'Target_Warning_{aid:03X}s{slot}_S', 0)
                        
                        mux_targets[f'0x{aid:03X}'][slot].append({
                            'ts': t, 'dx': dx, 'dy': dy, 'vx': vx, 'vy': vy, 'warn': warn
                        })
            except Exception:
                pass
                
    return mux_targets


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python target_tracker.py <file.blf> [--dbc-rrl <dbc>] [--dbc-rfl <dbc>]")
        sys.exit(1)

    blf = sys.argv[1]
    opts = dict(zip(sys.argv[2::2], sys.argv[3::2]))
    headers, tracks = parse_private_sgu_objects(blf, opts.get('--dbc-rrl'), opts.get('--dbc-rfl'))
    
    print("=== Radar SGU Header Summary ===")
    for prefix, info in headers.items():
        print(f"  {prefix}: Active Frames = {info['active_frames']}, Zero Frames = {info['zero_frames']}, Max Objects = {info['max_objects']}")
        
    print("\n=== Tracked SGU Objects ===")
    for prefix, id_tracks in tracks.items():
        print(f"\n--- Radar: {prefix} ({len(id_tracks)} unique track IDs) ---")
        for obj_id, pts in sorted(id_tracks.items()):
            dur = pts[-1]['ts'] - pts[0]['ts']
            avg_px = sum(p['px'] for p in pts) / len(pts)
            avg_py = sum(p['py'] for p in pts) / len(pts)
            print(f"  ID {obj_id:3d}: {len(pts):4d} pts ({dur:5.2f}s) | Avg Px={avg_px:6.2f}m, Py={avg_py:6.2f}m | First meas={pts[0]['meas']}")
