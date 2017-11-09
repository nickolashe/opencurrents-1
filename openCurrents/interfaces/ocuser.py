from datetime import datetime

from django.contrib.auth.models import User
from django.db.models import Max

from openCurrents.models import \
    UserEntity, \
	UserEventRegistration, \
    UserSettings, \
    UserTimeLog, \
    AdminActionUserTime, \
    Transaction, \
    TransactionAction

from openCurrents.interfaces import common
from openCurrents.interfaces import convert
from openCurrents.interfaces.ledger import OcLedger

import pytz
import logging

logging.basicConfig(level=logging.DEBUG, filename="log/views.log")
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class OcUser(object):
    def __init__(self, userid=None):
        self.userid = userid
        self.user = None

        if self.userid:
            try:
                self.user = User.objects.get(id=self.userid)
            except Exception as e:
                raise InvalidUserException

    def setup_user(self, username, email, first_name=None, last_name=None):
        user = None
        try:
            user = User(username=username, email=email)
            if first_name:
                user.first_name = first_name

            if last_name:
                user.last_name = last_name
            user.save()
        except Exception as e:
            self.user = User.objects.get(username=username)
            raise UserExistsException

        UserSettings.objects.create(user=user)
        UserEntity.objects.create(user=user)

        self.user = user

        return user

    def get_user(self):
        if self.user:
            return self.user
        else:
            raise InvalidUserException

    def update_user(self, first_name=None, last_name=None):
        user = self.get_user()

        if first_name:
            user.first_name = first_name

        if last_name:
            user.last_name = last_name

        user.save()
        self.user = user

    def get_user_entity(self):
        if self.user:
            return self.user.userentity
        else:
            raise InvalidUserException

    def get_events_registered(self, *argv):
        if not self.userid:
            raise InvalidUserException

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
        report total available currents
            - balance based on ledger
            - minus redeemed offers
        '''
        if not self.userid:
            raise InvalidUserException

        current_balance = OcLedger().get_balance(
            entity_id=self.user.userentity.id,
            entity_type='user'
        )

        # offer redemption requests
        redemption_reqs = Transaction.objects.filter(
            user__id=self.userid
        ).annotate(
            last_action_created=Max('transactionaction__date_created')
        )

        active_redemption_reqs = TransactionAction.objects.filter(
            date_created__in=[
                req.last_action_created for req in redemption_reqs
            ]
        ).filter(
            action_type='req'
        )

        total_redemptions = common._get_redemption_total(
            active_redemption_reqs
        )

        return current_balance - total_redemptions

    def get_balance_pending(self):
        '''
        report total pending currents
            - based on requested hours
        '''
        if not self.userid:
            raise InvalidUserException

        usertimelogs = UserTimeLog.objects.filter(
            user_id=self.userid
        ).filter(
            is_verified=False
        ).annotate(
            last_action_created=Max('adminactionusertime__date_created')
        )

        # pending requests
        active_hour_reqs = AdminActionUserTime.objects.filter(
            date_created__in=[
                utl.last_action_created for utl in usertimelogs
            ]
        ).filter(
            action_type='req'
        )

        total_hour = self._get_unique_hour_total(
            active_hour_reqs,
            from_admin_actions=True
        )

        return total_hour

    def get_balance_available_usd(self):
        '''
        available usd balance is composed of:
            - transactions in ledger
        '''
        balance_usd = OcLedger().get_balance(
            entity_id=self.user.userentity.id,
            entity_type='user',
            currency='usd'
        )

        return balance_usd

    def get_balance_pending_usd(self):
        '''
        pending usd balance is composed of:
            - requested and accepted redemptions
            - redemptions in status redeemed do not count
        '''
        redemption_reqs = Transaction.objects.filter(
            user__id=self.userid
        ).annotate(
            last_action_created=Max('transactionaction__date_created')
        )

        active_redemption_reqs = TransactionAction.objects.filter(
            date_created__in=[
                req.last_action_created for req in redemption_reqs
            ]
        ).filter(
            action_type__in=['req', 'app']
        )

        total_redemptions = common._get_redemption_total(
            active_redemption_reqs,
            'usd'
        )

        return total_redemptions

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
        if not self.userid:
            raise InvalidUserException

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


class UserExistsException(Exception):
	pass

class InvalidUserException(Exception):
	pass
