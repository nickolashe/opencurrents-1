from django.test import Client, TestCase
from django.contrib.auth.models import User

from datetime import datetime, timedelta
from django.utils import timezone

# from openCurrents import views, urls

from openCurrents.models import \
    Org, \
    Entity, \
    UserEntity, \
    OrgEntity, \
    OrgUser, \
    Project, \
    Event, \
    UserTimeLog, \
    AdminActionUserTime, \
    Ledger, \
    UserEventRegistration

from openCurrents.interfaces.ocuser import \
    OcUser, \
    InvalidUserException, \
    UserExistsException

from openCurrents.interfaces.orgs import \
    OcOrg, \
    OrgUserInfo

from openCurrents.tests.interfaces.common import \
    _create_test_user, \
    _create_project, \
    _setup_volunteer_hours, \
    _create_event, \
    _setup_user_event_registration


from openCurrents.interfaces.orgadmin import OrgAdmin
from openCurrents.interfaces.ledger import OcLedger

from openCurrents.interfaces.common import diffInHours

import pytz
import uuid
import random
import string
import re
from collections import OrderedDict

from unittest import skip


class NpfAdminView(TestCase):

    @staticmethod
    def create_user(org_user_name, org, is_org_user=False, is_org_admin=False, password='password'):
        """
        Crete Users and maps them to the org if needed.

        org_user_name - string
        if is_org_user = True, the user will be mapped to the org
        if is_org_admin = True, the user will be made an org admin
        org - Org object
        """
        org_user = OcUser().setup_user(
            username=org_user_name,
            email=org_user_name + '@email.cc',
            first_name=org_user_name + '_first_name',
            last_name=org_user_name + '_last_name'
        )

        if is_org_user:
            # mapping user to org
            oui = OrgUserInfo(org_user.id)
            oui.setup_orguser(org)

            # making a user an org admin
            if is_org_admin:
                oui.make_org_admin(org.id)

        org_user.set_password(password)
        org_user.save()

    def set_up_objects(self, old=False, user=False):
        # creating NPF org
        org = OcOrg().setup_org(name="NPF_org_1", status="npf")
        self.org_id = org_id = org.id

        # creating users
        # admins
        self.create_user('org_user_1', org, is_org_user=True, is_org_admin=True)
        self.create_user('org_user_2', org, is_org_user=True, is_org_admin=True, password='password2')
        self.create_user('org_user_3', org, is_org_user=True, is_org_admin=True, password='password3')

        self.org_user_1 = User.objects.get(username='org_user_1')
        self.org_user_2 = User.objects.get(username='org_user_2')
        self.org_user_3 = User.objects.get(username='org_user_3')

        # volunteer user
        self.create_user('volunteer_1', org, is_org_user=False, is_org_admin=False)
        self.create_user('volunteer_2', org, is_org_user=False, is_org_admin=False)

        # setup Project
        project = Project.objects.create(
            org=org,
            name="test_project_1"
        )

        org_admin = User.objects.get(username='org_user_1')

        future_date = timezone.now() + timedelta(days=1)
        past_date = timezone.now() - timedelta(days=2)

        # setting up events
        self.future_event = Event.objects.create(
            project=project,
            is_public=True,
            description="future event",
            location="test_location_1",
            coordinator=org_admin,
            creator_id=org_admin.id,
            event_type="GR",
            datetime_start=future_date,
            datetime_end=future_date + timedelta(days=1)
        )

        self.current_event = Event.objects.create(
            project=project,
            is_public=True,
            description="current event",
            location="test_location_2",
            coordinator=org_admin,
            creator_id=org_admin.id,
            event_type="GR",
            datetime_start=past_date,
            datetime_end=future_date
        )

        self.finished_event = Event.objects.create(
            project=project,
            is_public=True,
            description="finished event",
            location="test_location_3",
            coordinator=org_admin,
            creator_id=org_admin.id,
            event_type="GR",
            datetime_start=past_date,
            datetime_end=past_date + timedelta(days=1)
        )

        # @@ TODO @@
        # move repeatable actions during setting up testing environment to a class in tests/interfaces
        #

        # creating APPROVED 4 hours for NPF admin1
        volunteer1 = User.objects.get(username='volunteer_1')
        datetime_start = past_date + timedelta(hours=2)
        datetime_end = past_date + timedelta(hours=6)

        project = Project.objects.create(
            org=org,
            name="test_project_2"
        )

        volunteer1_mt_event_1 = Event.objects.create(
            project=project,
            is_public=True,
            description="finished event",
            location="test_location_4",
            coordinator=org_admin,
            event_type="MN",
            datetime_start=datetime_start,
            datetime_end=datetime_end
        )

        volunteer1_timelog = UserTimeLog.objects.create(
            user=volunteer1,
            event=volunteer1_mt_event_1,
            datetime_start=datetime_start,
            datetime_end=datetime_end,
            is_verified=True
        )

        actiontimelog = AdminActionUserTime.objects.create(
            user=org_admin,
            usertimelog=volunteer1_timelog,
            action_type='app'
        )

        # creating APPROVED 2 hours for NPF admin2
        org_admin = User.objects.get(username='org_user_2')
        volunteer2 = User.objects.get(username='volunteer_2')
        datetime_start = past_date + timedelta(hours=1)
        datetime_end = past_date + timedelta(hours=3)

        project = Project.objects.create(
            org=org,
            name="test_project_2"
        )

        volunteer2_mt_event_1 = Event.objects.create(
            project=project,
            is_public=True,
            description="finished event 2",
            location="test_location_5",
            coordinator=org_admin,
            event_type="MN",
            datetime_start=datetime_start,
            datetime_end=datetime_end
        )

        volunteer2_timelog = UserTimeLog.objects.create(
            user=volunteer2,
            event=volunteer2_mt_event_1,
            datetime_start=datetime_start,
            datetime_end=datetime_end,
            is_verified=True
        )

        actiontimelog = AdminActionUserTime.objects.create(
            user=org_admin,
            usertimelog=volunteer2_timelog,
            action_type='app'
        )

        # creating APPROVED 6 hours for NPF admin3
        org_admin = User.objects.get(username='org_user_3')
        volunteer2 = User.objects.get(username='volunteer_2')
        datetime_start = past_date + timedelta(hours=4)
        datetime_end = past_date + timedelta(hours=10)

        project = Project.objects.create(
            org=org,
            name="test_project_2"
        )

        volunteer2_mt_event_1 = Event.objects.create(
            project=project,
            is_public=True,
            description="finished event 2",
            location="test_location_5",
            coordinator=org_admin,
            event_type="MN",
            datetime_start=datetime_start,
            datetime_end=datetime_end
        )

        volunteer2_timelog = UserTimeLog.objects.create(
            user=volunteer2,
            event=volunteer2_mt_event_1,
            datetime_start=datetime_start,
            datetime_end=datetime_end,
            is_verified=True
        )

        actiontimelog = AdminActionUserTime.objects.create(
            user=org_admin,
            usertimelog=volunteer2_timelog,
            action_type='app'
        )

        # creating PENDING 1 hour assigned to NPF admin1 (currently logged in)
        volunteer2 = User.objects.get(username='volunteer_2')
        org_admin = User.objects.get(username='org_user_1')
        datetime_start = past_date + timedelta(hours=5)
        datetime_end = past_date + timedelta(hours=6)

        volunteer2_mt_event_2 = Event.objects.create(
            project=project,
            is_public=True,
            description="pending event",
            location="test_location_6",
            coordinator=org_admin,
            event_type="MN",
            datetime_start=datetime_start,
            datetime_end=datetime_end
        )

        volunteer2_timelog = UserTimeLog.objects.create(
            user=volunteer2,
            event=volunteer2_mt_event_2,
            datetime_start=datetime_start,
            datetime_end=datetime_end,
            is_verified=False
        )

        actiontimelog = AdminActionUserTime.objects.create(
            user=org_admin,
            usertimelog=volunteer2_timelog,
            action_type='req'
        )

        # creating PENDING 2 hours assigned to NPF admin2
        volunteer1 = User.objects.get(username='volunteer_1')
        org_admin = User.objects.get(username='org_user_2')
        datetime_start = past_date + timedelta(hours=2)
        datetime_end = past_date + timedelta(hours=4)

        volunteer1_mt_event_2 = Event.objects.create(
            project=project,
            is_public=True,
            description="pending event",
            location="test_location_7",
            coordinator=org_admin,
            event_type="MN",
            datetime_start=datetime_start,
            datetime_end=datetime_end
        )

        volunteer1_timelog = UserTimeLog.objects.create(
            user=volunteer1,
            event=volunteer1_mt_event_2,
            datetime_start=datetime_start,
            datetime_end=datetime_end,
            is_verified=False
        )

        actiontimelog = AdminActionUserTime.objects.create(
            user=org_admin,
            usertimelog=volunteer1_timelog,
            action_type='req'
        )

        # creating PENDING 3 hours assigned to NPF admin3
        volunteer2 = User.objects.get(username='volunteer_2')
        org_admin = User.objects.get(username='org_user_3')
        datetime_start = past_date + timedelta(hours=1)
        datetime_end = past_date + timedelta(hours=4)

        volunteer2_mt_event_2 = Event.objects.create(
            project=project,
            is_public=True,
            description="pending event",
            location="test_location_8",
            coordinator=org_admin,
            event_type="MN",
            datetime_start=datetime_start,
            datetime_end=datetime_end
        )

        volunteer2_timelog = UserTimeLog.objects.create(
            user=volunteer2,
            event=volunteer2_mt_event_2,
            datetime_start=datetime_start,
            datetime_end=datetime_end,
            is_verified=False
        )

        actiontimelog = AdminActionUserTime.objects.create(
            user=org_admin,
            usertimelog=volunteer2_timelog,
            action_type='req'
        )

    def _check_url_parser(self, event_id, url):
        """
        Assert string 'url' exist is in the response.content when edit an event.

        This method asserts forward (upon saving) and backward (upon loading
        EditEventForm) href HTML tags substitution in description field of an
        Event with id 'event_id' (integer).
        """
        # update event description field
        upcoming_event_obj = Event.objects.get(pk=event_id)
        upcoming_event_obj.description = url
        upcoming_event_obj.save()

        # check if URLs are shown on event-detail page
        response = self.client.get('/event-detail/%d/' % event_id)
        processed_content = re.sub(r'\s+', ' ', response.content)

        if ('http' not in url) and ('https' not in url):
            self.assertIn('href="http://%s"' % url, processed_content)
        else:
            self.assertIn('href="%s"' % url, processed_content)

        # check if there is no HTML tags in edit event form description field
        response = self.client.get('/edit-event/%d/' % event_id)
        self.assertNotIn('href=', response.context['form']['event_description'])

    def setUp(self):
        # setting up objects
        self.set_up_objects()

        # logging in user
        self.client = Client()
        org_user = User.objects.get(username="org_user_1")
        self.client.login(username=org_user.username, password='password')

    def test_npf_org_admin_profile_page(self):
        """Test user profile page accessibility and links to NPF org profile page."""
        response = self.client.get('/profile/')

        # check if users sees profile page
        self.assertEqual(response.status_code, 200)
        # self.assertTemplateUsed(response, 'profile.html')

        # check if user sees 2 urls to npf admin page
        self.assertContains(response, '<a href="/org-admin/">', count=2)
        # check if the 2nd npf admin url has an icon
        self.assertContains(response, '<i class="fa fa-lg fa-gear"></i>',)

    def test_npf_profile_page(self):
        """Test the content of an NPF org profile page."""
        response = self.client.get('/org-admin/')
        processed_content = re.sub(r'\s+', ' ', response.content)

        # check if users sees NFL org profile page
        self.assertEqual(response.status_code, 200)
        # self.assertTemplateUsed(response, 'org-admin.html')

        # assert org/my hours tracked are displayed
        self.assertIn('Org hours tracked: 12.0', processed_content)
        self.assertIn('My hours tracked: 4.0', processed_content, )

        # assert displayed events sections
        self.assertIn(
            'at <strong>test_location_1</strong>',
            processed_content,
        )  # testing upcoming events
        self.assertIn('Events happening now', processed_content)
        self.assertIn('Past events', processed_content)

        # hours pending and approved are there
        self.assertIn('Hours pending', processed_content)
        self.assertIn('Hours approved', processed_content)

        # check for buttons
        self.assertIn(
            '<a href="/live-dashboard/2/"/>',
            processed_content
        )  # testing start button
        self.assertIn('Approve hours', processed_content)
        self.assertIn('<a href="/approve-hours/"', processed_content)
        self.assertIn('Create event', processed_content)
        self.assertIn('<a href="/create-event/1/"', processed_content)

        # assert that events' titles are displayed correctly
        self.assertIn("test_project_1", processed_content)

        # assert that correct LOCATIONS are there
        self.assertContains(response, 'test_location_1', count=1)
        self.assertContains(response, 'test_location_2', count=1)
        self.assertContains(response, 'test_location_3', count=1)

    def test_npf_admin_approved_hours(self):
        response = self.client.get('/org-admin/')
        # checking if pending hours are correctly sorted (logged in admin first then all other admins by amount of pending hours in descending order)
        # expected_list_of_approved_hours_by_each_admin = OrderedDict([{1: 4.0}, {3: 6.0}, {2: 2.0}])
        expected_list_of_approved_hours_by_each_admin = OrderedDict([(self.org_user_1, 4.0), (self.org_user_3, 6.0), (self.org_user_2, 2.0)])
        self.assertDictEqual(
            response.context['issued_by_admin'],
            expected_list_of_approved_hours_by_each_admin
        )

    def test_npf_admin_pending_hours(self):
        response = self.client.get('/org-admin/')
        # checking if pending hours are correctly sorted (logged in admin first then all other admins by amount of pending hours in descending order)
        expected_list_of_pending_hours_by_each_admin = OrderedDict([(self.org_user_1, 1.0), (self.org_user_3, 3.0), (self.org_user_2, 2.0)])
        self.assertDictEqual(
            response.context['hours_pending_by_admin'],
            expected_list_of_pending_hours_by_each_admin
        )

    def test_npf_admins_displayed_in_pending_approved_hours_section(self):
        response = self.client.get('/org-admin/')
        processed_content = re.sub(r'\s+', ' ', response.content)

        self.assertIn(
            '<a href="/hours-detail/?is_admin=1&amp;user_id=1&amp;type=approved"',
            processed_content
        )
        self.assertIn(
            '<a href="/hours-detail/?is_admin=1&amp;user_id=2&amp;type=pending"',
            processed_content
        )
        self.assertIn(
            'org_user_1_first_name org_user_1_last_name: 4.000 </a>',
            processed_content
        )
        self.assertIn(
            'org_user_2_first_name org_user_2_last_name: 2.000 </a>',
            processed_content
        )

    def test_npf_page_upcoming_events_list(self):
        response = self.client.get('/org-admin/')
        upcoming_event_obj = Event.objects.filter(pk=1)[0]
        self.assertEqual(
            response.context['events_group_upcoming'][0],
            upcoming_event_obj
        )

    def test_npf_page_past_events_list(self):
        response = self.client.get('/org-admin/')
        past_event_obj = Event.objects.filter(pk=3)[0]
        self.assertEqual(
            response.context['events_group_past'][0],
            past_event_obj
        )

    def test_npf_page_create_event_button_url(self):
        response = self.client.get('/org-admin/')
        processed_content = re.sub(r'\s+', ' ', response.content)
        self.assertIn(
            '<a href="/create-event/{}/"'.format(self.org_id),
            processed_content
        )

    def test_hours_details_clickable(self):
        response = self.client.get('/org-admin/')

        # check hours_pending_npf_admin1.context
        hours_pending_npf_admin1 = self.client.get(
            '/hours-detail/?is_admin=1&user_id=1&type=pending')
        self.assertEqual(hours_pending_npf_admin1.status_code, 200)
        expected_queryset_len = 1
        self.assertEqual(
            len(hours_pending_npf_admin1.context['hours_detail'].all()),
            expected_queryset_len
        )

        # check hours_approved_npf_admin1.context
        hours_approved_npf_admin1 = self.client.get(
            '/hours-detail/?is_admin=1&user_id=1&type=approved')
        self.assertEqual(hours_approved_npf_admin1.status_code, 200)
        expected_queryset_len = 1
        self.assertEqual(
            len(hours_approved_npf_admin1.context['hours_detail'].all()),
            expected_queryset_len
        )

        # check hours_pending_npf_admin2.context
        hours_pending_npf_admin2 = self.client.get(
            '/hours-detail/?is_admin=1&user_id=2&type=pending')
        self.assertEqual(hours_pending_npf_admin2.status_code, 200)
        expected_queryset_len = 1
        self.assertEqual(
            len(hours_pending_npf_admin2.context['hours_detail'].all()),
            expected_queryset_len
        )

        # check hours_approved_npf_admin2.context
        hours_approved_npf_admin2 = self.client.get(
            '/hours-detail/?is_admin=1&user_id=2&type=approved')
        self.assertEqual(hours_approved_npf_admin2.status_code, 200)
        expected_queryset_len = 1
        self.assertEqual(
            len(hours_approved_npf_admin2.context['hours_detail'].all()),
            expected_queryset_len
        )

    def test_upcoming_event_description_parser(self):
        """Test parser in event description field when editing event."""
        upcoming_event_id = self.future_event.pk

        # adding url with WWW to upcoming event
        self._check_url_parser(upcoming_event_id, 'www.testurl.com')

        # adding url with http to upcoming event
        self._check_url_parser(upcoming_event_id, 'http://www.testurl.com')

        # adding url with https to upcoming event
        self._check_url_parser(upcoming_event_id, 'https://www.testurl.com')
