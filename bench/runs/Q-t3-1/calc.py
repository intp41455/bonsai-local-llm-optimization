def total_paid(rows):
    seen = set()
    total = 0.0
    for r in rows:
        if r['status'] == 'paid' and r['order_id'] not in seen:
            seen.add(r['order_id'])
            total += float(r['amount'])
    return total
