import csv
import sys
from calc import total_paid

# Load sales.csv
rows = []
with open('sales.csv', newline='') as f:
    for r in csv.DictReader(f):
        rows.append(r)

# Expected: paid rows deduped by order_id
# A001 120 paid, A003 200 paid (dup), A005 30 paid -> 120+200+30 = 350
expected = 350.0
got = total_paid(rows)
print(f"rows={len(rows)}")
print(f"expected={expected}")
print(f"got={got}")
assert got == expected, f"FAIL: got {got}, expected {expected}"

# Extra checks
# 1) only paid counted (refunded/pending excluded)
only_paid = [r for r in rows if r['status'] == 'paid']
assert total_paid(only_paid) == 350.0
# 2) empty -> 0
assert total_paid([]) == 0.0
# 3) no paid -> 0
assert total_paid([{'order_id':'X','amount':'10','status':'refunded'}]) == 0.0
# 4) duplicate paid same order counted once
dup = [{'order_id':'A','amount':'10','status':'paid'},
       {'order_id':'A','amount':'10','status':'paid'},
       {'order_id':'B','amount':'5','status':'paid'}]
assert total_paid(dup) == 15.0
# 5) duplicate order with different amounts -> first wins (dedup)
dup2 = [{'order_id':'A','amount':'10','status':'paid'},
        {'order_id':'A','amount':'20','status':'paid'}]
assert total_paid(dup2) == 10.0

print("ALL TESTS PASSED")
