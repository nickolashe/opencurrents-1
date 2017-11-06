from django.test import Client, TestCase, TransactionTestCase
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse

from openCurrents import views, urls
from openCurrents.interfaces.ocuser import OcUser
from openCurrents.interfaces.orgs import OcOrg
from openCurrents.models import Token

import pytz
import uuid

from datetime import datetime, timedelta

class TestSignup(TransactionTestCase):
    def setUp(self):
        '''
        set up test fixtures
        '''
        _TEST_UUID = uuid.uuid4()

        # urls tested
        self.url_signup = reverse(
            'process_signup',
            urlconf=urls,
            kwargs={'mock_emails': 1}
        )

        self.client = Client()

        # set up regular user
        userRegEmail = 'reg_%s@test.oc' % _TEST_UUID
        self.userReg = OcUser().setup_user(
            username=userRegEmail,
            email=userRegEmail,
        )

        # set up user with a npf affiliation
        userOrgEmail = 'org_%s@test.oc' % _TEST_UUID
        self.userOrg = OcUser().setup_user(
            username=userOrgEmail,
            email=userOrgEmail,
        )

        # set up user with a biz affiliation
        userBizEmail = 'biz_%s@test.oc' % _TEST_UUID
        self.userBiz = OcUser().setup_user(
            username=userBizEmail,
            email=userBizEmail,
        )

        # set up test org
        self.orgTest = OcOrg().setup_org(
            name='test_org_%s' % _TEST_UUID,
            status='npf'
        )

        # user email used in tests
        self.test_email = 'test_%s@email.com' % _TEST_UUID
        Token.objects.filter(email=self.test_email).delete()

    def tearDown(self):
        '''
        clean up test fixtures
        '''
        self.userReg.delete()
        self.userOrg.delete()
        self.userBiz.delete()
        self.orgTest.delete()

        User.objects.filter(username=self.test_email).delete()
        Token.objects.filter(email=self.test_email).delete()

    def _assert_user(self, username, is_true):
        does_exist = User.objects.filter(username=username).exists()
        if is_true:
            self.assertTrue(does_exist)
        else:
            self.assertFalse(does_exist)

    def _assert_user_has_usable_password(self, username, is_true):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.assertFalse(is_true)

        has_usable_password = user.has_usable_password()
        if is_true:
            self.assertTrue(has_usable_password)
        else:
            self.assertFalse(has_usable_password)

    def _assert_token_valid(self, username, is_true):
        nowish = datetime.now(tz=pytz.utc) - timedelta(seconds=3)
        tokens = Token.objects.filter(
            email=username,
            is_verified=False,
            token_type='signup',
            date_created__gte=nowish,
            date_expires__gte=nowish + timedelta(days=6),
            date_expires__lte=nowish + timedelta(days=8)
        )

        if is_true:
            self.assertTrue(tokens.exists())
        else:
            self.assertFalse(tokens.exists())

    def test_signup_user_new(self):
        '''
        test signup successful for a new user
            - user should be created
            - user should have no password set
            - token should have been generated
        '''
        self._assert_user(self.test_email, False)
        self._assert_token_valid(self.test_email, False)

        response = self.client.post(
            self.url_signup,
            data={
                'user_email': self.test_email,
                'user_firstname': 'test_firstname',
                'user_lastname': 'test_lastname'
            }
        )
        self._assert_user(self.test_email, True)
        self._assert_user_has_usable_password(self.test_email, False)
        self._assert_token_valid(self.test_email, True)

        url_check_email = reverse(
            'check-email',
            urlconf=urls,
            kwargs={'user_email': self.test_email}
        )
        self.assertRedirects(response, url_check_email)

    def test_signup_user_existing_no_password(self):
        '''
        tests signup successful for existing user without password
        '''
        self._assert_user(self.userReg.username, True)
        self._assert_user_has_usable_password(self.userReg.username, False)

        response = self.client.post(
            self.url_signup,
            data={
                'user_email': self.userReg.email,
                'user_firstname': 'test_firstname',
                'user_lastname': 'test_lastname'
            }
        )
        self._assert_user(self.userReg.email, True)
        self._assert_user_has_usable_password(self.userReg.email, False)
        self._assert_token_valid(self.userReg.email, True)

        # check first and last name were updated
        user = User.objects.get(username=self.userReg.username)
        self.assertEqual(user.first_name, 'test_firstname')
        self.assertEqual(user.last_name, 'test_lastname')

        url_check_email = reverse(
            'check-email',
            urlconf=urls,
            kwargs={'user_email': self.userReg.email}
        )
        self.assertRedirects(response, url_check_email)

    # def test_signup_user_existing_with_password(self):
    #     '''
    #     tests signup successful for existing user without password
    #     '''
    #     self._assert_user(self.userReg.username, True)
    #     self._assert_user_has_usable_password(self.userReg.username, False)
    #
    #     self.userReg.set_password(uuid.uuid4())
    #     self.userReg.save()
    #     self._assert_user_has_usable_password(self.userReg.username, True)
    #
    #     response = self.client.post(
    #         self.url_signup,
    #         data={
    #             'user_email': self.userReg.email,
    #             'user_firstname': 'test_firstname',
    #             'user_lastname': 'test_lastname'
    #         }
    #     )
    #
    #     url_check_email = reverse(
    #         'login',
    #         urlconf=urls,
    #         kwargs={'user_email': self.userReg.email}
    #     )
    #     self.assertRedirects(response, url_check_email)
