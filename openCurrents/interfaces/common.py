from openCurrents.interfaces import convert
from django.contrib.auth.models import User

from datetime import datetime, timedelta
from decimal import Decimal
import re

_MASTER_OFFER_LIMIT = 0.625
_GIFT_CARD_OFFER_LIMIT = 0.625
_SIGNUP_BONUS = 1.0


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


def event_description_url_parser(description):
    """
    Parse event description.

    Takes string 'description' (eg data['event_description']) and looks for
    url-like text, then replaces it with html code.
    """
    # looking for an URL in self.description:
    text = unicode(description)
    regexp = re.compile(r'(?i)\b((?:[a-z][\w-]+:(?:/{1,3}|[a-z0-9%])|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:\'\".,<>?]))')

    found = re.findall(regexp, text)

    # replacing urls with special marking tags
    text = re.sub(regexp, '<a__tag>', text)

    # replacing special tags one by one iterating through found urls
    for f in found:
        text = re.sub(
            r'<a__tag>',
            '<a href="{0}" target="_blank">{0}</a>'.format(f[0]),
            text,
            1
        )

    # adding http:// to www
    text = re.sub('href="www.', 'href="http://www.', text)

    return text
