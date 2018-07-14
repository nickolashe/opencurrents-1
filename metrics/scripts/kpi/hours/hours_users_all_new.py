from openCurrents.models import UserTimeLog, AdminActionUserTime
from django.contrib.auth.models import User
from django.db.models import Count, Sum

from csv import writer
from datetime import datetime, timedelta
from pytz import utc


dt = utc.localize(datetime(2017, 1, 2))
m = set()
d = {}

while dt < datetime.now(tz=utc):
    aauts = AdminActionUserTime.objects.exclude(
        usertimelog__user_id__in=m
    ).filter(
        date_created__gte=dt
    ).filter(
        date_created__lt=dt + timedelta(weeks=1)
    ).filter(
        usertimelog__is_verified=True
    ).filter(
        action_type='app'
    )

    m_new = set([aaut.usertimelog.user_id for aaut in aauts])
    d[dt.strftime('%Y-%m-%d')] = len(m_new)
    m.update(m_new)

    dt += timedelta(weeks=1)

print len(sorted(m))

with open('./metrics/scripts/kpi/hours/hours_users_all_new.csv', 'w') as f:
    wr = writer(f)
    for key, val in d.iteritems():
        wr.writerow([key, val])
