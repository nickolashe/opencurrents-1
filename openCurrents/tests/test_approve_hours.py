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
    UserTimeLog, \
    AdminActionUserTime

# INTERFACES
from openCurrents.interfaces.orgadmin import OrgAdmin
from openCurrents.interfaces.common import diffInHours
from openCurrents.interfaces.ocuser import OcUser
from openCurrents.interfaces.orgs import \
    OcOrg, \
    OrgUserInfo

# TESTING INTERFACES
from openCurrents.tests.interfaces.common import \
    _create_test_user, \
    _create_project, \
    _setup_volunteer_hours

import re


class TestApproveHoursOneWeek(TestCase):

    def setUp(self):

        # dates
        future_date = timezone.now() + timedelta(days=1)
        past_date = timezone.now() - timedelta(days=2)

        # creating org
        self.org1 = OcOrg().setup_org(name="NPF_org_1", status="npf")

        #creating volunteers
        self.volunteer_1 = _create_test_user('volunteer_1')
        self.volunteer_2 = _create_test_user('volunteer_2')

        # getting full names of volunteers
        self.volunteer_1_full_name = self.volunteer_1.first_name + ' ' + self.volunteer_1.last_name
        self.volunteer_2_full_name = self.volunteer_2.first_name + ' ' + self.volunteer_2.last_name

        # creating an admins for NPF_orgs
        self.npf_admin_1 = _create_test_user('npf_admin_1', org = self.org1, is_org_admin=True)

        # creating a project
        self.project_1 = _create_project(self.org1, 'org1_project_1')

         # 1st event time = 3 hours
        datetime_start_1 = past_date
        datetime_end_1 = past_date + timedelta(hours=3)
        # 2nd event time = 2 hours
        datetime_start_2 = past_date + timedelta(hours=3)
        datetime_end_2 = past_date + timedelta(hours=5)

        # setting 2 pending events
        _setup_volunteer_hours(self.volunteer_1, self.npf_admin_1, self.org1, self.project_1, datetime_start_1, datetime_end_1)

        _setup_volunteer_hours(self.volunteer_2, self.npf_admin_1, self.org1, self.project_1, datetime_start_2, datetime_end_2,)

        # getting previous week start
        self.monday = (timezone.now() - timedelta(days=timezone.now().weekday())).strftime("%-m-%-d-%Y")#.strftime("%b. %d, %Y")

        # setting up client
        self.client = Client()
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get('/approve-hours/')



    def test_logged_hours_displayed(self):

        self.assertEqual(self.response.status_code, 200)

        # digging into response dictionaries
        for k in self.response.context[0]['week'][0]:

            self.assertEqual(2, len(self.response.context[0]['week'][0][k]))

            self.assertEqual(3, len(self.response.context[0]['week'][0][k][self.volunteer_1.email]))
            self.assertEqual(3.0, self.response.context[0]['week'][0][k][self.volunteer_1.email]['Total'])
            self.assertEqual(self.volunteer_1_full_name, self.response.context[0]['week'][0][k][self.volunteer_1.email]['name'])


            self.assertEqual(3, len(self.response.context[0]['week'][0][k][self.volunteer_2.email]))
            self.assertEqual(2.0, self.response.context[0]['week'][0][k][self.volunteer_2.email]['Total'])
            self.assertEqual(self.volunteer_2_full_name, self.response.context[0]['week'][0][k][self.volunteer_2.email]['name'])


    def test_logged_hours_accept(self):

        self.assertEqual(self.response.status_code, 200)

        self.response = self.client.post('/approve-hours/', {
                'post-data': self.volunteer_1.username + ':1:' + self.monday +',' + self.volunteer_2.username + ':1:' + self.monday
                })

        self.assertRedirects(self.response, '/org-admin/2/0/', status_code=302)



        # DECLINING
        # HERE
        # <QueryDict: { u'post-data': [u',volunteer1@opencurrents.com:0:12-4-2017,']}>
        # cleared post data --> ,volunteer1@opencurrents.com:0:12-4-2017,
        # HERE

        # APPROVING:
        # <QueryDict: { u'post-data': [u'volunteer1@opencurrents.com:1:12-4-2017,volunteer2@opencurrents.com:1:12-4-2017,']}>
        # cleared post data -->  volunteer1@opencurrents.com:1:12-4-2017,volunteer2@opencurrents.com:1:12-4-2017,



