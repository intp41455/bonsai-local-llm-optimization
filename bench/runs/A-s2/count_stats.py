import csv, collections

# sales.csv stats
with open('sales.csv', newline='') as f:
    rows = list(csv.DictReader(f))
print("sales rows:", len(rows))
print("status counts:", collections.Counter(r['status'] for r in rows))
paid = sum(int(r['amount']) for r in rows if r['status']=='paid')
refunded = sum(int(r['amount']) for r in rows if r['status']=='refunded')
pending = sum(int(r['amount']) for r in rows if r['status']=='pending')
print("paid sum:", paid, "refunded sum:", refunded, "pending sum:", pending)
print("total sum:", paid+refunded+pending)

# log stats
with open('logs/run.log') as f:
    lines = f.readlines()
print("log lines:", len(lines))
info = sum(1 for l in lines if l.startswith('INFO'))
err = sum(1 for l in lines if l.startswith('ERROR'))
print("INFO:", info, "ERROR:", err)
for l in lines:
    if l.startswith('ERROR'):
        print("  ", l.strip())
