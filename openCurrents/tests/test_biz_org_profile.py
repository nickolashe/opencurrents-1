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

from openCurrents.tests.interfaces.common import \
     _create_test_user, \
     _create_project, \
    _setup_volunteer_hours, \
    _create_event, \
    _setup_user_event_registration, \
    _setup_transactions, \
    _setup_ledger_entry


import pytz
import uuid
import random
import string
import re
from decimal import Decimal

from unittest import skip

class SetupAll(TestCase):

    def setUp(self):

        # creating npf org and a volunteer
        self.org = OcOrg().setup_org(name="NPF_org_1", status="npf")

        self.volunteer_1 = _create_test_user('volunteer_1')
        self.vol_1_entity = UserEntity.objects.get(user=self.volunteer_1)

        # creting biz org and its admin
        self.biz_org = OcOrg().setup_org(name="BIZ_org_1", status='biz')
        self.biz_admin_1 = _create_test_user('biz_admin_1', org = self.biz_org, is_org_admin=True)

        # create Transaction adn Transactionaction
        _setup_transactions(self.biz_org, self.volunteer_1, 12, 20, offer_item_name="Test Item1") # Pending: $72.0
        _setup_transactions(self.biz_org, self.volunteer_1, 12, 20, offer_item_name="Test Item2") # Pending: $72.0

        # setting up client
        self.client = Client()


class TestOfferDelete(SetupAll):

    def test_remove_offer(self):

        self.client.login(username=self.biz_admin_1.username, password='password')
        response = self.client.get('/biz-admin/')

        # testing initial state
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(Offer.objects.exclude(is_active=False)), 2)
        self.assertEqual(len(Offer.objects.exclude(is_active=True)), 0)
        self.assertEqual(response.context['currents_pending'], 24 )
        self.assertEqual(len(response.context['offers']), 2 )

        processed_content = re.sub(r'\s+', ' ', response.content)
        self.assertIn('/delete-offer/1/', processed_content)
        self.assertIn('/delete-offer/2/', processed_content)

        #remove offer
        response = self.client.post('/delete-offer/1/')
        self.assertRedirects(response, '/biz-admin/The%20offer%20%22Offer%20for%2040%25%20on%20Test%20Item1%20by%20BIZ_org_1%22%20has%20been%20removed//', status_code=302, target_status_code=200)


        self.assertEqual(len(Offer.objects.exclude(is_active=False)), 1)
        self.assertEqual(len(Offer.objects.exclude(is_active=True)), 1)

        response = self.client.get('/biz-admin/')

        self.assertEqual(response.context['currents_pending'], 24 )
        self.assertEqual(len(response.context['offers']), 1 )

