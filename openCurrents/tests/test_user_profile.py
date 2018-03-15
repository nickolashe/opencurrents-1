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
    UserSettings, \
    Item, \
    Transaction, \
    Offer, \
    TransactionAction

from openCurrents.interfaces.ocuser import \
    OcUser, \
    InvalidUserException, \
    UserExistsException

from openCurrents.interfaces.orgs import \
    OcOrg, \
    OrgUserInfo

from openCurrents.interfaces.orgadmin import OrgAdmin
from openCurrents.interfaces.bizadmin import BizAdmin
from openCurrents.interfaces.ledger import OcLedger
from openCurrents.interfaces.common import diffInHours
from openCurrents.interfaces.community import OcCommunity

from openCurrents.tests.interfaces.common import (
     _create_test_user,
     _create_project,
    _setup_volunteer_hours,
    _create_event,
    _setup_user_event_registration,
    _setup_transactions,
    _setup_ledger_entry,
    _create_org
)

import pytz
import uuid
import random
import string
import re
from decimal import Decimal

from unittest import skip


class TestUserPopup(TestCase):

    def setUp(self):
        # creating org
        org = _create_org("NPF_org_1", "npf")

        #creating a volunteer that sees the popup
        user_name = 'volunteer_default'
        _create_test_user(user_name)

        #creating a volunteer that answered NO to the popup question
        user_name = 'volunteer_no'
        _create_test_user(user_name)

        # changing setting emulating NO answer to the tooltip
        oc_user = User.objects.get(username=user_name)
        oc_user_settings = UserSettings.objects.get(user=oc_user)
        oc_user_settings.popup_reaction = False
        oc_user_settings.save()

        #creating a volunteer that answered YES to the popup question
        user_name = 'volunteer_yes'
        _create_test_user(user_name)

        # changing setting emulating YES answer to the tooltip
        oc_user = User.objects.get(username=user_name)
        oc_user_settings = UserSettings.objects.get(user=oc_user)
        oc_user_settings.popup_reaction = True
        oc_user_settings.save()

        # setting up client
        self.client = Client()


    def test_user_sees_popup(self):
        #logging in user
        oc_user = User.objects.get(username="volunteer_default")
        self.client.login(username=oc_user.username, password='password')

        # did user accessed the page?
        response = self.client.get('/profile/')
        processed_content = re.sub(r'\s+', ' ', response.content )
        self.assertEqual(response.status_code, 200)

        # popup code is in the page
        self.assertIn("$('#welcome-popup').popup({", processed_content)


    def test_user_answ_no_doesnt_see_popup(self):
        #logging in user
        oc_user = User.objects.get(username="volunteer_no")
        self.client.login(username=oc_user.username, password='password')

        # did user accessed the page?
        response = self.client.get('/profile/')
        processed_content = re.sub(r'\s+', ' ', response.content )
        self.assertEqual(response.status_code, 200)

        # popup code is not on the page
        self.assertNotIn("$('#welcome-popup').popup({", processed_content)


    def test_user_answ_yes_doesnt_see_popup(self):
        #logging in user
        oc_user = User.objects.get(username="volunteer_yes")
        self.client.login(username=oc_user.username, password='password')

        # did user accessed the page?
        response = self.client.get('/profile/')
        processed_content = re.sub(r'\s+', ' ', response.content )
        self.assertEqual(response.status_code, 200)

        # popup code is in the page
        self.assertNotIn("$('#welcome-popup').popup({", processed_content)

    def test_user_answers_yes(self):
        #logging in user
        oc_user = User.objects.get(username="volunteer_default")
        self.client.login(username=oc_user.username, password='password')

        # did user accessed the page?
        response = self.client.get('/profile/')
        processed_content = re.sub(r'\s+', ' ', response.content )
        self.assertEqual(response.status_code, 200)

        # popup code is in the page
        self.assertIn("$('#welcome-popup').popup({", processed_content)

        # posting "YES"
        response = self.client.post('/edit-profile/',
            {
                'yes':'',
            })
        # user is redirected back to profile page
        self.assertRedirects(response, '/profile/', status_code=302)

        # getting user settings
        self.assertEqual(True, UserSettings.objects.filter(user=oc_user)[0].popup_reaction)

        response = self.client.get('/profile/')
        processed_content = re.sub(r'\s+', ' ', response.content )
        self.assertEqual(response.status_code, 200)

        # popup code is not on the page anymore
        self.assertNotIn("$('#welcome-popup').popup({", processed_content)


    def test_user_answers_no(self):
        #logging in user
        oc_user = User.objects.get(username="volunteer_default")
        self.client.login(username=oc_user.username, password='password')

        # did user accessed the page?
        response = self.client.get('/profile/')
        processed_content = re.sub(r'\s+', ' ', response.content )
        self.assertEqual(response.status_code, 200)

        # popup code is in the page
        self.assertIn("$('#welcome-popup').popup({", processed_content)

        # posting "YES"
        response = self.client.post('/edit-profile/',
            {
                'no':'',
            })
        # user is redirected back to profile page
        self.assertRedirects(response, '/profile/', status_code=302)

        # getting user settings
        self.assertEqual(False, UserSettings.objects.filter(user=oc_user)[0].popup_reaction)

        response = self.client.get('/profile/')
        processed_content = re.sub(r'\s+', ' ', response.content )
        self.assertEqual(response.status_code, 200)

        # popup code is not on the page anymore
        self.assertNotIn("$('#welcome-popup').popup({", processed_content)


class TestUserProfileView(TestCase):

    def setUp(self):
        # dates
        future_date = timezone.now() + timedelta(days=1)
        past_date = timezone.now() - timedelta(days=2)

        # creating orgs
        org1 = _create_org("NPF_org_1", "npf")
        org2 = _create_org("NPF_org_2", "npf")

        # creating a volunteer
        volunteer_1 = _create_test_user('volunteer_1')
        vol_1_entity = UserEntity.objects.get(user=volunteer_1)
        volunteer_2 = _create_test_user('volunteer_2')

        # creting bizorg and its admin
        biz_org = OcOrg().setup_org(name="BIZ_org_1", status='biz')
        biz_admin_1 = _create_test_user('biz_admin_1', org = biz_org, is_org_admin=True)

        # creating an admins for NPF_orgs
        npf_admin_1 = _create_test_user('npf_admin_1', org = org1, is_org_admin=True)
        npf_admin_2 = _create_test_user('npf_admin_2', org = org2, is_org_admin=True)

        # creating 2 projects for 2 npf orgs
        project_1 = _create_project(org1, 'org1_project_1')
        project_2 = _create_project(org2, 'org2_project_1')

        # 1st event time = 3 hours
        datetime_start_1 = past_date
        datetime_end_1 = past_date + timedelta(hours=3)
        # 2nd event time = 2 hours
        datetime_start_2 = past_date + timedelta(hours=3)
        datetime_end_2 = past_date + timedelta(hours=5)

        # setting 2 approved events for different NPF orgs in the past
        # 3 hrs
        _setup_volunteer_hours(volunteer_1, npf_admin_1, org1, project_1, datetime_start_1, datetime_end_1, is_verified = True, action_type = 'app')

        # 2 hrs
        _setup_volunteer_hours(volunteer_1, npf_admin_2, org2, project_2, datetime_start_2, datetime_end_2, is_verified = True, action_type = 'app')

        # setting a pending events 3 hrs
        _setup_volunteer_hours(volunteer_1, npf_admin_1, org1, project_1, datetime_start_1, datetime_end_1)

        # setting up future events
        self.event1 = _create_event(project_1, npf_admin_1.id, future_date, future_date + timedelta(hours=5), is_public=True)
        self.event2 = _create_event(project_1, npf_admin_1.id, future_date, future_date + timedelta(hours=5), description="Test Event 2", is_public=True)

        #issuing currents to volunteer1
        OcLedger().issue_currents(
            entity_id_from = org1.orgentity.id,
            entity_id_to = vol_1_entity.id,
            action =  None,
            amount = 20,
            )

        # registering user for an event
        _setup_user_event_registration(volunteer_1, self.event2)

        # setting up user dollars "Dollars available"
        _setup_ledger_entry(org1.orgentity, vol_1_entity, currency = 'usd', amount = 30.30, is_issued = True)

        # setting approved and pending dollars
        _setup_transactions(biz_org, volunteer_1, 12, 20) # Pending: $72.0
        _setup_transactions(biz_org, volunteer_1, 12, 20, action_type='app') #72.0 +
        _setup_transactions(biz_org, volunteer_1, 12, 20, action_type='red') # + 72.0 = 204

        # setting up client
        self.client = Client()


    def test_user_approved_buttons_exist(self):
        oc_user = User.objects.get(username="volunteer_1")
        self.client.login(username=oc_user.username, password='password')
        response = self.client.get('/profile/')

        processed_content = re.sub(r'\s+', ' ', response.content)

        self.assertEqual(response.status_code, 200)
        self.assertIn('NPF_org_1: 3.0', processed_content)
        self.assertIn('<a href="/hours-detail/?user_id=1&amp;org_id=1&amp;type=approved"',processed_content)
        self.assertIn('NPF_org_2: 2.0', processed_content)
        self.assertIn('<a href="/hours-detail/?user_id=1&amp;org_id=2&amp;type=approved"', processed_content)


    def test_user_events_upcoming(self):
        oc_user = User.objects.get(username="volunteer_1")
        self.client.login(username=oc_user.username, password='password')

        response = self.client.get('/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['events_upcoming']), 1)

        response = self.client.get('/upcoming-events/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['events']), 2)


    def test_user_currents_available(self):
        oc_user = User.objects.get(username="volunteer_1")
        self.client.login(username=oc_user.username, password='password')

        response = self.client.get('/profile/')
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context['balance_available'], 8.0)

    def test_user_currents_pending(self):
        oc_user = User.objects.get(username="volunteer_1")
        self.client.login(username=oc_user.username, password='password')

        response = self.client.get('/profile/')
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context['balance_pending'], 3.0)


    def test_user_dollars_available(self):
        oc_user = User.objects.get(username="volunteer_1")
        self.client.login(username=oc_user.username, password='password')

        response = self.client.get('/profile/')
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context['balance_available_usd'], 30.30)


    def test_user_dollars_pending(self):
        oc_user = User.objects.get(username="volunteer_1")
        self.client.login(username=oc_user.username, password='password')

        response = self.client.get('/profile/')
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context['balance_pending_usd'], 408.0)


    def test_user_offers_redemed(self):
        oc_user = User.objects.get(username="volunteer_1")
        self.client.login(username=oc_user.username, password='password')

        response = self.client.get('/profile/')
        self.assertEqual(response.status_code, 200)

        self.assertEqual(len(response.context['offers_redeemed']), 3)
        self.assertEqual(response.context['offers_redeemed'][0].transaction.currents_amount, 12)
        self.assertEqual(response.context['offers_redeemed'][0].transaction.price_reported, 20)


    def test_user_pending_hours_list(self):

        oc_user = User.objects.get(username="volunteer_1")
        self.client.login(username=oc_user.username, password='password')

        response = self.client.get('/profile/')
        self.assertEqual(response.status_code, 200)

        processed_content = re.sub(r'\s+', ' ', response.content)

        self.assertEqual(len(response.context['hours_requested']), 1)
        self.assertEqual(len(AdminActionUserTime.objects.filter(usertimelog__user=oc_user).filter(action_type='req')), 1)



    def test_user_approved_buttons_click(self):

        oc_user = User.objects.get(username="volunteer_1")
        self.client.login(username=oc_user.username, password='password')

        response = self.client.get('/hours-detail/?user_id=1&amp;org_id=1&amp;type=approved')

        self.assertEqual(response.status_code, 200)
        self.assertIn('hours_detail', response.context)
        expected_list_of_hours_len = 1
        self.assertEqual(len(response.context['hours_detail']),expected_list_of_hours_len)

        self.assertEqual(response.context['hours_detail'][0].usertimelog.user.username, 'volunteer_1')
        self.assertEqual(response.context['hours_detail'][0].usertimelog.event.project.org.name, 'NPF_org_1')

        self.assertEqual(diffInHours(response.context['hours_detail'][0].usertimelog.datetime_start, response.context['hours_detail'][0].usertimelog.datetime_end), 3.0)

        response = self.client.get('/hours-detail/?user_id=1&amp;org_id=2&amp;type=approved')
        expected_list_of_hours_len = 1
        self.assertEqual(len(response.context['hours_detail']),expected_list_of_hours_len)

        self.assertEqual(response.context['hours_detail'][0].usertimelog.user.username, 'volunteer_1')
        self.assertEqual(response.context['hours_detail'][0].usertimelog.event.project.org.name, 'NPF_org_2')

        self.assertEqual(diffInHours(response.context['hours_detail'][0].usertimelog.datetime_start, response.context['hours_detail'][0].usertimelog.datetime_end), 2.0)

    def test_user_has_no_approved_hours(self):
        oc_user = User.objects.get(username="volunteer_2")
        self.client.login(username=oc_user.username, password='password')

        response = self.client.get('/profile/')
        self.assertEqual(response.status_code, 200)

        processed_content = re.sub(r'\s+', ' ', response.content)

        self.assertEqual(response.context['balance_available'], 0.0)
        self.assertEqual(response.context['balance_pending'], 0.0)
        self.assertEqual(response.context['balance_available_usd'], 0.0)
        self.assertEqual(response.context['balance_pending_usd'], 0.0)
        self.assertEqual(response.context['hours_by_org'], {})
        self.assertEqual(len(response.context['hours_requested']), 0)
        self.assertEqual(len(response.context['offers_redeemed']), 0)

        self.assertIn('No hours have been approved', processed_content)
        self.assertIn('No hours have been requested', processed_content)
        self.assertIn('You have not yet redeemed any offers', processed_content)

        # assert the popup code in the page source
        self.assertIn('id="no-cash-popup"', processed_content)


class TestUserProfileCommunityActivity(TestCase):
    def setUp(self):
        # dates
        future_date = timezone.now() + timedelta(days=1)
        past_date = timezone.now() - timedelta(days=2)

        # creating orgs
        self.org1 = _create_org("NPF_org_1", "npf")
        self.org2 = _create_org("NPF_org_2", "npf")
        self.biz_org = _create_org("BIZ_org_1", 'biz')

        # creating 2 projects for 2 npf orgs
        self.project_1 = _create_project(self.org1, 'org1_project_1')
        self.project_2 = _create_project(self.org2, 'org2_project_1')

        # creating volunteers
        self.volunteer_1 = _create_test_user('volunteer_1')
        self.vol_1_entity = UserEntity.objects.get(user=self.volunteer_1)

        self.volunteer_2 = _create_test_user('volunteer_2')
        self.vol_2_entity = UserEntity.objects.get(user=self.volunteer_2)

        # creating admins
        self.npf_admin_1 = _create_test_user('npf_admin_1', org = self.org1, is_org_admin=True)
        self.npf_adm_1_entity = UserEntity.objects.get(user=self.npf_admin_1)

        self.npf_admin_2 = _create_test_user('npf_admin_2', org = self.org2, is_org_admin=True)
        self.npf_adm_2_entity = UserEntity.objects.get(user=self.npf_admin_2)

        self.biz_admin_1 = _create_test_user('biz_admin_1', org = self.biz_org, is_org_admin=True)
        # self.biz_adm_1_entity = UserEntity.objects.get(user=self.biz_admin_1)

        # 1st event time = 3 hours
        self.datetime_start_1 = past_date
        self.datetime_end_1 = past_date + timedelta(hours=3)

        # setting 1 pending events
        _setup_volunteer_hours(self.volunteer_1, self.npf_admin_1, self.org1, self.project_1, self.datetime_start_1, self.datetime_end_1)

        # setting 1 approved events
        _setup_volunteer_hours(self.volunteer_1, self.npf_admin_1, self.org1, self.project_1, self.datetime_start_1, self.datetime_end_1, is_verified = True, action_type = 'app')

        # issuing currents
        OcLedger().issue_currents(
            entity_id_from = self.org1.orgentity.id,
            entity_id_to = self.vol_1_entity.id,
            action =  None,
            amount = 20,
            )

        # transacting currents
        OcLedger().transact_currents(
            entity_type_from = self.vol_1_entity.entity_type,
            entity_id_from = self.vol_1_entity.id,
            entity_type_to = self.biz_org.orgentity.entity_type,
            entity_id_to = self.biz_org.orgentity.id,
            action = None,
            amount = 4
        )

        # setting up pending transaction
        _setup_transactions(self.biz_org, self.biz_admin_1, 0.436, 10.91)

        # setting up client
        self.client = Client()


    def test_community_activity(self):
        oc_user = User.objects.get(username="volunteer_1")
        self.client.login(username=oc_user.username, password='password')

        response = self.client.get('/profile/')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Currents issued: 20.00', response.content)
        self.assertEqual(response.context['currents_amount_total'], 20.000)

        self.assertIn('Active volunteers: 1', response.content)
        self.assertEqual(response.context['active_volunteers_total'], 1)

        self.assertIn('Currents redeemed: 4', response.content)
        self.assertEqual(float(response.context['biz_currents_total']), 4.436)


    def test_community_activity_click_curr_issued(self):

        oc_user = User.objects.get(username="volunteer_1")
        self.client.login(username=oc_user.username, password='password')

        response = self.client.get('/profile/')
        processed_content = re.sub(r'\s+', ' ', response.content)

        self.assertEqual(response.status_code, 200)

        # asserting npf orgs
        response = self.client.get('/public-record/?record_type=top-org&period=month')
        self.assertIn('entries', response.context)
        expected_entries = [{'total': 0, 'name': 'NPF_org_1'}, {'total': 0, 'name': 'NPF_org_2'}]
        self.assertEqual(expected_entries, response.context['entries'])

        # asserting biz org
        response = self.client.get('/public-record/?record_type=top-biz&period=month')
        self.assertIn('entries', response.context)
        self.assertEqual(response.context['entries'][0]['name'], self.biz_org.name)
        self.assertEqual(round(response.context['entries'][0]['total'], 3), 0.436)
