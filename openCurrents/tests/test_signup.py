"""Unit testing signup."""
from django.test import Client, TestCase, TransactionTestCase
from django.contrib.auth.models import User, Group
from django.core.urlresolvers import reverse
from django.contrib import messages

from openCurrents import views, urls
from openCurrents.interfaces.ocuser import OcUser
from openCurrents.interfaces.orgs import OcOrg, OrgUserInfo
from openCurrents.models import Org, OrgUser, Token

import pytz
import uuid

from datetime import datetime, timedelta


class TestSignup(TransactionTestCase):
    """Main test class."""

    def setUp(self):
        """Set up test fixtures."""
        _TEST_UUID = uuid.uuid4()

        # urls tested
        self.url_signup = reverse(
            'process_signup',
            urlconf=urls,
            kwargs={'mock_emails': 1}
        )

        self.url_signup_endpoint = reverse(
            'process_signup',
            urlconf=urls,
            kwargs={'mock_emails': 1, 'endpoint': True}
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
            name='test_org_existing',
            status='npf'
        )

        # link org user to test org
        OrgUserInfo(self.userOrg.id).setup_orguser(self.orgTest)

        # user email used in tests
        self.test_email = 'test_%s@email.com' % _TEST_UUID
        Token.objects.filter(email=self.test_email).delete()

        # org users in tests
        self.test_org_name = 'test_org_%s' % _TEST_UUID

    def tearDown(self):
        """Clear up test fixtures."""
        self.userReg.delete()
        self.userOrg.delete()
        self.userBiz.delete()
        self.orgTest.delete()

        User.objects.filter(username=self.test_email).delete()
        Token.objects.filter(email=self.test_email).delete()

        org = None
        try:
            org = Org.objects.get(name=self.test_org_name)
        except Exception:
            pass

        # delete org admin group
        if org:
            Group.objects.filter(name='admin_%s' % org.name).delete()

        Org.objects.filter(name=self.test_org_name).delete()

    def _assert_user(self, username, is_true):
        '''
        assert user exists
        '''
        users = User.objects.filter(username=username)
        does_exist = users.exists()
        if is_true:
            self.assertTrue(does_exist)
            return users[0]
        else:
            self.assertFalse(does_exist)
            return None

    def _assert_user_has_usable_password(self, username, is_true):
        '''
        assert user exists and has a password set
        '''
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.assertFalse(is_true)

        has_usable_password = user.has_usable_password()
        if is_true:
            self.assertTrue(has_usable_password)
        else:
            self.assertFalse(has_usable_password)

    def _assert_num_users(self, user_email, num_users):
        '''
        assert number of user for a given email
        '''
        users = User.objects.filter(email=user_email)
        self.assertEqual(len(users), num_users)

    def _assert_token_valid(self, username, is_true):
        '''
        assert valid verification token was generated
            - unverified
            - type signup
            - timestamp recent enough
        '''
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

    def _assert_org(self, org_name, org_status, is_true):
        '''
        assert org exists and is unique
        '''
        orgs = Org.objects.filter(name=org_name)
        if is_true:
            self.assertTrue(orgs.exists())
            self.assertEqual(len(orgs), 1)
            self.assertEqual(orgs[0].status, org_status)
            return orgs[0]
        else:
            self.assertFalse(orgs.exists())

    def _assert_org_user(self, org_name, user_email, is_true):
        '''
        assert orguser association exists and is unique
        '''
        orgusers = OrgUser.objects.filter(
            org__name=org_name,
            user__email=user_email
        )

        if is_true:
            self.assertTrue(orgusers.exists())
            self.assertEqual(len(orgusers), 1)
        else:
            self.assertFalse(orgusers.exists())

    def _assert_group(self, org_name, is_true):
        '''
        assert empty user group exists and is unique
        '''
        org = None
        try:
            org = Org.objects.get(name=org_name)
        except Exception as e:
            pass

        if is_true:
            self.assertTrue(org)
        else:
            self.assertFalse(org)

        groups = Group.objects.filter(name='admin_%s' % org.id)

        if is_true:
            self.assertTrue(groups.exists())
            self.assertEqual(len(groups), 1)

            if org.status == 'biz':
                self.assertEqual(len(groups[0].user_set.all()), 1)
            else:
                self.assertFalse(groups[0].user_set.all())
            return groups[0]
        else:
            self.assertFalse(groups.exists())



    def test_signup_user_new(self):
        '''
        test signup successful for a new user
            - user should be created
            - user should have no password set
            - token should have been generated
            - redirected to 'check-email'
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
            - new user not created
            - existing user should be used
            - user should have no password set
            - token should have been generated
            - redirected to 'check-email'
        '''
        self._assert_user(self.userReg.username, True)
        self._assert_num_users(self.userReg.email, 1)
        self._assert_user_has_usable_password(self.userReg.username, False)

        response = self.client.post(
            self.url_signup,
            data={
                'user_email': self.userReg.email,
                'user_firstname': 'test_firstname',
                'user_lastname': 'test_lastname'
            }
        )
        user = self._assert_user(self.userReg.email, True)
        self._assert_num_users(self.userReg.email, 1)
        self._assert_user_has_usable_password(self.userReg.email, False)
        self._assert_token_valid(self.userReg.email, True)

        # check first and last name were updated
        self.assertEqual(user.first_name, 'test_firstname')
        self.assertEqual(user.last_name, 'test_lastname')

        url_check_email = reverse(
            'check-email',
            urlconf=urls,
            kwargs={'user_email': self.userReg.email}
        )
        self.assertRedirects(response, url_check_email)

    def test_signup_user_existing_with_password(self):
        '''
        tests signup successful for existing user with password
            - new user not created
            - existing user should be used
            - token not generated
            - redirected to 'login'
        '''
        self._assert_user(self.userReg.username, True)
        self._assert_user_has_usable_password(self.userReg.username, False)
        self._assert_num_users(self.userReg.email, 1)
        self._assert_token_valid(self.userReg.email, False)

        # set password for user
        self.userReg.set_password(uuid.uuid4())
        self.userReg.save()
        self._assert_user_has_usable_password(self.userReg.username, True)

        response = self.client.post(
            self.url_signup,
            data={
                'user_email': self.userReg.email,
                'user_firstname': 'test_firstname',
                'user_lastname': 'test_lastname'
            }
        )

        self._assert_num_users(self.userReg.email, 1)
        self._assert_token_valid(self.userReg.email, False)

        url_login = reverse(
            'login',
            urlconf=urls,
            kwargs={
                'status_msg': 'User with this email already exists',
                'msg_type': 'alert'
            }
        )
        self.assertRedirects(response, url_login)

    def test_signup_user_org_npf_new(self):
        '''
        tests signup successful for new org user
            - new user created
            - token generated
            - org created
            - org user created
            - org admin group created
            - redirected to 'check-email' with org id
        '''
        self._assert_user(self.test_email, False)

        response = self.client.post(
            self.url_signup,
            data={
                'user_email': self.test_email,
                'user_firstname': 'test_firstname',
                'user_lastname': 'test_lastname',
                'org_name': self.test_org_name,
                'org_status': 'npf'
            }
        )

        self._assert_user(self.test_email, True)
        self._assert_user_has_usable_password(self.test_email, False)
        self._assert_token_valid(self.test_email, True)
        org = self._assert_org(self.test_org_name, 'npf', True)
        self._assert_org_user(self.test_org_name, self.test_email, True)
        self._assert_group(self.test_org_name, True)

        url_login = reverse(
            'check-email',
            urlconf=urls,
            kwargs={
                'user_email': self.test_email,
                'orgid': org.id
            }
        )
        self.assertRedirects(response, url_login)

    def test_signup_user_org_biz_new(self):
        '''
        tests signup successful for new biz user
            - new user created
            - token generated
            - biz org created
            - biz org user created
            - biz admin group created
            - redirected to 'check-email' with org id
        '''
        self._assert_user(self.test_email, False)

        response = self.client.post(
            self.url_signup,
            data={
                'user_email': self.test_email,
                'user_firstname': 'test_firstname',
                'user_lastname': 'test_lastname',
                'org_name': self.test_org_name,
                'org_status': 'biz'
            }
        )

        self._assert_user(self.test_email, True)
        self._assert_user_has_usable_password(self.test_email, False)
        self._assert_token_valid(self.test_email, True)
        org = self._assert_org(self.test_org_name, 'biz', True)
        self._assert_org_user(self.test_org_name, self.test_email, True)
        self._assert_group(self.test_org_name, True)

        # url_login = reverse(
        #     'check-email',
        #     urlconf=urls,
        #     kwargs={
        #         'user_email': self.test_email,
        #         'orgid': org.id
        #     }
        # )
        url_redirect = reverse(
            'offer',
            urlconf=urls,
        )
        self.assertRedirects(response, url_redirect)

    def test_signup_user_org_existing(self):
        '''
        tests signup fails for invalid org
            - new user created
            - token generated
            - biz org not created
            - biz org user not created
            - biz admin group not created
            - redirected to 'nonprofit' with proper status message
        '''
        self._assert_user(self.test_email, False)
        self._assert_org(self.orgTest.name, 'npf', True)

        response = self.client.post(
            self.url_signup,
            data={
                'user_email': self.test_email,
                'user_firstname': 'test_firstname',
                'user_lastname': 'test_lastname',
                'org_name': self.orgTest.name,
                'org_status': 'npf'
            }
        )

        self._assert_user(self.test_email, False)  # we don't create a user if org exists
        self._assert_token_valid(self.test_email, False)
        self._assert_org_user(self.orgTest.name, self.test_email, False)

        status_message = 'Organization named %s already exists!' % self.orgTest.name
        warning_messages = list(response.wsgi_request._messages)

        self.assertEqual(warning_messages[0].message, status_message)
        self.assertIn('alert', warning_messages[0].tags)

        url_nonprofit = reverse(
            'home',
            urlconf=urls,
        ) + '#signup'
        self.assertRedirects(response, url_nonprofit)

    def test_signup_livedashboard_optin(self):
        '''
        test signup from live dashboard with optin
            - user created
            - user no password set
            - token not generated
            - response status code 201 with user id
        '''
        self._assert_user(self.test_email, False)
        self._assert_token_valid(self.test_email, False)

        response = self.client.post(
            self.url_signup_endpoint,
            data={
                'user_email': self.test_email,
                'user_firstname': 'test_firstname',
                'user_lastname': 'test_lastname',
                'org_admin_id': self.userOrg.id
            }
        )
        user = self._assert_user(self.test_email, True)
        self._assert_user_has_usable_password(self.test_email, False)
        self._assert_token_valid(self.test_email, False)

        self.assertEqual(int(response.status_code), 201)
        self.assertEqual(int(response.content), user.id)
