from datetime import datetime, timedelta

from openCurrents.models import Org
from openCurrents.interfaces.bizadmin import BizAdmin
from openCurrents.interfaces.orgs import OcOrg, OcUser, InvalidOrgException

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
            for x in OcOrg().get_top_issued_npfs(
                period='all-time',
                quantity=int(1e6)
            )
            if x['total'] > 0
        ])

        return total_currents_amount


    def get_active_volunteers_total(self, quantity=None ):
        """
        returns total volunteers number in the system
        """
        if not quantity:
            quantity=int(1e6)

        active_volunteers_total = len([
            volunteer for volunteer in OcUser().get_top_received_users(
                period='all-time',
                quantity=quantity
            )
        ])

        return active_volunteers_total


    def get_biz_currents_accepted_total(self):
        """
        returns total currents accepted in the system
        note: accepted = approved + redeemed
        """
        currents_accepted_total = sum([
            x['total']
            for x in OcOrg().get_top_accepted_bizs(
                period='all-time',
                quantity=int(1e6)
            )
            if x['total'] > 0
        ])

        return currents_accepted_total

    def get_biz_currents_pending_total(self, quantity=None):
        total_pending = 0
        for biz in Org.objects.filter(status='biz'):
            try:
                biz_org = OcOrg(biz.id)
            except InvalidOrgException:
                continue

            biz_admins = biz_org.get_admins()
            if biz_admins:
                total_pending += BizAdmin(biz_admins.first().id).get_balance_pending()

        if isinstance(quantity, int):
            total_pending = total_pending[:quantity]

        return total_pending
