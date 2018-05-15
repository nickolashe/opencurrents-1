from openCurrents.interfaces import common
from openCurrents.interfaces.ocuser import OcUser
from openCurrents.models import UserSettings
from django.contrib.auth.models import User

from csv import writer
from datetime import datetime, timedelta
from pytz import utc

users = User.objects.filter(is_staff=False)

data = {}
for user in users:
    try:
        us = user.usersettings
    except UserSettings.DoesNotExist:
        continue

    ocuser = OcUser(user.id)
    print user.id
    hours_req = ocuser.get_hours_requested()

    for req in hours_req:
        data[req.id] = {
            'user_id': req.usertimelog.user.id,
            'user_email': req.usertimelog.user.email,
            'admin_email': req.user.email,
            'org': req.usertimelog.event.project.org.name,
            'hours': common.diffInHours(
                req.usertimelog.datetime_start,
                req.usertimelog.datetime_end
            ),
            'date_created': req.date_created.strftime('%m/%d/%Y')
        }

with open('./metrics/scripts/user/user-hours-data.csv', 'w') as f:
    wr = writer(f)
    wr.writerow(['id'] + data[data.keys()[0]].keys())

    for idx, metrics in data.iteritems():
        wr.writerow([idx] + metrics.values())
