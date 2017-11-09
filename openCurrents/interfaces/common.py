from openCurrents.interfaces import convert

def _get_redemption_total(records, currency='cur'):
    balance = 0

    for rec in records:
        tr = rec.transaction
        offer = tr.offer
        amount_usd = 0.01 * float(offer.currents_share) * float(tr.price_actual)
        if currency == 'cur':
            amount = convert.usd_to_cur(amount_usd)
        else:
            amount = amount_usd
        balance += amount

    return balance
