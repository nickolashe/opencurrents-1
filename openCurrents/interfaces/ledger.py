from datetime import datetime, timedelta
from itertools import chain

from django.db.models import Q, Sum
from openCurrents.models import \
    Entity, \
    UserEntity, \
    OrgEntity, \
    Ledger, \
    AdminActionUserTime, \
    TransactionAction

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
            is_issued=False
    ):
        entity_from = self._get_entity(entity_id_from, entity_type_from)

        # check for sufficient funds
        balance_from = self.get_balance(entity_from.id, entity_type_from)

        if not is_issued and balance_from < amount:
            raise InsufficientFundsException()

        entity_to = self._get_entity(entity_id_to, entity_type_to)
        ledger_rec = Ledger(
            entity_from=entity_from,
            entity_to=entity_to,
            amount=amount,
            is_issued=is_issued
        )

        # TODO: refactor using a joint table for actions
        if isinstance(action, AdminActionUserTime):
            ledger_rec.action = action
        elif isinstance(action, TransactionAction):
            ledger_rec.transaction = action
        #logger.info(ledger_rec)

        ledger_rec.save()

    def issue_currents(
            self,
            entity_id_from,
            entity_id_to,
            action,
            amount,
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
            is_issued=True
        )

    def add_fiat(self, id_to, type='usd'):
        pass

    def remove_fiat(self, id_from, type='usd'):
        pass

    def get_balance(self, entity_id, entity_type='user', currency='cur'):
        entity = self._get_entity(entity_id, entity_type)

        debit = Ledger.objects.filter(
            entity_from__id=entity.id,
            is_issued=False,
            currency=currency
        ).aggregate(total=Sum('amount'))

        debit_total = debit['total'] if debit['total'] else 0

        credit = Ledger.objects.filter(
            entity_to__id=entity.id,
            currency=currency
        ).aggregate(total=Sum('amount'))

        credit_total = credit['total'] if credit['total'] else 0

        total = credit_total - debit_total

        if total > 0:
            if currency == 'usd':
                total = round(total, 2)
            else:
                total = round(total, 3)

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
                action__date_created__gte=last_month
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


class InvalidEntityException(Exception):
    pass


class InsufficientFundsException(Exception):
    pass

class UnsupportedAggregate(Exception):
    pass
