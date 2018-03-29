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
    AdminActionUserTime, \
    Ledger, \
    UserEntity

# INTERFACES
from openCurrents.interfaces.ledger import OcLedger
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
        # creating org
        self.org1 = OcOrg().setup_org(name="NPF_org_1", status="npf")

        # creating volunteers
        self.volunteer_1 = _create_test_user('volunteer_1')
        self.volunteer_2 = _create_test_user('volunteer_2')

        # getting full names of volunteers
        self.volunteer_1_full_name = self.volunteer_1.first_name + ' ' + self.volunteer_1.last_name
        self.volunteer_2_full_name = self.volunteer_2.first_name + ' ' + self.volunteer_2.last_name

        # creating an admins for NPF_orgs
        self.npf_admin_1 = _create_test_user('npf_admin_1', org=self.org1, is_org_admin=True)

        # creating a project
        self.project_1 = _create_project(self.org1, 'org1_project_1')

        # 1st event time = 3 hours
        datetime_start_1 = timezone.now() - timedelta(hours=4)
        datetime_end_1 = datetime_start_1 + timedelta(hours=3)
        # 2nd event time = 2 hours
        datetime_start_2 = timezone.now() - timedelta(hours=4)
        datetime_end_2 = datetime_start_2 + timedelta(hours=2)

        # setting 2 pending events
        _setup_volunteer_hours(self.volunteer_1, self.npf_admin_1, self.org1, self.project_1, datetime_start_1, datetime_end_1)

        _setup_volunteer_hours(self.volunteer_2, self.npf_admin_1, self.org1, self.project_1, datetime_start_2, datetime_end_2,)

        # getting previous week start
        self.monday = (timezone.now() - timedelta(days=timezone.now().weekday())).strftime("%-m-%-d-%Y")

        # oc instances
        self.oc_vol_1 = OcUser(self.volunteer_1.id)
        self.oc_vol_2 = OcUser(self.volunteer_2.id)

        # user entities
        self.user_enitity_id_vol_1 = UserEntity.objects.get(user=self.volunteer_1).id
        self.user_enitity_id_vol_2 = UserEntity.objects.get(user=self.volunteer_2).id

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

        org_admin_response = self.client.get('/org-admin/')
        self.assertEqual(org_admin_response.status_code, 200)

        # checking pending hours before approving
        self.assertDictEqual(org_admin_response.context['hours_pending_by_admin'], {self.npf_admin_1: 5.0})
        self.assertEqual(0, len(AdminActionUserTime.objects.filter(action_type='app')))
        self.assertEqual(2, len(AdminActionUserTime.objects.filter(action_type='req')))

        # checking total approved hours
        self.assertEqual(org_admin_response.context['issued_by_all'], 0)

        # checking initial balance
        self.assertEqual(0, len(self.oc_vol_1.get_hours_approved()))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_1))
        self.assertEqual(0, len(self.oc_vol_2.get_hours_approved()))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_2))

        # approving hours
        self.response = self.client.post('/approve-hours/', {
            'post-data': self.volunteer_1.username + ':1:' + self.monday + ',' + self.volunteer_2.username + ':1:' + self.monday
        })

        # return to org-amdin after approving
        self.assertRedirects(self.response, '/org-admin/2/0/', status_code=302)

        # assert the creation of the corresponding usertimelog and adminaction records
        self.assertEqual(2, len(AdminActionUserTime.objects.filter(action_type='app')))
        self.assertEqual(0, len(AdminActionUserTime.objects.filter(action_type='req')))

        self.assertEqual(1, len(UserTimeLog.objects.filter(user=self.volunteer_1).filter(is_verified=True)))
        self.assertEqual(1, len(AdminActionUserTime.objects.filter(usertimelog__user=self.volunteer_1).filter(action_type='app')))
        self.assertEqual(1, len(UserTimeLog.objects.filter(user=self.volunteer_2).filter(is_verified=True)))
        self.assertEqual(1, len(AdminActionUserTime.objects.filter(usertimelog__user=self.volunteer_2).filter(action_type='app')))

        # checking ledger records
        ledger_query = Ledger.objects.all()
        self.assertEqual(2, len(ledger_query))
        # asserting the first user
        self.assertEqual(1, len(ledger_query.filter(action__usertimelog__user=self.volunteer_1)))
        self.assertEqual('cur', ledger_query.get(action__usertimelog__user=self.volunteer_1).currency)
        self.assertEqual(3, ledger_query.get(action__usertimelog__user=self.volunteer_1).amount)
        self.assertEqual(True, ledger_query.get(action__usertimelog__user=self.volunteer_1).is_issued)

        self.assertEqual(1, len(self.oc_vol_1.get_hours_approved()))
        self.assertEqual(3, OcLedger().get_balance(self.user_enitity_id_vol_1))

        # asserting the 2nd user
        self.assertEqual(1, len(ledger_query.filter(action__usertimelog__user=self.volunteer_2)))
        self.assertEqual('cur', ledger_query.get(action__usertimelog__user=self.volunteer_2).currency)
        self.assertEqual(2, ledger_query.get(action__usertimelog__user=self.volunteer_2).amount)
        self.assertEqual(True, ledger_query.get(action__usertimelog__user=self.volunteer_2).is_issued)

        self.assertEqual(1, len(self.oc_vol_2.get_hours_approved()))
        self.assertEqual(2, OcLedger().get_balance(self.user_enitity_id_vol_2))

    def test_logged_hours_declined(self):
        self.assertEqual(self.response.status_code, 200)

        org_admin_response = self.client.get('/org-admin/')
        self.assertEqual(org_admin_response.status_code, 200)

        # checking pending hours before declining
        self.assertDictEqual(org_admin_response.context['hours_pending_by_admin'], {self.npf_admin_1: 5.0})

        # checking total approved hours
        self.assertEqual(org_admin_response.context['issued_by_all'], 0)

        # checking initial balance
        self.assertEqual(0, len(self.oc_vol_1.get_hours_approved()))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_1))
        self.assertEqual(0, len(self.oc_vol_2.get_hours_approved()))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_2))

        self.response = self.client.post('/approve-hours/', {
            'post-data': self.volunteer_1.username + ':0:' + self.monday + ',' + self.volunteer_2.username + ':0:' + self.monday
        })

        # return to org-amdin after declining
        self.assertRedirects(self.response, '/org-admin/0/2/', status_code=302)

        # assert the creation of the corresponding usertimelog and adminaction records
        self.assertEqual(0, len(AdminActionUserTime.objects.filter(action_type='app')))
        self.assertEqual(0, len(AdminActionUserTime.objects.filter(action_type='app')))
        self.assertEqual(2, len(AdminActionUserTime.objects.filter(action_type='dec')))

        self.assertEqual(1, len(UserTimeLog.objects.filter(user=self.volunteer_1).filter(is_verified=False)))
        self.assertEqual(1, len(AdminActionUserTime.objects.filter(usertimelog__user=self.volunteer_1).filter(action_type='dec')))
        self.assertEqual(1, len(UserTimeLog.objects.filter(user=self.volunteer_2).filter(is_verified=False)))
        self.assertEqual(1, len(AdminActionUserTime.objects.filter(usertimelog__user=self.volunteer_2).filter(action_type='dec')))

        # checking ledger records
        ledger_query = Ledger.objects.all()
        self.assertEqual(0, len(ledger_query))
        # asserting the first user
        self.assertEqual(0, len(ledger_query.filter(action__usertimelog__user=self.volunteer_1)))
        self.assertEqual(0, len(self.oc_vol_1.get_hours_approved()))

        self.assertEqual(0, len(self.oc_vol_1.get_hours_approved()))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_1))

        # asserting the 2nd user
        self.assertEqual(0, len(ledger_query.filter(action__usertimelog__user=self.volunteer_2)))
        self.assertEqual(0, len(self.oc_vol_2.get_hours_approved()))

        self.assertEqual(0, len(self.oc_vol_2.get_hours_approved()))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_1))


class TestApproveHoursTwoWeeks(TestCase):

    def setUp(self):
        # creating org
        self.org1 = OcOrg().setup_org(name="NPF_org_1", status="npf")

        # creating volunteers
        self.volunteer_1 = _create_test_user('volunteer_1')
        self.volunteer_2 = _create_test_user('volunteer_2')

        # getting full names of volunteers
        self.volunteer_1_full_name = self.volunteer_1.first_name + ' ' + self.volunteer_1.last_name
        self.volunteer_2_full_name = self.volunteer_2.first_name + ' ' + self.volunteer_2.last_name

        # creating an admins for NPF_orgs
        self.npf_admin_1 = _create_test_user('npf_admin_1', org=self.org1, is_org_admin=True)

        # creating a project
        self.project_1 = _create_project(self.org1, 'org1_project_1')

        # 1st event time = 3 hours (last week)
        datetime_start_1 = timezone.now() - timedelta(hours=4)
        datetime_end_1 = datetime_start_1 + timedelta(hours=3)
        # 2nd event time = 2 hours (previous week)
        datetime_start_2 = timezone.now() - timedelta(days=7, hours=4)
        datetime_end_2 = datetime_start_2 + timedelta(hours=2)

        # setting 2 pending events
        _setup_volunteer_hours(self.volunteer_1, self.npf_admin_1, self.org1, self.project_1, datetime_start_1, datetime_end_1)

        _setup_volunteer_hours(self.volunteer_2, self.npf_admin_1, self.org1, self.project_1, datetime_start_2, datetime_end_2,)

        # getting previous week start
        self.monday_prev = (timezone.now() - timedelta(days=timezone.now().weekday() + 7)).strftime("%-m-%-d-%Y")
        self.monday_last = (timezone.now() - timedelta(days=timezone.now().weekday())).strftime("%-m-%-d-%Y")

        # oc instances
        self.oc_vol_1 = OcUser(self.volunteer_1.id)
        self.oc_vol_2 = OcUser(self.volunteer_2.id)

        # user entities
        self.user_enitity_id_vol_1 = UserEntity.objects.get(user=self.volunteer_1).id
        self.user_enitity_id_vol_2 = UserEntity.objects.get(user=self.volunteer_2).id

        # setting up client
        self.client = Client()
        self.client.login(username=self.npf_admin_1.username, password='password')
        self.response = self.client.get('/approve-hours/')

    def test_logged_hours_displayed(self):

        self.assertEqual(self.response.status_code, 200)

        # digging into response dictionaries
        context_hr_displayed = self.response.context[0]['week'][0]
        for k in context_hr_displayed:

            self.assertEqual(1, len(context_hr_displayed[k]))

            self.assertEqual(3, len(context_hr_displayed[k][self.volunteer_2.email]))
            self.assertEqual(2.0, context_hr_displayed[k][self.volunteer_2.email]['Total'])
            self.assertEqual(self.volunteer_2_full_name, context_hr_displayed[k][self.volunteer_2.email]['name'])

    def test_logged_hours_accept(self):

        self.assertEqual(self.response.status_code, 200)

        org_admin_response = self.client.get('/org-admin/')
        self.assertEqual(org_admin_response.status_code, 200)

        # checking pending hours before approving
        self.assertDictEqual(org_admin_response.context['hours_pending_by_admin'], {self.npf_admin_1: 5.0})

        # checking total approved hours
        self.assertEqual(org_admin_response.context['issued_by_all'], 0)

        # checking initial balance
        self.assertEqual(0, len(self.oc_vol_1.get_hours_approved()))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_1))
        self.assertEqual(0, len(self.oc_vol_2.get_hours_approved()))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_2))

        # approving hours
        self.response = self.client.post('/approve-hours/', {
            'post-data': self.volunteer_2.username + ':1:' + self.monday_prev
        })

        # return to org-amdin after approving
        self.assertRedirects(self.response, '/approve-hours/1/0/', status_code=302)

        # checking ledger records
        ledger_query = Ledger.objects.all()
        self.assertEqual(1, len(ledger_query))
        # asserting the first user
        self.assertEqual(0, len(ledger_query.filter(action__usertimelog__user=self.volunteer_1)))

        # asserting the 2nd user
        self.assertEqual(1, len(ledger_query.filter(action__usertimelog__user=self.volunteer_2)))
        self.assertEqual('cur', ledger_query.get(action__usertimelog__user=self.volunteer_2).currency)
        self.assertEqual(2, ledger_query.get(action__usertimelog__user=self.volunteer_2).amount)
        self.assertEqual(True, ledger_query.get(action__usertimelog__user=self.volunteer_2).is_issued)

        self.assertEqual(1, len(self.oc_vol_2.get_hours_approved()))
        self.assertEqual(2, OcLedger().get_balance(self.user_enitity_id_vol_2))

        # checking that the the last week submitted hours are displayed
        org_admin_response_approve_second_week = self.client.get('/approve-hours/2/0/')
        context_hr_last_week = org_admin_response_approve_second_week.context[0]['week'][0]
        for k in context_hr_last_week:
            self.assertEqual(1, len(context_hr_last_week[k]))

            self.assertEqual(3, len(context_hr_last_week[k][self.volunteer_1.email]))
            self.assertEqual(3.0, context_hr_last_week[k][self.volunteer_1.email]['Total'])
            self.assertEqual(self.volunteer_1_full_name, context_hr_last_week[k][self.volunteer_1.email]['name'])

        # approving hours for the last week
        response_post_last_week = self.client.post('/approve-hours/', {
            'post-data': self.volunteer_1.username + ':1:' + self.monday_last
        })

        # return to org-amdin after approving
        self.assertRedirects(response_post_last_week, '/org-admin/1/0/', status_code=302)

        # checking ledger records
        ledger_query = Ledger.objects.all()
        self.assertEqual(2, len(ledger_query))
        # asserting the first user
        self.assertEqual(1, len(ledger_query.filter(action__usertimelog__user=self.volunteer_1)))
        self.assertEqual('cur', ledger_query.get(action__usertimelog__user=self.volunteer_1).currency)
        self.assertEqual(3, ledger_query.get(action__usertimelog__user=self.volunteer_1).amount)
        self.assertEqual(True, ledger_query.get(action__usertimelog__user=self.volunteer_1).is_issued)

        self.assertEqual(1, len(self.oc_vol_2.get_hours_approved()))
        self.assertEqual(3, OcLedger().get_balance(self.user_enitity_id_vol_1))

        # asserting the 2nd user
        self.assertEqual(1, len(ledger_query.filter(action__usertimelog__user=self.volunteer_2)))
        self.assertEqual('cur', ledger_query.get(action__usertimelog__user=self.volunteer_2).currency)
        self.assertEqual(2, ledger_query.get(action__usertimelog__user=self.volunteer_2).amount)
        self.assertEqual(True, ledger_query.get(action__usertimelog__user=self.volunteer_2).is_issued)

        self.assertEqual(1, len(self.oc_vol_2.get_hours_approved()))
        self.assertEqual(2, OcLedger().get_balance(self.user_enitity_id_vol_2))

    def test_logged_hours_decline(self):
        self.assertEqual(self.response.status_code, 200)

        org_admin_response = self.client.get('/org-admin/')
        self.assertEqual(org_admin_response.status_code, 200)

        # checking pending hours before declining
        self.assertDictEqual(org_admin_response.context['hours_pending_by_admin'], {self.npf_admin_1: 5.0})

        # checking total approved hours
        self.assertEqual(org_admin_response.context['issued_by_all'], 0)

        # checking initial balance
        self.assertEqual(0, len(self.oc_vol_1.get_hours_approved()))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_1))
        self.assertEqual(0, len(self.oc_vol_2.get_hours_approved()))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_2))

        # declining hrs for the previous week
        post_decline_hours = self.client.post('/approve-hours/', {
            'post-data': self.volunteer_2.username + ':0:' + self.monday_prev
        })

        # return to org-amdin after declining
        self.assertRedirects(post_decline_hours, '/approve-hours/0/1/', status_code=302)

        # checking hours after declining
        # checking ledger records
        ledger_query = Ledger.objects.all()
        self.assertEqual(0, len(ledger_query))
        # asserting the first user
        self.assertEqual(0, len(ledger_query.filter(action__usertimelog__user=self.volunteer_1)))

        # asserting the 2nd user
        self.assertEqual(0, len(ledger_query.filter(action__usertimelog__user=self.volunteer_2)))

        self.assertEqual(0, len(self.oc_vol_2.get_hours_approved()))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_2))

        # declining for the last week
        post_decline_hours_last = self.client.post('/approve-hours/0/1/', {
            'post-data': self.volunteer_1.username + ':0:' + self.monday_last
        })

        # return to org-amdin after declining
        self.assertRedirects(post_decline_hours_last, '/org-admin/0/1/', status_code=302)

        # checking hours after declining
        # checking ledger records
        ledger_query = Ledger.objects.all()
        self.assertEqual(0, len(ledger_query))
        # asserting the first user
        self.assertEqual(0, len(ledger_query.filter(action__usertimelog__user=self.volunteer_1)))

        # asserting the 2nd user
        self.assertEqual(0, len(ledger_query.filter(action__usertimelog__user=self.volunteer_2)))

        self.assertEqual(0, len(self.oc_vol_1.get_hours_approved()))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_1))
        self.assertEqual(0, len(self.oc_vol_2.get_hours_approved()))
        self.assertEqual(0, OcLedger().get_balance(self.user_enitity_id_vol_2))
