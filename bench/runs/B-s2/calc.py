def total_paid(rows):
    seen = set()
    total = 0.0
    for r in rows:
        if r.get('status') != 'paid':
            continue
        order_id = r.get('order_id')
        if order_id in seen:
            continue
        seen.add(order_id)
        total += float(r['amount'])
    return total
