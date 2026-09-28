import csv, collections, re

# sales.csv
rows = []
with open('sales.csv', newline='') as f:
    r = csv.DictReader(f)
    for row in r:
        rows.append(row)

print("=== sales.csv ===")
print("data rows:", len(rows))
print("unique order_ids:", len({row['order_id'] for row in rows}))
print("status counts:", collections.Counter(row['status'] for row in rows))
print("total amount (all rows):", sum(int(row['amount']) for row in rows))

# dedup by order_id
seen = {}
for row in rows:
    seen[row['order_id']] = row
print("dedup rows:", len(seen))
print("dedup total amount:", sum(int(row['amount']) for row in seen.values()))

paid = [row for row in rows if row['status'] == 'paid']
print("paid rows (raw):", len(paid), "amount:", sum(int(r['amount']) for r in paid))
paid_dedup = {row['order_id']: row for row in paid}
print("paid dedup count:", len(paid_dedup), "amount:", sum(int(r['amount']) for r in paid_dedup.values()))

# logs/run.log
print("\n=== logs/run.log ===")
with open('logs/run.log') as f:
    lines = f.readlines()
print("total lines:", len(lines))
info = sum(1 for l in lines if l.startswith('INFO'))
err = sum(1 for l in lines if l.startswith('ERROR'))
print("INFO lines:", info)
print("ERROR lines:", err)
for l in lines:
    if l.startswith('ERROR'):
        print("  error:", l.strip())
print("last line:", lines[-1].strip() if lines else None)
nums = []
for l in lines:
    m = re.search(r'row=(\d+)', l)
    if m:
        nums.append(int(m.group(1)))
print("row range:", min(nums), "-", max(nums), "count:", len(nums))
missing = [i for i in range(min(nums), max(nums)+1) if i not in set(nums)]
print("missing row numbers:", missing)
