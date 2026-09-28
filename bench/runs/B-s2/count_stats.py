import csv
from collections import Counter

with open('sales.csv', newline='') as f:
    rows = list(csv.DictReader(f))
print("sales rows:", len(rows))
print("status counts:", dict(Counter(r['status'] for r in rows)))
total = sum(float(r['amount']) for r in rows)
print("total amount:", total)
paid = sum(float(r['amount']) for r in rows if r['status']=='paid')
refunded = sum(float(r['amount']) for r in rows if r['status']=='refunded')
pending = sum(float(r['amount']) for r in rows if r['status']=='pending')
print("paid:", paid, "refunded:", refunded, "pending:", pending)
print("unique order ids:", len(set(r['order_id'] for r in rows)))

with open('logs/run.log') as f:
    lines = f.readlines()
print("log lines:", len(lines))
info = sum(1 for l in lines if l.startswith('INFO'))
err = sum(1 for l in lines if l.startswith('ERROR'))
print("INFO:", info, "ERROR:", err)
for l in lines:
    if l.startswith('ERROR'):
        print("  err:", l.strip())
