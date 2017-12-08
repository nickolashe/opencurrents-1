from datetime import datetime

from django.db.models import Max

from openCurrents.models import \
	Project, \
    Event, \
    AdminActionUserTime, \
    UserTimeLog

from openCurrents.interfaces import common
from openCurrents.interfaces import convert
from openCurrents.interfaces.orgs import OrgUserInfo
from openCurrents.interfaces.ledger import OcLedger

import pytz


class OrgAdmin(object):
    def __init__(self, userid):
    	# userid
        self.userid = userid

        # orgid
        org_user_info = OrgUserInfo(self.userid)
        self.org = org_user_info.get_org()

        if not self.org or self.org.status != 'npf':
        	raise InvalidAffiliation

    def get_hours_requested(self):
        usertimelogs = self._get_usertimelogs()
        admin_actions = self._get_adminactions_for_usertimelogs(usertimelogs)

        return admin_actions

    def get_hours_approved(self):
        usertimelogs = self._get_usertimelogs(verified=True)
        admin_actions = self._get_adminactions_for_usertimelogs(
            usertimelogs,
            'app'
        )

        return admin_actions

    def _get_usertimelogs(self, verified=False):
        projects = Project.objects.filter(org__id=self.org.id)
        events = Event.objects.filter(
            project__in=projects
        )

        # determine whether there are any unverified timelogs for admin
        usertimelogs = UserTimeLog.objects.filter(
            event__in=events
        ).filter(
            is_verified=verified
        ).annotate(
            last_action_created=Max('adminactionusertime__date_created')
        )

        return usertimelogs

    def _get_adminactions_for_usertimelogs(self, usertimelogs, action_type='req'):
        # admin-specific requests
        admin_actions = AdminActionUserTime.objects.filter(
            user_id=self.userid
        ).filter(
            date_created__in=[
                utl.last_action_created for utl in usertimelogs
            ]
        ).filter(
            action_type=action_type
        )

        return admin_actions


class InvalidAffiliation(Exception):
	pass
