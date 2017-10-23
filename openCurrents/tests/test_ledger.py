from django.test import TestCase
from django.contrib.auth.models import User

from openCurrents.models import \
    Org, \
    Entity, \
    Account, \
    UserEntity, \
    OrgEntity, \
    BizEntity, \
    Ledger

from openCurrents.interfaces.ledger import OcLedger, InsufficientFundsException
from openCurrents.interfaces.ocuser import OcUser


class TestOcLedger(TestCase):
    def setUp(self):
        self.ledger = OcLedger()

        # regular user
        self.userReg = OcUser().setup_user(
            username='reg@g.com',
            email='reg@g.com',
        )

        # user with a npf affiliation
        self.userOrg = OcUser().setup_user(
            username='org@g.com',
            email='org@g.com',
        )

        # user with a biz affiliation
        self.userBiz = OcUser().setup_user(
            username='biz@g.com',
            email='biz@g.com',
        )

        self.orgTest = Org(name='test', status='npf')
        self.orgTest.save()
        account = Account()
        account.save()
        OrgEntity.objects.create(org=self.orgTest, account=account)

        # issue currents to userReg
        self.ledger.issue_currents(
            entity_id_from=self.orgTest.orgentity.id,
            entity_id_to=self.userReg.userentity.id,
            amount=1
        )

    def tearDown(self):
        self.userReg.delete()
        self.userOrg.delete()
        self.userBiz.delete()
        Ledger.objects.all().delete()

    def test_initial_balance(self):
        self.assertEqual(
            self.ledger.get_balance(self.userReg.userentity.id),
            1
        )
        self.assertEqual(
            self.ledger.get_balance(self.userOrg.userentity.id),
            0
        )

        # issued currents not counted towards balances
        self.assertEqual(
            self.ledger.get_balance(self.orgTest.orgentity.id, 'org'),
            0
        )

    def test_transact_user_user(self):
        self.ledger.transact_currents(
            entity_type_from='user',
            entity_id_from=self.userReg.userentity.id,
            entity_type_to='user',
            entity_id_to=self.userOrg.userentity.id,
            amount=1,
        )
        self.assertEqual(
            self.ledger.get_balance(self.userReg.userentity.id),
            0
        )
        self.assertEqual(
            self.ledger.get_balance(self.userOrg.userentity.id),
            1
        )
        self.assertEqual(
            self.ledger.get_balance(self.orgTest.orgentity.id, 'org'),
            0
        )

    def test_insufficient_funds(self):
        def _insufficient_funds_transaction():
            self.ledger.transact_currents(
                entity_type_from='user',
                entity_id_from=self.userReg.userentity.id,
                entity_type_to='user',
                entity_id_to=self.userOrg.userentity.id,
                amount=100
            )

        self.assertRaises(
            InsufficientFundsException,
            _insufficient_funds_transaction
        )
