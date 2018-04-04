"""Tests collection for approve time records functionality."""
from django.test import Client, TestCase
from django.contrib.auth.models import User
from django.shortcuts import redirect

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
from openCurrents.tests.interfaces.common import(
    _create_test_user,
    _create_project,
    _setup_volunteer_hours,
    SetUpTests
)

from datetime import datetime, timedelta
from numpy import random
import pytz
import re


class TestApproveHoursOneWeek(TestCase):
    """Collection of tests for time records within one week."""

    def setUp(self):
        """Set testing environment."""
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
    """Collection of tests for time records within 2 weeks."""

    def setUp(self):
        """Set testing environment."""
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


class SetupAdditionalTimeRecords():
    """SetUp class for TestApproveHoursRandomDates and  TestApproveHoursCornerCases."""

    def _get_earliest_monday(self):
        """Get earliest monday for approve-hours page."""
        earliest_request_date = self.org_admin.get_hours_requested().\
            order_by('usertimelog__datetime_start').first().\
            usertimelog.datetime_start
        earliest_monday = earliest_request_date - timedelta(
            days=(earliest_request_date.weekday()))
        earliest_monday = earliest_monday.replace(hour=00, minute=00, second=00)

        return earliest_monday

    def _current_week_records(self, earliest_monday):
        current_week_sunday = earliest_monday + timedelta(days=6)
        current_week_sunday = current_week_sunday.replace(
            hour=23, minute=59, second=59
        )
        admin_actions_requested = self.org_admin.get_hours_requested().\
            order_by('usertimelog__datetime_start')

        current_week_records = []
        for rec in admin_actions_requested:
            if earliest_monday <= rec.usertimelog.datetime_start <= current_week_sunday:
                current_week_records.append(rec)

        return current_week_records

    def _compare_shown_records(self, current_week_records, response):
        records_num = len(current_week_records)

        # asserting num of displayed records and num of real records in DB
        num_of_recs_in_context_week = 0
        for i in response.context[0]['week'][0].items()[0][1].items()[0][1].items()[2:]:
            num_of_recs_in_context_week += len(i[1]) - 1

        self.assertEqual(
            records_num,
            num_of_recs_in_context_week
        )
        return records_num

    def setUp(self):
        """Set testing environment."""
        biz_orgs_list = ['BIZ_org_1']
        npf_orgs_list = ['NPF_org_1']
        volunteers_list = ['volunteer_1']

        test_setup = SetUpTests()
        test_setup.generic_setup(npf_orgs_list, biz_orgs_list, volunteers_list)

        # setting orgs
        self.org_npf = test_setup.get_all_npf_orgs()[0]
        # self.org_biz = test_setup.get_all_biz_orgs()[0]

        # set up project
        self.project = test_setup.get_all_projects(self.org_npf)[0]

        # creating an npf admin
        all_admins = test_setup.get_all_npf_admins()
        self.npf_admin = all_admins[0]
        self.org_admin = OrgAdmin(self.npf_admin.id)

        # assigning existing volunteers to variables
        all_volunteers = test_setup.get_all_volunteers()

        self.volunteer_1 = all_volunteers[0]

        # oc instances
        self.oc_npf_adm = OcUser(self.npf_admin.id)
        # self.org_biz_adm = BizAdmin(self.biz_admin.id)
        self.oc_vol_1 = OcUser(self.volunteer_1.id)

        # user entities
        self.vol_1_entity = UserEntity.objects.get(user=self.volunteer_1)
        self.user_enitity_id_vol_1 = UserEntity.objects.get(
            user=self.volunteer_1).id

        # setting up client
        self.client = Client()
        self.client.login(username=self.npf_admin.username, password='password')


class TestApproveHoursRandomDates(SetupAdditionalTimeRecords, TestCase):
    """
    Tests with random dates for time records.

    The main purpose is to check that query returns proper time records per
    week and admin can approve these records.
    """

    def setUp(self):
        """Additional setup for TestApproveHoursRandomDates class."""
        # generating time records

        super(TestApproveHoursRandomDates, self).setUp()

        def _gen_time():
            datetime_start = datetime.now(tz=pytz.utc) - \
                timedelta(days=random.randint(60)) + \
                timedelta(hours=random.randint(12, 24))
            datetime_end = datetime_start + \
                timedelta(hours=random.randint(1, 4))
            return datetime_start, datetime_end

        self.counter = 10  # number of generated hours
        for i in range(self.counter):
            time = _gen_time()
            records = _setup_volunteer_hours(
                self.volunteer_1,
                self.npf_admin,
                self.org_npf,
                self.project,
                time[0],
                time[1]
            )
            # print time[0], '  ', time[1]

    def test_check_workflow(self):
        """
        Check if all entries are in week context arg for every week.

        It is expected that self.counter number of UserTimeLog objects and
        AdminActionUserTime with action_type='req' is created with different
        dates.
        These time records are displayed for every week and then approved
        by org-admin.
        """
        test_counter = 0

        while True:
            response = self.client.get('/approve-hours/')
            records_num_for_approval = 0
            # check how many AdminActionUserTime records are in the first week
            earliest_monday = self._get_earliest_monday()
            current_week_records = self._current_week_records(earliest_monday)

            # checking context varibale 'week' if it contains correct # of
            # AdminActionUserTime objects
            records_num_for_approval = self._compare_shown_records(
                current_week_records,
                response
            )

            # approving hours for displayed week
            post_response = self.client.post('/approve-hours/', {
                'post-data': self.volunteer_1.username +
                ':1:' +
                earliest_monday.strftime("%-m-%-d-%Y")
            })
            test_counter += records_num_for_approval

            if test_counter < self.counter:
                self.assertRedirects(
                    post_response,
                    '/approve-hours/1/0/',
                    status_code=302
                )
            if test_counter == self.counter:
                self.assertRedirects(
                    post_response,
                    '/org-admin/1/0/',
                    status_code=302
                )
                break

            # check if correct num of records approved
            self.assertEqual(
                test_counter,
                len(self.oc_vol_1.get_hours_approved())
            )


class TestApproveHoursCornerCases(SetupAdditionalTimeRecords, TestCase):
    """
    Tests with specific dates for time records.

    The main purpose is to check that query returns specific records per
    week and admin can approve these records.
    """

    def _get_current_week_start_end_utc(self, pytz_tz):
            """Return closest monday in provided pytz_tz timezone."""
            utc_now = datetime.now(tz=pytz_tz)
            utc_monday = utc_now - timedelta(days=(utc_now.weekday()))
            utc_monday = utc_monday.replace(hour=00, minute=00, second=00)
            utc_sunday = utc_monday + timedelta(days=6)
            # print utc_monday, utc_sunday

            return utc_monday, utc_sunday

    def _gen_weekdays_split_time(self, monday_date):
        """Generate a time record within current week UTC."""
        datetime_start = monday_date + \
            timedelta(days=random.randint(1, 5)) + \
            timedelta(hours=random.randint(20, 23))
        datetime_end = datetime_start + \
            timedelta(hours=random.randint(5, 8))

        return datetime_start, datetime_end

    def _gen_weekend_split_time(self, monday_date):
        """Generate a time record within current week UTC."""
        datetime_start = monday_date + \
            timedelta(days=6) + timedelta(hours=23)
        datetime_end = datetime_start + timedelta(hours=2)

        return datetime_start, datetime_end

    def _change_org_tz(self, org):
        Org.objects.filter(pk=org.pk)[0].timezone = 'America/Detroit'

    # def _clean_all_records(self):
    #     """Delete all previously requested hours."""
    #     UserTimeLog.objects.all().delete()
    #     AdminActionUserTime.objects.all().delete()

    def setUp(self):
        """Additional setup for TestApproveHoursRandomDates class."""
        super(TestApproveHoursCornerCases, self).setUp()

        # utc =  00:00
        # America/Detroit = -4:00
        # America/Chicago = -6:00
        self.pytz_utc = pytz.utc
        self.pytz_utc_minus_6 = pytz.timezone('America/Detroit')

        utc_current_week = self._get_current_week_start_end_utc(self.pytz_utc)
        self.utc_monday = utc_current_week[0]
        self.utc_sunday = utc_current_week[1]

        amchic_current_week = self._get_current_week_start_end_utc(
            self.pytz_utc_minus_6
        )
        self.amchic_monday = amchic_current_week[0]
        self.amchic_sunday = amchic_current_week[1]

        # setting up client
        self.client = Client()
        self.client.login(username=self.npf_admin.username, password='password')

    def test_timerecord_split_weekdays_utc(self):
        """
        Testing time record (UTC) that starts on one day and finishes on another day (weekdays).

        Expected behavior:
        - time record is correctly shown on approve-hours page.
        - time record may be approved by admin.
        """
        # setting up the record's time
        weekdays_records = self._gen_weekdays_split_time(self.utc_monday)
        _setup_volunteer_hours(
            self.volunteer_1,
            self.npf_admin,
            self.org_npf,
            self.project,
            weekdays_records[0],
            weekdays_records[1]
        )
        # print weekdays_records

        response = self.client.get('/approve-hours/')

        earliest_monday = self._get_earliest_monday()
        current_week_records = self._current_week_records(earliest_monday)

        # checking context varibale 'week' if it contains correct # of
        # AdminActionUserTime objects
        records_num_for_approval = self._compare_shown_records(
            current_week_records,
            response
        )

        # approving hours for displayed week
        post_response = self.client.post('/approve-hours/', {
            'post-data': self.volunteer_1.username +
            ':1:' +
            earliest_monday.strftime("%-m-%-d-%Y")
        })

        # check if correct num of records approved
        self.assertEqual(
            1,
            len(self.oc_vol_1.get_hours_approved())
        )

    def test_timerecord_split_weekend_utc(self):
        """
        Testing time record (UTC) that starts on one day and finishes on another day (weekend).

        Expected behavior:
        - time record is correctly shown on approve-hours page.
        - time record may be approved by admin.
        """
        # setting up the record's time
        weekdays_records = self._gen_weekend_split_time(self.utc_monday)
        _setup_volunteer_hours(
            self.volunteer_1,
            self.npf_admin,
            self.org_npf,
            self.project,
            weekdays_records[0],
            weekdays_records[1]
        )
        # print weekdays_records

        response = self.client.get('/approve-hours/')

        earliest_monday = self._get_earliest_monday()
        current_week_records = self._current_week_records(earliest_monday)

        # checking context varibale 'week' if it contains correct # of
        # AdminActionUserTime objects
        records_num_for_approval = self._compare_shown_records(
            current_week_records,
            response
        )

        # approving hours for displayed week
        post_response = self.client.post('/approve-hours/', {
            'post-data': self.volunteer_1.username +
            ':1:' +
            earliest_monday.strftime("%-m-%-d-%Y")
        })

        # check if correct num of records approved
        self.assertEqual(
            1,
            len(self.oc_vol_1.get_hours_approved())
        )

    def test_timerecord_split_weekdays_non_utc(self):
        """
        Testing time record (non-UTC) that starts on one day and finishes on another day (weekdays).

        Expected behavior:
        - time record is correctly shown on approve-hours page.
        - time record may be approved by admin.
        """
        # setting up the record's time
        weekdays_records = self._gen_weekdays_split_time(self.amchic_monday)
        _setup_volunteer_hours(
            self.volunteer_1,
            self.npf_admin,
            self.org_npf,
            self.project,
            weekdays_records[0],
            weekdays_records[1]
        )
        # print weekdays_records

        response = self.client.get('/approve-hours/')

        earliest_monday = self._get_earliest_monday()
        current_week_records = self._current_week_records(earliest_monday)

        # checking context varibale 'week' if it contains correct # of
        # AdminActionUserTime objects
        records_num_for_approval = self._compare_shown_records(
            current_week_records,
            response
        )

        # approving hours for displayed week
        post_response = self.client.post('/approve-hours/', {
            'post-data': self.volunteer_1.username +
            ':1:' +
            earliest_monday.strftime("%-m-%-d-%Y")
        })

        # check if correct num of records approved
        self.assertEqual(
            1,
            len(self.oc_vol_1.get_hours_approved())
        )

    def test_timerecord_split_weekend_non_utc(self):
        """
        Testing time record (non-UTC) that starts on one day and finishes on another day (weekend).

        Expected behavior:
        - time record is correctly shown on approve-hours page.
        - time record may be approved by admin.
        """
        # setting up the record's time
        weekdays_records = self._gen_weekend_split_time(self.amchic_monday)
        _setup_volunteer_hours(
            self.volunteer_1,
            self.npf_admin,
            self.org_npf,
            self.project,
            weekdays_records[0],
            weekdays_records[1]
        )
        # print weekdays_records

        response = self.client.get('/approve-hours/')

        earliest_monday = self._get_earliest_monday()
        current_week_records = self._current_week_records(earliest_monday)

        # checking context varibale 'week' if it contains correct # of
        # AdminActionUserTime objects
        records_num_for_approval = self._compare_shown_records(
            current_week_records,
            response
        )

        # approving hours for displayed week
        post_response = self.client.post('/approve-hours/', {
            'post-data': self.volunteer_1.username +
            ':1:' +
            earliest_monday.strftime("%-m-%-d-%Y")
        })

        # check if correct num of records approved
        self.assertEqual(
            1,
            len(self.oc_vol_1.get_hours_approved())
        )
