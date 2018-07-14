from openCurrents.interfaces.common import diffInHours
from openCurrents.models import UserTimeLog, AdminActionUserTime
from django.contrib.auth.models import User
from django.db.models import Count, Sum

from csv import writer
from datetime import datetime, timedelta
from pytz import utc


dt = utc.localize(datetime(2017, 6, 5))
m = set()
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

    # uts = filter(lambda x: x.user.has_usable_password(), uts)
    uts = set()
    d[dt.strftime('%Y-%m-%d')] = 0
    for aaut in aauts:
        ut = aaut.usertimelog
        if ut.id not in uts:
            d[dt.strftime('%Y-%m-%d')] += diffInHours(
                ut.event.datetime_start, ut.event.datetime_end
            )
            uts.add(ut.id)

    dt += timedelta(weeks=1)

print sum(d.values())

with open('./metrics/scripts/kpi/currents/currents_issued_all.csv', 'w') as f:
    wr = writer(f)
    for key, val in d.iteritems():
        wr.writerow([key, val])
