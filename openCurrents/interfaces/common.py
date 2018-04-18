from openCurrents.interfaces import convert
from django.contrib.auth.models import User

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


def check_if_new_biz_registration(self):
    """Check if user is autenticated or a new biz."""
    if self.request.user.is_authenticated():
        user_email = self.user.email
    elif 'new_biz_registration' in self.request.session.keys():
        user_email = User.objects.get(id=self.request.session['new_biz_user_id']).email

    return user_email


def where_to_redirect(oc_auth):
    """
    User redirection.

    Check if user is an org/biz admin or a volunteer and return redirect string
    with a proper page url.
    """
    redirection = 'openCurrents:profile'
    if oc_auth.is_admin_org():
        redirection = 'openCurrents:org-admin'
    elif oc_auth.is_admin_biz():
        redirection = 'openCurrents:biz-admin'


    return redirection
