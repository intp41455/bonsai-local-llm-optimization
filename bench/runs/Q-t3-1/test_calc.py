import csv
from calc import total_paid

# Test 1: from sales.csv
rows = list(csv.DictReader(open('sales.csv')))
# paid rows: A001(120), A003(200), A003(200 dup), A005(30)
# dedup by order_id -> A001, A003, A005 = 120+200+30 = 350
print("sales.csv total:", total_paid(rows))
assert total_paid(rows) == 350.0, "sales.csv mismatch"

# Test 2: inline
data = [
    {'order_id':'X1','amount':'10','status':'paid'},
    {'order_id':'X1','amount':'10','status':'paid'},
    {'order_id':'X2','amount':'5','status':'refunded'},
    {'order_id':'X3','amount':'7','status':'pending'},
    {'order_id':'X4','amount':'2.5','status':'paid'},
]
print("inline total:", total_paid(data))
assert total_paid(data) == 12.5, "inline mismatch"

# Test 3: empty
assert total_paid([]) == 0.0

print("ALL TESTS PASSED")
