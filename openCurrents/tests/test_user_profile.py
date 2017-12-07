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
    UserSettings

from openCurrents.interfaces.ocuser import \
    OcUser, \
    InvalidUserException, \
    UserExistsException

from openCurrents.interfaces.orgs import \
    OcOrg, \
    OrgUserInfo

from openCurrents.interfaces.orgadmin import OrgAdmin
from openCurrents.interfaces.ledger import OcLedger
from openCurrents.interfaces.common import diffInHours

from openCurrents.tests.interfaces.common import \
     _create_test_user, \
     _create_project, \
    _setup_volunteer_hours


import pytz
import uuid
import random
import string
import re

from unittest import skip


class TestUserPopup(TestCase):

    def setUp(self):
        # creating org
        org = OcOrg().setup_org(name="NPF_org_1", status="npf")


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

        # changing setting emulating NO answer to the tooltip
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

        # popup code is in the page
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



class TestUserProfileHoursApprovedButtons(TestCase):

    def setUp(self):
        # dates
        future_date = timezone.now() + timedelta(days=1)
        past_date = timezone.now() - timedelta(days=2)

        # creating org
        org1 = OcOrg().setup_org(name="NPF_org_1", status="npf")
        org2 = OcOrg().setup_org(name="NPF_org_2", status="npf")

        # creating a volunteer
        volunteer_1 = _create_test_user('volunteer_1')

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
        _setup_volunteer_hours(volunteer_1, npf_admin_1, org1, project_1, datetime_start_1, datetime_end_1, is_verified = True, action_type = 'app')

        _setup_volunteer_hours(volunteer_1, npf_admin_2, org2, project_2, datetime_start_2, datetime_end_2, is_verified = True, action_type = 'app')

        # setting up client
        self.client = Client()


    def test_user_approved_buttons_exist(self):

        oc_user = User.objects.get(username="volunteer_1")
        self.client.login(username=oc_user.username, password='password')
        response = self.client.get('/profile/')

        processed_content = re.sub(r'\s+', ' ', response.content)

        self.assertEqual(response.status_code, 200)
        self.assertIn('NPF_org_1: 3.0', processed_content)
        self.assertIn('<a href="/hours-detail/?user_id=1&org_id=1&type=approved"',processed_content)
        self.assertIn('NPF_org_2: 2.0', processed_content)
        self.assertIn('<a href="/hours-detail/?user_id=1&org_id=2&type=approved"', processed_content)


    def test_user_approved_buttons_click(self):

        oc_user = User.objects.get(username="volunteer_1")
        self.client.login(username=oc_user.username, password='password')

        response = self.client.get('/hours-detail/?user_id=1&org_id=1&type=approved')

        self.assertEqual(response.status_code, 200)
        self.assertIn('hours_detail', response.context)
        expected_list_of_hours_len = 1
        self.assertEqual(len(response.context['hours_detail']),expected_list_of_hours_len)

        self.assertEqual(response.context['hours_detail'][0].usertimelog.user.username, 'volunteer_1')
        self.assertEqual(response.context['hours_detail'][0].usertimelog.event.project.org.name, 'NPF_org_1')

        self.assertEqual(diffInHours(response.context['hours_detail'][0].usertimelog.datetime_start, response.context['hours_detail'][0].usertimelog.datetime_end), 3.0)


        response = self.client.get('/hours-detail/?user_id=1&org_id=2&type=approved')
        expected_list_of_hours_len = 1
        self.assertEqual(len(response.context['hours_detail']),expected_list_of_hours_len)

        self.assertEqual(response.context['hours_detail'][0].usertimelog.user.username, 'volunteer_1')
        self.assertEqual(response.context['hours_detail'][0].usertimelog.event.project.org.name, 'NPF_org_2')

        self.assertEqual(diffInHours(response.context['hours_detail'][0].usertimelog.datetime_start, response.context['hours_detail'][0].usertimelog.datetime_end), 2.0)


class TestUserProfileCommunityActivity(TestCase):
    def setUp(self):
        # dates
        future_date = timezone.now() + timedelta(days=1)
        past_date = timezone.now() - timedelta(days=2)

        # creating org
        org1 = OcOrg().setup_org(name="NPF_org_1", status="npf")
        org2 = OcOrg().setup_org(name="NPF_org_2", status="npf")
        biz_org = OcOrg().setup_org(name="BIZ_org_1", status='biz')


        # creating a volunteer
        volunteer_1 = _create_test_user('volunteer_1')
        vol_1_entity = UserEntity.objects.get(user=volunteer_1)

        volunteer_2 = _create_test_user('volunteer_2')
        vol_2_entity = UserEntity.objects.get(user=volunteer_2)

        # creating an admins for NPF_orgs
        npf_admin_1 = _create_test_user('npf_admin_1', org = org1, is_org_admin=True)
        npf_adm_1_entity = UserEntity.objects.get(user=npf_admin_1)

        npf_admin_2 = _create_test_user('npf_admin_2', org = org2, is_org_admin=True)
        npf_adm_2_entity = UserEntity.objects.get(user=npf_admin_2)

        biz_admin_1 = _create_test_user('biz_admin_1', org = biz_org, is_org_admin=True)
        biz_adm_1_entity = UserEntity.objects.get(user=biz_admin_1)

        # 1st event time = 3 hours
        datetime_start_1 = past_date
        datetime_end_1 = past_date + timedelta(hours=3)

        # 2nd event time = 2 hours
        datetime_start_2 = past_date + timedelta(hours=3)
        datetime_end_2 = past_date + timedelta(hours=5)

        # issuing currents
        OcLedger().issue_currents(
            entity_id_from = org1.orgentity.id,
            entity_id_to = vol_1_entity.id,
            action =  None,
            amount = 20,
            )

        # transacting currents
        OcLedger().transact_currents(
            entity_type_from = vol_1_entity.entity_type,
            entity_id_from = vol_1_entity.id,
            entity_type_to = biz_org.orgentity.entity_type,
            entity_id_to = biz_org.orgentity.id,
            action = None,
            amount = 4
        )

        # setting up client
        self.client = Client()


    def test_community_activity(self):
        oc_user = User.objects.get(username="volunteer_1")
        self.client.login(username=oc_user.username, password='password')

        response = self.client.get('/profile/')
        processed_content = re.sub(r'\s+', ' ', response.content)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Currents issued: 20.00', response.content)
        self.assertEqual(response.context['currents_amount_total'], 20.00)

        self.assertIn('Active volunteers: 5', response.content)
        self.assertEqual(response.context['active_volunteers_total'], 5)

        self.assertIn('Currents accepted: 4', response.content)
        self.assertEqual(response.context['currents_accepted'], 4.00)


