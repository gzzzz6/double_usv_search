with open(r'f:\pythonprojects\baseline_GP\marine_knownmap_runtime_2usv.py','r',encoding='utf-8') as f:
    for i, line in enumerate(f, 1):
        if line.strip().startswith('def '):
            print(f'{i}: {line.rstrip()}')
