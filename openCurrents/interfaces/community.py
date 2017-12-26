from datetime import datetime, timedelta

from .orgs import \
    OcOrg, \
    OcUser


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
        total_currents_amount = sum([
            x['total']
            for x in OcOrg().get_top_issued_npfs(period='all-time')
            if x['total'] > 0
        ])

        return total_currents_amount


    def get_active_volunteers_total(self):
        """
        returns total volunteers number in the system
        """
        active_volunteers_total = len([
            x for x in OcUser().get_top_received_users(period='all-time')
        ])

        return active_volunteers_total


    def get_currents_accepted_total(self):
        """
        returns total currents accepted in the system
        """
        currents_accepted_total = sum([
            x['total']
            for x in OcOrg().get_top_accepted_bizs(period='all-time')
            if x['total'] > 0
        ])

        return currents_accepted_total
