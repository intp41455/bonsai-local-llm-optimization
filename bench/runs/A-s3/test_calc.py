import csv
import sys
sys.path.insert(0, '.')
from calc import total_paid

# Test 1: basic fixture from sales.csv
with open('sales.csv', newline='') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

result = total_paid(rows)
expected = 350.0  # A001(120) + A003(200, dedup) + A005(30)
print(f"Test 1 (sales.csv): got={result}, expected={expected}")
assert result == expected, f"FAIL: {result} != {expected}"
print("PASS")

# Test 2: no paid rows
rows2 = [
    {'order_id': 'X1', 'amount': '100', 'status': 'refunded'},
    {'order_id': 'X2', 'amount': '50', 'status': 'pending'},
]
assert total_paid(rows2) == 0.0, "FAIL: empty paid"
print("Test 2 (no paid): PASS")

# Test 3: duplicate paid order_ids
rows3 = [
    {'order_id': 'D1', 'amount': '10', 'status': 'paid'},
    {'order_id': 'D1', 'amount': '10', 'status': 'paid'},
    {'order_id': 'D1', 'amount': '10', 'status': 'paid'},
]
assert total_paid(rows3) == 10.0, "FAIL: dedup"
print("Test 3 (dedup): PASS")

# Test 4: mixed statuses, dedup across statuses
rows4 = [
    {'order_id': 'M1', 'amount': '50', 'status': 'paid'},
    {'order_id': 'M1', 'amount': '50', 'status': 'refunded'},
    {'order_id': 'M2', 'amount': '25', 'status': 'paid'},
]
assert total_paid(rows4) == 75.0, "FAIL: mixed"
print("Test 4 (mixed): PASS")

# Test 5: empty list
assert total_paid([]) == 0.0, "FAIL: empty"
print("Test 5 (empty): PASS")

print("\nAll tests passed.")
