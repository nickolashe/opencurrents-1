from datetime import datetime

from django.db.models import Max

from openCurrents.models import \
	UserEventRegistration, \
    UserTimeLog, \
    AdminActionUserTime, \
    Offer, \
    Transaction, \
    TransactionAction

from openCurrents.orgs import OrgUserInfo

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


class InvalidAffiliation(Exception):
	pass
