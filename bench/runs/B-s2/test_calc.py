import csv
import sys
from calc import total_paid

def load_rows(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def test_basic():
    rows = [
        {'order_id': 'A001', 'amount': '120', 'status': 'paid'},
        {'order_id': 'A002', 'amount': '80', 'status': 'refunded'},
        {'order_id': 'A003', 'amount': '200', 'status': 'paid'},
        {'order_id': 'A003', 'amount': '200', 'status': 'paid'},
        {'order_id': 'A004', 'amount': '50', 'status': 'pending'},
        {'order_id': 'A005', 'amount': '30', 'status': 'paid'},
    ]
    # paid only: A001(120) + A003(200, dedup) + A005(30) = 350
    assert total_paid(rows) == 350.0, f"got {total_paid(rows)}"

def test_from_csv():
    rows = load_rows('sales.csv')
    assert total_paid(rows) == 350.0, f"got {total_paid(rows)}"

def test_empty():
    assert total_paid([]) == 0.0

def test_no_paid():
    rows = [{'order_id': 'X', 'amount': '10', 'status': 'refunded'}]
    assert total_paid(rows) == 0.0

def test_duplicate_paid_different_amount():
    # dedup by order_id keeps first occurrence
    rows = [
        {'order_id': 'A', 'amount': '10', 'status': 'paid'},
        {'order_id': 'A', 'amount': '20', 'status': 'paid'},
    ]
    assert total_paid(rows) == 10.0

if __name__ == '__main__':
    tests = [test_basic, test_from_csv, test_empty, test_no_paid, test_duplicate_paid_different_amount]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print("ALL TESTS PASSED")
