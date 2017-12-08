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
        self.monday = (timezone.now() - timedelta(days=timezone.now().weekday())).strftime("%b. %d, %Y")


        # setting up client
        self.client = Client()
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get('/approve-hours/')

    def test_one(self):

        processed_content = re.sub(r'\s+', ' ', self.response.content)

        self.assertEqual(self.response.status_code, 200)

        print "\nHERE"
        print self.response.context[0]
        print "HERE\n"

        # finding week

        for d in self.response.context[0]:
            if 'week' in d.keys():
                print d['week']

        # print "\nHERE"
        # print self.response.content
        # print
        # print self.response.context
        # print "HERE\n"

        #response.context[0]

        # assert displayed week starting date
        # print self.monday
        # self.assertIn(self.monday, processed_content)

        # assert context
        #self.assertIn('volunteer_1_first_name volunteer_1_last_name', self.response.context)


        # print "\nHERE"
        # print User.objects.all()
        # print Project.objects.all()
        # print Org.objects.all()
        # events = Event.objects.all()
        # u_timelogs =  UserTimeLog.objects.all()
        # a_actions = AdminActionUserTime.objects.all()
        # print a_actions
        # print "HERE\n"

        # print
        # for action in a_actions:
        #      print action.date_created

        # print
        # print "Events"
        # print Event.objects.all()
        # for event in events:
        #     print event.is_public
        #     print event.notified

        # print
        # for tlog in u_timelogs:
        #     print tlog.is_verified



