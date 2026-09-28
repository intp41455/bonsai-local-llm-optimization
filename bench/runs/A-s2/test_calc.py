import csv
import sys
sys.path.insert(0, '.')
from calc import total_paid

# Test 1: sales.csv data
with open('sales.csv', newline='') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

result = total_paid(rows)
print(f"sales.csv total_paid: {result}")
assert result == 350.0, f"Expected 350.0, got {result}"
print("PASS: sales.csv -> 350.0")

# Test 2: empty list
assert total_paid([]) == 0.0
print("PASS: empty list -> 0.0")

# Test 3: no paid rows
rows_nopaid = [{'order_id': 'X1', 'amount': '100', 'status': 'refunded'},
               {'order_id': 'X2', 'amount': '50', 'status': 'pending'}]
assert total_paid(rows_nopaid) == 0.0
print("PASS: no paid rows -> 0.0")

# Test 4: duplicate paid order_id, different amounts (first wins)
rows_dup = [{'order_id': 'D1', 'amount': '100', 'status': 'paid'},
            {'order_id': 'D1', 'amount': '200', 'status': 'paid'},
            {'order_id': 'D2', 'amount': '50', 'status': 'paid'}]
assert total_paid(rows_dup) == 150.0
print("PASS: duplicate order_id -> 150.0 (first occurrence)")

# Test 5: paid and non-paid same order_id
rows_mixed = [{'order_id': 'M1', 'amount': '100', 'status': 'refunded'},
              {'order_id': 'M1', 'amount': '200', 'status': 'paid'},
              {'order_id': 'M2', 'amount': '30', 'status': 'paid'}]
assert total_paid(rows_mixed) == 230.0
print("PASS: mixed status same order_id -> 230.0")

# Test 6: float amounts
rows_float = [{'order_id': 'F1', 'amount': '10.5', 'status': 'paid'},
              {'order_id': 'F2', 'amount': '20.25', 'status': 'paid'}]
assert total_paid(rows_float) == 30.75
print("PASS: float amounts -> 30.75")

print("\nAll tests passed!")
