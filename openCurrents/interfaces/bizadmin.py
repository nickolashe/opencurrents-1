from datetime import datetime

from django.db.models import Max

from openCurrents.models import \
	UserEventRegistration, \
    UserTimeLog, \
    AdminActionUserTime, \
    Offer, \
    Transaction, \
    TransactionAction

from openCurrents.interfaces import convert
from openCurrents.interfaces.orgs import OrgUserInfo
from openCurrents.interfaces.ledger import OcLedger

import pytz


class BizAdmin(object):
    def __init__(self, userid):
    	# userid
        self.userid = userid

        # orgid
        org_user_info = OrgUserInfo(self.userid)
        self.org = org_user_info.get_org()

        if not self.org or self.org.status != 'biz':
        	raise InvalidAffiliation

    def get_balance_available(self):
        '''
        report total available currents
        '''
        balance = OcLedger().get_balance(
            entity_id=self.org.orgentity.id,
            entity_type='org'
        )

        return balance

    def get_balance_pending(self):
        '''
        pending currents from offer redemption requests
        '''
        active_redemption_reqs = self.get_redemptions(status='pending')

        total_redemptions = self._get_redemption_total(
            active_redemption_reqs
        )

        return total_redemptions

    def get_offers_all(self):
        offers = Offer.objects.filter(
            org__id=self.org.id
        )
        return offers

    def get_redemptions(self, status=None):
        transactions = Transaction.objects.filter(
            offer__org__id=self.org.id
        ).annotate(
            last_action_created=Max('transactionaction__date_created')
        )

        # redemption requests
        org_offers_redeemed = TransactionAction.objects.filter(
            date_created__in=[
                tr.last_action_created for tr in transactions
            ]
        )

        # filter by status
        if status == 'pending':
            org_offers_redeemed = org_offers_redeemed.filter(
                action_type='req'
            )
        elif status == 'approved':
            org_offers_redeemed = org_offers_redeemed.filter(
                action_type='app'
            )

        return org_offers_redeemed

    def _get_redemption_total(self, records):
        balance = 0

        for rec in records:
            tr = rec.transaction
            offer = tr.offer
            balance += convert.usd_to_cur(
                0.01 * float(offer.currents_share) * float(tr.price_actual)
            )

        return balance

class InvalidAffiliation(Exception):
	pass
