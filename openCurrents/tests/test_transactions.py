from django.db import connection

from django.test import Client, TestCase, TransactionTestCase
from django.contrib.auth.models import User

from datetime import datetime, timedelta
from django.utils import timezone

from django.db import transaction

#from openCurrents import views, urls

from openCurrents.models import(
    Org,
    Entity,
    Item,
    UserEntity,
    OrgEntity,
    OrgUser,
    Project,
    Event,
    UserTimeLog,
    AdminActionUserTime,
    Ledger,
    TransactionAction,
    Transaction,
    UserEventRegistration
    )

from openCurrents.interfaces.ocuser import(
    OcUser,
    InvalidUserException,
    UserExistsException
)

from openCurrents.tests.interfaces.common import (
    SetUpTests,
    _create_test_user,
    _create_project,
    _setup_volunteer_hours,
    _create_event,
    _setup_user_event_registration,
    _create_org,
    _setup_ledger_entry,
    _create_offer
)


from openCurrents.interfaces.orgadmin import OrgAdmin
from openCurrents.interfaces.ledger import OcLedger
from openCurrents.interfaces.bizadmin import BizAdmin

from openCurrents.interfaces.common import diffInHours

import pytz
import uuid
import random
import string
import re
from collections import OrderedDict
from decimal import Decimal

from unittest import skip


class SetupTest(object):

    # [helpers begin]

    _USDCUR = 20
    _TR_FEE = 0.15
    _SHARE = .25

    def _asserting_user_ledger(
        self,
        user,
        ledger_query,
        expected_num_entries,
        expected_amount,
        currency='cur'):
        """
        user - user instance to assert
        ledger_query - query eg Ledger.objects.all()
        expected_num_entries - integer
        expected_amount - str
        currency - str 'cur' or 'usd'
        """
        if expected_num_entries != 0:
            self.assertEqual(expected_num_entries, len(ledger_query.filter(action__usertimelog__user=user)))
            self.assertEqual('cur', ledger_query.get(action__usertimelog__user=user).currency)
            self.assertEqual(Decimal(expected_amount), ledger_query.get(action__usertimelog__user=user).amount)
        else:
            self.assertEqual(expected_num_entries, len(ledger_query.filter(action__usertimelog__user=user)))


    def _assert_redeem_result(
        self,
        user_id,
        sum_payed,
        share = _SHARE, # default biz org share
        tr_fee = _TR_FEE, # transaction fee currently 15%
        usdcur= _USDCUR # exchange rate usd per 1 curr
        ):
        """
        asserts the amount of pending dollars after a transaction
        """

        accepted_sum = sum_payed * share
        expected_usd = accepted_sum - accepted_sum * tr_fee

        usd_pending = OcUser(user_id).get_balance_pending_usd()

        self.assertEqual(usd_pending, expected_usd)


    # [helpers End]

    def setUp(self):

        future_date = timezone.now() + timedelta(days=1)
        past_date = timezone.now() - timedelta(days=1)

        biz_orgs_list = ['BIZ_org_1']
        npf_orgs_list = ['NPF_org_1']
        volunteers_list = ['volunteer_1'] #, 'volunteer_2', 'volunteer_3', 'volunteer_4']

        test_setup = SetUpTests()
        test_setup.generic_setup(npf_orgs_list, biz_orgs_list, volunteers_list)

        # setting orgs
        self.org_npf = test_setup.get_all_npf_orgs()[0]
        self.org_biz = test_setup.get_all_biz_orgs()[0]

        # setting up projects
        # org_projects = test_setup.get_all_projects(self.org)
        # self.project_1 = org_projects[0]
        # self.project_2 = _create_project(self.org, 'test_project_2')

        #creating an npf admin
        # all_admins = test_setup.get_all_npf_admins()
        # self.npf_admin = all_admins[0]

        #creating an npf admin
        all_admins = test_setup.get_all_biz_admins()
        self.biz_admin = all_admins[0]

        #assigning existing volunteers to variables
        all_volunteers = test_setup.get_all_volunteers()

        self.volunteer_1 = all_volunteers[0]
        # self.volunteer_2 = all_volunteers[1]
        # self.volunteer_3 = all_volunteers[2]
        # self.volunteer_4 = all_volunteers[3]
        # self.volunteer_4.set_unusable_password() # mocking non-confirmed user

        # oc instances
        self.oc_npf_adm = OcUser(self.biz_admin.id)
        self.org_biz_adm = BizAdmin(self.biz_admin.id)
        self.oc_vol_1 = OcUser(self.volunteer_1.id)
        # self.oc_vol_2 = OcUser(self.volunteer_2.id)
        # self.oc_vol_3 = OcUser(self.volunteer_3.id)
        # self.oc_vol_4 = OcUser(self.volunteer_4.id)

        # user entities
        self.vol_1_entity = UserEntity.objects.get(user = self.volunteer_1)
        self.user_enitity_id_biz_adm = UserEntity.objects.get(user = self.biz_admin).id
        self.user_enitity_id_vol_1 = UserEntity.objects.get(user = self.volunteer_1).id
        # self.user_enitity_id_vol_2 = UserEntity.objects.get(user = self.volunteer_2).id
        # self.user_enitity_id_vol_3 = UserEntity.objects.get(user = self.volunteer_3).id
        # self.user_enitity_id_vol_4 = UserEntity.objects.get(user = self.volunteer_4).id

        # creating an offer
        self.offer = _create_offer(self.org_biz)

        # getting item
        self.purchased_item = Item.objects.filter(offer__id=self.offer.id)[0]

        # setting up client
        self.client = Client()


    def tearDown(self):
        pass


class Redemption(SetupTest, TestCase):

    def setUp(self):
        super(Redemption, self).setUp()

        # giving volunteer_1 some currency
        self.initial_currents = 20
        _setup_ledger_entry(self.org_npf.orgentity, self.vol_1_entity, amount=self.initial_currents, is_issued=True)


    def test_full_redemption(self):
        """
        Action:
        User redeems Currents with Currents balance that's no less than the offer's current share amount (based on reported price)

        Expected result:
        Message displayed 'You have submitted an offer for approval by {{ orgname ]}. Hooray!"
        DB Transaction record created: pop_type is "receipt" if image is uploaded and "other" if text proof provided; currents_amount is {{ current_share_amount }} (based on price reported)
        DB TransactionAction record of action_type "pending" created
        User's pending USD balance increased by {{ commissioned_amount_usd }}
        Transaction summary is displayed in /profile: {{ redemption_date }} - You requested {{ commissioned_amount_usd }} for {{ current_share_amount }} from {{ orgname }}
        Pending biz's Currents is increased by {{ current_share_amount }}

        If provided, receipt image is uploaded to images/redeem/YYYY/MM/DD path on the server

        Transaction summary is displayed in /biz-admin: {{ redemption_date }} - {{ user.first_name user.last_name} purchased {{ offer.item }} for {{ price_reported }} and would receive {{ commissioned_amount_usd }} for {{ current_share_amount }}

        """
        # logging in
        self.client.login(username=self.volunteer_1.username, password='password')
        response_balance = self.client.get('/get_user_balance_available/')
        self.assertEqual(response_balance.status_code, 200)

        # checkign initial user CURRENTS balance
        self.assertEqual(response_balance.content, str(20.0))

        response = self.client.get('/redeem-currents/1/')
        self.assertEqual(response.status_code, 200)

        # setting variables
        redeem_price = 20
        redeem_currents_amount = redeem_price * self._SHARE / self._USDCUR
        redeemed_sum_usd = redeem_price * self._SHARE - redeem_price * self._SHARE * self._TR_FEE
        today_date = timezone.now().strftime("%b %d, %Y") # eg Jan 15, 2018


        post_response = self.client.post('/redeem-currents/1/',
                {
                    'redeem_currents_amount': redeem_currents_amount,
                    'redeem_receipt': None,
                    'redeem_price': redeem_price,
                    'redeem_no_proof': 'test messgae',
                    'biz_name': ''}
            )

        # Message displayed 'You have submitted an offer for approval by {{ orgname ]}. Hooray!"
        self.assertRedirects(post_response, '/profile/You%20have%20submitted%20a%20request%20for%20approval%20by%20{}/'.format(self.org_biz.name), status_code=302, target_status_code=200)

        # DB TransactionAction record of action_type "pending" created
        self.assertEqual(len(TransactionAction.objects.filter(action_type='req')), 1)

        # DB Transaction record created: pop_type is "receipt" if image is uploaded and "other" if text proof provided; currents_amount is {{ current_share_amount }} (based on price reported)
        self.assertEqual(len(Transaction.objects.filter(user=self.volunteer_1).filter(currents_amount=redeem_currents_amount).filter(pop_type='oth')), 1)
        self._assert_redeem_result(3, 20)

        # checking that currents were subtracted from user's account
        response_balance = self.client.get('/get_user_balance_available/')
        self.assertEqual(response_balance.status_code, 200)
        self.assertEqual(response_balance.content, str(self.initial_currents - redeem_currents_amount))

        # Transaction summary is displayed in /profile:
        # {{ redemption_date }} - You requested {{ commissioned_amount_usd }} for {{ current_share_amount }} from {{ orgname }}
        response = self.client.get('/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['offers_redeemed'][0], TransactionAction.objects.get(transaction__user=self.volunteer_1))


        # My redeemed offers list entry
        redeemed_offer_text = '{} - You requested ${} for <span class="no-wrap"> <img class="med-text-symbol" src="/static/img/symbol-navy.svg"/> {}0 </span> from <strong> {} </strong>'.format(today_date, redeemed_sum_usd, redeem_currents_amount, self.org_biz.name)
        processed_content = re.sub(r'\s+', ' ', response.content )
        self.assertIn(redeemed_offer_text, processed_content)

        # User's pending USD balance increased by {{ commissioned_amount_usd }}
        self.assertEqual(response.context['balance_pending_usd'], redeemed_sum_usd)


        # logging in as biz admin
        self.client.login(username=self.biz_admin.username, password='password')
        response = self.client.get('/biz-admin/')
        self.assertEqual(response_balance.status_code, 200)

        # Pending biz's Currents is increased by {{ current_share_amount }}
        self.assertEqual(response.context['currents_pending'], redeem_currents_amount)

        # Transaction summary is displayed in /biz-admin:
        # {{ redemption_date }} - {{ user.first_name user.last_name} purchased {{ offer.item }} for {{ price_reported }} and would receive {{ commissioned_amount_usd }} for {{ current_share_amount }}
        self.assertEqual(float(response.context['redeemed_pending'][0].transaction.currents_amount), redeem_currents_amount)

        # <QuerySet [<TransactionAction: Action [req] taken at 02/08/2018 16:51:24 for Transaction initiated by user volunteer_1 for  offer 1 in the amount of 0.250 currents at 02/08/2018 16:51:24>]>
        processed_content = re.sub(r'\s+', ' ', response.content )
        redeemed_offer_text = '{} - {} {} purchased <strong> {} for ${}.00 </strong> and would receive ${} for <span class="no-wrap"> <img class="med-text-symbol" src="/static/img/symbol-navy.svg"/> {}0'.format(today_date, self.volunteer_1.first_name, self.volunteer_1.last_name, self.purchased_item.name, redeem_price, redeemed_sum_usd, redeem_currents_amount)

        self.assertIn(redeemed_offer_text, processed_content)
