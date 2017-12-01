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
            email = org_user_name+'@email.cc'
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


        #creating approved 2 hours for org admin
        datetime_start = past_date + timedelta(hours=2)
        datetime_end = past_date + timedelta(hours=6)

        org_admin_mt_event = Event.objects.create(
            project=project,
            is_public = True,
            description="finished event",
            location="test_location_3",
            coordinator=org_admin,
            creator_id=org_admin.id,
            event_type="MT",
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


        # @@ TODO @@
        # DELETE THIS BLOCK
        # print "\nHERE"
        # print response.content
        # print Project.objects.all()
        # print Event.objects.all()
        # print response.templates[0].name
        # print "HERE\n"

        # check if users sees NFL org profile page
        self.assertEqual(response.status_code, 200)
        #self.assertTemplateUsed(response, 'org-admin.html')

        # assert org/my hours tracked are displayed
        self.assertContains(response, '<h6 class="one-margin-top no-margin-bottom">Org hours tracked: 4.0</h6>')
        self.assertContains(response, '<h6 class="half-margin-bottom">My hours tracked: 4.0</h6>')

        # assert displayed events sections
        self.assertContains(response, 'at <strong>test_location_1</strong>') # testing upcoming events
        self.assertContains(response, '<h6 class="half-margin-bottom">Events happening now</h6>')
        self.assertContains(response, '<h6 class="half-margin-bottom">Past events</h6>')

        # hours pending and approved
        # @@ TODO @@
        # add numbers to hours
        self.assertContains(response, '<h6 class="half-margin-bottom">Hours pending</h6>')
        self.assertContains(response, '<h6 class="half-margin-bottom">Hours approved</h6>')

        # check for buttons
        self.assertContains(response, '<button class="button round small">Start</button>', count=1)
        self.assertContains(response, 'href="javascript:status()" class="button round tiny secondary"') #check for approve hours button
        self.assertContains(response, 'Create event', count=2)



        # assert that events' titles are displayed correctly
        self.assertContains(response, "Let's test_project_1!", count=3)



        # assert that correct LOCATIONS are there
        self.assertContains(response, 'test_location_1', count=1)
        self.assertContains(response, 'test_location_2', count=1)
        self.assertContains(response, 'test_location_3', count=1)


    def npf_admins_displayed_under_pending_approved_hours(self):

        response = self.client.get('/org-admin/')

        # @@TODO add NUMBER instead X @@
        self.assertContains(response, '<a href="/hours-detail/" class="button round tiny secondary">Admin1: X</a>')
        self.assertContains(response, '<a href="/hours-detail/" class="button round tiny secondary">Admin2: Y</a>')



