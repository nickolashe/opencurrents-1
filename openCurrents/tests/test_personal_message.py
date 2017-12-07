from django.test import Client, TestCase
from django.contrib.auth.models import User
from django.core import mail
from django.shortcuts import redirect

from openCurrents.models import Org

from openCurrents.interfaces.ocuser import OcUser
from openCurrents.interfaces.orgs import \
    OcOrg, \
    OrgUserInfo


class TestPersonalMessageAdmin(TestCase):

    def setUp(self):

        # creating org
        org = OcOrg().setup_org(name="NPF_org_1", status="npf")

        # volunteer user
        volunteer1 = OcUser().setup_user(
            username='test_user_1',
            email='test_user_1@e.com',
        )

        # npf admin
        npf_admin_1 = OcUser().setup_user(
            username='npf_admin_1',
            email='npf_admin_1@g.com',
        )
        oui = OrgUserInfo(npf_admin_1.id)
        oui.setup_orguser(org)
        oui.make_org_admin(org.id)

        for user in User.objects.all():
            user.set_password('password')
            user.save()


         # setting up client
        self.client = Client()
        #npf_admin_1 = User.objects.get(username="npf_admin_1")
        self.client.login(username=npf_admin_1.username, password='password')
        self.response = self.client.get('/invite-volunteers/')


    def test_personal_message_post_single_no_message(self):

        self.assertEqual(self.response.status_code, 200)

        # posting form
        response = self.client.post("/invite-volunteers/", {
            'vol-name-1':'test_guest_1',
            'vol-email-1':'single_test_guest_1@mail.cc',
            'bulk-vol':'',
            'count-vol':'1',
            'personal_message':'',
            })

        # assert if we've been redirected
        self.assertRedirects(response, '/org-admin/1/', status_code=302)

        # assert a user was created
        self.assertTrue(User.objects.get(username='single_test_guest_1@mail.cc'), 'single_test_guest_1@mail.cc')


    def test_personal_message_post_bulk_no_message(self):

        self.assertEqual(self.response.status_code, 200)

        # posting form
        self.response = self.client.post("/invite-volunteers/", {
            'bulk-vol':'bulk_test_guest_1@e.cc, bulk_test_guest_2@e.cc, bulk_test_guest_3@e.cc, bulk_test_guest_4@e.cc',
            'personal_message':'',
            })

        # assert if we've been redirected
        self.assertRedirects(self.response, '/org-admin/4/', status_code=302)

        # assert new users were created
        self.assertEqual(len(User.objects.filter(username__contains='bulk_test_guest_')), 4)


    def test_personal_message_post_single_with_personal_message(self):

        self.assertEqual(self.response.status_code, 200)

        # posting form
        response = self.client.post("/invite-volunteers/", {
            'vol-name-1':'test_guest_1',
            'vol-email-1':'single_test_guest_1@mail.cc',
            'bulk-vol':'',
            'count-vol':'1',
            'personal_message':'Test msg',
            })

        # assert if we've been redirected
        self.assertRedirects(response, '/org-admin/1/', status_code=302)


    def test_personal_message_post_bulk_with_personal_message(self):

        self.response = self.client.get('/invite-volunteers/')

        self.assertEqual(self.response.status_code, 200)

        # posting form
        response = self.client.post("/invite-volunteers/", {
            'bulk-vol':'bulk_test_guest_1@e.cc, bulk_test_guest_2@e.cc, bulk_test_guest_3@e.cc, bulk_test_guest_4@e.cc',
            'personal_message':'Test msg 2',
            })

        # assert if we've been redirected
        self.assertRedirects(response, '/org-admin/4/', status_code=302)

