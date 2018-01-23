from openCurrents.interfaces import convert

from decimal import Decimal

_MASTER_OFFER_LIMIT = 2

def one_week_from_now():
    return datetime.now() + timedelta(days=7)

def diffInHours(t1, t2):
    return round((t2 - t1).total_seconds() / 3600, 2)

def diffInMinutes(t1, t2):
    return round((t2 - t1).total_seconds() / 60, 1)

def _get_redemption_total(records, currency='cur'):
    balance = 0

    for rec in records:
        tr = rec.transaction
        amount_cur = tr.currents_amount

        if currency == 'usd':
            amount = convert.cur_to_usd(amount_cur)

            # apply transaction fee
            amount *= Decimal(1 - convert._TR_FEE)
        else:
            amount = amount_cur

        balance += amount

    return balance
