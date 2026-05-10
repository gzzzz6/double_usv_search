# -*- coding: utf-8 -*-
"""
Phase 0 audit: read-only scan of paper_simple_ring_mainline_20260505.
Checks config consistency against expected mainline values.
Reports anomalies only, does NOT modify anything.
"""
import json, os, glob, hashlib
from datetime import datetime

RESULTS_DIR = r'F:\pythonprojects\baseline_GP\results\paper_simple_ring_mainline_20260505'
OUT_DIR = r'F:\pythonprojects\baseline_GP\results\holoocean_bridge_v1\phase0_freeze'

EXPECTED = {
    'viewpoint_generation_mode': 'simple_ring_v1',
    'path_safety_mode': 'soft_clearance_astar_v1',
    'team_path_avoidance_mode': 'reservation_v1',
    'anomaly_tail_quantile': 0.90,
    'anomaly_weight_lambda': 1.25,
    'assignment_mode': 'coordinated',
}

EXPECTED_SINGLE_MAP = {'map_height_cells': 40, 'map_width_cells': 60}
EXPECTED_TWO_MAP = {'map_height_cells': 60, 'map_width_cells': 80}
EXPECTED_TWO_STARTS = ((25, 2), (35, 2))

RUNTIME_DEFAULTS = {
    'anomaly_weight_lambda': 1.0,
}

# ============================================================
# Collect all JSON files
# ============================================================
json_files = []
for root, dirs, files in os.walk(RESULTS_DIR):
    for f in files:
        if f.endswith('.json'):
            json_files.append(os.path.join(root, f))

print('Found %d JSON files' % len(json_files))

# ============================================================
# Scan config_snapshot.json files
# ============================================================
configs = []
for fp in json_files:
    if os.path.basename(fp) == 'config_snapshot.json':
        with open(fp, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        # Determine single vs two USV from policy_name
        policy = data.get('policy_name', '')
        is_two = '2usv' in policy.lower()
        configs.append({
            'file': fp,
            'is_two_usv': is_two,
            'policy_name': policy,
            'data': data,
        })

print('Found %d config_snapshot.json files' % len(configs))

# ============================================================
# Build audit records
# ============================================================
FIELDS = [
    'policy_name', 'assignment_mode', 'map_kind',
    'map_height_cells', 'map_width_cells',
    'target_motion_mode',
    'viewpoint_generation_mode', 'path_safety_mode',
    'team_path_avoidance_mode',
    'anomaly_tail_quantile', 'anomaly_weight_lambda',
]

records = []
anomalies = []

for cfg in configs:
    rec = {'file': cfg['file'], 'is_two_usv': cfg['is_two_usv']}
    data = cfg['data']
    for field in FIELDS:
        if field in data:
            rec[field] = data[field]
        else:
            rec[field] = None
            anomalies.append('MISSING_FIELD: %s in %s' % (field, os.path.basename(cfg['file'])))
    records.append(rec)

# Also check start positions for two-USV
for cfg in configs:
    if cfg['is_two_usv']:
        data = cfg['data']
        starts = data.get('start_positions', None)
        if starts is None:
            anomalies.append('MISSING_FIELD: start_positions in %s' % os.path.basename(cfg['file']))
        else:
            actual = tuple(tuple(s) for s in starts)
            if actual != EXPECTED_TWO_STARTS:
                anomalies.append('START_MISMATCH: expected %s, got %s in %s' % (
                    EXPECTED_TWO_STARTS, actual, os.path.basename(cfg['file'])))

# ============================================================
# Check consistency
# ============================================================
for rec in records:
    fname = os.path.basename(rec['file'])

    # Check viewpoint_generation_mode
    vgm = rec.get('viewpoint_generation_mode')
    if vgm is not None and vgm != EXPECTED['viewpoint_generation_mode']:
        anomalies.append('VIEWPOINT_MISMATCH: expected %s, got %s in %s' % (
            EXPECTED['viewpoint_generation_mode'], vgm, fname))

    # Check path_safety_mode
    psm = rec.get('path_safety_mode')
    if psm is not None and psm != EXPECTED['path_safety_mode']:
        anomalies.append('PATH_SAFETY_MISMATCH: expected %s, got %s in %s' % (
            EXPECTED['path_safety_mode'], psm, fname))

    # Check team_path_avoidance_mode (only for two-USV)
    if rec['is_two_usv']:
        tpa = rec.get('team_path_avoidance_mode')
        if tpa is not None and tpa != EXPECTED['team_path_avoidance_mode']:
            anomalies.append('TEAM_AVOID_MISMATCH: expected %s, got %s in %s' % (
                EXPECTED['team_path_avoidance_mode'], tpa, fname))

    # Check assignment_mode
    am = rec.get('assignment_mode')
    if rec['is_two_usv'] and am is not None and am != EXPECTED['assignment_mode']:
        anomalies.append('ASSIGNMENT_MISMATCH: expected %s, got %s in %s' % (
            EXPECTED['assignment_mode'], am, fname))

    # Check anomaly_tail_quantile
    atq = rec.get('anomaly_tail_quantile')
    if atq is not None:
        try:
            if abs(float(atq) - EXPECTED['anomaly_tail_quantile']) > 0.001:
                anomalies.append('ANOMALY_TAIL_QUANTILE_MISMATCH: expected %.2f, got %s in %s' % (
                    EXPECTED['anomaly_tail_quantile'], atq, fname))
        except (TypeError, ValueError):
            pass

    # Check anomaly_weight_lambda
    awl = rec.get('anomaly_weight_lambda')
    if awl is not None:
        try:
            if abs(float(awl) - EXPECTED['anomaly_weight_lambda']) > 0.001:
                anomalies.append('ANOMALY_WEIGHT_LAMBDA_MISMATCH: expected %.2f, got %s in %s. NOTE: runtime default is %.1f' % (
                    EXPECTED['anomaly_weight_lambda'], awl, fname, RUNTIME_DEFAULTS['anomaly_weight_lambda']))
        except (TypeError, ValueError):
            pass

    # Check map dimensions
    if rec['is_two_usv']:
        exp_map = EXPECTED_TWO_MAP
    else:
        exp_map = EXPECTED_SINGLE_MAP
    for dim in ('map_height_cells', 'map_width_cells'):
        val = rec.get(dim)
        if val is not None:
            try:
                if int(val) != exp_map[dim]:
                    anomalies.append('MAP_DIM_MISMATCH: %s expected %d, got %s in %s' % (
                        dim, exp_map[dim], val, fname))
            except (TypeError, ValueError):
                pass

# ============================================================
# Check episode_results.json count
# ============================================================
episode_files = [f for f in json_files if os.path.basename(f) == 'episode_results.json']
print('Found %d episode_results.json files' % len(episode_files))

# Check paper_tables existence
tables_dir = os.path.join(RESULTS_DIR, 'paper_tables')
tables_exist = os.path.isdir(tables_dir)
table_files = []
if tables_exist:
    table_files = sorted(os.listdir(tables_dir))
print('Paper tables dir exists: %s, files: %d' % (tables_exist, len(table_files)))

# ============================================================
# Runtime default vs mainline experiment check
# ============================================================
# Check if anomaly_weight_lambda in config is different from runtime default
for rec in records:
    awl = rec.get('anomaly_weight_lambda')
    if awl is not None:
        try:
            if abs(float(awl) - RUNTIME_DEFAULTS['anomaly_weight_lambda']) > 0.001:
                anomalies.append('RUNTIME_DEFAULT_DIFF: anomaly_weight_lambda in experiment = %s, but function default = %.1f. This is expected for mainline.' % (
                    awl, RUNTIME_DEFAULTS['anomaly_weight_lambda']))
                break  # Report once
        except (TypeError, ValueError):
            pass

# ============================================================
# Output JSON
# ============================================================
audit_data = {
    'audit_time': datetime.now().isoformat(),
    'results_dir': RESULTS_DIR,
    'expected_config': EXPECTED,
    'total_config_snapshots': len(configs),
    'total_episode_results': len(episode_files),
    'paper_tables_exists': tables_exist,
    'paper_tables_file_count': len(table_files),
    'records': records,
    'anomalies': anomalies,
    'anomaly_count': len(anomalies),
}

json_out = os.path.join(OUT_DIR, 'manifests', 'phase0_config_audit.json')
with open(json_out, 'w', encoding='utf-8') as fh:
    json.dump(audit_data, fh, ensure_ascii=False, indent=2)
print('Wrote', json_out)

# ============================================================
# Output Markdown report
# ============================================================
md = []
md.append('# Phase 0 Config Audit Report')
md.append('')
md.append('**Audit time:** %s' % datetime.now().isoformat())
md.append('**Results directory:** `%s`' % RESULTS_DIR)
md.append('')

md.append('## Summary')
md.append('')
md.append('| Metric | Value |')
md.append('|--------|-------|')
md.append('| Config snapshots found | %d |' % len(configs))
md.append('| Episode results files | %d |' % len(episode_files))
md.append('| Paper tables exist | %s |' % ('Yes' if tables_exist else '**No**'))
md.append('| Paper table files | %d |' % len(table_files))
md.append('| Anomalies detected | %d |' % len(anomalies))
md.append('')

md.append('## Expected Mainline Configuration')
md.append('')
md.append('| Key | Expected Value |')
md.append('|-----|---------------|')
for k, v in EXPECTED.items():
    md.append('| `%s` | `%s` |' % (k, v))
md.append('| single-USV map | %dx%d |' % (EXPECTED_SINGLE_MAP['map_height_cells'], EXPECTED_SINGLE_MAP['map_width_cells']))
md.append('| two-USV map | %dx%d |' % (EXPECTED_TWO_MAP['map_height_cells'], EXPECTED_TWO_MAP['map_width_cells']))
md.append('| two-USV starts | %s |' % str(EXPECTED_TWO_STARTS))
md.append('')

if configs:
    md.append('## Config Snapshots Found')
    md.append('')
    for rec in records:
        fname = os.path.basename(rec['file'])
        usv_type = 'two-USV' if rec['is_two_usv'] else 'single-USV'
        md.append('### %s (%s)' % (fname, usv_type))
        md.append('')
        md.append('| Field | Value | Status |')
        md.append('|-------|-------|--------|')
        for field in FIELDS:
            val = rec.get(field, 'N/A')
            if val is None:
                status = '**MISSING**'
            elif field in EXPECTED and val != EXPECTED[field]:
                status = '**MISMATCH**'
            else:
                status = 'OK'
            md.append('| `%s` | `%s` | %s |' % (field, val, status))
        md.append('')
else:
    md.append('## WARNING: No config snapshots found')
    md.append('')

if anomalies:
    md.append('## Anomalies')
    md.append('')
    for a in anomalies:
        md.append('- %s' % a)
    md.append('')
else:
    md.append('## No anomalies detected')
    md.append('')

md_out = os.path.join(OUT_DIR, 'reports', 'phase0_config_audit.md')
with open(md_out, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(md))
print('Wrote', md_out)
print('Done.')
