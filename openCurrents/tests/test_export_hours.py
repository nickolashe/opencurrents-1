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

from datetime import datetime, timedelta
from numpy import random
import io
import pytz
import re
from unittest import skip
import xlrd


class TestExportApprovedHoursRandomDates(SetupAdditionalTimeRecords, TestCase):
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
            '/export-data/',
            {
                'start-date': earliest_mon_date.strftime("%Y-%m-%d"),
                'end-date': latest_date.strftime("%Y-%m-%d")
            }
        )

        # assert file is downloaded
        self.assertEquals(
            response.get('Content-Disposition'),
            'attachment; filename="%s"' % (file_name)
        )

        return response

    def setUp(self):
        """Additional setup for TestApproveHoursRandomDates class."""
        # generating time records
        super(TestExportApprovedHoursRandomDates, self).setUp()

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
            records = _setup_volunteer_hours(
                self.volunteer_1,
                self.npf_admin,
                self.org_npf,
                self.project,
                time[0],
                time[1],
                is_verified=True,
                action_type='app',
            )
            # setting up recs for org2
            records2 = _setup_volunteer_hours(
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
        - 10 records in the file.
        """
        response = self._assert_file_created_downloaded()

        # reading file
        with io.BytesIO(response.content) as file:
            workbook = xlrd.open_workbook(file_contents=response.content)
            worksheet = workbook.sheet_by_name('Time logs')

            self.assertEquals(worksheet.nrows, self.counter + 1)

    @skip('For now')
    def test_ignore_recs_wo_start_end(self):
        """
        Check if records wo start or end dates don't get to exporeted file.

        Expected:
        - 9 records in the file.
        - 10 lines in the file in total.
        """
        response = self._assert_file_created_downloaded()

        user_time_logs = UserTimeLog.objects.filter(
            event__project__org=self.org_npf
        )
        first_rec = user_time_logs.first()
        first_rec.datetime_end = None
        first_rec.save()

        with io.BytesIO(response.content) as file:
            workbook = xlrd.open_workbook(file_contents=response.content)
            worksheet = workbook.sheet_by_name('Time logs')

            self.assertEquals(worksheet.nrows, self.counter)
