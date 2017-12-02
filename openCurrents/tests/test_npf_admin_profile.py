from django.test import Client, TestCase
from django.contrib.auth.models import User

from datetime import datetime, timedelta
from django.utils import timezone

#from openCurrents import views, urls

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
    Ledger

from openCurrents.interfaces.ocuser import \
    OcUser, \
    InvalidUserException, \
    UserExistsException

from openCurrents.interfaces.orgs import \
    OcOrg, \
    OrgUserInfo, \
    OcUser , \
    OcLedger

from openCurrents.interfaces.orgadmin import OrgAdmin

from openCurrents.interfaces.common import diffInHours

import pytz
import uuid
import random
import string
import re


class NpfAdminView(TestCase):

    @staticmethod
    def create_user(org_user_name, org, is_org_user=False, is_org_admin=False):
        """
        users and maps them to the org if needed.
        org_user_name - string
        if is_org_user = True, the user will be mapped to the org
        if is_org_admin = True, the user will be made an org admin
        org - Org object
        """

        org_user = OcUser().setup_user(
            username = org_user_name,
            email = org_user_name+'@email.cc',
            first_name=org_user_name + '_first_name',
            last_name= org_user_name + '_last_name'
        )

        if is_org_user:
            # mapping user to org
            oui = OrgUserInfo(org_user.id)
            oui.setup_orguser(org)

            # making a user an org admin
            if is_org_admin:
                oui.make_org_admin(org.id)

        org_user.set_password('password')
        org_user.save()


    def set_up_objects(self, old=False, user=False):
        # creaing org
        org = OcOrg().setup_org(name="NPF_org_1", status="npf")

        # creating users
        # admins
        self.create_user('org_user_1', org, is_org_user=True, is_org_admin=True)
        self.create_user('org_user_2', org, is_org_user=True, is_org_admin=True)

        # regular user
        #self.create_user('org_user_2', org, is_org_user=False, is_org_admin=False)

        # setup event
        project = Project.objects.create(
            org=org,
            name="test_project_1"
        )

        org_admin = User.objects.get(username='org_user_1')

        future_date = timezone.now() + timedelta(days=1)
        past_date = timezone.now() - timedelta(days=2)


        future_event = Event.objects.create(
            project=project,
            is_public = True,
            description="future event",
            location="test_location_1",
            coordinator=org_admin,
            creator_id=org_admin.id,
            event_type="GR",
            datetime_start=future_date,
            datetime_end=future_date + timedelta(days=1)
        )

        current_event = Event.objects.create(
            project=project,
            is_public = True,
            description="current event",
            location="test_location_2",
            coordinator=org_admin,
            creator_id=org_admin.id,
            event_type="GR",
            datetime_start=past_date,
            datetime_end=future_date
        )

        finished_event = Event.objects.create(
            project=project,
            is_public = True,
            description="finished event",
            location="test_location_3",
            coordinator=org_admin,
            creator_id=org_admin.id,
            event_type="GR",
            datetime_start=past_date,
            datetime_end=past_date + timedelta(days=1)
        )


        #creating approved 4 hours for NPF admin1
        datetime_start = past_date + timedelta(hours=2)
        datetime_end = past_date + timedelta(hours=6)

        project = Project.objects.create(
            org=org,
            name="test_project_2"
        )

        org_admin_mt_event = Event.objects.create(
            project=project,
            is_public = True,
            description="finished event",
            location="test_location_3",
            coordinator=org_admin,
            creator_id=org_admin.id,
            event_type="MN",
            datetime_start=datetime_start,
            datetime_end=datetime_end
        )

        org_admin_timelog = UserTimeLog.objects.create(
            user=org_admin,
            event=org_admin_mt_event,
            datetime_start=datetime_start,
            datetime_end=datetime_end,
            is_verified=True
        )

        actiontimelog = AdminActionUserTime.objects.create(
            user=org_admin,
            usertimelog=org_admin_timelog,
            action_type='app'
        )

        amount = diffInHours(datetime_start, datetime_end)
        OcLedger().issue_currents(
                entity_id_from=org.orgentity.id,
                entity_id_to=org_admin.userentity.id,
                action=actiontimelog,
                amount=amount
            )


        #creating pending 2 hours assigned to NPF admin2
        self.create_user('volunteer_1', org, is_org_user=False, is_org_admin=False)
        volunteer1 = User.objects.get(username='volunteer_1')
        org_admin = User.objects.get(username='org_user_2')
        datetime_start = past_date + timedelta(hours=2)
        datetime_end = past_date + timedelta(hours=4)

        volunteer1_mt_event = Event.objects.create(
            project=project,
            is_public = True,
            description="pending event",
            location="test_location_4",
            coordinator=org_admin,
            #creator_id=volunteer1.id,
            event_type="MN",
            datetime_start=datetime_start,
            datetime_end=datetime_end
        )

        volunteer1_timelog = UserTimeLog.objects.create(
            user=volunteer1,
            event=volunteer1_mt_event,
            datetime_start=datetime_start,
            datetime_end=datetime_end,
            is_verified=False
        )

        actiontimelog = AdminActionUserTime.objects.create(
            user=org_admin,
            usertimelog=volunteer1_timelog,
            action_type='req'
        )




    def setUp(self):
        # setting up objects
        self.set_up_objects()

        # logging in user
        self.client = Client()
        org_user = User.objects.filter(username="org_user_1")
        self.client.login(username='org_user_1', password='password')


    def test_npf_org_admin_profile_page(self):
        """
        tests user profile page accessibility and links to NPF org profile page
        """
        response = self.client.get('/profile/')

        # check if users sees profile page
        self.assertEqual(response.status_code, 200)
        #self.assertTemplateUsed(response, 'profile.html')

        # check if user sees 2 urls to npf admin page
        self.assertContains(response, '<a href="/org-admin/">', count=2)
        # check if the 2nd npf admin url has an icon
        self.assertContains(response, '<i class="fa fa-lg fa-gear"></i>',)


    def test_npf_profile_page(self):
        """
        tests the content of an NPF org profile page
        """
        response = self.client.get('/org-admin/')
        processed_content = re.sub(r'\s+', ' ', response.content )

        # @@ TODO @@
        # DELETE THIS BLOCK
        # print "\nHERE"
        # print processed_content
        # print Project.objects.all()
        # print Event.objects.all()
        # print response.templates[0].name
        # print "HERE\n"

        # check if users sees NFL org profile page
        self.assertEqual(response.status_code, 200)
        #self.assertTemplateUsed(response, 'org-admin.html')

        # assert org/my hours tracked are displayed
        self.assertIn('Org hours tracked: 4.0', processed_content)
        self.assertIn('My hours tracked: 4.0', processed_content, )

        # assert displayed events sections
        self.assertIn('at <strong>test_location_1</strong>', processed_content, ) # testing upcoming events
        self.assertIn('Events happening now', processed_content)
        self.assertIn( 'Past events', processed_content)

        # hours pending and approved are there
        self.assertIn( 'Hours pending', processed_content)
        self.assertIn( 'Hours approved', processed_content)

        # check for buttons
        self.assertIn( '<a href="/live-dashboard/2/"/>', processed_content) # testing start button
        self.assertIn( 'Approve hours', processed_content)
        self.assertIn( '<a href="javascript:status()"', processed_content)
        self.assertIn( 'Create event', processed_content)
        self.assertIn( '<a href="/create-event/1/"', processed_content)

        # assert that events' titles are displayed correctly
        self.assertIn( "Let's test_project_1!", processed_content)

        # assert that correct LOCATIONS are there
        self.assertContains(response, 'test_location_1', count=1)
        self.assertContains(response, 'test_location_2', count=1)
        self.assertContains(response, 'test_location_3', count=1)


    def test_npf_admin_approved_hours(self):
        response = self.client.get('/org-admin/')
        # checking if approved hours are correct
        expected_list_of_approved_hours_by_each_admin = [{1: 4.0}, {2: 0.0}]
        self.assertListEqual(response.context['issued_by_admin'],expected_list_of_approved_hours_by_each_admin)


    def test_npf_admin_pending_hours(self):
        response = self.client.get('/org-admin/')
        # checking if pending hours are correct
        expected_list_of_pending_hours_by_each_admin = [{1: 0.0}, {2: 2.0}]
        self.assertListEqual(response.context['hours_pending_by_admin'],expected_list_of_pending_hours_by_each_admin)


    def test_npf_admins_displayed_under_pending_approved_hours(self):

        response = self.client.get('/org-admin/')
        processed_content = re.sub(r'\s+', ' ', response.content )

        # @@TODO add user ID to URLs @@
        self.assertIn('<a href="/hours-detail/"', processed_content)
        self.assertIn('org_user_1_first_name org_user_1_last_name: 4.0 </a>', processed_content)
        self.assertIn('<a href="/hours-detail/"',processed_content)
        self.assertIn('<a href="/hours-detail/"', processed_content)
        self.assertIn('org_user_2_first_name org_user_2_last_name: 0.0 </a>',processed_content)
