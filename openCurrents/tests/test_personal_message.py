from django.test import Client, TestCase
from django.contrib.auth.models import User
from django.shortcuts import redirect

from datetime import datetime, timedelta
from django.utils import timezone

# MODELS
from openCurrents.models import \
    Org, \
    Project, \
    Event

# INTERFACES
from openCurrents.interfaces.ocuser import OcUser
from openCurrents.interfaces.orgs import \
    OcOrg, \
    OrgUserInfo


class TestIvniteVolunteersNoEvent(TestCase):

    def setUp(self):

        # creating org
        self.org = OcOrg().setup_org(name="NPF_org_1", status="npf")

        # volunteer user
        self.volunteer1 = OcUser().setup_user(
            username='test_user_1',
            email='test_user_1@e.com',
        )

        # npf admin
        self.npf_admin_1 = OcUser().setup_user(
            username='npf_admin_1',
            email='npf_admin_1@g.com',
        )
        oui = OrgUserInfo(self.npf_admin_1.id)
        oui.setup_orguser(self.org)
        oui.make_org_admin(self.org.id)

        for user in User.objects.all():
            user.set_password('password')
            user.save()

        # setting up client
        self.client = Client()
        self.client.login(username=self.npf_admin_1.username, password='password')
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

        self.assertEqual(self.response.status_code, 200)

        # posting form
        response = self.client.post("/invite-volunteers/", {
            'bulk-vol':'bulk_test_guest_1@e.cc, bulk_test_guest_2@e.cc, bulk_test_guest_3@e.cc, bulk_test_guest_4@e.cc',
            'personal_message':'Test msg 2',
            })

        # assert if we've been redirected
        self.assertRedirects(response, '/org-admin/4/', status_code=302)




class TestIvniteVolunteersToEvent(TestCase):

    def setUp(self):

        # creating org
        self.org = OcOrg().setup_org(name="NPF_org_1", status="npf")

        # volunteer user
        self.volunteer1 = OcUser().setup_user(
            username='test_user_1',
            email='test_user_1@e.com',
        )

        # npf admin
        self.npf_admin_1 = OcUser().setup_user(
            username='npf_admin_1',
            email='npf_admin_1@g.com',
        )
        oui = OrgUserInfo(self.npf_admin_1.id)
        oui.setup_orguser(self.org)
        oui.make_org_admin(self.org.id)

        for user in User.objects.all():
            user.set_password('password')
            user.save()

        # creating a project
        self.project = Project(
            org=self.org,
            name="test_project_1"
        )
        self.project.save()


        # creating future event to invite a user
        self.event = Event(
            project=self.project,
            description="Future event",
            location="test_location_1",
            coordinator=self.npf_admin_1,
            event_type="GR",
            datetime_start=timezone.now() + timedelta(days=1),
            datetime_end=timezone.now() + timedelta(days=2),
            is_public=True
        )
        self.event.save()

        # setting up client
        self.client = Client()
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get('/invite-volunteers/1/')


    def test_personal_message_post_single_no_message(self):

        self.assertEqual(self.response.status_code, 200)

        self.assertIn('Invite volunteers', self.response.content)

        # posting form
        response = self.client.post("/invite-volunteers/1/", {
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
        self.response = self.client.post("/invite-volunteers/1/", {
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
        response = self.client.post("/invite-volunteers/1/", {
            'vol-name-1':'test_guest_1',
            'vol-email-1':'single_test_guest_1@mail.cc',
            'bulk-vol':'',
            'count-vol':'1',
            'personal_message':'Test msg',
            })

        # assert if we've been redirected
        self.assertRedirects(response, '/org-admin/1/', status_code=302)


    def test_personal_message_post_bulk_with_personal_message(self):

        self.assertEqual(self.response.status_code, 200)

        # posting form
        response = self.client.post("/invite-volunteers/1/", {
            'bulk-vol':'bulk_test_guest_1@e.cc, bulk_test_guest_2@e.cc, bulk_test_guest_3@e.cc, bulk_test_guest_4@e.cc',
            'personal_message':'Test msg 2',
            })

        # assert if we've been redirected
        self.assertRedirects(response, '/org-admin/4/', status_code=302)

