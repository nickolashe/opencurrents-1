from datetime import datetime

from django.db.models import Max

from openCurrents.models import \
	UserEventRegistration, \
    UserTimeLog, \
    AdminActionUserTime

import pytz


class OcUser(object):
    def __init__(self, userid):
        self.userid = userid

    def get_events_registered(self, *argv):
    	user_event_regs = UserEventRegistration.objects.filter(
            user__id=self.userid
        )

    	datetime_from = datetime.now(tz=pytz.utc)
    	if argv:
    		assert(isinstance(argv[0], datetime))
    		datetime_from = argv[0]

        user_event_regs = user_event_regs.filter(
            event__datetime_start__gte=datetime_from
        )

        events = [userreg.event for userreg in user_event_regs]    	
        return events

    def get_balance_available(self):
        usertimelogs = UserTimeLog.objects.filter(
            user_id=self.userid
        ).filter(
            is_verified=True
        )

        balance = self._get_unique_hour_total(usertimelogs)
        return balance

    def get_balance_pending(self):
        usertimelogs = UserTimeLog.objects.filter(
            user_id=self.userid
        ).filter(
            is_verified=False
        ).annotate(
            last_action_created=Max('adminactionusertime__date_created')
        )

        # pending requests
        active_requests = AdminActionUserTime.objects.filter(
            date_created__in=[
                utl.last_action_created for utl in usertimelogs
            ]
        ).filter(
            action_type='req'
        )

        balance = self._get_unique_hour_total(
        	active_requests,
        	from_admin_actions=True
        )
        return balance

    def _get_unique_hour_total(self, records, from_admin_actions=False):
        event_user = set()
       	balance = 0

        for rec in records:
        	if from_admin_actions:
        		timelog = rec.usertimelog
        	else:
        		timelog = rec

			if not timelog.event.id in event_user:
				event_user.add(timelog.event.id)
				balance += (timelog.event.datetime_end - timelog.event.datetime_start).total_seconds() / 3600

        return balance
