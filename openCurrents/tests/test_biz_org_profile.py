"""Biz org profile unit tests."""

from django.test import Client, TestCase
from django.contrib.auth.models import User

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
    _create_org,
    _setup_transactions,
    SetupAdditionalTimeRecords,
)

from openCurrents.tests.interfaces import testing_urls

import re
import random
import string

from unittest import skip


class SetupAll(TestCase):
    """Setup tests class."""

    def setUp(self):
        """General setUp method."""
        # creating npf org and a volunteer
        self.org = _create_org("NPF_org_1", "npf")

        self.volunteer_1 = _create_test_user('volunteer_1')
        self.vol_1_entity = UserEntity.objects.get(user=self.volunteer_1)

        # creting biz org and its admin
        self.biz_org = _create_org("BIZ_org_1", 'biz')

        self.biz_admin_1 = _create_test_user(
            'biz_admin_1',
            org=self.biz_org,
            is_org_admin=True
        )

        # create Transaction adn Transactionaction
        _setup_transactions(
            self.biz_org,
            self.volunteer_1,
            12,
            20,
            offer_item_name="Test Item1")  # Pending: $72.0

        _setup_transactions(
            self.biz_org,
            self.volunteer_1,
            12,
            20,
            offer_item_name="Test Item2")  # Pending: $72.0

        # setting up client
        self.client = Client()

        self.offer_limit = random.randint(1, 100)
        self.offer_limit_choice = random.choice([0, 1])
        self.offer_item_name = ''.join(random.choice(string.ascii_letters) for x in range(15))
        self.offer_share = random.randint(1, 50)
        self.biz_dev_email = 'bizdev@opencurrents.com'


class TestCreateOfferEmail(SetupAll, SetupAdditionalTimeRecords):
    """Test sending email to bizdev after creating an offer by biz admin."""

    def test_new_offer_email_send(self):
        """Test bizdev email after an offer creation by existing biz admin."""
        self.client.login(
            username=self.biz_admin_1.username,
            password='password'
        )

        response = self.client.post(
            testing_urls.create_offer_url,
            {
                'offer_limit_value': str(self.offer_limit),
                'offer_limit_choice': str(self.offer_limit_choice),
                'offer_item': str(self.offer_item_name),
                'offer_current_share': str(self.offer_share),
                'test_time_tracker_mode': '1'  # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            }
        )
        session = self.client.session

        # asserting email vars values
        expected_list = [
            'ORG_NAME', 'FNAME', 'LNAME', 'EMAIL', 'ITEM_NAME',
            'CURRENT_SHARE', 'MONTHLY_LIMIT'
        ]
        self._assert_merge_vars(session['email_vars'], expected_list)
        # assert we pass emails to mandril with correct recepient with email vars
        self.assertEqual(self.biz_dev_email, session['recepient'])
        all_values = [d['content'] for d in session['email_vars']]
        self.assertIn(self.biz_org.name, all_values)
        self.assertIn(self.biz_admin_1.first_name, all_values)
        self.assertIn(self.biz_admin_1.last_name, all_values)
        self.assertIn(self.biz_admin_1.email, all_values)
        self.assertIn(self.offer_item_name, all_values)
        self.assertIn(self.offer_share, all_values)
        # if there is a limit choice, check limit value
        if self.offer_limit_choice != 0:
            self.assertIn(self.offer_limit, all_values)

        self.assertRedirects(
            response,
            testing_urls.biz_admin_url + 'Your%20offer%20for%20{}%20is%20now%20live!/'.format(self.offer_item_name),
            status_code=302)


class TestOfferDelete(SetupAll):
    """Testing class for removing offer by biz admin."""

    def test_remove_offer(self):
        """Biz admin removes offer."""
        self.client.login(
            username=self.biz_admin_1.username,
            password='password'
        )
        response = self.client.get('/biz-admin/')

        # testing initial state
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(Offer.objects.exclude(is_active=False)), 2)
        self.assertEqual(len(Offer.objects.exclude(is_active=True)), 0)
        self.assertEqual(response.context['currents_pending'], 24)
        self.assertEqual(len(response.context['offers']), 2)

        processed_content = re.sub(r'\s+', ' ', response.content)
        self.assertIn('/delete-offer/1/', processed_content)
        self.assertIn('/delete-offer/2/', processed_content)

        # remove offer
        response = self.client.post('/delete-offer/1/')
        self.assertRedirects(
            response,
            '/biz-admin/cashback%20offer%20for%2040%25%20share%20on%20Test%20Item1%20by%20BIZ_org_1%20has%20been%20removed//',
            status_code=302,
            target_status_code=200
        )

        self.assertEqual(len(Offer.objects.exclude(is_active=False)), 1)
        self.assertEqual(len(Offer.objects.exclude(is_active=True)), 1)

        response = self.client.get('/biz-admin/')

        self.assertEqual(response.context['currents_pending'], 24)
        self.assertEqual(len(response.context['offers']), 1)


@skip('we moved popup to a separate page')
class TestBizDetailsPopup(SetupAll):
    """Testing class for Biz Details popup."""

    def setUp(self):
        """setup."""
        super(TestBizDetailsPopup, self).setUp()

        biz_org = self.biz_org
        biz_org.website = biz_org.phone = biz_org.email = biz_org.address = biz_org.intro = ""
        biz_org.save()

    def test_biz_admin_save_empty_popup(self):
        """Biz admin tries to save empty popup.

        - Page should show alert message:
        "Please include at least one way for customers to contact you."
        - Popup reappeared.
        """
        self.client.login(
            username=self.biz_admin_1.username,
            password='password'
        )
        response = self.client.get('/biz-admin/')
        processed_content = re.sub(r'\s+', ' ', response.content)

        # checking if the popup is visible
        self.assertIn("autoopen: true", processed_content)

        # posting empty form
        response_post = self.client.post('/biz-admin/', {
            'website': '',
            'phone': '',
            'email': '',
            'address': '',
            'intro': ''
        })

        # assert redirection and message
        self.assertEqual(
            response_post['Location'],
            "/biz-admin/Please%20include%20at%20least%20one%20way%20for%20\
customers%20to%20contact%20you/alert/"
        )
