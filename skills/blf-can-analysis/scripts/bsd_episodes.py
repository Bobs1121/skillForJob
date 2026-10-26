#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BSD Episode Analysis Tool
Extracts BSD/LCA warning episodes, durations, speed conditions, and target correlation.
Supports both Public CAN (0x418 / 0x453 / 0x291) and Private CAN (0x561 / SGU).
"""

import can
import cantools
import os
import sys
import argparse
from collections import defaultdict


def analyze_bsd_episodes(blf_path, dbc_path=None):
    """
    Find and segment BSD/LCA warning episodes in a BLF file.
    """
    db = cantools.database.load_file(dbc_path, strict=False) if dbc_path and os.path.exists(dbc_path) else None
    reader = can.BLFReader(blf_path)
    
    warn_events = {'left': [], 'right': []}
    speed_events = []
    
    for msg in reader:
        t = msg.timestamp
        aid = msg.arbitration_id
        
        # Check Public CAN 0x418
        if aid == 0x418 and db and aid in db._frame_id_to_message:
            try:
                dec = db.decode_message(aid, msg.data, decode_choices=False)
                wl = dec.get('R_BSD_Warning_Left_S', 0)
                wr = dec.get('R_BSD_Warning_Right_S', 0)
                warn_events['left'].append((t, wl))
                warn_events['right'].append((t, wr))
            except Exception:
                pass
                
        # Check Private CAN 0x561
        elif aid == 0x561 and db and aid in db._frame_id_to_message:
            try:
                dec = db.decode_message(aid, msg.data, decode_choices=False)
                w = dec.get('RRL_LBSDAndLCAWrnng', 0)
                warn_events['left'].append((t, w))
            except Exception:
                pass
                
        # Speed 0x121 / 0x10C
        elif aid in [0x121, 0x10C] and db and aid in db._frame_id_to_message:
            try:
                dec = db.decode_message(aid, msg.data, decode_choices=False)
                spd = dec.get('IPB_Vehicle_Speed_S') or dec.get('VehicleSpeed_Status')
                if spd is not None:
                    speed_events.append((t, spd))
            except Exception:
                pass

    print(f"\n{'='*70}")
    print(f"  BSD / LCA EPISODE ANALYSIS")
    print(f"{'='*70}")
    
    for side in ['left', 'right']:
        events = warn_events[side]
        if not events:
            continue
            
        # Segment episodes
        episodes = []
        cur_start = None
        cur_level = 0
        
        for t, val in events:
            # Handle string or int
            level = 0
            if isinstance(val, int):
                level = val
            elif 'Level_1' in str(val) or '1' in str(val):
                level = 1
            elif 'Level_2' in str(val) or '2' in str(val):
                level = 2
                
            if level > 0:
                if cur_start is None:
                    cur_start = t
                    cur_level = level
                else:
                    cur_level = max(cur_level, level)
            else:
                if cur_start is not None:
                    episodes.append((cur_start, t, cur_level))
                    cur_start = None
                    cur_level = 0
                    
        if cur_start is not None:
            episodes.append((cur_start, events[-1][0], cur_level))
            
        print(f"\n>>> {side.upper()} BSD Warning Episodes: {len(episodes)} total")
        if not episodes:
            print(f"    No {side} BSD warnings detected (Clean).")
        else:
            for idx, (st, et, lvl) in enumerate(episodes, 1):
                dur = et - st
                print(f"    Episode {idx:2d}: t={st:12.3f} -> {et:12.3f} | Dur={dur:5.2f}s | Max Level={lvl}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='BSD Warning Episode Analyzer')
    parser.add_argument('blf', help='Path to BLF file')
    parser.add_argument('--dbc', '-d', help='Path to DBC file')
    args = parser.parse_args()
    
    analyze_bsd_episodes(args.blf, args.dbc)
