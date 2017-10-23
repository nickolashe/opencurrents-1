from datetime import datetime

from django.contrib.auth.models import User
from django.db.models import Max

from openCurrents.models import \
    UserEntity, \
    Account, \
	UserEventRegistration, \
    UserTimeLog, \
    AdminActionUserTime, \
    Transaction, \
    TransactionAction

import pytz


class OcUser(object):
    def __init__(self, userid=None):
        self.userid = userid

    def setup_user(self, username, email, first_name=None, last_name=None):
        user = User(username=username, email=email)
        if first_name:
            user.first_name = first_name

        if last_name:
            user.last_name = last_name
        user.save()

        account = Account()
        account.save()
        UserEntity.objects.create(user=user, account=account)
        return user

    def get_events_registered(self, *argv):
        assert(self.userid)

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
        '''
        TODO: replace with a call to a ledger-based method
        '''
        assert(self.userid)

        usertimelogs = UserTimeLog.objects.filter(
            user_id=self.userid
        ).filter(
            is_verified=True
        )

        balance = self._get_unique_hour_total(usertimelogs)
        return balance

    def get_balance_pending(self):
        assert(self.userid)

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

    def get_offers_redeemed(self):
        # user's transcations
        transactions = Transaction.objects.filter(
            user=self.userid
        ).annotate(
            last_action_created=Max('transactionaction__date_created')
        )

        # latest transaction status
        transaction_actions = TransactionAction.objects.filter(
            date_created__in=[
                tr.last_action_created for tr in transactions
            ]
        )

        return transaction_actions
