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

class NpfAdminCheckIn(TestCase):

    def setUp(self):

        future_date = timezone.now() + timedelta(days=1)
        past_date = timezone.now() - timedelta(days=2)

        # creating org
        self.org = OcOrg().setup_org(name="NPF_org_1", status="npf")

        # creating projects
        self.project_1 = _create_project(self.org, 'test_project_1')
        self.project_2 = _create_project(self.org, 'test_project_2')

        #creating an npf admin
        self.npf_admin = _create_test_user('npf_admin_1', org = self.org, is_org_admin=True)

        #creating  volunteers
        self.volunteer_1 = _create_test_user('volunteer_1')
        self.volunteer_2 = _create_test_user('volunteer_2')

        # creating an event that happening now (72 hrs)
        self.event_now = _create_event(self.project_1, past_date, future_date, is_public=True, event_type="GR", coordinator=self.npf_admin, creator_id=self.npf_admin.id)

        # creating a past event (48 hrs)
        past_date_2 = timezone.now() - timedelta(days=1)
        self.event_past = _create_event(self.project_2, past_date_2, future_date, is_public=True, event_type="GR", coordinator=self.npf_admin, creator_id=self.npf_admin.id)


        #creating UserEventRegistration for npf admin and a volunteer
        npf_admin_event_registration = _setup_user_event_registration(self.npf_admin, self.event_now)
        volunteer_event_registration = _setup_user_event_registration(self.volunteer_1, self.event_now)
        volunteer_event_registration = _setup_user_event_registration(self.volunteer_2, self.event_now)
        npf_admin_event2_registration = _setup_user_event_registration(self.npf_admin, self.event_past)
        volunteer_event2_registration = _setup_user_event_registration(self.volunteer_1, self.event_past)
        volunteer_event2_registration = _setup_user_event_registration(self.volunteer_2, self.event_past)

        # oc instances
        self.oc_npf_adm = OcUser(self.npf_admin.id)
        self.org_npf_adm = OrgAdmin(self.npf_admin.id)
        self.oc_vol_1 = OcUser(self.volunteer_1.id)
        self.oc_vol_2 = OcUser(self.volunteer_2.id)

        # user entities
        self.user_enitity_id_npf_adm = UserEntity.objects.get(user = self.npf_admin).id
        self.user_enitity_id_vol_1 = UserEntity.objects.get(user = self.volunteer_1).id
        self.user_enitity_id_vol_2 = UserEntity.objects.get(user = self.volunteer_2).id

        # setting up client
        self.client = Client()


    def test_current_event_check_in(self):

        # assertion of zero state
        self.assertEqual(6, len(UserEventRegistration.objects.all()))
        self.assertEqual(2, len(UserEventRegistration.objects.filter(user=self.npf_admin)))
        self.assertEqual(2, len(UserEventRegistration.objects.filter(user=self.volunteer_1)))
        self.assertEqual(2, len(UserEventRegistration.objects.filter(user=self.volunteer_2)))

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
        self.response = self.client.get('/live-dashboard/1/')
        # check if users sees the page
        self.assertEqual(self.response.status_code, 200)

        # checking the first volunteer
        post_response = self.client.post('/event_checkin/1/',
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
        self.assertEqual(144.0 , self.org_npf_adm.get_total_hours_issued())

        # checking ledger records
        ledger_query = Ledger.objects.all()
        self.assertEqual(2, len(ledger_query))

        # asserting npf_admin user
        self.assertEqual(1, len(ledger_query.filter(action__usertimelog__user=self.npf_admin)))
        self.assertEqual(1, len(ledger_query.filter(action__usertimelog__user=self.npf_admin)))
        self.assertEqual('cur', ledger_query.get(action__usertimelog__user=self.npf_admin).currency)
        self.assertEqual(72, ledger_query.get(action__usertimelog__user=self.npf_admin).amount)

        # asserting the first user
        self.assertEqual(1, len(ledger_query.filter(action__usertimelog__user=self.volunteer_1)))
        self.assertEqual(1, len(ledger_query.filter(action__usertimelog__user=self.volunteer_1)))
        self.assertEqual('cur', ledger_query.get(action__usertimelog__user=self.volunteer_1).currency)
        self.assertEqual(72, ledger_query.get(action__usertimelog__user=self.volunteer_1).amount)

        # asserting the 2nd user
        self.assertEqual(0, len(ledger_query.filter(action__usertimelog__user=self.volunteer_2)))

        # assert get_balance()
        self.assertEqual(72, OcLedger().get_balance(self.user_enitity_id_npf_adm))
        self.assertEqual(72, OcLedger().get_balance(self.user_enitity_id_vol_1))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_2))


        # checking the second volunteer
        post_response = self.client.post('/event_checkin/1/',
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
        self.assertEqual(216.0 , self.org_npf_adm.get_total_hours_issued())


        # checking ledger records
        ledger_query = Ledger.objects.all()
        self.assertEqual(3, len(ledger_query))

        # asserting npf_admin user
        self.assertEqual(1, len(ledger_query.filter(action__usertimelog__user=self.npf_admin)))
        self.assertEqual(1, len(ledger_query.filter(action__usertimelog__user=self.npf_admin)))
        self.assertEqual('cur', ledger_query.get(action__usertimelog__user=self.npf_admin).currency)
        self.assertEqual(72, ledger_query.get(action__usertimelog__user=self.npf_admin).amount)

        # asserting the first user
        self.assertEqual(1, len(ledger_query.filter(action__usertimelog__user=self.volunteer_1)))
        self.assertEqual(1, len(ledger_query.filter(action__usertimelog__user=self.volunteer_1)))
        self.assertEqual('cur', ledger_query.get(action__usertimelog__user=self.volunteer_1).currency)
        self.assertEqual(72, ledger_query.get(action__usertimelog__user=self.volunteer_1).amount)

        # asserting the 2nd user
        self.assertEqual(1, len(ledger_query.filter(action__usertimelog__user=self.volunteer_2)))
        self.assertEqual(1, len(ledger_query.filter(action__usertimelog__user=self.volunteer_1)))
        self.assertEqual('cur', ledger_query.get(action__usertimelog__user=self.volunteer_1).currency)
        self.assertEqual(72, ledger_query.get(action__usertimelog__user=self.volunteer_1).amount)

        # assert get_balance()
        self.assertEqual(72, OcLedger().get_balance(self.user_enitity_id_npf_adm))
        self.assertEqual(72, OcLedger().get_balance(self.user_enitity_id_vol_1))
        self.assertEqual(72, OcLedger().get_balance(self.user_enitity_id_vol_2))



    def test_past_event_check_in(self):

        # assertion of zero state
        self.assertEqual(6, len(UserEventRegistration.objects.all()))
        self.assertEqual(2, len(UserEventRegistration.objects.filter(user=self.npf_admin)))
        self.assertEqual(2, len(UserEventRegistration.objects.filter(user=self.volunteer_1)))
        self.assertEqual(2, len(UserEventRegistration.objects.filter(user=self.volunteer_2)))

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
        self.response = self.client.get('/live-dashboard/2/')
        # check if users sees the page
        self.assertEqual(self.response.status_code, 200)

        # checking the first volunteer
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
        self.assertEqual(1, len(ledger_query.filter(action__usertimelog__user=self.npf_admin)))
        self.assertEqual(1, len(ledger_query.filter(action__usertimelog__user=self.npf_admin)))
        self.assertEqual('cur', ledger_query.get(action__usertimelog__user=self.npf_admin).currency)
        self.assertEqual(48, ledger_query.get(action__usertimelog__user=self.npf_admin).amount)

        # asserting the first user
        self.assertEqual(1, len(ledger_query.filter(action__usertimelog__user=self.volunteer_1)))
        self.assertEqual(1, len(ledger_query.filter(action__usertimelog__user=self.volunteer_1)))
        self.assertEqual('cur', ledger_query.get(action__usertimelog__user=self.volunteer_1).currency)
        self.assertEqual(48, ledger_query.get(action__usertimelog__user=self.volunteer_1).amount)

        # asserting the 2nd user
        self.assertEqual(0, len(ledger_query.filter(action__usertimelog__user=self.volunteer_2)))

        # assert get_balance()
        self.assertEqual(48, OcLedger().get_balance(self.user_enitity_id_npf_adm))
        self.assertEqual(48, OcLedger().get_balance(self.user_enitity_id_vol_1))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_2))


        # checking the second volunteer
        post_response = self.client.post('/event_checkin/2/',
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
        self.assertEqual(144.0 , self.org_npf_adm.get_total_hours_issued())


        # checking ledger records
        ledger_query = Ledger.objects.all()
        self.assertEqual(3, len(ledger_query))

        # asserting npf_admin user
        self.assertEqual(1, len(ledger_query.filter(action__usertimelog__user=self.npf_admin)))
        self.assertEqual(1, len(ledger_query.filter(action__usertimelog__user=self.npf_admin)))
        self.assertEqual('cur', ledger_query.get(action__usertimelog__user=self.npf_admin).currency)
        self.assertEqual(48, ledger_query.get(action__usertimelog__user=self.npf_admin).amount)

        # asserting the first user
        self.assertEqual(1, len(ledger_query.filter(action__usertimelog__user=self.volunteer_1)))
        self.assertEqual(1, len(ledger_query.filter(action__usertimelog__user=self.volunteer_1)))
        self.assertEqual('cur', ledger_query.get(action__usertimelog__user=self.volunteer_1).currency)
        self.assertEqual(48, ledger_query.get(action__usertimelog__user=self.volunteer_1).amount)

        # asserting the 2nd user
        self.assertEqual(1, len(ledger_query.filter(action__usertimelog__user=self.volunteer_2)))
        self.assertEqual(1, len(ledger_query.filter(action__usertimelog__user=self.volunteer_1)))
        self.assertEqual('cur', ledger_query.get(action__usertimelog__user=self.volunteer_1).currency)
        self.assertEqual(48, ledger_query.get(action__usertimelog__user=self.volunteer_1).amount)

        # assert get_balance()
        self.assertEqual(48, OcLedger().get_balance(self.user_enitity_id_npf_adm))
        self.assertEqual(48, OcLedger().get_balance(self.user_enitity_id_vol_1))
        self.assertEqual(48, OcLedger().get_balance(self.user_enitity_id_vol_2))

