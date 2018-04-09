"""Test existing and new users registration to event."""

from django.test import Client, TestCase
from django.contrib.auth.models import User

from datetime import datetime, timedelta
from django.utils import timezone
from django.core.urlresolvers import reverse

from openCurrents import urls

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
    TransactionAction, \
    UserEventRegistration

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
    _create_event,
    SetUpTests
)

import pytz
import uuid
import random
import string
import re
from decimal import Decimal

from unittest import skip


class SetupTests():
    """Setup Tests class."""

    def setUp(self):
        """Set testing environment."""
        self.url_signup = reverse(
            'process_signup',
            urlconf=urls,
            kwargs={'mock_emails': 1}
        )

        self.url_login = reverse(
            'process_login',
            urlconf=urls
        )

        biz_orgs_list = ['BIZ_org_1']
        npf_orgs_list = ['NPF_org_1']
        volunteers_list = ['volunteer_1']

        test_setup = SetUpTests()
        test_setup.generic_setup(npf_orgs_list, biz_orgs_list, volunteers_list)

        # setting orgs
        self.org_npf = test_setup.get_all_npf_orgs()[0]

        # set up project
        self.project = test_setup.get_all_projects(self.org_npf)[0]
        self.project_id = self.project.id

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

        # dates and event
        future_date = timezone.now() + timedelta(days=1)

        self.event1 = _create_event(
            self.project,
            self.npf_admin.id,
            future_date,
            future_date + timedelta(hours=5),
            is_public=True
        )

        # setting up client
        self.client = Client()


class TestNewUserEventRegistration(SetupTests, TestCase):
    """Register new user to events test."""

    def test_new_user_visits_event_page(self):
        """
        New user is accessing event page.

        Expected:
        - not logged in visitor sees "Register" button and can click it
        - after a click user is redirected to login page with "next" url arg
        - after signing up user is registered to event
        """
        response = self.client.get('/event-detail/1/')
        processed_content = re.sub(r'\s+', ' ', response.content)
        self.assertIn(
            'three-halves-margin-top row left hidden',
            processed_content
        )
        self.assertIn('/login/?next=/event-detail/1/', processed_content)

        response = self.client.get('/login/?next=/event-detail/1/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('<a href="/#6">Join openCurrents</a>', response.content)

        response = self.client.post(
            self.url_signup,
            data={
                'user_email': 'new@user.cc',
                'user_firstname': 'test_firstname',
                'user_lastname': 'test_lastname'
            }
        )
        user_registrations = UserEventRegistration.objects.all()
        self.assertEqual(len(user_registrations), 1)


class TestExistingUserEventRegistration(SetupTests, TestCase):
    """An existing user visits event page."""

    def setUp(self):
        """Set up test."""
        super(TestExistingUserEventRegistration, self).setUp()

    def test_existing_user_visits_event_page(self):
        """
        New user is accessing event page.

        Expected:
        - not logged in visitor sees "Register" button and can click it
        - after a click user is REDIRECTED to login page with "next" url arg
        - after logging in user is redirected back to event page where he/she
          sees 'Register' button and 'Get in touch (optional)' textarea field.
        """
        response = self.client.get('/event-detail/1/')
        processed_content = re.sub(r'\s+', ' ', response.content)
        self.assertIn('/login/?next=/event-detail/1/', processed_content)

        # logging in user and asserting what is displayed
        response = self.client.post(
            self.url_login,
            {
                'user_email': self.volunteer_1.email,
                'user_password': 'password',
                'next': '/event-detail/1/',
            }
        )
        self.assertRedirects(response, '/event-detail/1/')

        # response = self.client.get('/event-detail/1/')
        # processed_content = re.sub(r'\s+', ' ', response.content)
        # self.assertEqual(response.status_code, 200)
        # self.assertIn(
        #     '<button type="submit" class="button round"> Register </button>',
        #     processed_content
        # )
        # self.assertNotIn(
        #     'three-halves-margin-top row left hidden',
        #     processed_content
        # )
