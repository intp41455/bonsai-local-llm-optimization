import os
for p in ['tmp_count.py', 'tmp_err.py']:
    if os.path.exists(p):
        os.remove(p)
        print('removed', p)
