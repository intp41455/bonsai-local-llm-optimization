import csv
from calc import total_paid

# Test 1: basic dedup + paid-only
rows = [
    {'order_id': 'A001', 'amount': '120', 'status': 'paid'},
    {'order_id': 'A002', 'amount': '80', 'status': 'refunded'},
    {'order_id': 'A003', 'amount': '200', 'status': 'paid'},
    {'order_id': 'A003', 'amount': '200', 'status': 'paid'},
    {'order_id': 'A004', 'amount': '50', 'status': 'pending'},
    {'order_id': 'A005', 'amount': '30', 'status': 'paid'},
]
# paid unique: A001(120) + A003(200) + A005(30) = 350
assert total_paid(rows) == 350, f"got {total_paid(rows)}"

# Test 2: empty
assert total_paid([]) == 0

# Test 3: no paid
assert total_paid([{'order_id':'X','amount':'10','status':'refunded'}]) == 0

# Test 4: same order_id paid twice with different amounts -> count once (first)
r2 = [
    {'order_id': 'B1', 'amount': '10', 'status': 'paid'},
    {'order_id': 'B1', 'amount': '20', 'status': 'paid'},
]
assert total_paid(r2) == 10

# Test 5: csv from sales.csv
with open('sales.csv', newline='') as f:
    csv_rows = list(csv.DictReader(f))
assert total_paid(csv_rows) == 350, f"csv got {total_paid(csv_rows)}"

print("ALL TESTS PASSED")
print("sales.csv total_paid =", total_paid(csv_rows))
