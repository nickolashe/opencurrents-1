from openCurrents.models import UserTimeLog, AdminActionUserTime
from django.contrib.auth.models import User

from csv import writer
from datetime import datetime, timedelta
from pytz import utc


dt = utc.localize(datetime(2017, 9, 4))
d = {}

while dt < datetime.now(tz=utc):
    aauts = AdminActionUserTime.objects.filter(
        date_created__gte=dt
    ).filter(
        date_created__lt=dt + timedelta(weeks=1)
    ).filter(
        usertimelog__is_verified=True
    ).filter(
        action_type='app'
    )

    m_new = set([
        aaut.usertimelog.event.project.org.id for aaut in aauts
    ])
    d[dt.strftime('%Y-%m-%d')] = len(m_new)

    dt += timedelta(weeks=1)


with open('./metrics/scripts/orgs/npfs_active_all.csv', 'w') as f:
    wr = writer(f)
    for key, val in d.iteritems():
        wr.writerow([key, val])
