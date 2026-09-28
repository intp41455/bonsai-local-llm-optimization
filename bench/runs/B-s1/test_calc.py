import csv
import sys
sys.path.insert(0, '.')
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
assert total_paid(rows) == 350.0, f"got {total_paid(rows)}"
print("test1 OK:", total_paid(rows))

# Test 2: empty
assert total_paid([]) == 0.0
print("test2 OK:", total_paid([]))

# Test 3: no paid
assert total_paid([{'order_id':'X','amount':'10','status':'refunded'}]) == 0.0
print("test3 OK:", total_paid([{'order_id':'X','amount':'10','status':'refunded'}]))

# Test 4: same order_id paid then refunded -> count once (first paid)
rows2 = [
    {'order_id':'B1','amount':'100','status':'paid'},
    {'order_id':'B1','amount':'100','status':'refunded'},
]
assert total_paid(rows2) == 100.0
print("test4 OK:", total_paid(rows2))

# Test 5: same order_id refunded then paid -> count once
rows3 = [
    {'order_id':'B2','amount':'100','status':'refunded'},
    {'order_id':'B2','amount':'100','status':'paid'},
]
assert total_paid(rows3) == 100.0
print("test5 OK:", total_paid(rows3))

# Test 6: read from sales.csv
with open('sales.csv', newline='') as f:
    reader = csv.DictReader(f)
    csv_rows = list(reader)
print("csv rows:", len(csv_rows))
print("csv total_paid:", total_paid(csv_rows))
assert total_paid(csv_rows) == 350.0

print("ALL TESTS PASSED")
