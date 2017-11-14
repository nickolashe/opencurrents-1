from django.db.models import Sum
from openCurrents.models import \
    Entity, \
    UserEntity, \
    OrgEntity, \
    Ledger

import logging

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
            assert(entity_type in valid_entity_types)

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
        logger.info(ledger_rec)

        ledger_rec.save()

    def issue_currents(
        self,
        entity_id_from,
        entity_id_to,
        amount,
        entity_type_to='user',
        entity_type_from='org',
    ):
        self.transact_currents(
            entity_type_from,
            entity_id_from,
            entity_type_to,
            entity_id_to,
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

        return credit_total - debit_total


class InvalidEntityException(Exception):
	pass

class InsufficientFundsException(Exception):
	pass
