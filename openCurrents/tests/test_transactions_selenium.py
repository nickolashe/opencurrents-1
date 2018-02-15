"""test_transactions_selenium."""

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from openCurrents.tests.interfaces.transactions_setup import SetupTest

from openCurrents.tests.interfaces.common import (
    _create_offer,
    _setup_ledger_entry,
    _selenium_wait_for
)

from openCurrents.interfaces.ocuser import(
    OcUser
)

from selenium import webdriver
from seleniumlogin import force_login


class PartialRedemptionSelenium(SetupTest, StaticLiveServerTestCase):
    """Test currents full redemption process."""

    def setUp(self):
        """Setup Selenium test."""
        super(PartialRedemptionSelenium, self).setUp()

        self.selenium = webdriver.Firefox()
        self.live_server_url = 'http://127.0.0.1:8081/'

        # giving volunteer_1 some currency
        self.initial_currents = 1.0
        self.receipt_path = 'openCurrents/tests/test_files/'
        self.receipt_name = 'unittest_receipt.jpg'
        _setup_ledger_entry(self.org_npf.orgentity, self.vol_1_entity,
                            amount=self.initial_currents, is_issued=True)

        # creating a new offer to prevent error 500 on marketplace page
        self.offer = _create_offer(
            self.org_biz,
            offer_item_name='Test Item Master',
            currents_share=self._SHARE * 100,
            is_master=True)

    def tearDown(self):
        """Tear down Selenium test."""
        self.selenium.quit()

    def test_partial_redemption_selenium(self):
        """
        Partial redemption test.

        Action:
        User redeems Currents with Currents balance that's below the offer's
        current share (based on reported price)

        Expected result:
        - DB Transaction record created: pop_type is "receipt" if image is
        uploaded and "other" if text proof provided; currents_amount is
        {{ user_balance_available }} (equals user's currents available)

        - If provided, receipt image is uploaded to images/redeem/YYYY/MM/DD
        path on the server

        - DB TransactionAction record of action_type "pending" created

        - User's pending USD balance increased by {{ commissioned_amount_usd }}
        - Transaction summary is displayed in /profile: {{ redemption_date }} -
        You requested {{ commissioned_amount_usd }} for
        {{ user_balance_available }} from {{ orgname }}

        - Pending biz's Currents is increased by {{ user_balance_available }}

        - Transaction summary is displayed in /biz-admin:
        {{ redemption_date }} - {{ user.first_name user.last_name} purchased
        {{ offer.item }} for {{ price_reported }} and would receive
        {{ commissioned_amount_usd }} for {{ user_balance_available }}
        """
        selenium = self.selenium

        redeem_price = 2000
        exprected_usd_amount_gross = 20
        exprected_usd_amount_net = 17

        # logging in as biz admin to check initial state of pending currents
        self.biz_pending_currents_assertion(self.biz_admin, 0)

        # asserting initial currents for volunteer 1
        self.volunteer_currents_assert(self.volunteer_1, self.initial_currents)

        force_login(self.volunteer_1, selenium, self.live_server_url)
        selenium.set_window_size(1024, 768)
        selenium.get('{}redeem-currents/1/'.format(self.live_server_url))

        # STEP 1: Add description of purchase
        selenium.find_element_by_class_name('no-receipt-popup_open').click()
        text_to_input = 'this is a test description'
        selenium.find_element_by_id('no-proof-typed').send_keys(text_to_input)
        selenium.find_element_by_class_name('no-receipt-popup_close').click()
        text_area_text = selenium.find_element_by_id('id_redeem_no_proof').\
            get_attribute('value')
        self.assertEqual(text_area_text, text_to_input)
        button = selenium.find_element_by_xpath(
            '/html/body/div[3]/div/form/div[1]/div[2]/a')
        selenium.execute_script("$(arguments[0]).click();", button)

        # STEP 2: Record price
        _selenium_wait_for(lambda: selenium.find_element_by_id(
            'id_redeem_price'
        ))
        selenium.find_element_by_id('id_redeem_price').send_keys(redeem_price)
        button = selenium.find_element_by_xpath(
            '/html/body/div[3]/div/form/div[1]/div[2]/a')
        selenium.execute_script("$(arguments[0]).click();", button)

        # STEP 3: Confirm exchange
        submit_button = selenium.find_element_by_xpath(
            '//*[@id="offer-3"]/div/div/div/input')
        _selenium_wait_for(lambda: submit_button)
        self.assertIn('$<span class="dollars-total">{}</span>'.format(
            exprected_usd_amount_gross), selenium.page_source)
        self.assertIn('$<span class="dollars-received">{}</span>'.format(
            exprected_usd_amount_net), selenium.page_source)
        selenium.execute_script("$(arguments[0]).click();", submit_button)

        # wait for redirection to user profile page
        _selenium_wait_for(
            lambda: selenium.find_element_by_class_name(
                'earn-currents-popup_open'))

        # asserting currents and USD for volunteer_1 after submitting the form
        self.volunteer_currents_assert(self.volunteer_1, 0.0)
        self.assertEqual(
            OcUser(self.volunteer_1.id).get_balance_pending_usd(),
            exprected_usd_amount_net)

        # logging in as biz admin to check state of pending currents after
        # submitting the form
        self.biz_pending_currents_assertion(self.biz_admin, 1.0)
