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
    SetUpTests,
    SetupAdditionalTimeRecords
)
import openCurrents.tests.interfaces.testing_urls as testing_urls

from datetime import datetime, timedelta
from numpy import random
import io
import pytz
import re
# from unittest import skip
import xlrd


class TestExportApprovedHours(SetupAdditionalTimeRecords, TestCase):
    """Tests with random dates for time records export."""

    def _assert_file_created_downloaded(self):
        """Define dates, generate file, assert file downloaded."""
        earliest_mon_date = self._get_earliest_monday()
        latest_date = datetime.now(tz=pytz.utc)
        file_name = "timelog_report_{}_{}.xls".format(
            earliest_mon_date.strftime("%Y-%m-%d"),
            latest_date.strftime("%Y-%m-%d")
        )

        response = self.client.post(
            testing_urls.export_data_url,
            {
                'date_start': earliest_mon_date.strftime("%Y-%m-%d"),
                'date_end': latest_date.strftime("%Y-%m-%d")
            }
        )

        # assert file is downloaded
        self.assertEquals(
            response.get('Content-Disposition'),
            'attachment; filename="%s"' % (file_name)
        )

        return response

    def _assert_date_input(self, start_d, end_d):
        """
        Assert date input when Export volunteer data.

        Takes str() start_d, end_d and evaluates
        """
        error_msg = ''

        # check if stat date is empty
        if start_d == '':
            error_msg = "Start%20date%20cannot%20be%20empty!/alert"

        else:
            # check if date_start in formatted correctly
            try:
                datetime.strptime(
                    start_d,
                    '%Y-%m-%d'
                )
            except ValueError:
                error_msg = "Incorrect%20dates!/alert"

        url = testing_urls.export_data_url
        response = self.client.post(
            url,
            {
                'date_start': start_d,
                'date_end': end_d
            }
        )
        if error_msg:
            expected_url = url + error_msg
            self.assertRedirects(
                response,
                expected_url,
                status_code=302,
                target_status_code=200
            )
        else:
            self._assert_file_created_downloaded()

    def setUp(self):
        """Additional setup for TestApproveHoursRandomDates class."""
        # generating time records
        super(TestExportApprovedHours, self).setUp()

        def _gen_time():
            datetime_start = datetime.now(tz=pytz.utc) - \
                timedelta(days=random.randint(1, 60)) + \
                timedelta(hours=random.randint(12, 24))
            datetime_end = datetime_start + \
                timedelta(hours=random.randint(1, 4))

            return datetime_start, datetime_end

        self.counter = 10  # number of generated records
        for i in range(self.counter):
            time = _gen_time()
            manual_records_org1 = _setup_volunteer_hours(
                self.volunteer_1,
                self.npf_admin,
                self.org_npf,
                self.project,
                time[0],
                time[1],
                is_verified=True,
                action_type='app',
            )
            group_records_org1 = _setup_volunteer_hours(
                self.volunteer_1,
                self.npf_admin,
                self.org_npf,
                self.project,
                time[0],
                time[1],
                event_type="GR",
                is_verified=True,
                action_type='app',
            )
            # setting up recs for org2
            manual_records_org2 = _setup_volunteer_hours(
                self.volunteer_1,
                self.npf_admin2,
                self.org_npf2,
                self.project2,
                time[0],
                time[1],
                is_verified=True,
                action_type='app',
            )

    def test_export_and_content(self):
        """
        Check if file is exported.

        Also check if all records are in downloaded file.
        Expected:
        - file is downloaded
        - it is exptected to get self.counter * 2 records (half for manual and
          half for group events) in the xls file + 1 heading line
        """
        response = self._assert_file_created_downloaded()

        # reading file
        with io.BytesIO(response.content) as file:
            workbook = xlrd.open_workbook(file_contents=response.content)
            worksheet = workbook.sheet_by_name('Time logs')

            self.assertEquals(worksheet.nrows, self.counter * 2 + 1)

    def test_incorrect_dates_input(self):
        """
        Check incorrect dates input.

        Expected:
        - user is returned to export page
        - warning message is displayed
        """
        # badly formatted start date
        self._assert_date_input(
            '20118-112-343',
            datetime.now(tz=pytz.utc).strftime("%Y-%m-%d")
        )

        # badly formatted end date
        self._assert_date_input(
            (datetime.now(tz=pytz.utc) - timedelta(days=10)).strftime("%Y-%m-%d"),
            '20118-112-343'
        )

        # start date in the future
        self._assert_date_input(
            (datetime.now(tz=pytz.utc) + timedelta(days=10)).strftime("%Y-%m-%d"),
            datetime.now(tz=pytz.utc).strftime("%Y-%m-%d")
        )

        # end date in the future
        self._assert_date_input(
            datetime.now(tz=pytz.utc).strftime("%Y-%m-%d"),
            (datetime.now(tz=pytz.utc) + timedelta(days=10)).strftime("%Y-%m-%d")
        )

    def test_empty_dates_input(self):
        """
        Check empty dates input.

        Expected:
        - user is returned to export page
        - warning message is displayed
        """
        # empty start date
        self._assert_date_input(
            '',
            datetime.now(tz=pytz.utc).strftime("%Y-%m-%d")
        )

        # empty end date
        self._assert_date_input(
            (datetime.now(tz=pytz.utc) - timedelta(days=10)).strftime("%Y-%m-%d"),
            '',
        )

    def test_importing_empty_sheet(self):
        """
        Test error when export for selected dates is empty.

        Expected red alert msg 'The query is empty, please, try another set of
        dates.'
        """
        date_start_str = (
            datetime.now(tz=pytz.utc) - timedelta(days=100)
        ).strftime("%Y-%m-%d")
        date_end_str = (
            datetime.now(tz=pytz.utc) - timedelta(days=90)
        ).strftime("%Y-%m-%d")

        url = testing_urls.export_data_url
        error_msg = 'The%20query%20is%20empty,%20please,%20try%20another%20set%20of%20dates./alert'
        expected_url = url + error_msg
        response = self.client.post(
            url,
            {
                'date_start': date_start_str,
                'date_end': date_end_str
            }
        )
        self.assertRedirects(
            response,
            expected_url,
            status_code=302,
            target_status_code=200
        )
