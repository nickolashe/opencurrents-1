from openCurrents.models import AdminActionUserTime
from openCurrents.interfaces.ledger import OcLedger

app_recs = AdminActionUserTime.objects.filter(action_type='app')

def _retro_issue(app_rec):
    ut = app_rec.usertimelog
    vol_user = ut.user
    event = ut.event
    org = event.project.org
    if (event.event_type == 'MN'):
        amount = ut.datetime_end - ut.datetime_start
    else:
        amount = event.datetime_start - event.datetime_end

    amount = amount.total_seconds() / 3600
    print "issuing %.2f from %s to %s" % (amount, org.name, vol_user.username)
    OcLedger().issue_currents(
        org.orgentity.id, vol_user.userentity.id, app_rec, amount
    )

map(_retro_issue, app_recs)
