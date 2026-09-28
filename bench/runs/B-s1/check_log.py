with open('logs/run.log') as f:
    lines = f.readlines()
print("total_lines", len(lines))
for i, l in enumerate(lines, 1):
    if not l.startswith('INFO'):
        print(i, repr(l.strip()))
