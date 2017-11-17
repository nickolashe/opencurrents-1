from django.test import TestCase
from django.contrib.auth.models import User

from openCurrents.models import \
    Org, \
    Project, \
    Event, \
    Entity, \
    UserEntity, \
    OrgEntity, \
    Ledger, \
    UserTimeLog, \
    AdminActionUserTime

from openCurrents.interfaces.ledger import OcLedger, InsufficientFundsException
from openCurrents.interfaces.ocuser import OcUser
from openCurrents.interfaces.orgs import OcOrg

from datetime import datetime, timedelta


class TestOcLedger(TestCase):
    def setUp(self):
        '''
        set up test fixtures
        '''
        self.ledger = OcLedger()

        # set up regular user
        self.userReg = OcUser().setup_user(
            username='reg@g.com',
            email='reg@g.com',
        )

        # set up user with a npf affiliation
        self.userOrg = OcUser().setup_user(
            username='org@g.com',
            email='org@g.com',
        )

        # set up user with a biz affiliation
        self.userBiz = OcUser().setup_user(
            username='biz@g.com',
            email='biz@g.com',
        )

        # set up test org
        self.orgTest = OcOrg().setup_org(
            name='test_org_123',
            status='npf'
        )

        self.projectUserRegMT = Project(
            org=self.orgTest,
            name='MT by userReg'
        )
        self.projectUserRegMT.save()

        self.eventUserRegMT = Event(
            project=self.projectUserRegMT,
            description='MT by userReg',
            location='test',
            coordinator=self.userOrg,
            creator_id=self.userOrg.id,
            event_type='MN',
            datetime_start=datetime.now() - timedelta(hours=2),
            datetime_end=datetime.now() - timedelta(hours=1)
        )
        self.eventUserRegMT.save()

        self.userRegTimeLog = UserTimeLog(
            user=self.userReg,
            event=self.eventUserRegMT,
            is_verified=True,
            datetime_start=datetime.now(),
            datetime_end=datetime.now() + timedelta(hours=1)
        )
        self.userRegTimeLog.save()

        self.actionUserReg = AdminActionUserTime(
            user=self.userOrg,
            usertimelog=self.userRegTimeLog,
            action_type='app'
        )
        self.actionUserReg.save()

        # issue currents to userReg
        self.ledger.issue_currents(
            self.orgTest.orgentity.id,
            self.userReg.userentity.id,
            self.actionUserReg,
            1
        )

    def tearDown(self):
        '''
        clean up test fixtures
        '''
        self.userReg.delete()
        self.userOrg.delete()
        self.userBiz.delete()
        self.orgTest.delete()
        Ledger.objects.filter(
            entity_from__id__in=[
                self.userReg.userentity.id,
                self.userOrg.userentity.id,
                self.userBiz.userentity.id,
                self.orgTest.orgentity.id
            ]
        ).delete()

    def test_initial_balance(self):
        '''
        test initial balances correct after set up
        '''
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
        '''
        transact from one user to another and check balances
        '''
        self.ledger.transact_currents(
            entity_type_from='user',
            entity_id_from=self.userReg.userentity.id,
            entity_type_to='user',
            entity_id_to=self.userBiz.userentity.id,
            action=self.actionUserReg,
            amount=1,
        )
        self.assertEqual(
            self.ledger.get_balance(self.userReg.userentity.id),
            0
        )
        self.assertEqual(
            self.ledger.get_balance(self.userBiz.userentity.id),
            1
        )

    def test_insufficient_funds(self):
        '''
        check appropriate exception raised when sender has insufficient funds
        '''
        def _insufficient_funds_transaction():
            self.ledger.transact_currents(
                entity_type_from='user',
                entity_id_from=self.userReg.userentity.id,
                entity_type_to='user',
                entity_id_to=self.userOrg.userentity.id,
                action=self.actionUserReg,
                amount=100
            )

        self.assertRaises(
            InsufficientFundsException,
            _insufficient_funds_transaction
        )
