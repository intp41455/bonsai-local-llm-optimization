import os
# Search more broadly for sales.csv
for root, dirs, files in os.walk('.'):
    for f in files:
        if 'sales' in f.lower() or f.endswith('.csv'):
            print(os.path.join(root, f))
# Also check parent dirs
for d in ['..', '../..']:
    if os.path.exists(d):
        for root, dirs, files in os.walk(d):
            for f in files:
                if 'sales' in f.lower() or f.endswith('.csv'):
                    print(os.path.join(root, f))
