from datetime import datetime, timedelta

from .orgs import \
    OcOrg, \
    OcUser

from .orgadmin import OrgAdmin
from .common import diffInHours


import logging
logging.basicConfig(level=logging.DEBUG, filename="log/views.log")
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class OcCommunity(object):
    """
    Community stats
    """

    def get_amount_currents_total(self):
        """
        returns total amount of currents in the system
        """
        total_currents_amount = sum([x['total'] for x in OcOrg().get_top_issued_npfs(period='all-time') if x['total']>0])

        return total_currents_amount


    def get_active_volunteers_total(self):
        """
        returns total volunteers number in the system
        """
        active_volunteers_total = len([x for x in OcUser().get_top_received_users(period='all-time')])

        return active_volunteers_total


    def get_currents_accepted_total(self):
        """
        returns total currents accepted in the system
        """
        currents_accepted_total = reduce(lambda x,y : x + y, [x['total'] for x in OcOrg().get_top_accepted_bizs(period='all-time') if x['total']>0])

        return currents_accepted_total


    def get_hours_pending_admin (self, admin_id):
        """
        returns admin's pending hours
        """
        hours_pending_admin = sum([diffInHours(x.usertimelog.datetime_start, x.usertimelog.datetime_end) for x in OrgAdmin(admin_id).get_hours_requested()])

        return hours_pending_admin


    def get_hours_issued_admin (self, admin_id):
        """
        returns admin's issued hours
        """
        hours_issued_admin = sum(
                    [diffInHours(x.usertimelog.datetime_start, x.usertimelog.datetime_end) for x in OrgAdmin(admin_id).get_hours_approved()])

        return hours_issued_admin

