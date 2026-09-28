def total_paid(rows):
    seen = set()
    total = 0.0
    for r in rows:
        if r.get('status') != 'paid':
            continue
        oid = r.get('order_id')
        if oid in seen:
            continue
        seen.add(oid)
        total += float(r['amount'])
    return total
