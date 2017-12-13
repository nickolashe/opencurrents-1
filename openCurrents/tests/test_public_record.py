from datetime import timedelta
from django.utils import timezone

import pytz
import random
import string

from django.test import TestCase

from openCurrents.interfaces.orgs import OcOrg, OcLedger, OcUser
from openCurrents.models import Event, Project, UserTimeLog, AdminActionUserTime, Ledger


class PublicRecordViewTestSuite(TestCase):
    def setUp(self):
        self.top_with_names = list()
        self.old_top_with_names = list()

    def tearDown(self):
        pass

    @staticmethod
    def _generate_test_name(prefix="", length=6):
        return prefix + "".join(random.sample(string.ascii_lowercase, length))

    def set_up_org(self, status, old=False, user=False):
        org = OcOrg().setup_org(name=self._generate_test_name(prefix=status), status=status)
        user_org = OcUser().setup_user(
            username=self._generate_test_name(prefix='username'),
            email=self._generate_test_name(prefix='email'),
        )
        project = Project.objects.create(
            org=org,
            name=self._generate_test_name(prefix='project')
        )
        event = Event.objects.create(
            project=project,
            description=self._generate_test_name(prefix='desc'),
            location=self._generate_test_name(prefix='loc'),
            coordinator=user_org,
            creator_id=user_org.id,
            event_type=self._generate_test_name(prefix='event_type'),
            datetime_start=timezone.now() - timedelta(hours=2),
            datetime_end=timezone.now() - timedelta(hours=1)
        )
        regular_user = OcUser().setup_user(
            username=self._generate_test_name(prefix='username'),
            email=self._generate_test_name(prefix='email'),
        )
        user_reg_time_log = UserTimeLog.objects.create(
            user=regular_user,
            event=event,
            is_verified=True,
            datetime_start=timezone.now(),
            datetime_end=timezone.now() + timedelta(hours=1)
        )
        regular_user_action = AdminActionUserTime.objects.create(
            user=user_org,
            usertimelog=user_reg_time_log,
            action_type='app'
        )

        amount = random.randint(1, 10)
        if status == 'npf':
            OcLedger().issue_currents(
                org.orgentity.id,
                regular_user.userentity.id,
                regular_user_action,
                amount,
            )
        elif status == 'biz':
            OcLedger().issue_currents(
                org.orgentity.id,
                regular_user.userentity.id,
                regular_user_action,
                amount,
            )
            OcLedger().transact_currents(
                'user',
                regular_user.userentity.id,
                'org',
                org.orgentity.id,
                regular_user_action,
                amount
            )
        if old:
            t = Ledger.objects.last()
            t.date_created -= timedelta(days=33)
            t.save()

            action_ut = AdminActionUserTime.objects.last()
            action_ut.date_created -= timedelta(days=33)
            action_ut.save()

            if user:
                self.old_top_with_names.append({'name': regular_user.username, 'total': amount})
            else:
                self.old_top_with_names.append({'name': org.name, 'total': amount})
            self.old_top_with_names.sort(key=lambda x: x['total'], reverse=True)
        else:
            if user:
                self.top_with_names.append({'name': regular_user.username, 'total': amount})
            else:
                self.top_with_names.append({'name': org.name, 'total': amount})
            self.top_with_names.sort(key=lambda x: x['total'], reverse=True)

    def test_view_displays_up_to_10_active_npf_last_month(self):
        # Create 5 npfs
        # Each of them has admin, project, event, user with timelog accepted by admin and issued transaction
        [self.set_up_org(status='npf') for _ in range(5)]

        # Random transaction amounts are recorded to the list
        # And compared to interface output
        top_npf_last_month = OcOrg().get_top_issued_npfs('month')
        self.assertEqual(top_npf_last_month[0], self.top_with_names[0])

        # Create 10 more organisations to check that interface method outputs 10 items
        [self.set_up_org(status='npf') for _ in range(10)]
        top_npf_last_month = OcOrg().get_top_issued_npfs('month')
        self.assertEqual(len(top_npf_last_month), 10)

    def test_view_displays_up_to_10_active_npf_all_time(self):
        # Create 5 npfs
        # Each of them has admin, project, event, user with timelog accepted by admin and issued transaction
        [self.set_up_org(status='npf', old=True) for _ in range(5)]

        # There were no transactions for last month
        top_npf_last_month = OcOrg().get_top_issued_npfs('month')
        self.assertEqual(top_npf_last_month[0]['total'], 0)

        # Random transaction amounts are recorded to the list
        # And compared to interface output
        top_npf_all_time = OcOrg().get_top_issued_npfs('all-time')
        self.assertEqual(top_npf_all_time[0], self.old_top_with_names[0])

        # Create 10 more organisations to check that interface method outputs 10 items
        [self.set_up_org(status='npf', old=True) for _ in range(10)]
        top_npf_all_time = OcOrg().get_top_issued_npfs('all-time')
        self.assertEqual(len(top_npf_all_time), 10)

    def test_view_displays_up_to_10_active_biz_last_month(self):
        # Create 5 bizs
        # Each of them has admin, project, event, user with timelog accepted by admin and issued transaction
        [self.set_up_org(status='biz') for _ in range(5)]

        # Random transaction amounts are recorded to the list
        # And compared to interface output
        top_biz_last_month = OcOrg().get_top_accepted_bizs('month')
        self.assertEqual(top_biz_last_month[0], self.top_with_names[0])

        # Create 10 more organisations to check that interface method outputs 10 items
        [self.set_up_org(status='biz') for _ in range(10)]
        top_biz_last_month = OcOrg().get_top_accepted_bizs('month')
        self.assertEqual(len(top_biz_last_month), 10)

    def test_view_displays_up_to_10_active_biz_all_time(self):
        # Create 5 bizs
        # Each of them has admin, project, event, user with timelog accepted by admin and issued transaction
        [self.set_up_org(status='biz', old=True) for _ in range(5)]

        # There were no transactions for last month
        top_npf_last_month = OcOrg().get_top_accepted_bizs('month')
        self.assertEqual(top_npf_last_month[0]['total'], 0)

        # Random transaction amounts are recorded to the list
        # And compared to interface output
        top_npf_all_time = OcOrg().get_top_accepted_bizs('all-time')
        self.assertEqual(top_npf_all_time[0], self.old_top_with_names[0])

        # Create 10 more organisations to check that interface method outputs 10 items
        [self.set_up_org(status='biz', old=True) for _ in range(10)]
        top_npf_all_time = OcOrg().get_top_accepted_bizs('all-time')
        self.assertEqual(len(top_npf_all_time), 10)

    def test_view_displays_up_to_10_active_users_last_month(self):
        # Create 5 npfs
        # Each of them has admin, project, event, user with timelog accepted by admin and issued transaction
        [self.set_up_org(status='npf', user=True) for _ in range(5)]

        # Random transaction amounts are recorded to the list
        # And compared to interface output
        top_users_last_month = OcUser().get_top_received_users('month')
        # 10 users for 5 orgs is because each org contains admin
        self.assertEqual(len(top_users_last_month), 5)
        self.assertEqual(top_users_last_month[0], self.top_with_names[0])

        # Create 10 more organisations to check that interface method outputs 10 items
        [self.set_up_org(status='npf') for _ in range(10)]
        top_users_last_month = OcUser().get_top_received_users('month')
        self.assertEqual(len(top_users_last_month), 10)

    def test_view_displays_up_to_10_active_users_all_time(self):
        # Create 5 npfs
        # Each of them has admin, project, event, user with timelog accepted by admin and issued transaction
        [self.set_up_org(status='npf', user=True, old=True) for _ in range(5)]

        # Random transaction amounts are recorded to the list
        # And compared to interface output
        top_users_last_month = OcUser().get_top_received_users('all-time')

        self.assertEqual(len(top_users_last_month), 5)
        self.assertEqual(top_users_last_month[0], self.old_top_with_names[0])

        # Create 10 more organisations to check that interface method outputs 10 items
        [self.set_up_org(status='npf') for _ in range(10)]
        top_users_last_month = OcUser().get_top_received_users('all-time')
        self.assertEqual(len(top_users_last_month), 10)
