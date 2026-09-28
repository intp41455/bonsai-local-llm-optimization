import csv
from collections import Counter

rows = []
with open('sales.csv', newline='') as f:
    r = csv.DictReader(f)
    for row in r:
        rows.append(row)

total = len(rows)
status = Counter(row['status'] for row in rows)
amounts = [float(row['amount']) for row in rows]
total_amount = sum(amounts)
paid = sum(a for row, a in zip(rows, amounts) if row['status'] == 'paid')
refunded = sum(a for row, a in zip(rows, amounts) if row['status'] == 'refunded')
pending = sum(a for row, a in zip(rows, amounts) if row['status'] == 'pending')
unique_orders = len(set(row['order_id'] for row in rows))

print("total_rows", total)
print("status", dict(status))
print("total_amount", total_amount)
print("paid", paid, "refunded", refunded, "pending", pending)
print("unique_orders", unique_orders)

info = err = 0
with open('logs/run.log') as f:
    for line in f:
        if line.startswith('INFO'):
            info += 1
        elif line.startswith('ERROR'):
            err += 1
print("log_info", info, "log_error", err)
