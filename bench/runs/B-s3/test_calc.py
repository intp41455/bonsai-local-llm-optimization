import csv
import sys
from calc import total_paid

def load_rows(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def main():
    rows = load_rows('sales.csv')
    got = total_paid(rows)
    # paid rows: A001=120, A003=200 (dup), A005=30 -> dedup by order_id -> 120+200+30 = 350
    expected = 350.0
    assert got == expected, f"expected {expected}, got {got}"
    print(f"total_paid = {got} (expected {expected}) OK")

    # extra sanity: refunded/pending excluded, dup paid excluded
    extra = [
        {'order_id': 'X1', 'amount': '10', 'status': 'paid'},
        {'order_id': 'X1', 'amount': '10', 'status': 'paid'},
        {'order_id': 'X2', 'amount': '5', 'status': 'refunded'},
        {'order_id': 'X3', 'amount': '7', 'status': 'pending'},
    ]
    assert total_paid(extra) == 10.0, f"extra case failed: {total_paid(extra)}"
    print("extra sanity OK")

if __name__ == '__main__':
    main()
