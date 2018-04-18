"""Common classes and methods for unit tests."""
from django.contrib.auth.models import User

from openCurrents.models import \
    AdminActionUserTime, \
    Item, \
    Ledger, \
    Offer, \
    Org, \
    OrgUser, \
    Project, \
    Event, \
    Transaction, \
    TransactionAction, \
    UserEventRegistration, \
    UserTimeLog

from openCurrents.interfaces.orgs import (
    OrgUserInfo,
    OcOrg
)

from openCurrents.interfaces.ocuser import (
    OcUser
)

from openCurrents.interfaces.auth import (OcAuth)

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.common.exceptions import WebDriverException

import time


# ====== CONTENT =======
# _create_org
# _create_test_user
# _create_project
# _create_event
# _create_offer
# _setup_user_event_registration
# _setup_volunteer_hours
# _setup_transactions
# _setup_ledger_entry
# _selenium_wait_for


class SetUpTests(object):
    """Helper class to setup tests."""

    def generic_setup(
            self,
            npf_orgs_list,
            biz_orgs_list,
            volunteers_list,
            create_admins=True,
            create_projects=True
    ):
        """
        Take lists of initial data and create needed objects.

        npf_orgs_list - list of NPF orgs titles (string)
        biz_orgs_list - list of BIZ orgs titles (string)
        volunteers_list - list of volunteers names (string)
        create_admins - boolean, to create an admin per NPF/BIZ org
        create_projects - boolean, to create a project per each NPF org
        """
        # creating NPF org with projects if required
        org_i = 0
        for npf_org in npf_orgs_list:

            org_i += 1
            org = _create_org(npf_org, "npf")

            # creating projects
            if create_projects:
                _create_project(org, 'test_project_{}'.format(str(org_i)))

            # creating an NPF admin
            if create_admins:
                _create_test_user(
                    'npf_admin_{}'.format(str(org_i)),
                    org=org,
                    is_org_admin=True
                )

        # creating BIZ org
        biz_org_i = 0
        for biz_org in biz_orgs_list:

            biz_org_i += 1
            org = _create_org(biz_org, "biz")

            # creating an NPF admin
            if create_admins:
                _create_test_user(
                    'biz_admin_{}'.format(str(biz_org_i)),
                    org=org,
                    is_org_admin=True
                )

        # creating existing volunteers
        for volunteer in volunteers_list:
            _create_test_user(volunteer)

    def get_all_volunteers(self):
        """Return list of volunteers."""
        volunteers = []
        for user in User.objects.all():
            if not OcAuth(user.id).is_admin():
                volunteers.append(user)
        return volunteers

    def get_all_npf_admins(self):
        """Return list of NPF admins (user instance)."""
        npf_admins = []
        for user in OrgUser.objects.all():
            u = OcAuth(user.id)
            if u.is_admin_org():
                npf_admins.append(user.user)
        return npf_admins

    def get_all_biz_admins(self):
        """Return list of BIZ admins."""
        biz_admins = []
        for user in OrgUser.objects.all():
            u = OcAuth(user.id)
            if u.is_admin_biz():
                biz_admins.append(user.user)

        return biz_admins

    def get_all_npf_orgs(self):
        """Return list of NPF orgs."""
        return [org for org in Org.objects.filter(status='npf')]

    def get_all_biz_orgs(self):
        """Return list of BIZ orgs."""
        return [org for org in Org.objects.filter(status='biz')]

    def get_all_projects(self, org):
        """Return list of projects."""
        return [proj for proj in Project.objects.filter(org=org)]


def _create_org(org_name, org_status):
    """
    Create users and maps them to the org if needed.

    Takes:
        org_name - string
        org_status - string ('npf', 'biz')
    """
    new_org = OcOrg().setup_org(name=org_name, status=org_status)

    return new_org


def _create_test_user(
    user_name,
    password='password',
    org=None,
    is_org_admin=False
):
    """
    Create users and maps them to the org if needed.

    Takes:
        user_name - string

        org - Org object. A NPF admin will be created, if Org is provided and is_org_admin = True.
        An org user will be created if org is provided and is_org_admin = False.
        If no org provided - a volunteer will be created.

        is_org_admin - if True, the user will be made an org admin, if org is provided.
    """
    test_user = OcUser().setup_user(
        username=user_name,
        email=user_name + '@email.cc',
        first_name=user_name + '_first_name',
        last_name=user_name + '_last_name'
    )

    if org:
        # mapping user to org
        oui = OrgUserInfo(test_user.id)
        oui.setup_orguser(org)

        # making a user an org admin
        if is_org_admin:
            oui.make_org_admin(org.id)

    test_user.set_password(password)
    test_user.save()
    return test_user


def _create_project(org, project_name):
    """
    Create project.

    org - Org object
    project_name - string
    """
    project = Project(
        org=org,
        name=project_name
    )
    project.save()
    return project


def _create_event(
    project,
    creator_id,
    datetime_start,
    datetime_end,
    description="Test Event",
    location="test_location",
    is_public=False,
    event_type="MN",
    coordinator=None
):
    """
    creates an event with given parameters
    """
    event = Event(
        project=project,
        description=description,
        location=location,
        is_public=is_public,
        datetime_start=datetime_start,
        datetime_end=datetime_end,
        coordinator=coordinator,
        creator_id=creator_id
    )
    event.save()
    return event


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


def _setup_user_event_registration(
    user,
    event,
    is_confirmed=False
):
    """
    creates a user event registration with given parameters
    """
    user_event_registration = UserEventRegistration(
        user=user,
        event=event,
        is_confirmed=is_confirmed
    )
    user_event_registration.save()
    return user_event_registration


def _setup_volunteer_hours(
    volunteer,
    npf_admin,
    org,
    project,
    datetime_start,
    datetime_end,
    description="Manually tracked time ",
    event_type="MN",
    is_verified=False,
    action_type='req'
):
    """
    Set up volunteers manually recprded hours.

    function takes:
        volunteer = User objects
        npf_admin = npf admin object
        org = Org object
        project = Project object
        description = provided string will be added to the end of default string
        event_type = string "MN" or "GR" (defautl "MN")
        datetime_start = datetime.datetime
        datetime_end = datetime.datetime
        is_verified = False/True (default False)
        action_type = 'app'/'dec'/'req' (default 'req')
    and creates respective records in testing DB.
    """
    event = Event.objects.create(
        project=project,
        is_public=True,
        description="finished event",
        location="test_location",
        coordinator=npf_admin,
        event_type=event_type,
        datetime_start=datetime_start,
        datetime_end=datetime_end
    )

    volunteer_timelog = UserTimeLog.objects.create(
        user=volunteer,
        event=event,
        datetime_start=datetime_start,
        datetime_end=datetime_end,
        is_verified=is_verified
    )

    actiontimelog = AdminActionUserTime.objects.create(
        user=npf_admin,
        usertimelog=volunteer_timelog,
        action_type=action_type
    )

    return volunteer_timelog, actiontimelog, event


def _setup_transactions(
    biz_org,
    biz_admin,
    transaction_currents_amount,
    transaction_price_reported,
    price_actual=None,
    pop_type='rec',
    offer_item_name="Test Item",
    currents_share=40,
    action_type='req'
):
    """
    Create pending or approved transactions.

    biz_org - biz org instance;
    biz_admin - biz admin user instance;
    transaction_currents_amount - int or float;
    transaction_price_reported - int or float;
    offer_item_name - string;
    currents_share - int or float;
    action_type - string. Possible values: 'req', 'app', 'red', 'dec'
    """
    offer_item = Item(name=offer_item_name)
    offer_item.save()

    offer = Offer(
        org=biz_org,
        item=offer_item,
        currents_share=currents_share
    )
    offer.save()

    if price_actual is None:
        price_actual = transaction_price_reported

    transaction = Transaction(
        user=biz_admin,
        offer=offer,
        price_reported=transaction_price_reported,
        currents_amount=transaction_currents_amount,
        price_actual=price_actual
    )
    transaction.save()

    action = TransactionAction(
        transaction=transaction,
        action_type=action_type
    )
    action.save()


def _setup_ledger_entry(
    entity_from,
    entity_to,
    currency='cur',
    amount=100.30,
    is_issued=False,
    action=None,
    transaction=None
):
    """
    USE IT UNTILL WE HAVE ledger.OcLedger.add_fiat implemented.

    entity_from -   Entity objects (eg User and Org)
    entity_to -     Entity objects (eg User and Org)
    currency -      string 'cur' or 'usd'
    amount -        Int of Float
    is_issued -     boolean
    action -        AdminActionUserTime instance
    transaction -   TransactionAction instance
    """
    ledger_rec = Ledger(
        entity_from=entity_from,
        entity_to=entity_to,
        currency=currency,
        amount=amount,
        is_issued=is_issued,
        action=action,
        transaction=transaction
    )
    ledger_rec.save()
    return ledger_rec


def _selenium_wait_for(fn):
    """Wait for ement on the page for 5 seconds."""
    start_time = time.time()
    while True:
        try:
            return fn()
        except (AssertionError, WebDriverException) as e:
            if time.time() - start_time > 10:
                raise e
            time.sleep(0.5)
