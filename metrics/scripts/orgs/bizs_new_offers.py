from openCurrents.models import Org, Offer
from django.contrib.auth.models import User
from django.db.models import Count

from csv import writer
from datetime import datetime, timedelta
from pytz import utc


dt = utc.localize(datetime(2017, 9, 4))
d = {}

while dt < datetime.now(tz=utc):
    bizs = Org.objects.filter(
        date_created__gte=dt
    ).filter(
        date_created__lt=dt + timedelta(weeks=1)
    ).filter(
        status='biz'
    )

    d[dt.strftime('%Y-%m-%d')] = len([
        biz for biz in bizs if biz.offer_set.exists()
    ])

    dt += timedelta(weeks=1)


with open('./metrics/scripts/orgs/bizs_new_offers.csv', 'w') as f:
    wr = writer(f)
    for key, val in d.iteritems():
        wr.writerow([key, val])
