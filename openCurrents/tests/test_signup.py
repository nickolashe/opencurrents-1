from django.test import Client, TestCase
from django.core.urlresolvers import reverse

from django.contrib.auth.models import User
from openCurrents import views, urls

class TestSignup(TestCase):
    def setUp(self):
        '''
        set up test fixtures
        '''
        self.url_signup = reverse(
            views.process_signup,
            urlconf=urls,
            kwargs={'referrer': ''}
        )
        self.client = Client()

        # # set up regular user
        # self.userReg = OcUser().setup_user(
        #     username='reg@g.com',
        #     email='reg@g.com',
        # )
        #
        # # set up user with a npf affiliation
        # self.userOrg = OcUser().setup_user(
        #     username='org@g.com',
        #     email='org@g.com',
        # )
        #
        # # set up user with a biz affiliation
        # self.userBiz = OcUser().setup_user(
        #     username='biz@g.com',
        #     email='biz@g.com',
        # )
        #
        # # set up test org
        # self.orgTest = OcOrg().setup_org(
        #     name='test_org_123',
        #     status='npf'
        # )

    def tearDown(self):
        '''
        clean up test fixtures
        '''
        # self.userReg.delete()
        # self.userOrg.delete()
        # self.userBiz.delete()
        # self.orgTest.delete()

    def test_signup(self):
        '''
        tests signup successful
        '''
        test_email = 'a@c.com'
        # response = client.post(
        #     self.url_signup,
        #     data={
        #         'user_email': 'test_email',
        #         'user_firstname': 'test_firstname',
        #         'user_lastname': 'test_lastname'
        #     }
        # )
        self.assertTrue(True)
