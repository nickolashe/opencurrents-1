"""Transactions tests setup."""


from django.test import Client
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
    UserEntity
)

from openCurrents.tests.interfaces.common import (
    _create_offer,
    SetUpTests
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

    def biz_pending_currents_assertion(
        self,
        biz_admin,  # User, biz admin
        expected_pending_current,  # integer
    ):
        """Assert biz pending currents."""
        self.client.login(
            username=biz_admin.username, password='password')
        response = self.client.get('/biz-admin/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['currents_pending'], expected_pending_current)

        return response

    def volunteer_currents_assert(
        self,
        user,  # User, volunteer
        currents_amount,  # integer
    ):
        """Assert volunteer currents."""
        self.client.login(username=user.username,
                          password='password')
        response_balance = self.client.get('/get_user_balance_available/')
        self.assertEqual(response_balance.status_code, 200)

        # checking initial user CURRENTS balance
        self.assertEqual(response_balance.content, str(currents_amount))

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

        # creating master offer
        if len(biz_orgs_list) > 0:
            self.offer = _create_offer(
                self.org_biz,
                currents_share=self._SHARE * 100,
                is_master=True
            )

        # getting item
        self.purchased_item = Item.objects.filter(offer__id=self.offer.id)[0]

        # setting up client
        self.client = Client()

    def tearDown(self):
        """Tear down."""
        pass
