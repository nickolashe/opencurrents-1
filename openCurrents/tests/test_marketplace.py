"""Marketplace page unit tests."""

from django.test import Client, TestCase

from openCurrents.models import \
    Item, \
    Offer, \
    UserEntity


from openCurrents.tests.interfaces.common import (
    _create_test_user,
    _create_org,
)

import re

# from unittest import skip


# @@@ TODO @@@
# remove this function when merged with kostya_transaction_unittests branch
def _create_offer(
        org,
        offer_item_name='Test Item',
        offer_limit=None,
        currents_share=25,
        is_master=False
):
    """
    Create offer.

    takes
    org - biz Org instance
    item_name - string
    offer_limit - None or Int
    currents_share - int
    creates Item and Offer, returns Offer object
    """
    offer_item = Item(name=offer_item_name)
    offer_item.save()

    offer = Offer(
        org=org,
        item=offer_item,
        currents_share=currents_share,
        is_master=is_master
    )

    if offer_limit:
        offer.limit = offer_limit

    offer.save()

    return offer


class SetupAll(TestCase):
    """Setup class."""

    def setUp(self):
        """Main setup method."""
        self._SHARE = .25

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

        # creating an offer
        self.offer_master = _create_offer(
            self.biz_org, currents_share=self._SHARE * 100, is_master=True)

        # getting item
        self.purchased_item = Item.objects.filter(offer__id=self.offer_master.id)[0]

        # setting up client
        self.client = Client()


class TestMarketplaceNonLogged(SetupAll):
    """Set of tests for marketplace as non-logged user."""

    def test_access_marketplace_nonlogged(self):
        """
        Non logged in user visits marketplace page.

        Non-logged user can see market place page with the list of the offers.
        """
        response = self.client.get('/marketplace/')
        processed_content = re.sub(r'\s+', ' ', response.content)

        # generic assertions
        self.assertIn(
            '<h3 class="title-sub"> Marketplace </h3>', processed_content
        )

        # assert user sees public marketplace page
        for biz_name in ['HEB']:
            self.assertIn(
                '/redeem-option/?biz_name={}'.format(biz_name),
                response.content
            )

        # TODO: add other biz's offers and assert for their presence

    def test_reedeem_offer_marketplace_nonlogged(self):
        """
        Non logged in user tries to redeem an offer.

        Non-logged user is redirected to login page. The URL parameter 'next'
        point to the redeem-currents page.
        """
        # try to redeem offer without logging
        response = self.client.get('/redeem-currents/1/')

        self.assertRedirects(
            response,
            '/login/?next=/redeem-currents/1/',
            status_code=302,
            target_status_code=200
        )
