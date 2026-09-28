import csv
from calc import total_paid

rows = [
    {'order_id': 'A001', 'amount': '120', 'status': 'paid'},
    {'order_id': 'A002', 'amount': '80', 'status': 'refunded'},
    {'order_id': 'A003', 'amount': '200', 'status': 'paid'},
    {'order_id': 'A003', 'amount': '200', 'status': 'paid'},
    {'order_id': 'A004', 'amount': '50', 'status': 'pending'},
    {'order_id': 'A005', 'amount': '30', 'status': 'paid'},
]
# paid only, dedup by order_id: A001=120, A003=200, A005=30 -> 350
assert total_paid(rows) == 350.0, f"got {total_paid(rows)}"

# empty
assert total_paid([]) == 0.0
# no paid
assert total_paid([{'order_id': 'X', 'amount': '10', 'status': 'refunded'}]) == 0.0
# duplicate paid with different amounts: keep first occurrence
assert total_paid([
    {'order_id': 'B', 'amount': '10', 'status': 'paid'},
    {'order_id': 'B', 'amount': '20', 'status': 'paid'},
]) == 10.0

# load from sales.csv
with open('sales.csv', newline='') as f:
    csv_rows = list(csv.DictReader(f))
assert total_paid(csv_rows) == 350.0, f"csv got {total_paid(csv_rows)}"

print("all tests passed")
