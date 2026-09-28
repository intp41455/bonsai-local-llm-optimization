import os
for root, dirs, files in os.walk('.'):
    for f in files:
        if f.endswith('.csv'):
            print(os.path.join(root, f))
