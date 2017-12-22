from django.test import Client, TestCase
from django.contrib.auth.models import User
from django.shortcuts import redirect

from datetime import datetime, timedelta
from django.utils import timezone

# MODELS
from openCurrents.models import \
    Org, \
    Project, \
    Event, \
    UserSettings, \
    UserEntity

# INTERFACES
from openCurrents.interfaces.ocuser import OcUser
from openCurrents.interfaces.orgs import \
    OcOrg, \
    OrgUserInfo


class TestIvniteVolunteersNoEvent(TestCase):

    def _get_merge_vars_keys_values(self, merge_vars):

        values=[]
        for i in merge_vars:
            values.extend(i.values())
        return values


    def _assert_merge_vars(self, merge_vars, values_list):
        mergedvars_values=self._get_merge_vars_keys_values(merge_vars)
        for value in values_list:
            self.assertIn(value, mergedvars_values)


    def setUp(self):

        # creating org
        self.org = OcOrg().setup_org(name="NPF_org_1", status="npf")

        # volunteer user 1
        self.volunteer1 = OcUser().setup_user(
            username='test_user_1',
            email='test_user_1@e.com',
        )

        # volunteer user 2
        self.volunteer2 = OcUser().setup_user(
            username='test_user_2',
            email='test_user_2@e.com',
        )

        # npf admin
        self.npf_admin_1 = OcUser().setup_user(
            username='npf_admin_1',
            email='npf_admin_1@g.com',
            first_name='first_npf_admin_1',
            last_name='last_npf_admin_1'
        )
        oui = OrgUserInfo(self.npf_admin_1.id)
        oui.setup_orguser(self.org)
        oui.make_org_admin(self.org.id)

        for user in User.objects.all():
            user.set_password('password')
            user.save()

        # setting up client
        self.client = Client()


    def test_invite_new_single_no_message(self):
        """
        test invitation of a single new volunteer without a personal message (no event)
        """

        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get('/invite-volunteers/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # posting form
        response = self.client.post("/invite-volunteers/", {
            'vol-name-1':'test_guest_1',
            'vol-email-1':'single_test_guest_1@mail.cc',
            'bulk-vol':'',
            'count-vol':'1',
            'personal_message':'',
            'test_mode':'1' # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            })

        # assert if we've been redirected
        self.assertRedirects(response, '/org-admin/1/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(self.client.session['bulk'], '1')

        # assert a user was created
        self.assertTrue(User.objects.get(username='single_test_guest_1@mail.cc'), 'single_test_guest_1@mail.cc')

        # assert user profile was created
        self.assertTrue(UserSettings.objects.get(user__username='single_test_guest_1@mail.cc'), 'single_test_guest_1@mail.cc')

        # assert userentity was created
        self.assertTrue(UserEntity.objects.get(user__username='single_test_guest_1@mail.cc'), 'single_test_guest_1@mail.cc')

        # asserting email vars values
        expected_list = ['first_npf_admin_1', 'ADMIN_FIRSTNAME', 'last_npf_admin_1', 'ADMIN_LASTNAME', 'NPF_org_1', 'ORG_NAME']
        self._assert_merge_vars(session['merge_vars'],expected_list)




    def test_invite_new_bulk_no_message(self):
        """
        test invitation of a bunch of new volunteers without a personal message (no event)
        """

        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get('/invite-volunteers/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # posting form
        self.response = self.client.post("/invite-volunteers/", {
            'bulk-vol':'bulk_test_guest_1@e.cc, bulk_test_guest_2@e.cc, bulk_test_guest_3@e.cc, bulk_test_guest_4@e.cc',
            'personal_message':'',
            'test_mode':'1' # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            })

        # assert if we've been redirected
        self.assertRedirects(self.response, '/org-admin/4/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(self.client.session['bulk'], '1')

        # assert new users were created
        self.assertEqual(len(User.objects.filter(username__contains='bulk_test_guest_')), 4)

        # assert user profiles were created
        self.assertEqual(len(UserSettings.objects.filter(user__username__contains='bulk_test_guest_')), 4)

        # assert userentities were created
        self.assertEqual(len(UserEntity.objects.filter(user__username__contains='bulk_test_guest_')), 4)

        # asserting email vars values
        expected_list = ['first_npf_admin_1', 'ADMIN_FIRSTNAME', 'last_npf_admin_1', 'ADMIN_LASTNAME', 'NPF_org_1', 'ORG_NAME']
        self._assert_merge_vars(session['merge_vars'],expected_list)


    def test_invite_new_single_with_personal_message(self):
        """
        test invitation of a single new volunteer with personal message (no event)
        """

        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get('/invite-volunteers/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # posting form
        response = self.client.post("/invite-volunteers/", {
            'vol-name-1':'test_guest_1',
            'vol-email-1':'single_test_guest_1@mail.cc',
            'bulk-vol':'',
            'count-vol':'1',
            'personal_message':'Test msg',
            'test_mode':'1' # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            })

        # assert if we've been redirected
        self.assertRedirects(response, '/org-admin/1/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(self.client.session['bulk'], '1')

        # assert a user was created
        self.assertTrue(User.objects.get(username='single_test_guest_1@mail.cc'), 'single_test_guest_1@mail.cc')

        # assert user profile was created
        self.assertTrue(UserSettings.objects.get(user__username='single_test_guest_1@mail.cc'), 'single_test_guest_1@mail.cc')

        # assert userentity was created
        self.assertTrue(UserEntity.objects.get(user__username='single_test_guest_1@mail.cc'), 'single_test_guest_1@mail.cc')

        # asserting email vars values
        expected_list = ['Test msg', 'PERSONAL_MESSAGE', 'first_npf_admin_1', 'ADMIN_FIRSTNAME', 'last_npf_admin_1', 'ADMIN_LASTNAME', 'NPF_org_1', 'ORG_NAME']
        self._assert_merge_vars(session['merge_vars'],expected_list)


    def test_invite_new_bulk_with_personal_message(self):

        """
        test invitation of a bunch of new volunteers with personal message (no event)
        """

        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get('/invite-volunteers/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # posting form
        response = self.client.post("/invite-volunteers/", {
            'bulk-vol':'bulk_test_guest_1@e.cc, bulk_test_guest_2@e.cc, bulk_test_guest_3@e.cc, bulk_test_guest_4@e.cc',
            'personal_message':'Test msg 2',
            'test_mode':'1' # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            })

        # assert if we've been redirected
        self.assertRedirects(response, '/org-admin/4/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(self.client.session['bulk'], '1')

        # assert new users were created
        self.assertEqual(len(User.objects.filter(username__contains='bulk_test_guest_')), 4)

        # assert user profiles were created
        self.assertEqual(len(UserSettings.objects.filter(user__username__contains='bulk_test_guest_')), 4)

        # assert userentities were created
        self.assertEqual(len(UserEntity.objects.filter(user__username__contains='bulk_test_guest_')), 4)

        # asserting email vars values
        expected_list = ['Test msg 2', 'PERSONAL_MESSAGE', 'first_npf_admin_1', 'ADMIN_FIRSTNAME', 'last_npf_admin_1', 'ADMIN_LASTNAME', 'NPF_org_1', 'ORG_NAME']
        self._assert_merge_vars(session['merge_vars'],expected_list)



    def test_invite_single_existing_no_message(self):
        """
        test invitation of a registered single volunteer without a personal message (no event)
        """

        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get('/invite-volunteers/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # assert a user exists
        self.assertTrue(User.objects.get(username=self.volunteer1.username), self.volunteer1.username)

        # posting form
        response = self.client.post("/invite-volunteers/", {
            'vol-name-1': self.volunteer1.username,
            'vol-email-1': self.volunteer1.email,
            'bulk-vol':'',
            'count-vol':'1',
            'personal_message':'',
            'test_mode':'1' # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            })

        # assert if we've been redirected
        self.assertRedirects(response, '/org-admin/1/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(self.client.session['bulk'], '1')

        #asserting user is in recepients
        self.assertTrue(self.client.session['recepient'][0]['email'], self.volunteer1.email)
        self.assertTrue(self.client.session['recepient'][0]['name'], self.volunteer1.username)

        # asserting email vars values
        expected_list = ['first_npf_admin_1', 'ADMIN_FIRSTNAME', 'last_npf_admin_1', 'ADMIN_LASTNAME', 'NPF_org_1', 'ORG_NAME']
        self._assert_merge_vars(session['merge_vars'],expected_list)


    def test_invite_single_existing_with_message(self):
        """
        test invitation of a registered single volunteer with a personal message (no event)
        """

        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get('/invite-volunteers/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # assert a user exists
        self.assertTrue(User.objects.get(username=self.volunteer1.username), self.volunteer1.username)

        # posting form
        response = self.client.post("/invite-volunteers/", {
            'vol-name-1': self.volunteer1.username,
            'vol-email-1': self.volunteer1.email,
            'bulk-vol':'',
            'count-vol':'1',
            'personal_message':'Test msg single existing',
            'test_mode':'1' # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            })

        # assert if we've been redirected
        self.assertRedirects(response, '/org-admin/1/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(self.client.session['bulk'], '1')

        #asserting user is in recepients
        self.assertTrue(self.client.session['recepient'][0]['email'], self.volunteer1.email)
        self.assertTrue(self.client.session['recepient'][0]['name'], self.volunteer1.username)

        # asserting email vars values
        expected_list = ['Test msg single existing', 'PERSONAL_MESSAGE', 'first_npf_admin_1', 'ADMIN_FIRSTNAME', 'last_npf_admin_1', 'ADMIN_LASTNAME', 'NPF_org_1', 'ORG_NAME']
        self._assert_merge_vars(session['merge_vars'],expected_list)


    def test_invite_bulk_existing_with_personal_message(self):
        """
        test invitation of a bunch of existing volunteers with personal message (no event)
        """

        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get('/invite-volunteers/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # asserting the users exist
        self.assertTrue(User.objects.get(username=self.volunteer1.username), self.volunteer1.username)
        self.assertTrue(User.objects.get(username=self.volunteer2.username), self.volunteer2.username)

        # posting form
        response = self.client.post("/invite-volunteers/", {
            'bulk-vol': "'" + self.volunteer1.email + ", " + self.volunteer2.email + "'",
            'personal_message':'Test msg bulk existing users',
            'test_mode':'1' # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            })

        # assert if we've been redirected
        self.assertRedirects(response, '/org-admin/2/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(self.client.session['bulk'], '1')

        #asserting both users are in recepients
        self.assertTrue(self.client.session['recepient'][0]['email'], self.volunteer1.email)
        self.assertTrue(self.client.session['recepient'][1]['email'], self.volunteer2.email)

        # asserting email vars values
        expected_list = ['Test msg bulk existing users', 'PERSONAL_MESSAGE', 'first_npf_admin_1', 'ADMIN_FIRSTNAME', 'last_npf_admin_1', 'ADMIN_LASTNAME', 'NPF_org_1', 'ORG_NAME']
        self._assert_merge_vars(session['merge_vars'],expected_list)


    def test_invite_bulk_existing_without_personal_message(self):
        """
        test invitation of a bunch of existing volunteers with personal message (no event)
        """

        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get('/invite-volunteers/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # asserting the users exist
        self.assertTrue(User.objects.get(username=self.volunteer1.username), self.volunteer1.username)
        self.assertTrue(User.objects.get(username=self.volunteer2.username), self.volunteer2.username)

        # posting form
        response = self.client.post("/invite-volunteers/", {
            'bulk-vol': "'" + self.volunteer1.email + ", " + self.volunteer2.email + "'",
            'personal_message':'',
            'test_mode':'1' # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            })

        # assert if we've been redirected
        self.assertRedirects(response, '/org-admin/2/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(self.client.session['bulk'], '1')

        #asserting both users are in recepients
        self.assertTrue(self.client.session['recepient'][0]['email'], self.volunteer1.email)
        self.assertTrue(self.client.session['recepient'][1]['email'], self.volunteer2.email)

        # asserting email vars values
        expected_list = ['first_npf_admin_1', 'ADMIN_FIRSTNAME', 'last_npf_admin_1', 'ADMIN_LASTNAME', 'NPF_org_1', 'ORG_NAME']
        self._assert_merge_vars(session['merge_vars'],expected_list)




class TestIvniteVolunteersToEvent(TestCase):


    def _get_merge_vars_keys_values(self, merge_vars):

        values=[]
        for i in merge_vars:
            values.extend(i.values())
        return values


    def _assert_merge_vars(self, merge_vars, values_list):
        mergedvars_values=self._get_merge_vars_keys_values(merge_vars)
        for value in values_list:
            self.assertIn(value, mergedvars_values)


    def setUp(self):

        # creating org
        self.org = OcOrg().setup_org(name="NPF_org_1", status="npf")

        # volunteer user 1
        self.volunteer1 = OcUser().setup_user(
            username='test_user_1',
            email='test_user_1@e.com',
        )

        # volunteer user 2
        self.volunteer2 = OcUser().setup_user(
            username='test_user_2',
            email='test_user_2@e.com',
        )

        # npf admin
        self.npf_admin_1 = OcUser().setup_user(
            username='npf_admin_1',
            email='npf_admin_1@g.com',
            first_name='first_npf_admin_1',
            last_name='last_npf_admin_1'
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



    def test_invite_new_single_no_message(self):
        """
        test invitation of a new volunteer without a personal message to future event
        """

        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get('/invite-volunteers/1/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        self.assertIn('Invite volunteers', self.response.content)

        # posting form
        response = self.client.post("/invite-volunteers/1/", {
            'vol-name-1':'test_guest_1',
            'vol-email-1':'single_test_guest_1@mail.cc',
            'bulk-vol':'',
            'count-vol':'1',
            'personal_message':'',
            'test_mode':'1' # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            })

        # assert if we've been redirected
        self.assertRedirects(response, '/org-admin/1/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(self.client.session['bulk'], '1')

        # assert a user was created
        self.assertTrue(User.objects.get(username='single_test_guest_1@mail.cc'), 'single_test_guest_1@mail.cc')

        # assert user profile was created
        self.assertTrue(UserSettings.objects.get(user__username='single_test_guest_1@mail.cc'), 'single_test_guest_1@mail.cc')

        # assert userentity was created
        self.assertTrue(UserEntity.objects.get(user__username='single_test_guest_1@mail.cc'), 'single_test_guest_1@mail.cc')

        # asserting email vars values
        expected_list = ['first_npf_admin_1', 'ADMIN_FIRSTNAME', 'last_npf_admin_1', 'ADMIN_LASTNAME', 'test_project_1', 'EVENT_TITLE', 'NPF_org_1', 'ORG_NAME', 'test_location_1', 'EVENT_LOCATION']
        self._assert_merge_vars(session['merge_vars'],expected_list)


    def test_invite_new_bulk_no_message(self):
        """
        test invitation of a bunch of new volunteers without a personal message to future event
        """

        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get('/invite-volunteers/1/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # posting form
        self.response = self.client.post("/invite-volunteers/1/", {
            'bulk-vol':'bulk_test_guest_1@e.cc, bulk_test_guest_2@e.cc, bulk_test_guest_3@e.cc, bulk_test_guest_4@e.cc',
            'personal_message':'',
            'test_mode':'1' # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            })

        # assert if we've been redirected
        self.assertRedirects(self.response, '/org-admin/4/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(self.client.session['bulk'], '1')

        # assert new users were created
        self.assertEqual(len(User.objects.filter(username__contains='bulk_test_guest_')), 4)

        # assert user profiles were created
        self.assertEqual(len(UserSettings.objects.filter(user__username__contains='bulk_test_guest_')), 4)

        # assert userentities were created
        self.assertEqual(len(UserEntity.objects.filter(user__username__contains='bulk_test_guest_')), 4)

        # asserting email vars values
        expected_list = ['first_npf_admin_1', 'ADMIN_FIRSTNAME', 'last_npf_admin_1', 'ADMIN_LASTNAME', 'test_project_1', 'EVENT_TITLE', 'NPF_org_1', 'ORG_NAME', 'test_location_1', 'EVENT_LOCATION']
        self._assert_merge_vars(session['merge_vars'],expected_list)


    def test_invite_new_single_with_message(self):
        """
        test invitation of a volunteer with personal message to future event
        """

        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get('/invite-volunteers/1/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # posting form
        response = self.client.post("/invite-volunteers/1/", {
            'vol-name-1':'test_guest_1',
            'vol-email-1':'single_test_guest_1@mail.cc',
            'bulk-vol':'',
            'count-vol':'1',
            'personal_message':'Test msg',
            'test_mode':'1' # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            })

        # assert if we've been redirected
        self.assertRedirects(response, '/org-admin/1/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(self.client.session['bulk'], '1')

        # assert a user was created
        self.assertTrue(User.objects.get(username='single_test_guest_1@mail.cc'), 'single_test_guest_1@mail.cc')

        # assert user profile was created
        self.assertTrue(UserSettings.objects.get(user__username='single_test_guest_1@mail.cc'), 'single_test_guest_1@mail.cc')

        # assert userentity was created
        self.assertTrue(UserEntity.objects.get(user__username='single_test_guest_1@mail.cc'), 'single_test_guest_1@mail.cc')

        # asserting email vars values
        expected_list = ['Test msg', 'PERSONAL_MESSAGE', 'first_npf_admin_1', 'ADMIN_FIRSTNAME', 'last_npf_admin_1', 'ADMIN_LASTNAME', 'test_project_1', 'EVENT_TITLE', 'NPF_org_1', 'ORG_NAME', 'test_location_1', 'EVENT_LOCATION']
        self._assert_merge_vars(session['merge_vars'],expected_list)


    def test_invite_new_bulk_with_message(self):
        """
        test invitation of a bunch of volunteers without a personal message to future event
        """

        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get('/invite-volunteers/1/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # posting form
        response = self.client.post("/invite-volunteers/1/", {
            'bulk-vol':'bulk_test_guest_1@e.cc, bulk_test_guest_2@e.cc, bulk_test_guest_3@e.cc, bulk_test_guest_4@e.cc',
            'personal_message':'Test msg 2',
            'test_mode':'1' # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            })

        # assert if we've been redirected
        self.assertRedirects(response, '/org-admin/4/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(self.client.session['bulk'], '1')

        # assert new users were created
        self.assertEqual(len(User.objects.filter(username__contains='bulk_test_guest_')), 4)

        # assert user profiles were created
        self.assertEqual(len(UserSettings.objects.filter(user__username__contains='bulk_test_guest_')), 4)

        # assert userentities were created
        self.assertEqual(len(UserEntity.objects.filter(user__username__contains='bulk_test_guest_')), 4)

        # asserting email vars values
        expected_list = ['Test msg 2', 'PERSONAL_MESSAGE', 'first_npf_admin_1', 'ADMIN_FIRSTNAME', 'last_npf_admin_1', 'ADMIN_LASTNAME', 'test_project_1', 'EVENT_TITLE', 'NPF_org_1', 'ORG_NAME', 'test_location_1', 'EVENT_LOCATION']
        self._assert_merge_vars(session['merge_vars'],expected_list)


    def test_invite_to_event_single_existing_no_message(self):
        """
        test invitation of a registered single volunteer without a personal message to future event
        """

        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get('/invite-volunteers/1/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # assert a user exists
        self.assertTrue(User.objects.get(username=self.volunteer1.username), self.volunteer1.username)

        # posting form
        response = self.client.post("/invite-volunteers/1/", {
            'vol-name-1': self.volunteer1.username,
            'vol-email-1': self.volunteer1.email,
            'bulk-vol':'',
            'count-vol':'1',
            'personal_message':'',
            'test_mode':'1' # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            })

        # assert if we've been redirected
        self.assertRedirects(response, '/org-admin/1/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(self.client.session['bulk'], '1')

        #asserting user is in recepients
        self.assertTrue(self.client.session['recepient'][0]['email'], self.volunteer1.email)
        self.assertTrue(self.client.session['recepient'][0]['name'], self.volunteer1.username)

        # asserting email vars values
        expected_list = ['first_npf_admin_1', 'ADMIN_FIRSTNAME', 'last_npf_admin_1', 'ADMIN_LASTNAME', 'test_project_1', 'EVENT_TITLE', 'NPF_org_1', 'ORG_NAME', 'test_location_1', 'EVENT_LOCATION']
        self._assert_merge_vars(session['merge_vars'],expected_list)

        # asserting email vars values
        expected_list = ['first_npf_admin_1', 'ADMIN_FIRSTNAME', 'last_npf_admin_1', 'ADMIN_LASTNAME', 'test_project_1', 'EVENT_TITLE', 'NPF_org_1', 'ORG_NAME', 'test_location_1', 'EVENT_LOCATION']
        self._assert_merge_vars(session['merge_vars'],expected_list)


    def test_invite_to_event_single_existing_with_message(self):
        """
        test invitation of a registered single volunteer with a personal message to future event
        """

        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get('/invite-volunteers/1/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # assert a user exists
        self.assertTrue(User.objects.get(username=self.volunteer1.username), self.volunteer1.username)

        # posting form
        response = self.client.post("/invite-volunteers/1/", {
            'vol-name-1': self.volunteer1.username,
            'vol-email-1': self.volunteer1.email,
            'bulk-vol':'',
            'count-vol':'1',
            'personal_message':'Test msg single existing',
            'test_mode':'1' # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            })

        # assert if we've been redirected
        self.assertRedirects(response, '/org-admin/1/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(self.client.session['bulk'], '1')

        #asserting user is in recepients
        self.assertTrue(self.client.session['recepient'][0]['email'], self.volunteer1.email)
        self.assertTrue(self.client.session['recepient'][0]['name'], self.volunteer1.username)

        # asserting email vars values
        expected_list = ['Test msg single existing', 'PERSONAL_MESSAGE', 'first_npf_admin_1', 'ADMIN_FIRSTNAME', 'last_npf_admin_1', 'ADMIN_LASTNAME', 'test_project_1', 'EVENT_TITLE', 'NPF_org_1', 'ORG_NAME', 'test_location_1', 'EVENT_LOCATION']
        self._assert_merge_vars(session['merge_vars'],expected_list)


    def test_invite_bulk_existing_with_personal_message(self):
        """
        test invitation of a bunch of existing volunteers with personal message to future event
        """

        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get('/invite-volunteers/1/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # asserting the users exist
        self.assertTrue(User.objects.get(username=self.volunteer1.username), self.volunteer1.username)
        self.assertTrue(User.objects.get(username=self.volunteer2.username), self.volunteer2.username)

        # posting form
        response = self.client.post("/invite-volunteers/1/", {
            'bulk-vol': "'" + self.volunteer1.email + ", " + self.volunteer2.email + "'",
            'personal_message':'Test msg bulk existing users',
            'test_mode':'1' # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            })

        # assert if we've been redirected
        self.assertRedirects(response, '/org-admin/2/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(self.client.session['bulk'], '1')

        #asserting both users are in recepients
        self.assertTrue(self.client.session['recepient'][0]['email'], self.volunteer1.email)
        self.assertTrue(self.client.session['recepient'][1]['email'], self.volunteer2.email)

        # asserting email vars values
        expected_list = ['Test msg bulk existing users', 'PERSONAL_MESSAGE', 'first_npf_admin_1', 'ADMIN_FIRSTNAME', 'last_npf_admin_1', 'ADMIN_LASTNAME', 'test_project_1', 'EVENT_TITLE', 'NPF_org_1', 'ORG_NAME', 'test_location_1', 'EVENT_LOCATION']
        self._assert_merge_vars(session['merge_vars'],expected_list)


    def test_invite_bulk_existing_users_no_message(self):

        """
        test invitation of a bunch of existing volunteers with personal message to future event
        """

        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get('/invite-volunteers/1/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # asserting the users exist
        self.assertTrue(User.objects.get(username=self.volunteer1.username), self.volunteer1.username)
        self.assertTrue(User.objects.get(username=self.volunteer2.username), self.volunteer2.username)

        # posting form
        response = self.client.post("/invite-volunteers/1/", {
            'bulk-vol': "'" + self.volunteer1.email + ", " + self.volunteer2.email + "'",
            'personal_message':'',
            'test_mode':'1' # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            })

        # assert if we've been redirected
        self.assertRedirects(response, '/org-admin/2/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(self.client.session['bulk'], '1')

        #asserting both users are in recepients
        self.assertTrue(self.client.session['recepient'][0]['email'], self.volunteer1.email)
        self.assertTrue(self.client.session['recepient'][1]['email'], self.volunteer2.email)

        # asserting email vars values
        expected_list = ['first_npf_admin_1', 'ADMIN_FIRSTNAME', 'last_npf_admin_1', 'ADMIN_LASTNAME', 'test_project_1', 'EVENT_TITLE', 'NPF_org_1', 'ORG_NAME', 'test_location_1', 'EVENT_LOCATION']
        self._assert_merge_vars(session['merge_vars'],expected_list)
