from openCurrents.interfaces.ocuser import OcUser
from openCurrents.interfaces.ledger import OcLedger
from openCurrents.models import UserSettings
from django.contrib.auth.models import User

from csv import writer
from datetime import datetime, timedelta
from pytz import utc

users = User.objects.filter(is_staff=False)
ocledger = OcLedger()
data = {}

for user in users:
    try:
        us = user.usersettings
    except UserSettings.DoesNotExist:
        continue

    ocuser = OcUser(user.id)
    redemptions = ocuser.get_offers_redeemed()
    redemptions_req = filter(lambda x: x.action_type == 'req', redemptions)
    redemptions_app = filter(lambda x: x.action_type == 'app', redemptions)

    hours_req = ocuser.get_hours_requested()
    hours_app = ocuser.get_hours_approved()


    data[user.id] = {
        'email': user.email,
        'first_name': user.first_name.encode('utf-8'),
        'last_name': user.last_name.encode('utf-8'),
        'connector': user.usersettings.popup_reaction,
        'monthly_updates': user.usersettings.monthly_updates,
        'verified': user.has_usable_password(),
        'balance (C)': ocuser.get_balance_available(),
        'balance ($)': ocuser.get_balance_available_usd(),
        'has_bonus': ocledger.has_bonus(user.userentity),
        'redemptions (approved)': len(redemptions_app),
        'date first redemption approved':
            redemptions_app[-1].date_created.strftime('%m/%d/%Y') if redemptions_app else None,
        'date last redemption approved':
            redemptions_app[0].date_created.strftime('%m/%d/%Y') if redemptions_app else None,
        'redemptions (pending)': len(redemptions_req),
        'date first redemption pending':
            redemptions_req[-1].date_created.strftime('%m/%d/%Y') if redemptions_req else None,
        'date last redemption pending':
            redemptions_req[0].date_created.strftime('%m/%d/%Y') if redemptions_req else None,
        'hours (requested)': len(hours_req),
        'date first hour requested':
            hours_req.last().date_created.strftime('%m/%d/%Y') if hours_req else None,
        'date last hour requested':
            hours_req.first().date_created.strftime('%m/%d/%Y') if hours_req else None,
        'hours (approved)': len(hours_app),
        'date first hour approved':
            hours_app.last().date_created.strftime('%m/%d/%Y') if hours_app else None,
        'date last hour approved':
            hours_app.first().date_created.strftime('%m/%d/%Y') if hours_app else None,
        'date_joined': user.date_joined.strftime('%m/%d/%Y'),
        'date_last_login': user.last_login.strftime('%m/%d/%Y') if user.last_login else None
    }

with open('./metrics/scripts/user/user-data.csv', 'w') as f:
    wr = writer(f)
    wr.writerow(['id'] + data[data.keys()[0]].keys())

    for idx, metrics in data.iteritems():
        wr.writerow([idx] + metrics.values())
