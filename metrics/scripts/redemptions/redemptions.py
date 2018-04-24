from openCurrents.interfaces.common import diffInHours
from openCurrents.models import Transaction
from django.contrib.auth.models import User
from django.db.models import Count, Sum

from csv import writer
from datetime import datetime, timedelta
from pytz import utc


dt = utc.localize(datetime(2017, 6, 5))
m = set()
d = {}

while dt < datetime.now(tz=utc):
    trs = Transaction.objects.filter(
        date_created__gte=dt
    ).filter(
        date_created__lt=dt + timedelta(weeks=1)
    )

    d[dt.strftime('%Y-%m-%d')] = len(trs)
    dt += timedelta(weeks=1)

with open('./metrics/scripts/redemptions/redemptions.csv', 'w') as f:
    wr = writer(f)
    for key, val in d.iteritems():
        wr.writerow([key, val])
