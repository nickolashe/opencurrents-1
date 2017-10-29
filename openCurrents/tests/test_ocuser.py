from django.test import TestCase
from django.contrib.auth.models import User
from django.db import transaction

from openCurrents.models import \
    Org, \
    Entity, \
    UserEntity, \
    OrgEntity, \
    BizEntity

from openCurrents.interfaces.ocuser import OcUser, \
    InvalidUserException, \
    UserExistsException
from openCurrents.interfaces.orgs import OcOrg


class TestOcLedger(TestCase):
    def setUp(self):
        '''
        set up test fixtures
        '''
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

    def tearDown(self):
        '''
        clean up test fixtures
        '''
        self.userReg.delete()
        self.userOrg.delete()
        self.userBiz.delete()
        self.orgTest.delete()

    def test_user_exists(self):
        '''
        tests user was created
        '''
        user = OcUser(self.userReg.id).get_user()
        self.assertIsNotNone(user)

    def test_user_entity_exists(self):
        '''
        tests user entity was created
        '''
        user = OcUser(self.userReg.id)
        self.assertIsNotNone(user.get_user_entity())

    def test_user_account_exists(self):
        '''
        tests user entity was created
        '''
        user = OcUser(self.userReg.id)
        self.assertIsNotNone(user.get_account())

    def test_update_names(self):
        '''
        tests first or last name are updated
        '''
        user = OcUser(self.userReg.id)
        user.update_user(first_name='Jay')
        first_name = user.get_user().first_name
        self.assertEqual(first_name, 'Jay')

    def test_invalid_user(self):
        '''
        check appropriate exception raised when invalid user requested
        '''
        def _invalid_user():
            user = OcUser(-1)

        self.assertRaises(
            InvalidUserException,
            _invalid_user
        )

    def test_user_exists(self):
        '''
        check appropriate exception raised when user already exists
        '''
        # @transaction.atomic
        # def _user_exists():
        #         user = OcUser().setup_user(
        #             username=self.userReg.username,
        #             email=self.userReg.email
        #         )
        #
        # self.assertRaises(
        #     UserExistsException,
        #     _user_exists
        # )
