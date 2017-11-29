from openCurrents.interfaces import convert


def one_week_from_now():
    return datetime.now() + timedelta(days=7)

def diffInHours(t1, t2):
    return round((t2 - t1).total_seconds() / 3600, 2)

def _get_redemption_total(records, currency='cur'):
    balance = 0

    for rec in records:
        tr = rec.transaction
        offer = tr.offer
        # amount_usd = 0.01 * float(offer.currents_share) * float(tr.price_actual)
        amount_cur = tr.currents_amount

        if currency == 'usd':
            amount = convert.cur_to_usd(amount_cur)
        else:
            amount = amount_cur

        balance += amount

    return balance
