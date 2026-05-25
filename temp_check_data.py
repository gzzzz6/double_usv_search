import json

with open('F:/pythonprojects/baseline_GP/results/paper_obstacle_field_mainline_20260510/paper_tables_merged_for_report/table_payload.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('=== two_static_delta (cf. thesis Table 5-6) ===')
for row in data['two_static_delta']:
    print(row)

print()
print('=== single_anomaly_delta (cf. thesis Table 5-10) ===')
for row in data['single_anomaly_delta']:
    print(row)

print()
print('=== VERIFICATION: Raw diffs from appendix data ===')

# Two static: coordinated - independent
ind = {}
coord = {}
for r in data['two_static_assignment']:
    if r[1] == 'independent':
        ind[r[0]] = {'T_first': float(r[2]), 'T_all': float(r[3]), 'success': float(r[4]), 'detection': float(r[5])}
    elif r[1] == 'coordinated':
        coord[r[0]] = {'T_first': float(r[2]), 'T_all': float(r[3]), 'success': float(r[4]), 'detection': float(r[5])}

print('--- two_static raw delta (coord - ind) ---')
for m in ['总体', 'open_water', 'obstacle_field', 'peninsula_passage']:
    ci = coord[m]
    ii = ind[m]
    print('%s: dT_first=%.1f, dT_all=%.1f, dsuccess=%.1f, ddetection=%.1f' % (
        m, ci['T_first']-ii['T_first'], ci['T_all']-ii['T_all'],
        ci['success']-ii['success'], ci['detection']-ii['detection']))

# Single static anomaly
ucb = {}
anom = {}
for r in data['single_static_anomaly']:
    if r[1] == 'UCB':
        ucb[r[0]] = {'T_first': float(r[2]), 'T_all': float(r[3]), 'success': float(r[4]), 'detection': float(r[5])}
    elif r[1] == 'anomaly_upper_tail':
        anom[r[0]] = {'T_first': float(r[2]), 'T_all': float(r[3]), 'success': float(r[4]), 'detection': float(r[5])}

print('--- single_static_anomaly raw delta (anom - ucb) ---')
for m in ['总体', 'open_water', 'obstacle_field', 'peninsula_passage']:
    am = anom[m]
    um = ucb[m]
    print('%s: dT_first=%.1f, dT_all=%.1f, dsuccess=%.1f, ddetection=%.1f' % (
        m, am['T_first']-um['T_first'], am['T_all']-um['T_all'],
        am['success']-um['success'], am['detection']-um['detection']))

# Single random anomaly
ucb_r = {}
anom_r = {}
for r in data['single_random_anomaly']:
    if r[1] == 'UCB':
        ucb_r[r[0]] = {'T_first': float(r[2]), 'T_all': float(r[3]), 'success': float(r[4]), 'detection': float(r[5])}
    elif r[1] == 'anomaly_upper_tail':
        anom_r[r[0]] = {'T_first': float(r[2]), 'T_all': float(r[3]), 'success': float(r[4]), 'detection': float(r[5])}

print('--- single_random_anomaly raw delta (anom - ucb) ---')
for m in ['总体', 'open_water', 'obstacle_field', 'peninsula_passage']:
    am = anom_r[m]
    um = ucb_r[m]
    print('%s: dT_first=%.1f, dT_all=%.1f, dsuccess=%.1f, ddetection=%.1f' % (
        m, am['T_first']-um['T_first'], am['T_all']-um['T_all'],
        am['success']-um['success'], am['detection']-um['detection']))

# Two random delta
print()
print('=== two_random_delta (cf. thesis Table 5-8) ===')
for row in data['two_random_delta']:
    print(row)

# Two anomaly delta
print()
print('=== two_anomaly_delta (cf. thesis Table 5-11) ===')
for row in data['two_anomaly_delta']:
    print(row)
