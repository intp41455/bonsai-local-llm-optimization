import csv
import sys
sys.path.insert(0, '.')
from calc import total_paid

# Test 1: basic - only paid, dedup by order_id
rows = [
    {'order_id': 'A001', 'amount': '120', 'status': 'paid'},
    {'order_id': 'A002', 'amount': '80', 'status': 'refunded'},
    {'order_id': 'A003', 'amount': '200', 'status': 'paid'},
    {'order_id': 'A003', 'amount': '200', 'status': 'paid'},  # duplicate
    {'order_id': 'A004', 'amount': '50', 'status': 'pending'},
    {'order_id': 'A005', 'amount': '30', 'status': 'paid'},
]
result = total_paid(rows)
expected = 120 + 200 + 30  # A001 + A003 (dedup) + A005
print(f"Test 1: total_paid = {result}, expected = {expected}")
assert result == expected, f"FAIL: {result} != {expected}"
print("Test 1 PASSED")

# Test 2: empty list
result = total_paid([])
print(f"Test 2: total_paid([]) = {result}")
assert result == 0.0, f"FAIL: {result} != 0.0"
print("Test 2 PASSED")

# Test 3: no paid rows
rows = [
    {'order_id': 'B001', 'amount': '100', 'status': 'refunded'},
    {'order_id': 'B002', 'amount': '50', 'status': 'pending'},
]
result = total_paid(rows)
print(f"Test 3: total_paid(no paid) = {result}")
assert result == 0.0, f"FAIL: {result} != 0.0"
print("Test 3 PASSED")

# Test 4: all paid, no duplicates
rows = [
    {'order_id': 'C001', 'amount': '10', 'status': 'paid'},
    {'order_id': 'C002', 'amount': '20', 'status': 'paid'},
]
result = total_paid(rows)
print(f"Test 4: total_paid(all paid) = {result}")
assert result == 30.0, f"FAIL: {result} != 30.0"
print("Test 4 PASSED")

# Test 5: read from sales.csv
with open('sales.csv', newline='') as f:
    reader = csv.DictReader(f)
    csv_rows = list(reader)
result = total_paid(csv_rows)
print(f"Test 5: total_paid(sales.csv) = {result}")
assert result == 350.0, f"FAIL: {result} != 350.0"
print("Test 5 PASSED")

print("\nAll tests PASSED!")
