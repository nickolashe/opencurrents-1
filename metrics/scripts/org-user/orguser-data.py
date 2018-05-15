from openCurrents.interfaces import common
from openCurrents.interfaces.ocuser import OcUser
from openCurrents.interfaces.orgs import OrgUserInfo
from openCurrents.interfaces.orgadmin import OrgAdmin

from openCurrents.models import OrgUser
from django.contrib.auth.models import User

from csv import writer
from datetime import datetime, timedelta
from pytz import utc

orgusers = OrgUser.objects.filter(org__status='npf')

data = {}
for orguser in orgusers:
    user = orguser.user
    orguserinfo = OrgUserInfo(user.id)
    is_approved = orguserinfo.is_org_admin()

    orgadmin = OrgAdmin(user.id)
    hours_req = orgadmin.get_hours_requested()
    hours_app = orgadmin.get_hours_approved()
    hours_total_pending = orgadmin.get_total_hours_pending()
    hours_total_approved_all = orgadmin.get_total_hours_issued()
    hours_total_approved_last_week = sum([
        common.diffInHours(
            rec.usertimelog.event.datetime_start,
            rec.usertimelog.event.datetime_end
        )
        for rec in hours_app
        if rec.date_created > datetime.now(tz=utc) - timedelta(weeks=1)
    ])

    data[user.id] = {
        'org': orguser.org.name,
        'admin_email': user.email,
        'admin_first_name': user.first_name.encode('utf-8'),
        'admin_last_name': user.last_name.encode('utf-8'),
        'is_approved': is_approved,
        'admin hours total (pending)': hours_total_pending,
        'admin hours total (approved)': hours_total_approved_all,
        'admin hours total (approved, last week)': hours_total_approved_last_week,
        'date last hour approved':
            hours_app[0].date_created.strftime('%m/%d/%Y') if hours_app else None,
        'date_joined': user.date_joined.strftime('%m/%d/%Y'),
        'date_last_login': user.last_login.strftime('%m/%d/%Y') if user.last_login else None
    }

with open('./metrics/scripts/org-user/orguser-data.csv', 'w') as f:
    wr = writer(f)
    wr.writerow(['id'] + data[data.keys()[0]].keys())

    for idx, metrics in data.iteritems():
        print idx
        wr.writerow([idx] + metrics.values())
