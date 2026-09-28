def total_paid(rows):
    return sum(float(r['amount']) for r in rows)
