"""Testing transactions."""
import re
import pytz
import os

from datetime import datetime
from django.test import Client, TestCase
from django.utils import timezone

from openCurrents.interfaces.bizadmin import BizAdmin

from openCurrents.interfaces.convert import (
    _TR_FEE,
    _USDCUR
)

from openCurrents.interfaces.ocuser import(
    OcUser
)

from openCurrents.models import(
    Item,
    Transaction,
    TransactionAction,
    UserEntity,
)

from openCurrents.tests.interfaces.common import (
    SetUpTests,
    _create_offer,
    _setup_ledger_entry
)


class SetupTest(object):
    """Setup class."""

    # [helpers begin]

    _SHARE = .25

    def assert_redeemed_amount_usd(
        self,
        user,
        sum_payed,
        share=_SHARE,  # default biz org share
        tr_fee=_TR_FEE,  # transaction fee currently 15%
        usdcur=_USDCUR  # exchange rate usd per 1 curr
    ):
        """Assert the amount of pending dollars after a transaction."""
        accepted_sum = sum_payed * share
        expected_usd = accepted_sum - accepted_sum * tr_fee

        usd_pending = OcUser(user.id).get_balance_pending_usd()

        self.assertEqual(usd_pending, expected_usd)

    # [helpers End]

    def setUp(self):
        """Set testing environment."""
        biz_orgs_list = ['BIZ_org_1']
        npf_orgs_list = ['NPF_org_1']
        volunteers_list = ['volunteer_1']

        test_setup = SetUpTests()
        test_setup.generic_setup(npf_orgs_list, biz_orgs_list, volunteers_list)

        # setting orgs
        self.org_npf = test_setup.get_all_npf_orgs()[0]
        self.org_biz = test_setup.get_all_biz_orgs()[0]

        # creating an npf admin
        # all_admins = test_setup.get_all_npf_admins()
        # self.npf_admin = all_admins[0]

        # creating an npf admin
        all_admins = test_setup.get_all_biz_admins()
        self.biz_admin = all_admins[0]

        # assigning existing volunteers to variables
        all_volunteers = test_setup.get_all_volunteers()

        self.volunteer_1 = all_volunteers[0]

        # oc instances
        self.oc_npf_adm = OcUser(self.biz_admin.id)
        self.org_biz_adm = BizAdmin(self.biz_admin.id)
        self.oc_vol_1 = OcUser(self.volunteer_1.id)
        # self.oc_vol_2 = OcUser(self.volunteer_2.id)
        # self.oc_vol_3 = OcUser(self.volunteer_3.id)
        # self.oc_vol_4 = OcUser(self.volunteer_4.id)

        # user entities
        self.vol_1_entity = UserEntity.objects.get(user=self.volunteer_1)
        self.user_enitity_id_biz_adm = UserEntity.objects.get(
            user=self.biz_admin).id
        self.user_enitity_id_vol_1 = UserEntity.objects.get(
            user=self.volunteer_1).id

        # creating an offer
        self.offer = _create_offer(
            self.org_biz, currents_share=self._SHARE * 100)

        # getting item
        self.purchased_item = Item.objects.filter(offer__id=self.offer.id)[0]

        # setting up client
        self.client = Client()

    def tearDown(self):
        """Tear down."""
        pass


class Redemption(SetupTest, TestCase):
    """Test currents redemption process."""

    def setUp(self):
        """Setting up testing environment."""
        super(Redemption, self).setUp()

        # giving volunteer_1 some currency
        self.initial_currents = 30.0
        self.receipt_path = 'openCurrents/tests/test_files/'
        self.receipt_name = 'unittest_receipt.jpg'
        _setup_ledger_entry(self.org_npf.orgentity, self.vol_1_entity,
                            amount=self.initial_currents, is_issued=True)

    def test_full_redemption_custom_msg(self):
        """
        Test full redemption by a volunteer.

        Action:
        User redeems Currents with Currents balance that's no less than the
        offer's current share amount (based on reported price)

        Expected result:
        - Message displayed 'You have submitted an offer for approval
        by {{ orgname ]}. Hooray!"

        - DB Transaction record created: pop_type is "receipt" if image is
        uploaded and "other" if text proof provided; currents_amount is
        {{ current_share_amount }} (based on price reported)

        - DB TransactionAction record of action_type "pending" created
        User's pending USD balance increased by {{ commissioned_amount_usd }}
        Transaction summary is displayed in /profile:
        {{ redemption_date }} - You requested {{ commissioned_amount_usd }} for
        {{ current_share_amount }} from {{ orgname }}

        - Pending biz's Currents is increased by {{ current_share_amount }}

        - Transaction summary is displayed in /biz-admin:
        {{ redemption_date }} - {{ user.first_name user.last_name} purchased
        {{ offer.item }} for {{ price_reported }} and would receive
        {{ commissioned_amount_usd }} for {{ current_share_amount }}

        # @@ TODO @@
        - If provided, receipt image is uploaded to images/redeem/YYYY/MM/DD
        path on the server
        """
        # logging in as biz admin to check initial state of pending currents
        self.client.login(
            username=self.biz_admin.username, password='password')
        response = self.client.get('/biz-admin/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['currents_pending'], 0)

        # logging in as a volunteer 1
        self.client.login(username=self.volunteer_1.username,
                          password='password')
        response_balance = self.client.get('/get_user_balance_available/')
        self.assertEqual(response_balance.status_code, 200)

        # checking initial user CURRENTS balance
        self.assertEqual(response_balance.content, str(self.initial_currents))

        response = self.client.get('/redeem-currents/1/')
        self.assertEqual(response.status_code, 200)

        # setting variables
        redeem_price = 20
        redeem_currents_amount = redeem_price * self._SHARE / _USDCUR
        redeemed_usd_amount = redeem_price * self._SHARE - \
            redeem_price * self._SHARE * _TR_FEE
        uzer_tz = pytz.timezone(self.volunteer_1.usersettings.timezone)
        today_date = datetime.now(uzer_tz).strftime("%b %d, %Y")  # eg Jan 15, 2018

        post_response = self.client.post('/redeem-currents/1/', {
            'redeem_currents_amount': redeem_currents_amount,
            'redeem_receipt': None,
            'redeem_price': redeem_price,
            'redeem_no_proof': 'test message',
            'biz_name': ''
        })

        # Message displayed 'You have submitted an offer for approval
        # by {{ orgname ]}. Hooray!"
        self.assertRedirects(
            post_response, '/profile/You%20have%20submitted%20a%20request%20for%20approval%20by%20{}/'.format(self.org_biz.name),
            status_code=302, target_status_code=200)

        # DB TransactionAction record of action_type "pending" created
        self.assertEqual(len(TransactionAction.objects.filter(
            action_type='req')), 1)

        # DB Transaction record created: pop_type is "receipt" if image is
        # uploaded and "other" if text proof provided; currents_amount is
        # {{ current_share_amount }} (based on price reported)
        transacton = Transaction.objects.filter(user=self.volunteer_1)
        self.assertEqual(len(transacton), 1)
        self.assertEqual(transacton[0].currents_amount, redeem_currents_amount)
        self.assertEqual(transacton[0].pop_type, 'oth')

        self.assert_redeemed_amount_usd(self.volunteer_1, 20)

        # checking that currents were subtracted from user's account
        response_balance = self.client.get('/get_user_balance_available/')
        self.assertEqual(response_balance.status_code, 200)
        self.assertEqual(
            response_balance.content,
            str(self.initial_currents - redeem_currents_amount))

        # Transaction summary is displayed in /profile:
        # {{ redemption_date }} - You requested {{ commissioned_amount_usd }}
        # for {{ current_share_amount }} from {{ orgname }}
        response = self.client.get('/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['offers_redeemed'][0],
            TransactionAction.objects.get(transaction__user=self.volunteer_1))

        # My redeemed offers list entry
        redeemed_offer_text = '{} - You requested ${} for <span class="no-wrap"> <img class="med-text-symbol" src="/static/img/symbol-navy.svg"/> {}0 </span> from <strong> {} </strong>'.format(
            today_date,
            redeemed_usd_amount,
            redeem_currents_amount,
            self.org_biz.name)
        processed_content = re.sub(r'\s+', ' ', response.content)
        self.assertIn(redeemed_offer_text, processed_content)

        # User's pending USD balance increased by {{ commissioned_amount_usd }}
        self.assertEqual(
            response.context['balance_pending_usd'], redeemed_usd_amount)

        # logging in as biz admin
        self.client.login(
            username=self.biz_admin.username, password='password')
        response = self.client.get('/biz-admin/')

        self.assertEqual(response.status_code, 200)

        # Pending biz's Currents is increased by {{ current_share_amount }}
        self.assertEqual(
            response.context['currents_pending'], redeem_currents_amount)

        # Transaction summary is displayed in /biz-admin:
        # {{ redemption_date }} - {{ user.first_name user.last_name} purchased
        # {{ offer.item }} for {{ price_reported }} and would receive
        # {{ commissioned_amount_usd }} for {{ current_share_amount }}
        self.assertEqual(
            float(response.context['redeemed_pending'][0].
                  transaction.currents_amount),
            redeem_currents_amount)

        processed_content = re.sub(r'\s+', ' ', response.content)
        redeemed_offer_text = '{} - {} {} purchased <strong> {} for ${}.00 </strong> and would receive ${} for <span class="no-wrap"> <img class="med-text-symbol" src="/static/img/symbol-navy.svg"/> {}0'.format(
            today_date,
            self.volunteer_1.first_name,
            self.volunteer_1.last_name,
            self.purchased_item.name,
            redeem_price,
            redeemed_usd_amount,
            redeem_currents_amount)
        self.assertIn(redeemed_offer_text, processed_content)

    def test_redemption_img_upload(self):
        """Test redemption img upload by a volunteer."""
        # logging in as biz admin to check initial state of pending currents
        self.client.login(
            username=self.biz_admin.username, password='password')
        response = self.client.get('/biz-admin/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['currents_pending'], 0)

        # logging in as a volunteer 1
        self.client.login(username=self.volunteer_1.username,
                          password='password')
        response_balance = self.client.get('/get_user_balance_available/')
        self.assertEqual(response_balance.status_code, 200)

        # checking initial user CURRENTS balance
        self.assertEqual(response_balance.content, str(self.initial_currents))
        response = self.client.get('/redeem-currents/1/')
        self.assertEqual(response.status_code, 200)

        # setting variables
        redeem_price = 20
        redeem_currents_amount = redeem_price * self._SHARE / _USDCUR
        redeemed_usd_amount = redeem_price * self._SHARE - \
            redeem_price * self._SHARE * _TR_FEE
        today_date = timezone.now().strftime("%b %d, %Y")  # eg Jan 15, 2018

        with open(self.receipt_path + self.receipt_name) as f:
            post_response = self.client.post('/redeem-currents/1/', {
                'redeem_currents_amount': redeem_currents_amount,
                'redeem_receipt': f,
                'redeem_price': redeem_price,
                'redeem_no_proof': '',
                'biz_name': ''
            })

        # check if the file was created
        uploaded_receipt_path = 'oc/mediafiles/images/redeem/{}/{}/{}/{}'.format(
            timezone.now().strftime("%Y"),
            timezone.now().strftime("%m"),
            timezone.now().strftime("%d"),
            self.receipt_name)
        self.assertTrue(os.path.isfile(uploaded_receipt_path))

        # cleaning uploaded file after test
        try:
            os.remove(uploaded_receipt_path)
        except OSError:
            print "Uploaded testing receipt wasn't deleted!"

        # Message displayed 'You have submitted an offer for approval
        # by {{ orgname ]}. Hooray!"
        self.assertRedirects(
            post_response, '/profile/You%20have%20submitted%20a%20request%20for%20approval%20by%20{}/'.format(self.org_biz.name),
            status_code=302, target_status_code=200)

        # DB TransactionAction record of action_type "pending" created
        self.assertEqual(len(TransactionAction.objects.filter(
            action_type='req')), 1)

        # DB Transaction record created: pop_type is "receipt" if image is
        # uploaded and "other" if text proof provided; currents_amount is
        # {{ current_share_amount }} (based on price reported)
        transacton = Transaction.objects.filter(user=self.volunteer_1)
        self.assertEqual(len(transacton), 1)
        self.assertEqual(transacton[0].currents_amount, redeem_currents_amount)
        self.assertEqual(transacton[0].pop_type, 'rec')

        self.assert_redeemed_amount_usd(self.volunteer_1, 20)

        # checking that currents were subtracted from user's account
        response_balance = self.client.get('/get_user_balance_available/')
        self.assertEqual(response_balance.status_code, 200)
        self.assertEqual(
            response_balance.content,
            str(self.initial_currents - redeem_currents_amount))

        # Transaction summary is displayed in /profile:
        # {{ redemption_date }} - You requested {{ commissioned_amount_usd }}
        # for {{ current_share_amount }} from {{ orgname }}
        response = self.client.get('/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['offers_redeemed'][0],
            TransactionAction.objects.get(transaction__user=self.volunteer_1))

        # My redeemed offers list entry
        redeemed_offer_text = '{} - You requested ${} for <span class="no-wrap"> <img class="med-text-symbol" src="/static/img/symbol-navy.svg"/> {}0 </span> from <strong> {} </strong>'.format(
            today_date,
            redeemed_usd_amount,
            redeem_currents_amount,
            self.org_biz.name)
        processed_content = re.sub(r'\s+', ' ', response.content)
        self.assertIn(redeemed_offer_text, processed_content)

        # User's pending USD balance increased by {{ commissioned_amount_usd }}
        self.assertEqual(
            response.context['balance_pending_usd'], redeemed_usd_amount)

        # logging in as biz admin
        self.client.login(
            username=self.biz_admin.username, password='password')
        response = self.client.get('/biz-admin/')

        self.assertEqual(response.status_code, 200)

        # Pending biz's Currents is increased by {{ current_share_amount }}
        self.assertEqual(
            response.context['currents_pending'], redeem_currents_amount)

        # Transaction summary is displayed in /biz-admin:
        # {{ redemption_date }} - {{ user.first_name user.last_name} purchased
        # {{ offer.item }} for {{ price_reported }} and would receive
        # {{ commissioned_amount_usd }} for {{ current_share_amount }}
        self.assertEqual(
            float(response.context['redeemed_pending'][0].
                  transaction.currents_amount),
            redeem_currents_amount)

        processed_content = re.sub(r'\s+', ' ', response.content)
        redeemed_offer_text = '{} - {} {} purchased <strong> {} for ${}.00 </strong> and would receive ${} for <span class="no-wrap"> <img class="med-text-symbol" src="/static/img/symbol-navy.svg"/> {}0'.format(
            today_date,
            self.volunteer_1.first_name,
            self.volunteer_1.last_name,
            self.purchased_item.name,
            redeem_price,
            redeemed_usd_amount,
            redeem_currents_amount)

        self.assertIn(redeemed_offer_text, processed_content)
