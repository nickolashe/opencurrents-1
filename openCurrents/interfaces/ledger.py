from datetime import datetime, timedelta
from itertools import chain

from django.db.models import Q, Sum
from openCurrents.models import (
    Org,
    Entity,
    UserEntity,
    OrgEntity,
    Ledger,
    AdminActionUserTime,
    TransactionAction
)

from django.contrib.auth.models import User

import logging
import pytz


logging.basicConfig(level=logging.DEBUG, filename="log/views.log")
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class OcLedger(object):
    '''
    Ledger of completed transactions
    '''

    def _get_entity(self, entity_id, entity_type='user'):
        '''
        entity_type (user | org)
        '''
        valid_entity_types = ['user', 'org']
        try:
            assert (entity_type in valid_entity_types)

            if entity_type == 'user':
                entity = UserEntity.objects.get(id=entity_id)
            elif entity_type == 'org':
                entity = OrgEntity.objects.get(id=entity_id)

            return entity

        except Exception as e:
            raise InvalidEntityException()

    def transact_currents(
            self,
            entity_type_from,
            entity_id_from,
            entity_type_to,
            entity_id_to,
            action,
            amount,
            is_issued=False,
            is_bonus=False
    ):
        entity_from = self._get_entity(entity_id_from, entity_type_from)

        # check for sufficient funds
        balance_from = self.get_balance(entity_from.id, entity_type_from)

        # check for sufficient balance
        if not is_issued and balance_from < amount:
            raise InsufficientFundsException()

        entity_to = self._get_entity(entity_id_to, entity_type_to)

        # check for previously issued bonus
        if is_bonus and self.has_bonus(entity_to):
            raise DuplicateBonusException()

        ledger_rec = Ledger(
            entity_from=entity_from,
            entity_to=entity_to,
            amount=amount,
            is_issued=is_issued,
            is_bonus=is_bonus
        )

        if isinstance(action, AdminActionUserTime):
            ledger_rec.action = action
        elif isinstance(action, TransactionAction):
            ledger_rec.transaction = action
        # logger.info(ledger_rec)

        ledger_rec.save()

    def issue_currents(
            self,
            entity_id_from,
            entity_id_to,
            action,
            amount,
            is_bonus=False,
            entity_type_to='user',
            entity_type_from='org',
    ):
        self.transact_currents(
            entity_type_from,
            entity_id_from,
            entity_type_to,
            entity_id_to,
            action,
            amount,
            is_issued=True,
            is_bonus=is_bonus
        )

    def transact_fiat(
        self,
        entity_from,
        entity_to,
        amount,
        tr_action=None,
        currency='usd'
    ):
        ledger_rec = Ledger(
            entity_from=entity_from,
            entity_to=entity_to,
            amount=amount,
            currency=currency,
        )

        logger.info(tr_action)

        if tr_action and not isinstance(tr_action, TransactionAction):
            raise Exception('Invalid transaction reference')
        else:
            ledger_rec.transaction = tr_action

        ledger_rec.save()

    def transact_usd_user_oc(self, userid, amount, tr_action=None):
        entity_user = User.objects.get(id=userid).userentity
        entity_oc = Org.objects.get(name='openCurrents').orgentity

        self.transact_fiat(entity_user, entity_oc, amount, tr_action)

    def get_balance(self, entity_id, entity_type='user', currency='cur'):
        entity = self._get_entity(entity_id, entity_type)

        debit = Ledger.objects.filter(
            entity_from__id=entity.id,
            is_issued=False,
            currency=currency,
        ).exclude(
            transaction__transaction__offer__offer_type='gft'
        ).aggregate(total=Sum('amount'))

        debit_total = debit['total'] if debit['total'] else 0

        credit = Ledger.objects.filter(
            entity_to__id=entity.id,
            currency=currency
        ).aggregate(total=Sum('amount'))

        credit_total = credit['total'] if credit['total'] else 0

        total = credit_total - debit_total

        return total

    def get_issued_cur_amount(self, org_id, period):
        entity_id = OrgEntity.objects.get(org__id=org_id).id
        queryset = Ledger.objects.filter(
            entity_from__id=entity_id,
            currency='cur',
            is_issued=True
        )
        queryset = self._filter_queryset_by_period(queryset, period)

        return queryset.aggregate(total=Sum('amount'))

    def get_accepted_cur_amount(self, org_id, period):
        entity_id = OrgEntity.objects.get(org__id=org_id).id
        queryset = Ledger.objects.filter(
            entity_to__id=entity_id,
            currency='cur',
            is_issued=False
        )
        queryset = self._filter_queryset_by_period(queryset, period)

        return queryset.aggregate(total=Sum('amount'))

    def get_earned_cur_amount(self, user_id, period):
        entity_id = UserEntity.objects.get(user__id=user_id).id
        queryset = Ledger.objects.filter(
            entity_to__id=entity_id,
            currency='cur',
            is_issued=True
        )
        queryset = self._filter_queryset_by_period(queryset, period)

        return queryset.aggregate(total=Sum('amount'))

    def _filter_queryset_by_period(self, queryset, period):
        if period == 'month':
            last_month = datetime.now(tz=pytz.utc) - timedelta(days=30)
            query_date_filter_hours = Q(action__isnull=False)
            queryset_hours = queryset.filter(
                query_date_filter_hours
            ).filter(
                action__usertimelog__event__datetime_start__gte=last_month
            )

            query_date_filter_transactions = Q(transaction__isnull=False)
            queryset_transactions = queryset.filter(
                query_date_filter_transactions
            ).filter(
                transaction__date_created__gte=last_month
            )

            if queryset and not (queryset_hours or queryset_transactions):
                logger.warning('Legacy ledger: %s', queryset)

            return queryset_hours | queryset_transactions
        elif period == 'all-time':
            return queryset
        else:
            raise UnsupportedAggregate()

    def has_bonus(self, entity):
        return Ledger.objects.filter(
            entity_to=entity
        ).filter(
            is_bonus=True
        ).exists()

    def has_transactions(self, entity):
        return Ledger.objects.filter(
            entity_to=entity
        ).exists()


class InvalidEntityException(Exception):
    def __init__(self):
        super(InvalidEntityException, self).__init__(
            'Invalid entity type: user or org types supported'
        )


class InsufficientFundsException(Exception):
    def __init__(self):
        super(InsufficientFundsException, self).__init__(
            'Pay has insufficient funds'
        )


class DuplicateBonusException(Exception):
    def __init__(self):
        super(DuplicateBonusException, self).__init__(
            'Entity has already been issued bonus'
        )


class NoBonusException(Exception):
    def __init__(self):
        super(NoBonusException, self).__init__(
            'Entity already has currents - no bonus'
        )


class UnsupportedAggregate(Exception):
    def __init__(self):
        super(UnsupportedAggregate, self).__init__(
            'Invalid public record aggregation period'
        )
