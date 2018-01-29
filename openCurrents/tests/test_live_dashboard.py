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
    Ledger, \
    UserEventRegistration

from openCurrents.interfaces.ocuser import \
    OcUser, \
    InvalidUserException, \
    UserExistsException

from openCurrents.tests.interfaces.common import (
    SetUpTests,
    _create_test_user,
    _create_project,
    _setup_volunteer_hours,
    _create_event,
    _setup_user_event_registration,
    _create_org
)


from openCurrents.interfaces.orgadmin import OrgAdmin
from openCurrents.interfaces.ledger import OcLedger

from openCurrents.interfaces.common import diffInHours

import pytz
import uuid
import random
import string
import re
from collections import OrderedDict
from decimal import Decimal

from unittest import skip


class SetupTest(TestCase):

    # [helpers begin]

    def _asserting_user_ledger(
        self,
        user,
        ledger_query,
        expected_num_entries,
        expected_amount,
        currency='cur'):
        """
        user - user instance to assert
        ledger_query - query eg Ledger.objects.all()
        expected_num_entries - integer
        expected_amount - str
        currency - str 'cur' or 'usd'
        """
        if expected_num_entries != 0:
            self.assertEqual(expected_num_entries, len(ledger_query.filter(action__usertimelog__user=user)))
            self.assertEqual('cur', ledger_query.get(action__usertimelog__user=user).currency)
            self.assertEqual(Decimal(expected_amount), ledger_query.get(action__usertimelog__user=user).amount)
        else:
            self.assertEqual(expected_num_entries, len(ledger_query.filter(action__usertimelog__user=user)))




    def _add_user_to_event(
        self,
        admin,
        event_id,
        volunteer,
        registered_users_num,
        expected_user_registration=True
        ):
        """
        client - unittest client
        event_id - integer
        admin - user instance for NPF admin
        volunteer - user instance
        registered_users_num - number of ALREADY registered users
        expected_user_registration - defines if user shoul or shoudn't be added to the
        event
        """
        # logging in
        self.client.login(username=admin.username, password='password')
        response = self.client.get('/live-dashboard/{}/'.format(str(event_id)))

        # check if users sees the page
        self.assertEqual(response.status_code, 200)

        # verify there are correct number of registered users under event
        self.assertEqual(len(response.context['registered_users']), registered_users_num)

        # assert approved hours from npf admin perspective
        self.assertEqual(0.0 , self.org_npf_adm.get_total_hours_issued())

        # registering the first volunteer
        post_response = self.client.post('/event_register_live/{}/'.format(str(event_id)),
            {
                'userid':str(volunteer.id)
            })

        # getting data from live-dasboard
        response = self.client.get('/live-dashboard/{}/'.format(str(event_id)))

        if expected_user_registration:
            self.assertEqual(post_response.status_code, 201)
            self.assertEqual(len(response.context['registered_users']), registered_users_num + 1)
            self.assertIn('"userid": "{}"'.format(str(volunteer.id)), post_response.content)
            self.assertIn('"eventid": "{}"'.format(str(event_id)), post_response.content)

        else:
            self.assertEqual(post_response.status_code, 201)
            self.assertEqual(len(response.context['registered_users']), registered_users_num)

    # [helpers End]


    def setUp(self):

        future_date = timezone.now() + timedelta(days=1)
        past_date = timezone.now() - timedelta(days=1)
        biz_orgs_list = []


        npf_orgs_list = ['NPF_org_1']
        volunteers_list = ['volunteer_1', 'volunteer_2', 'volunteer_3', 'volunteer_4']

        test_setup = SetUpTests()
        test_setup.generic_setup(npf_orgs_list, biz_orgs_list, volunteers_list)


        # setting org var
        self.org = test_setup.get_all_npf_orgs()[0]

        # setting up projects
        org_projects = test_setup.get_all_projects(self.org)
        self.project_1 = org_projects[0]
        self.project_2 = _create_project(self.org, 'test_project_2')

        #creating an npf admin
        all_admins = test_setup.get_all_npf_admins()
        self.npf_admin = all_admins[0]

        #assigning existing volunteers to variables
        all_volunteers = test_setup.get_all_volunteers()

        self.volunteer_1 = all_volunteers[0]
        self.volunteer_2 = all_volunteers[1]
        self.volunteer_3 = all_volunteers[2]
        self.volunteer_4 = all_volunteers[3]

        self.volunteer_4.set_unusable_password() # mocking non-confirmed user


        # creating a future event  (event duration: 24 hrs)
        future_date2 = future_date +timedelta(days=1)
        self.event_future = _create_event(
                            self.project_1,
                            self.npf_admin.id,
                            future_date,
                            future_date2,
                            description="Future Event",
                            is_public=True,
                            event_type="GR",
                            coordinator=self.npf_admin
                        )

        # creating an event that's happening now (event duration: 48 hrs)
        self.event_current = _create_event(
                            self.project_1,
                            self.npf_admin.id,
                            past_date,
                            future_date,
                            description="Current Event",
                            is_public=True,
                            event_type="GR",
                            coordinator=self.npf_admin
                        )

        # creating a past event (event duration: 24 hrs)
        past_date_2 = past_date - timedelta(days=1)
        self.event_past = _create_event(
                            self.project_1,
                            self.npf_admin.id,
                            past_date_2,
                            past_date,
                            description="Past Event",
                            is_public=True,
                            event_type="GR",
                            coordinator=self.npf_admin
                        )


        #creating UserEventRegistration for event_future for npf admin and a volunteer1
        npf_admin_event_registration = _setup_user_event_registration(self.npf_admin, self.event_future)
        volunteer_event_registration = _setup_user_event_registration(self.volunteer_1, self.event_future)
        volunteer_event_registration = _setup_user_event_registration(self.volunteer_2, self.event_future)

        #creating UserEventRegistration for event_current for npf admin and a volunteer2
        npf_admin_event2_registration = _setup_user_event_registration(self.npf_admin, self.event_current)
        volunteer_event2_registration = _setup_user_event_registration(self.volunteer_1, self.event_current)
        volunteer_event2_registration = _setup_user_event_registration(self.volunteer_2, self.event_current)

        #creating UserEventRegistration for event_past for npf admin and a volunteer3
        npf_admin_event3_registration = _setup_user_event_registration(self.npf_admin, self.event_past)
        volunteer_event3_registration = _setup_user_event_registration(self.volunteer_1, self.event_past)
        volunteer_event3_registration = _setup_user_event_registration(self.volunteer_2, self.event_past)

        # oc instances
        self.oc_npf_adm = OcUser(self.npf_admin.id)
        self.org_npf_adm = OrgAdmin(self.npf_admin.id)
        self.oc_vol_1 = OcUser(self.volunteer_1.id)
        self.oc_vol_2 = OcUser(self.volunteer_2.id)
        self.oc_vol_3 = OcUser(self.volunteer_3.id)
        self.oc_vol_4 = OcUser(self.volunteer_4.id)

        # user entities
        self.user_enitity_id_npf_adm = UserEntity.objects.get(user = self.npf_admin).id
        self.user_enitity_id_vol_1 = UserEntity.objects.get(user = self.volunteer_1).id
        self.user_enitity_id_vol_2 = UserEntity.objects.get(user = self.volunteer_2).id
        self.user_enitity_id_vol_3 = UserEntity.objects.get(user = self.volunteer_3).id
        self.user_enitity_id_vol_4 = UserEntity.objects.get(user = self.volunteer_4).id

        # setting up client
        self.client = Client()



class LiveDashboard(SetupTest):

    def test_initial_setup_assertion(self):
        """
        1 event in the past
        1 event is happening now
        1 event in the future
        """
        # logging in
        self.client.login(username=self.npf_admin.username, password='password')
        response = self.client.get('/org-admin/')

        self.assertEqual(response.status_code, 200)

        # checkign UI
        self.assertIn('/create-event/1/', response.content)

        # checking if all the events are there
        self.assertEqual(len(response.context['events_group_current']), 1)
        self.assertEqual(len(response.context['events_group_past']), 1)
        self.assertEqual(len(response.context['events_group_current']), 1)
        self.assertEqual(len(Event.objects.all()), 3)

        # checking links in dropdowns per event
        self.assertIn('/live-dashboard/1/', response.content)
        self.assertIn('/live-dashboard/2/', response.content)
        self.assertIn('/live-dashboard/3/', response.content)


    def test_future_event(self):

        self.client.login(username=self.npf_admin.username, password='password')
        response = self.client.get('/live-dashboard/1/')

        #checking registered users
        self.assertEqual(len(response.context['registered_users']), 3)
        self.assertIn(self.npf_admin, response.context['registered_users'])
        self.assertIn(self.volunteer_1, response.context['registered_users'])
        self.assertIn(self.volunteer_2, response.context['registered_users'])


    def test_running_event(self):

        self.client.login(username=self.npf_admin.username, password='password')
        response = self.client.get('/live-dashboard/2/')

        #checking registered users
        self.assertEqual(len(response.context['registered_users']), 3)
        self.assertIn(self.npf_admin, response.context['registered_users'])
        self.assertIn(self.volunteer_1, response.context['registered_users'])
        self.assertIn(self.volunteer_2, response.context['registered_users'])


    def test_past_event(self):

        self.client.login(username=self.npf_admin.username, password='password')
        response = self.client.get('/live-dashboard/3/')

        #checking registered users
        self.assertEqual(len(response.context['registered_users']), 3)
        self.assertIn(self.npf_admin, response.context['registered_users'])
        self.assertIn(self.volunteer_1, response.context['registered_users'])
        self.assertIn(self.volunteer_2, response.context['registered_users'])




class CurrentEventCheckIn(SetupTest):

    def test_current_event_check_in(self):

        # assertion of zero state
        self.assertEqual(9, len(UserEventRegistration.objects.all()))
        self.assertEqual(3, len(UserEventRegistration.objects.filter(user=self.npf_admin)))
        self.assertEqual(3, len(UserEventRegistration.objects.filter(user=self.volunteer_1)))
        self.assertEqual(3, len(UserEventRegistration.objects.filter(user=self.volunteer_2)))

        self.assertEqual(0, len(UserTimeLog.objects.all()))
        self.assertEqual(0, len(AdminActionUserTime.objects.all()))

        self.assertEqual(0, len(self.oc_npf_adm.get_hours_approved()))
        self.assertEqual(0, len(self.oc_vol_1.get_hours_approved()))
        self.assertEqual(0, len(self.oc_vol_2.get_hours_approved()))


        # checking ledger records
        ledger_query = Ledger.objects.all()
        self.assertEqual(0, len(ledger_query))
        # asserting npf_admin user
        self.assertEqual(0, len(ledger_query.filter(action__usertimelog__user=self.npf_admin)))
        # asserting the first user
        self.assertEqual(0, len(ledger_query.filter(action__usertimelog__user=self.volunteer_1)))
        # asserting the 2nd user
        self.assertEqual(0, len(ledger_query.filter(action__usertimelog__user=self.volunteer_2)))

        # assert get_balance()
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_npf_adm))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_1))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_2))

        # logging in
        self.client.login(username=self.npf_admin.username, password='password')
        response = self.client.get('/live-dashboard/2/')
        # check if users sees the page
        self.assertEqual(response.status_code, 200)

        # checking the first volunteer
        time_now = timezone.now()
        post_response = self.client.post('/event_checkin/2/',
            {
                'userid':str(self.volunteer_1.id),
                'checkin':'true',
            })

        self.assertEqual(post_response.status_code, 201)


        # ASSERTION AFTER THE FIRST USER CHECK-IN

        # general assertion
        self.assertEqual(2, len(UserTimeLog.objects.all()))
        self.assertEqual(2, len(AdminActionUserTime.objects.all()))

        # asserting UserTimeLog timestamp
        ut = UserTimeLog.objects.get(user=self.volunteer_1)
        self.assertAlmostEqual(ut.datetime_start, time_now, delta=timedelta(seconds=1))


        # assert approved hours from users perspective
        self.assertEqual(1, len(self.oc_npf_adm.get_hours_approved()))
        self.assertEqual(1, len(self.oc_vol_1.get_hours_approved()))
        self.assertEqual(0, len(self.oc_vol_2.get_hours_approved()))

        # assert approved hours from npf admin perspective
        self.assertEqual(96.0 , self.org_npf_adm.get_total_hours_issued())

        # checking ledger records
        ledger_query = Ledger.objects.all()
        self.assertEqual(2, len(ledger_query))

        # asserting npf_admin user
        self._asserting_user_ledger(self.npf_admin, ledger_query, 1, 48)

        # asserting the first user
        self._asserting_user_ledger(self.volunteer_1, ledger_query, 1, 48)

        # asserting the 2nd user
        self._asserting_user_ledger(self.volunteer_2, ledger_query, 0, 0)

        # assert get_balance()
        self.assertEqual(Decimal('48'), OcLedger().get_balance(self.user_enitity_id_npf_adm))
        self.assertEqual(Decimal('48'), OcLedger().get_balance(self.user_enitity_id_vol_1))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_2))


        # checking the second volunteer
        time_now = timezone.now()
        post_response = self.client.post('/event_checkin/2/',
            {
                'userid':str(self.volunteer_2.id),
                'checkin':'true',
            })


        # ASSERTION AFTER THE SECOND USER CHECK-IN

        # general assertion
        self.assertEqual(3, len(UserTimeLog.objects.all()))
        self.assertEqual(3, len(AdminActionUserTime.objects.all()))

        # asserting UserTimeLog timestamp for volunteer2
        ut = UserTimeLog.objects.get(user=self.volunteer_2)
        self.assertAlmostEqual(ut.datetime_start, time_now, delta=timedelta(seconds=1))

        # assert approved hours from users perspective
        self.assertEqual(1, len(self.oc_npf_adm.get_hours_approved()))
        self.assertEqual(1, len(self.oc_vol_1.get_hours_approved()))
        self.assertEqual(1, len(self.oc_vol_2.get_hours_approved()))

        # assert approved hours from npf admin perspective
        self.assertEqual(144.0 , self.org_npf_adm.get_total_hours_issued())


        # checking ledger records
        ledger_query = Ledger.objects.all()
        self.assertEqual(3, len(ledger_query))

        # asserting npf_admin user
        self._asserting_user_ledger(self.npf_admin, ledger_query, 1, 48)

        # asserting the first user
        self._asserting_user_ledger(self.volunteer_1, ledger_query, 1, 48)

        # asserting the 2nd user
        self._asserting_user_ledger(self.volunteer_2, ledger_query, 1, 48)

        # assert get_balance()
        self.assertEqual(48, OcLedger().get_balance(self.user_enitity_id_npf_adm))
        self.assertEqual(48, OcLedger().get_balance(self.user_enitity_id_vol_1))
        self.assertEqual(48, OcLedger().get_balance(self.user_enitity_id_vol_2))


    @skip('until 1017 is fixed')
    def test_current_event_uncheck_user(self):

        # logging in
        self.client.login(username=self.npf_admin.username, password='password')
        response = self.client.get('/live-dashboard/2/')
        # check if users sees the page
        self.assertEqual(response.status_code, 200)

        # check there are no checked users
        self.assertEqual(len(response.context['checkedin_users']), 0)

        # asserting the first volunteer has grey icon
        self.assertNotIn('name="vol-checkin-2" value="2" class="hidden checkin-checkbox" checked', re.sub(r'\s+', ' ', response.content ))

        # checking IN the first volunteer
        post_response = self.client.post('/event_checkin/2/',
            {
                'userid':str(self.volunteer_1.id),
                'checkin':'true',
            })

        self.assertEqual(post_response.status_code, 201)

        # check there are two checked users
        response = self.client.get('/live-dashboard/2/')
        self.assertEqual(len(response.context['checkedin_users']), 2)
        self.assertIn(self.volunteer_1.id, response.context['checkedin_users'])

        # asserting the first volunteer has blue icon
        self.assertIn('name="vol-checkin-2" value="2" class="hidden checkin-checkbox" checked', re.sub(r'\s+', ' ', response.content ))

        # general assertion
        self.assertEqual(2, len(UserTimeLog.objects.all()))
        self.assertEqual(2, len(AdminActionUserTime.objects.all()))

        # assert approved hours from users perspective
        self.assertEqual(1, len(self.oc_npf_adm.get_hours_approved()))
        self.assertEqual(1, len(self.oc_vol_1.get_hours_approved()))
        self.assertEqual(0, len(self.oc_vol_2.get_hours_approved()))

        # assert approved hours from npf admin perspective
        self.assertEqual(96.0 , self.org_npf_adm.get_total_hours_issued())

        # asserting the first user
        ledger_query = Ledger.objects.all()
        self._asserting_user_ledger(self.volunteer_1, ledger_query, 1, 48)

        # assert get_balance()
        self.assertEqual(48, OcLedger().get_balance(self.user_enitity_id_npf_adm))
        self.assertEqual(48, OcLedger().get_balance(self.user_enitity_id_vol_1))

        # checking OUT the first volunteer
        time_now = timezone.now()
        post_response = self.client.post('/event_checkin/2/',
            {
                'userid':str(self.volunteer_1.id),
                'checkin':'false'
            })

        self.assertEqual(post_response.status_code, 201)

        # check there is only admin checked
        response = self.client.get('/live-dashboard/2/')
        self.assertIn(self.npf_admin.id, response.context['checkedin_users'])
        self.assertEqual(len(response.context['checkedin_users']), 1) # THIS ASSERTION FAILS !!!

        # asserting the first volunteer has grey icon
        self.assertNotIn('name="vol-checkin-2" value="2" class="hidden checkin-checkbox" checked', re.sub(r'\s+', ' ', response.content )) # THIS ASSERTION FAILS !!!

        # general assertion
        self.assertEqual(2, len(UserTimeLog.objects.all()))
        self.assertEqual(2, len(AdminActionUserTime.objects.all()))

        # asserting UserTimeLog timestamp
        ut = UserTimeLog.objects.get(user=self.volunteer_1)
        self.assertAlmostEqual(ut.datetime_end, time_now, delta=timedelta(seconds=1))

        # assert approved hours from users perspective
        self.assertEqual(1, len(self.oc_npf_adm.get_hours_approved()))
        self.assertEqual(1, len(self.oc_vol_1.get_hours_approved()))
        self.assertEqual(0, len(self.oc_vol_2.get_hours_approved()))

        # assert approved hours from npf admin perspective
        self.assertEqual(96.0 , self.org_npf_adm.get_total_hours_issued())

        # asserting the first user
        ledger_query = Ledger.objects.all()
        self._asserting_user_ledger(self.volunteer_1, ledger_query, 1, 48)

        # assert get_balance()
        self.assertEqual(48, OcLedger().get_balance(self.user_enitity_id_npf_adm))
        self.assertEqual(48, OcLedger().get_balance(self.user_enitity_id_vol_1))


    def test_current_event_add_existing_nonregistered_user(self):

        """
        user is added to the event
        """
        self._add_user_to_event(self.npf_admin, 1, self.volunteer_3, 3)



class CurrentEventInvite(SetupTest):

    def test_current_event_invite_new_user_invitation_opt_out(self):
        """
        Admin invites new user to the event, Invite volunteer to openCurrents
        option is checked

        Results:
        - User created for volunteer with no password
        - new user automatically registered to event
        - UserTimeLog created and UserEventRegistration created
        - AdminActionUserTime created and 'approved'
        - Volunteer's available Currents increase by the duration of the event
        - Email sent to volunteer (invite-volunteer)
        - If admin has not been awarded hours for the event, corresponding
          UserTimeLog and AdminActionUserTime are created for the admin user
          as well (so they get credit for the event)
        """

        self.client.login(username=self.npf_admin.username, password='password')
        response = self.client.get('/live-dashboard/2/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['registered_users']), 3)
        self._add_user_to_event(self.npf_admin, 2, self.volunteer_4, 3)

        # 1 in the url below means we're mocking emails
        post_signup = self.client.post('/process_signup/True/False/',
            {
                'user_firstname': 'newuser_name',
                'user_lastname': 'newuser_lastname',
                'user_email': 'newuser@ccc.cc',
                'org_admin_id': '',
                'org_name': '',
                'org_status': ''
            })

        # user is created with unusable password
        new_user = User.objects.filter(email='newuser@ccc.cc')[0]
        new_user_id = new_user.id
        self.assertEqual(len(User.objects.filter(email='newuser@ccc.cc')), 1)
        self.assertFalse(new_user.has_usable_password())

        # checking in new volunteer
        post_response = self.client.post('/event_checkin/2/',
            {
                'userid':str(new_user_id),
                'checkin':'true',
            })
        self.assertEqual(post_response.status_code, 201)

        # ASSERTION AFTER USER CHECK-IN
        # general assertion
        self.assertEqual(2, len(UserTimeLog.objects.all()))
        self.assertEqual(2, len(AdminActionUserTime.objects.all()))

        # assert approved hours from users perspective
        self.assertEqual(1, len(self.oc_npf_adm.get_hours_approved()))

        oc_new_user = OcUser(new_user.id)
        self.assertEqual(1, len(oc_new_user.get_hours_approved()))


        # assert approved hours from npf admin perspective
        self.assertEqual(96.0 , self.org_npf_adm.get_total_hours_issued())


        # checking ledger records
        ledger_query = Ledger.objects.all()
        self.assertEqual(2, len(ledger_query))

        # asserting npf_admin user
        self._asserting_user_ledger(self.npf_admin, ledger_query, 1, 48)

        # asserting the first user
        self._asserting_user_ledger(self.volunteer_1, ledger_query, 0, 0)

        # asserting the 2nd user
        self._asserting_user_ledger(self.volunteer_2, ledger_query, 0, 0)

        # asserting the 2nd user
        self._asserting_user_ledger(new_user, ledger_query, 1, 48)

        # assert get_balance()
        self.assertEqual(48, OcLedger().get_balance(self.user_enitity_id_npf_adm))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_1))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_2))

        new_user_entity_id = UserEntity.objects.get(user = new_user).id
        self.assertEqual(48, OcLedger().get_balance(new_user_entity_id))



    def test_current_event_invite_new_user_invitation_opt_in(self):
        """
        Admin invites new user to the event, Invite volunteer to openCurrents
        option is checked

        Results:
        - User created for volunteer with no password
        - new user automatically registered to event
        - UserTimeLog created and UserEventRegistration created
        - AdminActionUserTime created and 'approved'
        - Volunteer's available Currents increase by the duration of the event
        - Email sent to volunteer (invite-volunteer)
        - If admin has not been awarded hours for the event, corresponding
          UserTimeLog and AdminActionUserTime are created for the admin user
          as well (so they get credit for the event)
        """

        self.client.login(username=self.npf_admin.username, password='password')
        response = self.client.get('/live-dashboard/2/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['registered_users']), 3)
        self._add_user_to_event(self.npf_admin, 2, self.volunteer_4, 3)

        # 1 in the url below means we're mocking emails
        post_signup = self.client.post('/process_signup/True/True/1/',
            {
                'user_firstname': 'newuser2_name',
                'user_lastname': 'newuser2_lastname',
                'user_email': 'newuser2@ccc.cc',
                'org_admin_id': self.npf_admin.id,
                'org_name': '',
                'org_status': ''
            })

        # check if email was sent to user
        self.assertTrue(self.client.session['invitation_email'])

        # user is created with unusable password
        new_user = User.objects.filter(email='newuser2@ccc.cc')[0]
        new_user_id = new_user.id
        self.assertEqual(len(User.objects.filter(email='newuser2@ccc.cc')), 1)
        self.assertFalse(new_user.has_usable_password())

        # checking in new volunteer
        post_response = self.client.post('/event_checkin/2/',
            {
                'userid':str(new_user_id),
                'checkin':'true',
            })
        self.assertEqual(post_response.status_code, 201)

        # ASSERTION AFTER THE SECOND USER CHECK-IN
        # general assertion
        self.assertEqual(2, len(UserTimeLog.objects.all()))
        self.assertEqual(2, len(AdminActionUserTime.objects.all()))

        # assert approved hours from users perspective
        self.assertEqual(1, len(self.oc_npf_adm.get_hours_approved()))

        oc_new_user = OcUser(new_user.id)
        self.assertEqual(1, len(oc_new_user.get_hours_approved()))


        # assert approved hours from npf admin perspective
        self.assertEqual(96.0 , self.org_npf_adm.get_total_hours_issued())


        # checking ledger records
        ledger_query = Ledger.objects.all()
        self.assertEqual(2, len(ledger_query))

        # asserting npf_admin user
        self._asserting_user_ledger(self.npf_admin, ledger_query, 1, 48)

        # asserting the first user
        self._asserting_user_ledger(self.volunteer_1, ledger_query, 0, 0)

        # asserting the 2nd user
        self._asserting_user_ledger(self.volunteer_2, ledger_query, 0, 0)

        # asserting the 2nd user
        self._asserting_user_ledger(new_user, ledger_query, 1, 48)

        # assert get_balance()
        self.assertEqual(48, OcLedger().get_balance(self.user_enitity_id_npf_adm))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_1))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_2))

        new_user_entity_id = UserEntity.objects.get(user = new_user).id
        self.assertEqual(48, OcLedger().get_balance(new_user_entity_id))




class PastEventInvite(SetupTest):

    @skip('until speck is confirmed')
    def test_past_event_invite_new_user_invitation_opt_out(self):
        """
        Admin invites new user to the event, Invite volunteer to openCurrents
        option is checked

        Results:
        - User created for volunteer with no password
        - new user automatically registered to event
        - UserTimeLog created and UserEventRegistration created
        - AdminActionUserTime created and 'approved'
        - Volunteer's available Currents increase by the duration of the event
        - Email sent to volunteer (invite-volunteer)
        - If admin has not been awarded hours for the event, corresponding
          UserTimeLog and AdminActionUserTime are created for the admin user
          as well (so they get credit for the event)
        """

        self.client.login(username=self.npf_admin.username, password='password')
        response = self.client.get('/live-dashboard/3/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['registered_users']), 3)
        self._add_user_to_event(self.npf_admin, 2, self.volunteer_4, 3)

        # 1 in the url below means we're mocking emails
        post_signup = self.client.post('/process_signup/True/False/',
            {
                'user_firstname': 'newuser_name',
                'user_lastname': 'newuser_lastname',
                'user_email': 'newuser@ccc.cc',
                'org_admin_id': '',
                'org_name': '',
                'org_status': ''
            })

        # user is created with unusable password
        new_user = User.objects.filter(email='newuser@ccc.cc')[0]
        new_user_id = new_user.id
        self.assertEqual(len(User.objects.filter(email='newuser@ccc.cc')), 1)
        self.assertFalse(new_user.has_usable_password())

        # checking in new volunteer
        post_response = self.client.post('/event_checkin/3/',
            {
                'userid':str(new_user_id),
                'checkin':'true',
            })
        self.assertEqual(post_response.status_code, 201)

        # ASSERTION AFTER USER CHECK-IN
        # general assertion
        self.assertEqual(2, len(UserTimeLog.objects.all()))
        self.assertEqual(2, len(AdminActionUserTime.objects.all()))

        # assert approved hours from users perspective
        self.assertEqual(1, len(self.oc_npf_adm.get_hours_approved()))

        oc_new_user = OcUser(new_user.id)
        self.assertEqual(1, len(oc_new_user.get_hours_approved()))


        # assert approved hours from npf admin perspective
        self.assertEqual(96.0 , self.org_npf_adm.get_total_hours_issued())


        # checking ledger records
        ledger_query = Ledger.objects.all()
        self.assertEqual(2, len(ledger_query))

        # asserting npf_admin user
        self._asserting_user_ledger(self.npf_admin, ledger_query, 1, 48)

        # asserting the first user
        self._asserting_user_ledger(self.volunteer_1, ledger_query, 0, 0)

        # asserting the 2nd user
        self._asserting_user_ledger(self.volunteer_2, ledger_query, 0, 0)

        # asserting the 2nd user
        self._asserting_user_ledger(new_user, ledger_query, 1, 48)

        # assert get_balance()
        self.assertEqual(48, OcLedger().get_balance(self.user_enitity_id_npf_adm))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_1))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_2))

        new_user_entity_id = UserEntity.objects.get(user = new_user).id
        self.assertEqual(48, OcLedger().get_balance(new_user_entity_id))


    @skip('until speck is confirmed')
    def test_past_event_invite_new_user_invitation_opt_in(self):
        """
        Admin invites new user to the event, Invite volunteer to openCurrents
        option is checked

        Results:
        - User created for volunteer with no password
        - new user automatically registered to event
        - UserTimeLog created and UserEventRegistration created
        - AdminActionUserTime created and 'approved'
        - Volunteer's available Currents increase by the duration of the event
        - Email sent to volunteer (invite-volunteer)
        - If admin has not been awarded hours for the event, corresponding
          UserTimeLog and AdminActionUserTime are created for the admin user
          as well (so they get credit for the event)
        """

        self.client.login(username=self.npf_admin.username, password='password')
        response = self.client.get('/live-dashboard/3/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['registered_users']), 3)
        self._add_user_to_event(self.npf_admin, 2, self.volunteer_4, 3)

        # 1 in the url below means we're mocking emails
        post_signup = self.client.post('/process_signup/True/True/1/',
            {
                'user_firstname': 'newuser2_name',
                'user_lastname': 'newuser2_lastname',
                'user_email': 'newuser2@ccc.cc',
                'org_admin_id': self.npf_admin.id,
                'org_name': '',
                'org_status': ''
            })

        # check if email was sent to user
        self.assertTrue(self.client.session['invitation_email'])

        # user is created with unusable password
        new_user = User.objects.filter(email='newuser2@ccc.cc')[0]
        new_user_id = new_user.id
        self.assertEqual(len(User.objects.filter(email='newuser2@ccc.cc')), 1)
        self.assertFalse(new_user.has_usable_password())

        # checking in new volunteer
        post_response = self.client.post('/event_checkin/3/',
            {
                'userid':str(new_user_id),
                'checkin':'true',
            })
        self.assertEqual(post_response.status_code, 201)

        # ASSERTION AFTER THE SECOND USER CHECK-IN
        # general assertion
        self.assertEqual(2, len(UserTimeLog.objects.all()))
        self.assertEqual(2, len(AdminActionUserTime.objects.all()))

        # assert approved hours from users perspective
        self.assertEqual(1, len(self.oc_npf_adm.get_hours_approved()))

        oc_new_user = OcUser(new_user.id)
        self.assertEqual(1, len(oc_new_user.get_hours_approved()))


        # assert approved hours from npf admin perspective
        self.assertEqual(96.0 , self.org_npf_adm.get_total_hours_issued())


        # checking ledger records
        ledger_query = Ledger.objects.all()
        self.assertEqual(2, len(ledger_query))

        # asserting npf_admin user
        self._asserting_user_ledger(self.npf_admin, ledger_query, 1, 48)

        # asserting the first user
        self._asserting_user_ledger(self.volunteer_1, ledger_query, 0, 0)

        # asserting the 2nd user
        self._asserting_user_ledger(self.volunteer_2, ledger_query, 0, 0)

        # asserting the 2nd user
        self._asserting_user_ledger(new_user, ledger_query, 1, 48)

        # assert get_balance()
        self.assertEqual(48, OcLedger().get_balance(self.user_enitity_id_npf_adm))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_1))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_2))

        new_user_entity_id = UserEntity.objects.get(user = new_user).id
        self.assertEqual(48, OcLedger().get_balance(new_user_entity_id))



class PastEventCheckIn(SetupTest):

    def test_past_event_check_in(self):

        """
        admin checks-in a volunteer
        admin and the volunteer receive amount of currents that is equal to
        event duration
        """

        # assertion of zero state
        self.assertEqual(9, len(UserEventRegistration.objects.all()))
        self.assertEqual(3, len(UserEventRegistration.objects.filter(user=self.npf_admin)))
        self.assertEqual(3, len(UserEventRegistration.objects.filter(user=self.volunteer_1)))
        self.assertEqual(3, len(UserEventRegistration.objects.filter(user=self.volunteer_2)))

        self.assertEqual(0, len(UserTimeLog.objects.all()))
        self.assertEqual(0, len(AdminActionUserTime.objects.all()))

        self.assertEqual(0, len(self.oc_npf_adm.get_hours_approved()))
        self.assertEqual(0, len(self.oc_vol_1.get_hours_approved()))
        self.assertEqual(0, len(self.oc_vol_2.get_hours_approved()))

        # checking ledger records
        ledger_query = Ledger.objects.all()
        self.assertEqual(0, len(ledger_query))
        # asserting npf_admin user
        self._asserting_user_ledger(self.npf_admin, ledger_query, 0, 0)

        # asserting the first user
        self._asserting_user_ledger(self.volunteer_1, ledger_query, 0, 0)

        # asserting the 2nd user
        self._asserting_user_ledger(self.volunteer_2, ledger_query, 0, 0)

        # assert get_balance()
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_npf_adm))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_1))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_2))

        # logging in
        self.client.login(username=self.npf_admin.username, password='password')
        response = self.client.get('/live-dashboard/3/')
        # check if users sees the page
        self.assertEqual(response.status_code, 200)

        # checking the first volunteer
        post_response = self.client.post('/event_checkin/3/',
            {
                'userid':str(self.volunteer_1.id),
                'checkin':'true',
            })

        self.assertEqual(post_response.status_code, 201)


        # ASSERTION AFTER THE FIRST USER CHECK-IN

        # general assertion
        self.assertEqual(2, len(UserTimeLog.objects.all()))
        self.assertEqual(2, len(AdminActionUserTime.objects.all()))

        # assert approved hours from users perspective
        self.assertEqual(1, len(self.oc_npf_adm.get_hours_approved()))
        self.assertEqual(1, len(self.oc_vol_1.get_hours_approved()))
        self.assertEqual(0, len(self.oc_vol_2.get_hours_approved()))

        # assert approved hours from npf admin perspective
        self.assertEqual(48.0 , self.org_npf_adm.get_total_hours_issued())


        # checking ledger records
        ledger_query = Ledger.objects.all()
        self.assertEqual(2, len(ledger_query))


        # asserting npf_admin user
        self._asserting_user_ledger(self.npf_admin, ledger_query, 1, 24)

        # asserting the first user
        self._asserting_user_ledger(self.volunteer_1, ledger_query, 1, 24)

        # asserting the 2nd user
        self._asserting_user_ledger(self.volunteer_2, ledger_query, 0, 0)


        # assert get_balance()
        self.assertEqual(24, OcLedger().get_balance(self.user_enitity_id_npf_adm))
        self.assertEqual(24, OcLedger().get_balance(self.user_enitity_id_vol_1))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_2))


        # checking the second volunteer
        post_response = self.client.post('/event_checkin/3/',
            {
                'userid':str(self.volunteer_2.id),
                'checkin':'true',
            })


        # ASSERTION AFTER THE SECOND USER CHECK-IN

        # general assertion
        self.assertEqual(3, len(UserTimeLog.objects.all()))
        self.assertEqual(3, len(AdminActionUserTime.objects.all()))

        # assert approved hours from users perspective
        self.assertEqual(1, len(self.oc_npf_adm.get_hours_approved()))
        self.assertEqual(1, len(self.oc_vol_1.get_hours_approved()))
        self.assertEqual(1, len(self.oc_vol_2.get_hours_approved()))

        # assert approved hours from npf admin perspective
        self.assertEqual(72.0 , self.org_npf_adm.get_total_hours_issued())


        # checking ledger records
        ledger_query = Ledger.objects.all()
        self.assertEqual(3, len(ledger_query))


        # asserting npf_admin user
        self._asserting_user_ledger(self.npf_admin, ledger_query, 1, 24)

        # asserting the first user
        self._asserting_user_ledger(self.volunteer_1, ledger_query, 1, 24)

        # asserting the 2nd user
        self._asserting_user_ledger(self.volunteer_2, ledger_query, 1, 24)


        # assert get_balance()
        self.assertEqual(24, OcLedger().get_balance(self.user_enitity_id_npf_adm))
        self.assertEqual(24, OcLedger().get_balance(self.user_enitity_id_vol_1))
        self.assertEqual(24, OcLedger().get_balance(self.user_enitity_id_vol_2))


    @skip('until 1017 is fixed')
    def test_past_event_uncheck_user(self):

        """
        the time tracked and currents amounts doesn't change, if admin unchecks
        a volunteer
        """

        # logging in
        self.client.login(username=self.npf_admin.username, password='password')
        response = self.client.get('/live-dashboard/3/')
        # check if users sees the page
        self.assertEqual(response.status_code, 200)

        # assert approved hours from npf admin perspective
        self.assertEqual(0.0 , self.org_npf_adm.get_total_hours_issued())

        # check there are no checked users
        self.assertEqual(len(response.context['checkedin_users']), 0)

        # asserting the first volunteer has grey icon
        self.assertNotIn('name="vol-checkin-2" value="2" class="hidden checkin-checkbox" checked', re.sub(r'\s+', ' ', response.content ))

        # checking the first volunteer
        post_response = self.client.post('/event_checkin/3/',
            {
                'userid':str(self.volunteer_1.id),
                'checkin':'true',
            })

        self.assertEqual(post_response.status_code, 201)

        # check there are two checked users
        response = self.client.get('/live-dashboard/2/')
        self.assertEqual(len(response.context['checkedin_users']), 2) # THIS ASSERTION FAILS !!!
        self.assertIn(self.volunteer_1.id, response.context['checkedin_users']) # THIS ASSERTION FAILS !!!

        # asserting the first volunteer has blue icon
        self.assertIn('name="vol-checkin-2" value="2" class="hidden checkin-checkbox" checked', re.sub(r'\s+', ' ', response.content )) # THIS ASSERTION FAILS !!!

        # general assertion
        self.assertEqual(2, len(UserTimeLog.objects.all()))
        self.assertEqual(2, len(AdminActionUserTime.objects.all()))

        # assert approved hours from users perspective
        self.assertEqual(1, len(self.oc_npf_adm.get_hours_approved()))
        self.assertEqual(1, len(self.oc_vol_1.get_hours_approved()))
        self.assertEqual(0, len(self.oc_vol_2.get_hours_approved()))

        # assert approved hours from npf admin perspective
        self.assertEqual(48.0 , self.org_npf_adm.get_total_hours_issued())


        # asserting the first user
        ledger_query = Ledger.objects.all()
        self._asserting_user_ledger(self.volunteer_1, ledger_query, 1, 24)


        # assert get_balance()
        self.assertEqual(24, OcLedger().get_balance(self.user_enitity_id_npf_adm))
        self.assertEqual(24, OcLedger().get_balance(self.user_enitity_id_vol_1))


        # UN-checking the first volunteer
        post_response = self.client.post('/event_checkin/3/',
            {
                'userid':str(self.volunteer_1.id),
                'checkin':'true',
            })

        self.assertEqual(post_response.status_code, 200)

        # check there is only admin checked
        response = self.client.get('/live-dashboard/2/')
        self.assertIn(self.npf_admin.id, response.context['checkedin_users'])
        self.assertEqual(len(response.context['checkedin_users']), 1) # THIS ASSERTION FAILS !!!

        # asserting the first volunteer has grey icon
        self.assertNotIn('name="vol-checkin-2" value="2" class="hidden checkin-checkbox" checked', re.sub(r'\s+', ' ', response.content )) # THIS ASSERTION FAILS !!!

        # general assertion
        self.assertEqual(2, len(UserTimeLog.objects.all()))
        self.assertEqual(2, len(AdminActionUserTime.objects.all()))

        # assert approved hours from users perspective
        self.assertEqual(1, len(self.oc_npf_adm.get_hours_approved()))
        self.assertEqual(1, len(self.oc_vol_1.get_hours_approved()))
        self.assertEqual(0, len(self.oc_vol_2.get_hours_approved()))

        # assert approved hours from npf admin perspective
        self.assertEqual(48.0 , self.org_npf_adm.get_total_hours_issued())

        # asserting the first user
        ledger_query = Ledger.objects.all()
        self._asserting_user_ledger(self.volunteer_1, ledger_query, 1, 24)

        # assert get_balance()
        self.assertEqual(24, OcLedger().get_balance(self.user_enitity_id_npf_adm))
        self.assertEqual(24, OcLedger().get_balance(self.user_enitity_id_vol_1))


    def test_past_event_add_existing_nonregistered_user(self):

        """
        user is added to the event
        not checked in
        """
        self._add_user_to_event(self.npf_admin, 3, self.volunteer_3, 3)



class FutureEventAddition(SetupTest):

    def test_future_event_add_user(self):

        """
        this unit test is the same for registered and non-registered users
        user is not added to the event
        """

        self.client.login(username=self.npf_admin.username, password='password')
        response = self.client.get('/live-dashboard/1/')

        # check if users sees the page
        self.assertEqual(response.status_code, 200)

        # checking that invite button is disabled
        processed_content = re.sub(r'\s+', ' ', response.content )
        self.assertIn('disabled > Add volunteer </a>', processed_content)

