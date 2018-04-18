"""Unit test: transactions."""
import glob
import re
import pytz
import os

from django.conf import settings
from datetime import datetime
from django.test import TestCase
from django.utils import timezone


from openCurrents.interfaces.convert import (
    _TR_FEE,
    _USDCUR
)

from openCurrents.models import(
    Transaction,
    TransactionAction,
    Offer
)

# from openCurrents.tests.interfaces.transactions_setup import SetupTest
from openCurrents.tests.interfaces.common import (
    _setup_ledger_entry,
    SetupAdditionalTimeRecords,
    _SHARE
)


class FullRedemption(SetupAdditionalTimeRecords, TestCase):
    """Test currents full redemption process."""

    def setUp(self):
        """Setting up testing environment."""
        super(FullRedemption, self).setUp()

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
        """
        # logging in as biz admin to check initial state of pending currents
        self.biz_pending_currents_assertion(self.biz_admin, 0)

        # asserting initial currents for volunteer 1
        self.volunteer_currents_assert(self.volunteer_1, self.initial_currents)

        # setting variables
        redeem_price = 20
        redeem_currents_amount = redeem_price * _SHARE / _USDCUR
        redeemed_usd_amount = redeem_price * _SHARE - \
            redeem_price * _SHARE * _TR_FEE
        uzer_tz = pytz.timezone(self.volunteer_1.usersettings.timezone)

        # today date, eg Jan 15, 2018
        today_date = datetime.now(uzer_tz).strftime("%b %d, %Y")

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
            post_response,
            '/profile/You%20have%20submitted%20a%20request%20for%20\
approval%20by%20{}/'.format(self.org_biz.name),
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
        self.volunteer_currents_assert(
            self.volunteer_1, self.initial_currents - redeem_currents_amount)

        # Transaction summary is displayed in /profile:
        # {{ redemption_date }} - You requested {{ commissioned_amount_usd }}
        # for {{ current_share_amount }} from {{ orgname }}
        response = self.client.get('/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['offers_redeemed'][0],
            TransactionAction.objects.get(transaction__user=self.volunteer_1))

        processed_content = re.sub(r'\s+', ' ', response.content)

        # My redeemed offers list entry contains last transaction
        redeemed_offer_text = '{} - You requested ${} for'.format(
            today_date,
            redeemed_usd_amount,
        )
        self.assertIn(redeemed_offer_text, processed_content)
        # with visible blue icon
        redeemed_offer_text = '/static/img/symbol-navy.svg"/> {}0 </span> from \
<strong> {} </strong>'.format(
            redeem_currents_amount,
            self.org_biz.name
        )
        self.assertIn(redeemed_offer_text, processed_content)

        # User's pending USD balance increased by {{ commissioned_amount_usd }}
        self.assertEqual(
            response.context['balance_pending_usd'], redeemed_usd_amount)

        # Pending biz's Currents is increased by {{ current_share_amount }}
        response = self.biz_pending_currents_assertion(
            self.biz_admin, redeem_currents_amount)

        # Transaction summary is displayed in /biz-admin:
        # {{ redemption_date }} - {{ user.first_name user.last_name} purchased
        # {{ offer.item }} for {{ price_reported }} and would receive
        # {{ commissioned_amount_usd }} for {{ current_share_amount }}
        self.assertEqual(
            float(response.context['redeemed_pending'][0].
                  transaction.currents_amount),
            redeem_currents_amount)

        processed_content = re.sub(r'\s+', ' ', response.content)
        redeemed_offer_text = '{} - {} {} purchased <strong> {} for ${}.00 \
</strong> and would receive ${} for'.format(
            today_date,
            self.volunteer_1.first_name,
            self.volunteer_1.last_name,
            self.purchased_item.name,
            redeem_price,
            redeemed_usd_amount,
        )
        self.assertIn(redeemed_offer_text, processed_content)
        redemmed_offer_text = 'src="/static/img/symbol-navy.svg"/> {}0'.format(
            redeem_currents_amount
        )
        self.assertIn(redeemed_offer_text, processed_content)

    def test_redemption_img_upload(self):
        """Test redemption img upload by a volunteer."""
        # logging in as biz admin to check initial state of pending currents
        self.biz_pending_currents_assertion(self.biz_admin, 0)

        # logging in as a volunteer 1
        self.client.login(username=self.volunteer_1.username,
                          password='password')
        response = self.client.get('/redeem-currents/1/')
        self.assertEqual(response.status_code, 200)

        # setting variables
        redeem_price = 20
        redeem_currents_amount = redeem_price * _SHARE / _USDCUR

        with open(self.receipt_path + self.receipt_name) as f:
            response = self.client.post(
                '/redeem-currents/{}/'.format(self.offer.id),
                {
                    'redeem_currents_amount': redeem_currents_amount,
                    'redeem_receipt': f,
                    'redeem_price': redeem_price,
                    'redeem_no_proof': '',
                    'biz_name': ''
                }
            )

        ext = self.receipt_name.split('.')[-1]
        updated_file_name = 'oc/mediafiles/receipts/{}/{}/org_{}.offer_{}.user_{}.price_reported_{}.date_{}.time_{}{}.{}'.format(
            timezone.now().strftime("%Y"),
            timezone.now().strftime("%m"),
            self.offer.org.name,
            self.offer.id,
            self.volunteer_1.id,
            redeem_price,
            datetime.now().strftime('%d'),
            datetime.now().strftime('%H-%M-'),
            "*",
            ext
        )

        uploaded_file = glob.glob(updated_file_name)[0]

        self.assertTrue(os.path.isfile(uploaded_file))

        # cleaning uploaded file after test
        try:
            os.remove(uploaded_file)
        except OSError:
            print "Uploaded testing receipt wasn't deleted!"

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
