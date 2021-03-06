from django.test import Client, TestCase
from django.contrib.auth.models import User
from django.shortcuts import redirect

from datetime import datetime, timedelta
from django.utils import timezone

# MODELS
from openCurrents.models import (
    Org,
    Project,
    Event,
    UserSettings,
    UserEntity,
    UserEventRegistration
)

# INTERFACES
from openCurrents.interfaces.ocuser import OcUser
from openCurrents.interfaces.orgs import (
    OcOrg,
    OrgUserInfo
)
from openCurrents.tests.interfaces import testing_urls
from openCurrents.tests.interfaces.common import (
    SetupAdditionalTimeRecords,
    _get_random_string,
)

invite_volunteers_url = testing_urls.invite_volunteers_url
org_admin_url = testing_urls.org_admin_url


def _personal_message_wrap(msg):
    """Take msg string and wrap it into <pre> HTML tag."""
    return '<pre>' + msg + '</pre>'


class TestIvniteVolunteersNoEvent(SetupAdditionalTimeRecords, TestCase):

    def setUp(self):
        """Setup testing env."""
        # creating org
        self.org = OcOrg().setup_org(name="NPF_org_1", status="npf")

        # volunteer user 1 with usable_password
        self.volunteer1 = OcUser().setup_user(
            username='test_user_1',
            email='test_user_1@e.com',
        )

        # volunteer user 2 with usable_password
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

        # volunteer user 3 (has_usable_password)
        self.volunteer3 = OcUser().setup_user(
            username='test_user_3',
            email='test_user_3@e.com',
        )

        # volunteer user 4 (has_usable_password)
        self.volunteer4 = OcUser().setup_user(
            username='test_user_4',
            email='test_user_4@e.com',
        )
        self.volunteer4.set_unusable_password()
        self.volunteer4.save()

        # setting up client
        self.client = Client()

    def test_invite_new_single_no_message(self):
        """Test invitation of a single new volunteer without a personal message (no event)."""
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url)
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # posting form
        response = self.client.post(
            invite_volunteers_url,
            {
                'vol-name-1': 'test_guest_1',
                'vol-email-1': 'single_test_guest_1@mail.cc',
                'bulk-vol': '',
                'count-vol': '1',
                'personal_message': '',
                'test_mode': '1',  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            }
        )

        # assert if we've been redirected
        self.assertRedirects(response, org_admin_url + '1/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(session['bulk'], '1')

        # assert a user was created
        self.assertTrue(User.objects.get(username='single_test_guest_1@mail.cc'), 'single_test_guest_1@mail.cc')

        # assert user profile was created
        self.assertTrue(UserSettings.objects.get(user__username='single_test_guest_1@mail.cc'), 'single_test_guest_1@mail.cc')

        # assert userentity was created
        self.assertTrue(UserEntity.objects.get(user__username='single_test_guest_1@mail.cc'), 'single_test_guest_1@mail.cc')

        # asserting email vars values
        expected_list = [
            'first_npf_admin_1', 'ADMIN_FIRSTNAME',
            'last_npf_admin_1', 'ADMIN_LASTNAME',
            'NPF_org_1', 'ORG_NAME'
        ]
        self._assert_merge_vars(session['merge_vars'], expected_list)

        # assert we pass emails to mandril
        self.assertEqual(len(session['recepient']), 1)
        self.assertIn('single_test_guest_1@mail.cc', session['recepient'][0]['email'])

    def test_invite_new_bulk_no_message(self):
        """Test invitation of a bunch of new volunteers without a personal message (no event)."""
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url)
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # posting form
        self.response = self.client.post(
            invite_volunteers_url,
            {
                'bulk-vol': '<bulk_test_guest_1@e.cc>, test_guest_firstname test_guest_lastname <bulk_test_guest_2@e.cc>, bulk_test_guest_3@e.cc, bulk_test_guest_4@e.cc',
                'personal_message': '',
                'test_mode': '1'  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            }
        )
        # assert if we've been redirected
        self.assertRedirects(self.response, org_admin_url + '4/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(session['bulk'], '1')

        # assert new users were created
        self.assertEqual(len(User.objects.filter(username__contains='bulk_test_guest_')), 4)

        # assert user profiles were created
        self.assertEqual(len(UserSettings.objects.filter(user__username__contains='bulk_test_guest_')), 4)

        # assert userentities were created
        self.assertEqual(len(UserEntity.objects.filter(user__username__contains='bulk_test_guest_')), 4)

        # asserting email vars values
        expected_list = [
            'first_npf_admin_1', 'ADMIN_FIRSTNAME',
            'last_npf_admin_1', 'ADMIN_LASTNAME',
            'NPF_org_1', 'ORG_NAME'
        ]
        self._assert_merge_vars(session['merge_vars'], expected_list)

        # assert we pass emails to mandril
        self.assertEqual(len(session['recepient']), 4)
        self.assertIn('bulk_test_guest_1@e.cc', session['recepient'][0]['email'])
        self.assertIn('bulk_test_guest_2@e.cc', session['recepient'][1]['email'])
        self.assertIn('bulk_test_guest_3@e.cc', session['recepient'][2]['email'])
        self.assertIn('bulk_test_guest_4@e.cc', session['recepient'][3]['email'])

    def test_invite_new_single_with_personal_message(self):
        """Test invitation of a single new volunteer with personal message (no event)."""
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url)
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # posting form
        personal_message = _get_random_string()
        response = self.client.post(
            invite_volunteers_url,
            {
                'vol-name-1': 'test_guest_1',
                'vol-email-1': 'single_test_guest_1@mail.cc',
                'bulk-vol': '',
                'count-vol': '1',
                'personal_message': personal_message,
                'test_mode': '1'  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            }
        )

        # assert if we've been redirected
        self.assertRedirects(response, org_admin_url + '1/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(session['bulk'], '1')

        # assert a user was created
        self.assertTrue(User.objects.get(username='single_test_guest_1@mail.cc'), 'single_test_guest_1@mail.cc')

        # assert user profile was created
        self.assertTrue(UserSettings.objects.get(user__username='single_test_guest_1@mail.cc'), 'single_test_guest_1@mail.cc')

        # assert userentity was created
        self.assertTrue(UserEntity.objects.get(user__username='single_test_guest_1@mail.cc'), 'single_test_guest_1@mail.cc')

        # asserting email vars values
        expected_list = [
            _personal_message_wrap(personal_message), 'PERSONAL_MESSAGE',
            'first_npf_admin_1', 'ADMIN_FIRSTNAME',
            'last_npf_admin_1', 'ADMIN_LASTNAME',
            'NPF_org_1', 'ORG_NAME'
        ]
        self._assert_merge_vars(session['merge_vars'], expected_list)

        # assert we pass emails to mandril
        self.assertEqual(len(session['recepient']), 1)
        self.assertIn('single_test_guest_1@mail.cc', session['recepient'][0]['email'])

    def test_invite_new_bulk_with_personal_message(self):
        """
        Test invitation of a bunch of new volunteers.

        with personal message (no event)
        """
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url)
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # posting form
        personal_message = _get_random_string()
        response = self.client.post(
            invite_volunteers_url,
            {
                'bulk-vol': '<bulk_test_guest_1@e.cc>, test_guest_firstname test_guest_lastname <bulk_test_guest_2@e.cc>, bulk_test_guest_3@e.cc, bulk_test_guest_4@e.cc',
                'personal_message': personal_message,
                'test_mode': '1'  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            }
        )

        # assert if we've been redirected
        self.assertRedirects(response, org_admin_url + '4/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(session['bulk'], '1')

        # assert new users were created
        self.assertEqual(len(User.objects.filter(username__contains='bulk_test_guest_')), 4)

        # assert user profiles were created
        self.assertEqual(len(UserSettings.objects.filter(user__username__contains='bulk_test_guest_')), 4)

        # assert userentities were created
        self.assertEqual(len(UserEntity.objects.filter(user__username__contains='bulk_test_guest_')), 4)

        # asserting email vars values
        expected_list = [
            _personal_message_wrap(personal_message), 'PERSONAL_MESSAGE',
            'first_npf_admin_1', 'ADMIN_FIRSTNAME',
            'last_npf_admin_1', 'ADMIN_LASTNAME',
            'NPF_org_1', 'ORG_NAME'
        ]
        self._assert_merge_vars(session['merge_vars'], expected_list)

        # assert we pass emails to mandril
        self.assertEqual(len(session['recepient']), 4)
        self.assertIn('bulk_test_guest_1@e.cc', session['recepient'][0]['email'])
        self.assertIn('bulk_test_guest_2@e.cc', session['recepient'][1]['email'])
        self.assertIn('bulk_test_guest_3@e.cc', session['recepient'][2]['email'])
        self.assertIn('bulk_test_guest_4@e.cc', session['recepient'][3]['email'])

    def test_invite_single_existing_no_message(self):
        """Test invitation of a registered single volunteer without a personal message (no event) - No emails sent."""
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url)
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # assert a user exists
        self.assertTrue(User.objects.get(username=self.volunteer1.username), self.volunteer1.username)

        # posting form
        response = self.client.post(
            invite_volunteers_url,
            {
                'vol-name-1': self.volunteer1.username,
                'vol-email-1': self.volunteer1.email,
                'bulk-vol': '',
                'count-vol': '1',
                'personal_message': '',
                'test_mode': '1'  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            }
        )

        # assert if we've been redirected
        self.assertRedirects(response, org_admin_url + '1/', status_code=302)

        # asserting that bulk email function didn't launch
        self.assertNotIn('bulk', session)

        # asserting user not is in recepients
        self.assertNotIn('recepient', session)

        # asserting email vars didn't get to session
        self.assertNotIn('merge_vars', session)

    def test_invite_single_existing_with_message(self):
        """Test invitation of a registered single volunteer with a personal message (no event) - No emails sent."""
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url)
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # assert a user exists
        self.assertTrue(User.objects.get(username=self.volunteer1.username), self.volunteer1.username)

        # posting form
        response = self.client.post(
            invite_volunteers_url,
            {
                'vol-name-1': self.volunteer1.username,
                'vol-email-1': self.volunteer1.email,
                'bulk-vol': '',
                'count-vol': '1',
                'personal_message': 'Test msg single existing',
                'test_mode': '1'  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            }
        )

        # assert if we've been redirected
        self.assertRedirects(response, org_admin_url + '1/', status_code=302)

        # asserting that bulk email function didn't launch
        self.assertNotIn('bulk', session)

        # asserting user is not in recepients
        self.assertNotIn('recepient', session)

        # asserting email vars didn't get to session
        self.assertNotIn('merge_vars', session)

    def test_invite_bulk_existing_with_personal_message(self):
        """Test invitation of a bunch of existing volunteers with personal message (no event) - No emails sent."""
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url)
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # asserting the users exist
        self.assertTrue(User.objects.get(username=self.volunteer1.username), self.volunteer1.username)
        self.assertTrue(User.objects.get(username=self.volunteer2.username), self.volunteer2.username)

        # posting form
        response = self.client.post(
            invite_volunteers_url,
            {
                'bulk-vol': self.volunteer1.email + ", " + self.volunteer2.email,
                'personal_message': 'Test msg bulk existing users',
                'test_mode': '1'  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            }
        )

        # assert if we've been redirected
        self.assertRedirects(response, org_admin_url + '2/', status_code=302)

        # asserting that bulk email function didn't launch
        self.assertNotIn('bulk', session)

        # asserting user is not in recepients
        self.assertNotIn('recepient', session)

        # asserting email vars didn't get to session
        self.assertNotIn('merge_vars', session)

    def test_invite_bulk_existing_without_personal_message(self):
        """Test invitation of a bunch of existing volunteers with personal message (no event) - No emails sent."""
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url)
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # asserting the users exist
        self.assertTrue(User.objects.get(username=self.volunteer1.username), self.volunteer1.username)
        self.assertTrue(User.objects.get(username=self.volunteer2.username), self.volunteer2.username)

        # posting form
        response = self.client.post(
            invite_volunteers_url,
            {
                'bulk-vol': self.volunteer1.email + ", " + self.volunteer2.email,
                'personal_message': '',
                'test_mode': '1'  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            }
        )

        # assert if we've been redirected
        self.assertRedirects(response, org_admin_url + '2/', status_code=302)

        # asserting that bulk email function didn't launch
        self.assertNotIn('bulk', session)

        # asserting user not is in recepients
        self.assertNotIn('recepient', session)

        # asserting email vars didn't get to session
        self.assertNotIn('merge_vars', session)

    def test_invite_wo_password_bulk_with_personal_message(self):
        """
        Test invitation of a bunch of existing volunteers W/WO passw with personal message (no event).

        - don't send email to the the user W pass
        """
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url)
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # posting form
        personal_message = _get_random_string()
        response = self.client.post(
            invite_volunteers_url,
            {
                'bulk-vol': self.volunteer1.email + ", " + self.volunteer2.email + ", " + self.volunteer3.email,
                'personal_message': personal_message,
                'test_mode': '1'  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            }
        )

        # assert if we've been redirected
        self.assertRedirects(response, org_admin_url + '3/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(session['bulk'], '1')

        # assert new users were created
        self.assertEqual(len(User.objects.filter(username__contains='test_user_3')), 1)

        # assert user profiles were created
        self.assertEqual(len(UserSettings.objects.filter(user__username__contains='test_user_3')), 1)

        # assert userentities were created
        self.assertEqual(len(UserEntity.objects.filter(user__username__contains='test_user_3')), 1)

        # asserting email vars values
        expected_list = [
            _personal_message_wrap(personal_message), 'PERSONAL_MESSAGE',
            'first_npf_admin_1', 'ADMIN_FIRSTNAME',
            'last_npf_admin_1', 'ADMIN_LASTNAME',
            'NPF_org_1', 'ORG_NAME'
        ]
        self._assert_merge_vars(session['merge_vars'], expected_list)

        # assert we pass emails to mandril
        self.assertEqual(len(session['recepient']), 1)
        self.assertNotIn('test_user_1', session['recepient'][0]['email'])
        self.assertNotIn('test_user_2', session['recepient'][0]['email'])
        self.assertIn('test_user_3', session['recepient'][0]['email'])

    def test_invite_wo_password_bulk_wo_personal_message(self):
        """
        Test invitation of a bunch of existing volunteers W/WO passw WO personal message (no event).

        - don't send email to the the user WO pass
        """
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url)
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # posting form
        response = self.client.post(
            invite_volunteers_url,
            {
                'bulk-vol': self.volunteer1.email + ", " + self.volunteer2.email + ", " + self.volunteer3.email,
                'personal_message': '',
                'test_mode': '1'  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            }
        )

        # assert if we've been redirected
        self.assertRedirects(response, org_admin_url + '3/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(session['bulk'], '1')

        # assert additional user wasn't created
        self.assertEqual(len(User.objects.filter(username__contains='test_user_3')), 1)

        # assert additional user profile wasn't created
        self.assertEqual(len(UserSettings.objects.filter(user__username__contains='test_user_3')), 1)

        # assert additional userentity wasn't created
        self.assertEqual(len(UserEntity.objects.filter(user__username__contains='test_user_3')), 1)

        # asserting email vars values
        expected_list = [
            'first_npf_admin_1', 'ADMIN_FIRSTNAME',
            'last_npf_admin_1', 'ADMIN_LASTNAME',
            'NPF_org_1', 'ORG_NAME'
        ]
        self._assert_merge_vars(session['merge_vars'], expected_list)

        # assert we pass emails to mandril
        self.assertEqual(len(session['recepient']), 1)
        self.assertNotIn('test_user_1', session['recepient'][0]['email'])
        self.assertNotIn('test_user_2', session['recepient'][0]['email'])
        self.assertIn('test_user_3', session['recepient'][0]['email'])

    def test_invite_existing_wo_pass_single_no_message(self):
        """
        Test invitation of a single existing volunteer WO usable passw without a personal message (no event).

        - send email
        """
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url)
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # posting form
        response = self.client.post(
            invite_volunteers_url,
            {
                'vol-name-1': self.volunteer3.username,
                'vol-email-1': self.volunteer3.email,
                'bulk-vol': '',
                'count-vol': '1',
                'personal_message': '',
                'test_mode': '1'  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            }
        )

        # assert if we've been redirected
        self.assertRedirects(response, org_admin_url + '1/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(session['bulk'], '1')

        # assert additional user wasn't created
        self.assertEqual(len(User.objects.filter(username__contains='test_user_3')), 1)

        # assert additional user profile wasn't created
        self.assertEqual(len(UserSettings.objects.filter(user__username__contains='test_user_3')), 1)

        # assert additional userentity wasn't created
        self.assertEqual(len(UserEntity.objects.filter(user__username__contains='test_user_3')), 1)

        # asserting email vars values
        expected_list = [
            'first_npf_admin_1', 'ADMIN_FIRSTNAME',
            'last_npf_admin_1', 'ADMIN_LASTNAME',
            'NPF_org_1', 'ORG_NAME'
        ]
        self._assert_merge_vars(session['merge_vars'], expected_list)

        # assert we pass emails to mandril
        self.assertEqual(len(session['recepient']), 1)
        self.assertNotIn('test_user_1', session['recepient'][0]['email'])
        self.assertNotIn('test_user_2', session['recepient'][0]['email'])
        self.assertIn('test_user_3', session['recepient'][0]['email'])


class TestIvniteVolunteersToEvent(SetupAdditionalTimeRecords, TestCase):

    def setUp(self):
        """Setup testing env."""
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

        # volunteer user 3 with not usable pass
        self.volunteer3 = OcUser().setup_user(
            username='test_user_3',
            email='test_user_3@e.com',
        )

        # volunteer user 3 with not usable pass
        self.volunteer4 = OcUser().setup_user(
            username='test_user_4',
            email='test_user_4@e.com',
        )

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
        """Test invitation of a new volunteer Without a personal message to future event  and invite checkbox on."""
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url + '1/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        self.assertIn('Invite volunteers', self.response.content)

        # posting form
        response = self.client.post(
            invite_volunteers_url + '1/',
            {
                'vol-name-1': 'test_guest_1',
                'vol-email-1': 'single_test_guest_1@mail.cc',
                'bulk-vol': '',
                'count-vol': '1',
                'personal_message': '',
                'test_mode': '1',  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
                'invite-volunteers-checkbox': 'on'
            }
        )

        # assert if we've been redirected
        self.assertRedirects(response, org_admin_url + '1/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(session['bulk'], '1')

        # assert a user was created
        self.assertTrue(User.objects.get(username='single_test_guest_1@mail.cc'), 'single_test_guest_1@mail.cc')

        # assert user profile was created
        self.assertTrue(UserSettings.objects.get(user__username='single_test_guest_1@mail.cc'), 'single_test_guest_1@mail.cc')

        # assert userentity was created
        self.assertTrue(UserEntity.objects.get(user__username='single_test_guest_1@mail.cc'), 'single_test_guest_1@mail.cc')

        # asserting email vars values
        expected_list = [
            'first_npf_admin_1', 'ADMIN_FIRSTNAME',
            'last_npf_admin_1', 'ADMIN_LASTNAME',
            'test_project_1', 'EVENT_TITLE',
            'NPF_org_1', 'ORG_NAME',
            'test_location_1', 'EVENT_LOCATION'
        ]
        self._assert_merge_vars(session['merge_vars'], expected_list)

        # assert we pass emails to mandril
        self.assertEqual(len(session['recepient']), 1)
        self.assertIn('single_test_guest_1', session['recepient'][0]['email'])

        # asserting user has been registered to event
        u = User.objects.get(email='single_test_guest_1@mail.cc')
        self.assertEqual(len(UserEventRegistration.objects.filter(user=u)), 1)

    def test_invite_new_bulk_no_message(self):
        """Test invitation of a bunch of new volunteers without a personal message to future event  and invite checkbox on."""
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url + '1/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # posting form
        self.response = self.client.post(
            invite_volunteers_url + '1/',
            {
                'bulk-vol': 'bulk_test_guest_1@e.cc, bulk_test_guest_2@e.cc, bulk_test_guest_3@e.cc, bulk_test_guest_4@e.cc',
                'personal_message': '',
                'test_mode': '1',  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
                'invite-volunteers-checkbox': 'on'
            }
        )

        # assert if we've been redirected
        self.assertRedirects(self.response, org_admin_url + '4/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(session['bulk'], '1')

        # assert new users were created
        self.assertEqual(len(User.objects.filter(username__contains='bulk_test_guest_')), 4)

        # assert user profiles were created
        self.assertEqual(len(UserSettings.objects.filter(user__username__contains='bulk_test_guest_')), 4)

        # assert userentities were created
        self.assertEqual(len(UserEntity.objects.filter(user__username__contains='bulk_test_guest_')), 4)

        # asserting email vars values
        expected_list = [
            'first_npf_admin_1', 'ADMIN_FIRSTNAME',
            'last_npf_admin_1', 'ADMIN_LASTNAME',
            'test_project_1', 'EVENT_TITLE',
            'NPF_org_1', 'ORG_NAME',
            'test_location_1', 'EVENT_LOCATION'
        ]
        self._assert_merge_vars(session['merge_vars'], expected_list)

        # assert we pass emails to mandril
        self.assertEqual(len(session['recepient']), 4)
        self.assertEqual(len(session['recepient']), 4)
        self.assertIn(
            'bulk_test_guest_1@e.cc', session['recepient'][0]['email']
        )
        self.assertIn(
            'bulk_test_guest_2@e.cc', session['recepient'][1]['email']
        )
        self.assertIn(
            'bulk_test_guest_3@e.cc', session['recepient'][2]['email']
        )
        self.assertIn(
            'bulk_test_guest_4@e.cc', session['recepient'][3]['email']
        )

        # asserting user has been registered to event
        self.assertEqual(
            len(UserEventRegistration.objects.filter(user__username__contains='bulk_test_guest_')), 4
        )

    def test_invite_new_single_with_message(self):
        """Test invitation of a volunteer with personal message to future event  and invite checkbox on."""
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url + '1/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # posting form
        personal_message = _get_random_string()
        response = self.client.post(
            invite_volunteers_url + '1/',
            {
                'vol-name-1': 'test_guest_1',
                'vol-email-1': 'single_test_guest_1@mail.cc',
                'bulk-vol': '',
                'count-vol': '1',
                'personal_message': personal_message,
                'test_mode': '1',  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
                'invite-volunteers-checkbox': 'on'
            }
        )

        # assert if we've been redirected
        self.assertRedirects(response, org_admin_url + '1/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(session['bulk'], '1')

        # assert a user was created
        self.assertTrue(
            User.objects.get(username='single_test_guest_1@mail.cc'),
            'single_test_guest_1@mail.cc'
        )

        # assert user profile was created
        self.assertTrue(
            UserSettings.objects.get(user__username='single_test_guest_1@mail.cc'),
            'single_test_guest_1@mail.cc'
        )

        # assert userentity was created
        self.assertTrue(
            UserEntity.objects.get(user__username='single_test_guest_1@mail.cc'),
            'single_test_guest_1@mail.cc'
        )

        # asserting email vars values
        expected_list = [
            _personal_message_wrap(personal_message), 'PERSONAL_MESSAGE',
            'first_npf_admin_1', 'ADMIN_FIRSTNAME',
            'last_npf_admin_1', 'ADMIN_LASTNAME',
            'test_project_1', 'EVENT_TITLE',
            'NPF_org_1', 'ORG_NAME',
            'test_location_1', 'EVENT_LOCATION'
        ]
        self._assert_merge_vars(session['merge_vars'], expected_list)

        # assert we pass emails to mandril
        self.assertEqual(len(session['recepient']), 1)
        self.assertIn('single_test_guest_1', session['recepient'][0]['email'])

        # asserting user has been registered to event
        u = User.objects.get(email='single_test_guest_1@mail.cc')
        self.assertEqual(len(UserEventRegistration.objects.filter(user=u)), 1)

    def test_invite_new_bulk_with_message(self):
        """Test invitation of a bunch of volunteers without a personal message to future event  and invite checkbox on."""
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url + '1/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # posting form
        personal_message = _get_random_string()
        response = self.client.post(
            invite_volunteers_url + '1/',
            {
                'bulk-vol': 'bulk_test_guest_1@e.cc, bulk_test_guest_2@e.cc, bulk_test_guest_3@e.cc, bulk_test_guest_4@e.cc',
                'personal_message': personal_message,
                'test_mode': '1',  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
                'invite-volunteers-checkbox': 'on'
            }
        )

        # assert if we've been redirected
        self.assertRedirects(response, org_admin_url + '4/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(session['bulk'], '1')

        # assert new users were created
        self.assertEqual(
            len(User.objects.filter(username__contains='bulk_test_guest_')), 4
        )

        # assert user profiles were created
        self.assertEqual(
            len(UserSettings.objects.filter(user__username__contains='bulk_test_guest_')), 4
        )

        # assert userentities were created
        self.assertEqual(
            len(UserEntity.objects.filter(user__username__contains='bulk_test_guest_')), 4
        )

        # asserting email vars values
        expected_list = [
            _personal_message_wrap(personal_message), 'PERSONAL_MESSAGE',
            'first_npf_admin_1', 'ADMIN_FIRSTNAME',
            'last_npf_admin_1', 'ADMIN_LASTNAME',
            'test_project_1', 'EVENT_TITLE',
            'NPF_org_1', 'ORG_NAME',
            'test_location_1', 'EVENT_LOCATION'
        ]
        self._assert_merge_vars(session['merge_vars'], expected_list)

        # assert we pass emails to mandril
        self.assertEqual(len(session['recepient']), 4)
        self.assertIn('bulk_test_guest_1@e.cc', session['recepient'][0]['email'])
        self.assertIn('bulk_test_guest_2@e.cc', session['recepient'][1]['email'])
        self.assertIn('bulk_test_guest_3@e.cc', session['recepient'][2]['email'])
        self.assertIn('bulk_test_guest_4@e.cc', session['recepient'][3]['email'])

        # asserting user has been registered to event
        self.assertEqual(len(UserEventRegistration.objects.filter(user__username__contains='bulk_test_guest_')), 4)

    def test_invite_to_event_single_existing_no_message(self):
        """Test invitation of a registered single volunteer without a personal message to future event  and invite checkbox on."""
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url + '1/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # assert a user exists
        self.assertTrue(
            User.objects.get(username=self.volunteer1.username),
            self.volunteer1.username
        )

        # posting form
        response = self.client.post(
            invite_volunteers_url + '1/',
            {
                'vol-name-1': self.volunteer1.username,
                'vol-email-1': self.volunteer1.email,
                'bulk-vol': '',
                'count-vol': '1',
                'personal_message': '',
                'test_mode': '1',  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
                'invite-volunteers-checkbox': 'on'
            }
        )

        # assert if we've been redirected
        self.assertRedirects(response, org_admin_url + '1/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(session['bulk'], '1')

        # asserting user is in recepients
        self.assertTrue(
            session['recepient'][0]['email'],
            self.volunteer1.email
        )
        self.assertTrue(
            session['recepient'][0]['name'],
            self.volunteer1.username
        )

        # asserting email vars values
        expected_list = [
            'first_npf_admin_1', 'ADMIN_FIRSTNAME',
            'last_npf_admin_1', 'ADMIN_LASTNAME',
            'test_project_1', 'EVENT_TITLE',
            'NPF_org_1', 'ORG_NAME',
            'test_location_1', 'EVENT_LOCATION'
        ]
        self._assert_merge_vars(session['merge_vars'], expected_list)

        # asserting email vars values
        expected_list = [
            'first_npf_admin_1', 'ADMIN_FIRSTNAME',
            'last_npf_admin_1', 'ADMIN_LASTNAME',
            'test_project_1', 'EVENT_TITLE',
            'NPF_org_1', 'ORG_NAME',
            'test_location_1', 'EVENT_LOCATION'
        ]
        self._assert_merge_vars(session['merge_vars'], expected_list)

        # assert we pass emails to mandril
        self.assertEqual(len(session['recepient']), 1)

        # asserting user has been registered to event
        self.assertEqual(
            len(UserEventRegistration.objects.filter(user=self.volunteer1)), 1
        )

    def test_invite_to_event_single_existing_nopass_with_message(self):
        """Test invitation of a registered single volunteer with a personal message to future event  and invite checkbox on."""
        # Expected: users wo pass invited to event should receive email
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url + '1/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # assert a user exists
        self.assertTrue(
            User.objects.get(username=self.volunteer1.username),
            self.volunteer1.username
        )

        # posting form
        personal_message = _get_random_string()
        response = self.client.post(
            invite_volunteers_url + '1/',
            {
                'vol-name-1': self.volunteer3.username,
                'vol-email-1': self.volunteer3.email,
                'bulk-vol': '',
                'count-vol': '1',
                'personal_message': personal_message,
                'test_mode': '1',  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
                'invite-volunteers-checkbox': 'on'
            }
        )

        # assert if we've been redirected
        self.assertRedirects(response, org_admin_url + '1/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(session['bulk'], '1')

        # asserting user is in recepients
        self.assertTrue(
            session['recepient'][0]['email'],
            self.volunteer1.email
        )
        self.assertTrue(
            session['recepient'][0]['name'],
            self.volunteer1.username
        )

        # asserting email vars values
        expected_list = [
            _personal_message_wrap(personal_message), 'PERSONAL_MESSAGE',
            'first_npf_admin_1', 'ADMIN_FIRSTNAME',
            'last_npf_admin_1', 'ADMIN_LASTNAME',
            'test_project_1', 'EVENT_TITLE',
            'NPF_org_1', 'ORG_NAME',
            'test_location_1', 'EVENT_LOCATION'
        ]
        self._assert_merge_vars(session['merge_vars'], expected_list)

        # assert we pass emails to mandril
        self.assertEqual(len(session['recepient']), 1)

        # asserting user has been registered to event
        self.assertEqual(
            len(UserEventRegistration.objects.filter(user=self.volunteer3)), 1
        )

    def test_invite_to_event_single_existing_nopass_no_message(self):
        """Test invitation of a registered single volunteer with a personal message to future event  and invite checkbox on."""
        # Expected: users wo pass invited to event should receive email
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url + '1/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # assert a user exists
        self.assertTrue(
            User.objects.get(username=self.volunteer1.username),
            self.volunteer1.username
        )

        # posting form
        response = self.client.post(
            invite_volunteers_url + '1/',
            {
                'vol-name-1': self.volunteer3.username,
                'vol-email-1': self.volunteer3.email,
                'bulk-vol': '',
                'count-vol': '1',
                'personal_message': '',
                'test_mode': '1',  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
                'invite-volunteers-checkbox': 'on'
            }
        )

        # assert if we've been redirected
        self.assertRedirects(response, org_admin_url + '1/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(session['bulk'], '1')

        # asserting user is in recepients
        self.assertTrue(
            session['recepient'][0]['email'],
            self.volunteer3.email
        )
        self.assertTrue(
            session['recepient'][0]['name'],
            self.volunteer3.username
        )

        # asserting email vars values
        expected_list = [
            'first_npf_admin_1', 'ADMIN_FIRSTNAME',
            'last_npf_admin_1', 'ADMIN_LASTNAME',
            'test_project_1', 'EVENT_TITLE',
            'NPF_org_1', 'ORG_NAME',
            'test_location_1', 'EVENT_LOCATION'
        ]
        self._assert_merge_vars(session['merge_vars'], expected_list)

        # assert we pass emails to mandril
        self.assertEqual(len(session['recepient']), 1)

        # asserting user has been registered to event
        self.assertEqual(
            len(UserEventRegistration.objects.filter(user=self.volunteer3)), 1
        )

    def test_invite_to_event_single_existing_with_message(self):
        """Test invitation of a registered single volunteer with a personal message to future event and invite checkbox on."""
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url + '1/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # assert a user exists
        self.assertTrue(
            User.objects.get(username=self.volunteer1.username),
            self.volunteer1.username
        )

        # posting form
        personal_message = _get_random_string()
        response = self.client.post(
            invite_volunteers_url + '1/',
            {
                'vol-name-1': self.volunteer1.username,
                'vol-email-1': self.volunteer1.email,
                'bulk-vol': '',
                'count-vol': '1',
                'personal_message': personal_message,
                'test_mode': '1',  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
                'invite-volunteers-checkbox': 'on'
            }
        )

        # assert if we've been redirected
        self.assertRedirects(response, org_admin_url + '1/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(session['bulk'], '1')

        # asserting user is in recepients
        self.assertTrue(
            session['recepient'][0]['email'],
            self.volunteer1.email
        )
        self.assertTrue(
            session['recepient'][0]['name'],
            self.volunteer1.username
        )

        # asserting email vars values
        expected_list = [
            _personal_message_wrap(personal_message), 'PERSONAL_MESSAGE',
            'first_npf_admin_1', 'ADMIN_FIRSTNAME',
            'last_npf_admin_1', 'ADMIN_LASTNAME',
            'test_project_1', 'EVENT_TITLE',
            'NPF_org_1', 'ORG_NAME',
            'test_location_1', 'EVENT_LOCATION'
        ]
        self._assert_merge_vars(session['merge_vars'], expected_list)

        # assert we pass emails to mandril
        self.assertEqual(len(session['recepient']), 1)

        # asserting user has been registered to event
        self.assertEqual(len(UserEventRegistration.objects.filter(user=self.volunteer1)), 1)

    def test_invite_bulk_existing_with_personal_message(self):
        """Test invitation of a bunch of existing volunteers with personal message to future event  and invite checkbox on."""
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url + '1/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # asserting the users exist
        self.assertTrue(
            User.objects.get(username=self.volunteer1.username),
            self.volunteer1.username
        )
        self.assertTrue(
            User.objects.get(username=self.volunteer2.username),
            self.volunteer2.username
        )

        # posting form
        personal_message = _get_random_string()
        response = self.client.post(
            invite_volunteers_url + '1/',
            {
                'bulk-vol': self.volunteer1.email + ", " + self.volunteer2.email,
                'personal_message': personal_message,
                'test_mode': '1',  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
                'invite-volunteers-checkbox': 'on'
            }
        )

        # assert if we've been redirected
        self.assertRedirects(response, org_admin_url + '2/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(session['bulk'], '1')

        # asserting both users are in recepients
        self.assertTrue(
            session['recepient'][0]['email'],
            self.volunteer1.email
        )
        self.assertTrue(
            session['recepient'][1]['email'],
            self.volunteer2.email
        )

        # asserting email vars values
        expected_list = [
            _personal_message_wrap(personal_message), 'PERSONAL_MESSAGE',
            'first_npf_admin_1', 'ADMIN_FIRSTNAME',
            'last_npf_admin_1', 'ADMIN_LASTNAME',
            'test_project_1', 'EVENT_TITLE',
            'NPF_org_1', 'ORG_NAME',
            'test_location_1', 'EVENT_LOCATION'
        ]
        self._assert_merge_vars(session['merge_vars'], expected_list)

        # assert we pass emails to mandril
        self.assertEqual(len(session['recepient']), 2)

        # asserting user has been registered to event
        self.assertEqual(
            len(UserEventRegistration.objects.filter(user=self.volunteer1)), 1
        )

    def test_invite_bulk_existing_users_no_message(self):
        """Test invitation of a bunch of existing volunteers with personal message to future event  and invite checkbox on."""
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url + '1/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # asserting the users exist
        self.assertTrue(
            User.objects.get(username=self.volunteer1.username),
            self.volunteer1.username
        )
        self.assertTrue(
            User.objects.get(username=self.volunteer2.username),
            self.volunteer2.username
        )

        # posting form
        response = self.client.post(
            invite_volunteers_url + '1/',
            {
                'bulk-vol': self.volunteer1.email + ", " + self.volunteer2.email,
                'personal_message': '',
                'test_mode': '1',  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
                'invite-volunteers-checkbox': 'on'
            }
        )

        # assert if we've been redirected
        self.assertRedirects(response, org_admin_url + '2/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(session['bulk'], '1')

        # asserting both users are in recepients
        self.assertTrue(
            session['recepient'][0]['email'],
            self.volunteer1.email
        )
        self.assertTrue(
            session['recepient'][1]['email'],
            self.volunteer2.email
        )

        # asserting email vars values
        expected_list = [
            'first_npf_admin_1', 'ADMIN_FIRSTNAME',
            'last_npf_admin_1', 'ADMIN_LASTNAME',
            'test_project_1', 'EVENT_TITLE',
            'NPF_org_1', 'ORG_NAME',
            'test_location_1', 'EVENT_LOCATION'
        ]
        self._assert_merge_vars(session['merge_vars'], expected_list)

        # assert we pass emails to mandril
        self.assertEqual(len(session['recepient']), 2)

        # asserting user has been registered to event
        self.assertEqual(
            len(UserEventRegistration.objects.filter(user=self.volunteer1)), 1
        )
        self.assertEqual(
            len(UserEventRegistration.objects.filter(user=self.volunteer2)), 1
        )

    def test_invite_bulk_existing_nopass_no_message(self):
        """Test invitation of a bunch of new volunteers without a personal message to future event."""
        # Expected: users wo pass invited to event should receive email
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url + '1/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # posting form
        self.response = self.client.post(
            invite_volunteers_url + '1/',
            {
                'bulk-vol': self.volunteer3.email + ", " + self.volunteer4.email,
                'personal_message': '',
                'test_mode': '1',  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
                'invite-volunteers-checkbox': 'on'
            }
        )

        # assert if we've been redirected
        self.assertRedirects(self.response, org_admin_url + '2/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(session['bulk'], '1')

        # assert new users weren't created (equals 4 because of 2 volunteers with usable passwrds)
        self.assertEqual(
            len(User.objects.filter(username__contains='test_user_')), 4
        )

        # assert user profiles weren't created
        self.assertEqual(
            len(UserSettings.objects.filter(user__username__contains='test_user_')),
            4
        )

        # assert userentities weren't created
        self.assertEqual(
            len(UserEntity.objects.filter(user__username__contains='test_user_')),
            4
        )

        # asserting email vars values
        expected_list = [
            'first_npf_admin_1', 'ADMIN_FIRSTNAME',
            'last_npf_admin_1', 'ADMIN_LASTNAME',
            'test_project_1', 'EVENT_TITLE',
            'NPF_org_1', 'ORG_NAME',
            'test_location_1', 'EVENT_LOCATION'
        ]
        self._assert_merge_vars(session['merge_vars'], expected_list)

        # assert we pass emails to mandril
        self.assertEqual(len(session['recepient']), 2)

        # asserting user has been registered to event
        self.assertEqual(
            len(UserEventRegistration.objects.filter(user=self.volunteer3)), 1
        )
        self.assertEqual(
            len(UserEventRegistration.objects.filter(user=self.volunteer4)), 1
        )

    def test_invite_bulk_existing_nopass_with_personal_message(self):
        """Test invitation of a bunch of existing volunteers with personal message to future event  and invite checkbox on."""
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url + '1/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # asserting the users exist
        self.assertTrue(
            User.objects.get(username=self.volunteer1.username),
            self.volunteer1.username
        )
        self.assertTrue(
            User.objects.get(username=self.volunteer2.username),
            self.volunteer2.username
        )

        # posting form
        personal_message = _get_random_string()
        response = self.client.post(
            invite_volunteers_url + '1/',
            {
                'bulk-vol': self.volunteer3.email + ", " + self.volunteer4.email,
                'personal_message': personal_message,
                'test_mode': '1',  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
                'invite-volunteers-checkbox': 'on'
            }
        )

        # assert if we've been redirected
        self.assertRedirects(response, org_admin_url + '2/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertEqual(session['bulk'], '1')

        # assert new users weren't created (equals 4 because of 2 volunteers with usable passwrds)
        self.assertEqual(
            len(User.objects.filter(username__contains='test_user_')), 4
        )

        # assert user profiles weren't created
        self.assertEqual(
            len(UserSettings.objects.filter(user__username__contains='test_user_')), 4
        )

        # assert userentities weren't created
        self.assertEqual(
            len(UserEntity.objects.filter(user__username__contains='test_user_')), 4
        )

        # asserting both users are in recepients
        self.assertTrue(session['recepient'][0]['email'], self.volunteer3.email)
        self.assertTrue(session['recepient'][1]['email'], self.volunteer4.email)

        # asserting email vars values
        expected_list = [
            _personal_message_wrap(personal_message), 'PERSONAL_MESSAGE',
            'first_npf_admin_1', 'ADMIN_FIRSTNAME',
            'last_npf_admin_1', 'ADMIN_LASTNAME',
            'test_project_1', 'EVENT_TITLE',
            'NPF_org_1', 'ORG_NAME',
            'test_location_1', 'EVENT_LOCATION'
        ]
        self._assert_merge_vars(session['merge_vars'], expected_list)

        # assert we pass emails to mandril
        self.assertEqual(len(session['recepient']), 2)

        # asserting user has been registered to event
        self.assertEqual(
            len(UserEventRegistration.objects.filter(user=self.volunteer3)), 1
        )
        self.assertEqual(
            len(UserEventRegistration.objects.filter(user=self.volunteer4)), 1
        )

    def test_invite_existing_vol_checkbox_off(self):
        """Test invitation of an existing single volunteer to a future event and invite checkbox OFF. Expected no email sent."""
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url + '1/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # assert a user exists
        self.assertTrue(
            User.objects.get(username=self.volunteer1.username),
            self.volunteer1.username
        )

        # posting form
        personal_message = _get_random_string()
        response = self.client.post(
            invite_volunteers_url + '1/',
            {
                'vol-name-1': self.volunteer1.username,
                'vol-email-1': self.volunteer1.email,
                'bulk-vol': '',
                'count-vol': '1',
                'personal_message': personal_message,
                'test_mode': '1',  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            }
        )

        # assert if we've been redirected
        self.assertRedirects(response, org_admin_url + '1/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertNotIn('bulk', session)

        # asserting user is not in recepients
        self.assertNotIn('recepient', session)

        # asserting email vars didn't get to session
        self.assertNotIn('merge_vars', session)

        # asserting user has been registered to event
        self.assertEqual(len(UserEventRegistration.objects.filter(user=self.volunteer1)), 1)

    def test_invite_existing_vol_unusable_pass_checkbox_off(self):
        """Test invitation of an existing single volunteer WO usable_password to a future event and invite checkbox OFF. Expected no email sent."""
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url + '1/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # assert a user exists
        self.assertTrue(
            User.objects.get(username=self.volunteer4.username),
            self.volunteer4.username
        )

        # posting form
        personal_message = _get_random_string()
        response = self.client.post(
            invite_volunteers_url + '1/',
            {
                'vol-name-1': self.volunteer4.username,
                'vol-email-1': self.volunteer4.email,
                'bulk-vol': '',
                'count-vol': '1',
                'personal_message': personal_message,
                'test_mode': '1',  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            }
        )

        # assert if we've been redirected
        self.assertRedirects(response, org_admin_url + '1/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertNotIn('bulk', session)

        # asserting user is not in recepients
        self.assertNotIn('recepient', session)

        # asserting email vars didn't get to session
        self.assertNotIn('merge_vars', session)

        # asserting user has been registered to event
        self.assertEqual(len(UserEventRegistration.objects.filter(user=self.volunteer4)), 1)

    def test_invite_new_vol_checkbox_off(self):
        """Test invitation of a new single volunteer to a future event and invite checkbox OFF. Expected no email sent."""
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get(invite_volunteers_url + '1/')
        session = self.client.session

        self.assertEqual(self.response.status_code, 200)

        # assert a user exists
        self.assertTrue(
            User.objects.get(username=self.volunteer1.username),
            self.volunteer1.username
        )

        # posting form
        personal_message = _get_random_string()
        response = self.client.post(
            invite_volunteers_url + '1/',
            {
                'vol-name-1': 'test_guest_1',
                'vol-email-1': 'single_test_guest_1@mail.cc',
                'bulk-vol': '',
                'count-vol': '1',
                'personal_message': personal_message,
                'test_mode': '1',  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            }
        )

        # assert if we've been redirected
        self.assertRedirects(response, org_admin_url + '1/', status_code=302)

        # asserting that bulk email function has been launched
        self.assertNotIn('bulk', session)

        # asserting user is not in recepients
        self.assertNotIn('recepient', session)

        # asserting email vars didn't get to session
        self.assertNotIn('merge_vars', session)

        # asserting user has been registered to event
        self.assertEqual(len(UserEventRegistration.objects.filter(user__email='single_test_guest_1@mail.cc')), 1)
