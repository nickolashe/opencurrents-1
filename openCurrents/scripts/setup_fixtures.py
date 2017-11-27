from django.contrib.auth.models import User

from openCurrents.interfaces.common import diffInHours
from openCurrents.interfaces.ocuser import OcUser, UserExistsException
from openCurrents.interfaces.ledger import OcLedger
from openCurrents.interfaces.orgs import OcOrg, \
    OrgUserInfo, \
    OrgExistsException, \
    InvalidOrgException, \
    InvalidOrgUserException, \
    ExistingAdminException

from openCurrents.models import Org, \
    Project, \
    Event, \
    UserEventRegistration, \
    AdminActionUserTime, \
    UserTimeLog, \
    Item, \
    Offer, \
    TransactionAction, \
    Transaction, \
    Ledger

from datetime import datetime, timedelta
from numpy import random
import string
import pytz

fixtures_user = [
    {
        'email': 'volunteer1@opencurrents.com',
        'firstname': 'John',
        'lastname': 'Volunteer',
        'type': 'volunteer'
    },
    {
        'email': 'volunteer2@opencurrents.com',
        'firstname': 'Patrick',
        'lastname': 'Volunteer',
        'type': 'volunteer'
    },
    {
        'email': 'greatdeeds_admin1@opencurrents.com',
        'firstname': 'Chris',
        'lastname': 'GreatDeedsAdmin',
        'type': 'npf'
    },
    {
        'email': 'greatdeeds_admin2@opencurrents.com',
        'firstname': 'Ed',
        'lastname': 'GreatDeedsAdmin',
        'type': 'npf'
    },
    {
        'email': 'goodvibes_admin@opencurrents.com',
        'firstname': 'Kate',
        'lastname': 'GoodVibesAdmin',
        'type': 'npf'
    },
    {
        'email': 'consciousbiz_admin1@opencurrents.com',
        'firstname': 'Mark',
        'lastname': 'ConciousBizAdmin',
        'type': 'biz'
    },
    {
        'email': 'consciousbiz_admin2@opencurrents.com',
        'firstname': 'Andrew',
        'lastname': 'ConciousBizAdmin',
        'type': 'biz'
    },
    {
        'email': 'greenbiz_admin@opencurrents.com',
        'firstname': 'Ann',
        'lastname': 'GreenBizAdmin',
        'type': 'biz'
    }
]

fixtures_orgs = [
    {'name': 'GreatDeeds', 'status': 'npf'},
    {'name': 'GoodVibes', 'status': 'npf'},
    {'name': 'ConciousBiz', 'status': 'biz'},
    {'name': 'GreenBiz', 'status': 'biz'}
]

def _get_random_item(items):
    return random.choice(items)

def _get_random_string():
    rnd_digits = ''.join([
        random.choice(list(string.digits))
        for i in xrange(8)
    ])
    rnd_chars = ''.join([
        random.choice(list(string.letters))
        for i in xrange(15)
    ])

    return rnd_digits + rnd_chars

# set up orgs
def setup_orgs():
    orgs_all = []
    for fxt in fixtures_orgs:
        try:
            org = OcOrg().setup_org(fxt['name'], fxt['status'])
        except OrgExistsException:
            org = Org.objects.get(name=fxt['name'])
            print 'Org %s already exists' % fxt['name']

        orgs_all.append(org)

    return orgs_all

# set up users and user <=> org mappings
def setup_users():
    users_all = []
    for fxt in fixtures_user:
        try:
            user = OcUser().setup_user(
                fxt['email'],
                fxt['email'],
                fxt['firstname'],
                fxt['lastname']
            )
        except UserExistsException:
            user = User.objects.get(email=fxt['email'])
            print 'User %s already exists' % fxt['email']

        user.set_password(fxt['lastname'])
        user.save()
        users_all.append(user)

        if fxt['type'] != 'volunteer':
            org = None
            orgname = fxt['lastname'].strip('Admin')
            try:
                org = Org.objects.get(name=orgname)
            except Exception as e:
                print 'No org named %s (%s)' % (orgname, org.name)
                return

            oui = OrgUserInfo(user.id)

            try:
                oui.setup_orguser(org)
            except InvalidOrgUserException:
                print 'Unable to configure %s <=> %s mapping (possible it already exists)' % (org.name, fxt['email'])

            try:
                oui.make_org_admin(org.id)
            except InvalidOrgException:
                print 'Unable to grant admin privilege to %s on org %s (check for exitence of admin group)' % (user.username, org.name)
            except ExistingAdminException:
                print '%s already granted admin privilege on org %s' % (user.username, org.name)

    return users_all


def setup_events(users, orgs):
    npf_orgs = [org for org in orgs if org.status == 'npf']
    names = random.choice(list(string.letters), 10, replace=False)

    for name in names:
        org = _get_random_item(npf_orgs)
        project, created = Project.objects.get_or_create(
            name=' '.join(['Let\'s', name]),
            org=org
        )

        datetime_start = datetime.now(tz=pytz.utc) + \
            _get_random_item([-1, 1]) * timedelta(days=random.randint(60)) + \
            timedelta(hours=random.randint(12, 24))
        datetime_end = datetime_start + timedelta(hours=random.randint(4))
        num_locations = random.randint(3)

        for loc in xrange(num_locations):
            event = Event.objects.create(
                project=project,
                description=_get_random_string(),
                location='Location' + str(loc),
                coordinator=_get_random_item(User.objects.filter(last_name=org.name + 'Admin')),
                is_public=True,
                datetime_start=datetime_start,
                datetime_end=datetime_end
            )
            print str(event)

            # register for event
            users_reg = random.choice(users, random.randint(1, len(users)), replace=False)
            for user in users_reg:
                try:
                    uer = UserEventRegistration.objects.create(
                        user=user,
                        event=event,
                        is_confirmed=True
                    )
                    print str(uer)
                except Exception as e:
                    print e.message
                    pass

            # checkin at random time
            users_checkin = random.choice(users_reg, random.randint(len(users_reg)), replace=False)
            event_duration = datetime_end - datetime_start

            for user_chk in users_checkin:
                try:
                    utl = UserTimeLog.objects.create(
                        user=user_chk,
                        event=event,
                        is_verified=True,
                        datetime_start=datetime_start + _get_random_item([-1, 0, 1]) * random.randint(4) * event_duration
                    )

                    # randomly checkout
                    if random.randint(2):
                        utl.datetime_end = datetime_start + timedelta(hours=random.randint(12))
                        utl.save()
                    print str(utl)
                except Exception as e:
                    print e.message
                    pass

def setup_volunteer_requests(users, orgs):
    npf_orgs = [org for org in orgs if org.status == 'npf']
    usertimelogs = UserTimeLog.objects.filter(user__in=users)
    if len(usertimelogs) >= 30:
        print 'Sufficient number of existing hour requests already'
        return

    for i in xrange(30):
        user = _get_random_item(users)
        org = random.choice(npf_orgs)
        action = random.choice(['req', 'app', 'dec'])
        is_verified = action == 'app'

        project, created = Project.objects.get_or_create(
            org=org,
            name='ManualTracking'
        )

        datetime_start = datetime.now(tz=pytz.utc) - \
            timedelta(days=random.randint(7)) + \
            timedelta(hours=random.randint(24)) + \
            timedelta(minutes=random.randint(4) * 15)
        datetime_end = datetime_start + \
            timedelta(minutes=random.randint(1,16) * 15)

        event = Event.objects.create(
            project=project,
            description=_get_random_string(),
            event_type='MN',
            datetime_start=datetime_start,
            datetime_end=datetime_end
        )

        usertimelog = UserTimeLog.objects.create(
            user=user,
            event=event,
            datetime_start=datetime_start,
            datetime_end=datetime_end,
            is_verified=is_verified
        )

        admin = _get_random_item(User.objects.filter(
            last_name=org.name + 'Admin'
        ))
        actiontimelog = AdminActionUserTime.objects.create(
            user=admin,
            usertimelog=usertimelog,
            action_type=action
        )
        amount = diffInHours(datetime_start, datetime_end)
        # print 'Action [%s] for %.2f hours submitted by %s' % (action, amount, user.email)
        print str(actiontimelog)

        if is_verified:
            OcLedger().issue_currents(
                entity_id_from=org.orgentity.id,
                entity_id_to=user.userentity.id,
                action=actiontimelog,
                amount=amount
            )


def setup_offers(orgs):
    biz_orgs = [org for org in orgs if org.status == 'biz']

    offer_items = [
        'All products',
        'Kombucha',
        'Jun'
    ]

    for org in biz_orgs:
        orgs_offers = Offer.objects.filter(org=org)
        if len(orgs_offers) < 3:
            for name in offer_items:
                limit = random.randint(-5, 5)
                item, created = Item.objects.get_or_create(name=name)
                offer, created = Offer.objects.get_or_create(
                    org=org,
                    item=item,
                    currents_share=random.randint(1, 20) * 5,
                    limit=(-1 if limit <= 0 else limit * 5)
                )
                #orgs_offers.append(offer)
                #print 'Offer for %s by %s' % (offer.item.name, offer.org.name)
                print str(offer)
        else:
            print '%s has enough offers already' % org.name

    return


def setup_redemptions(users, orgs):
    biz_orgs = [org for org in orgs if org.status == 'biz']

    transactions = Transaction.objects.filter(user__in=users)
    if len(transactions) >= 20:
        print 'Sufficient number of redemptions already'
        return

    for i in xrange(20):
        org = _get_random_item(biz_orgs)
        orgs_offers = Offer.objects.filter(org=org)
        users = [
            user
            for user in users
            if OcUser(user.id).get_balance_available() > 0
        ]

        if not users:
            print 'No users with currents available!'
            return

        user = _get_random_item(users)
        user_balance = OcUser(user.id).get_balance_available()
        amount_spent_cur = round(random.random() * float(user_balance), 3)

        offer = _get_random_item(orgs_offers)
        price_reported = round(
            1000. / offer.currents_share * amount_spent_cur,
            2
        )

        transaction = Transaction.objects.create(
            user=user,
            offer=offer,
            pop_no_proof=_get_random_string(),
            pop_type='other',
            price_reported=price_reported,
            currents_amount=amount_spent_cur
        )

        action = random.choice(['req', 'app', 'red', 'dec'])
        transaction_action = TransactionAction.objects.create(
            transaction=transaction,
            action_type=action
        )
        print str(transaction_action)

        is_verified = (action in ['app', 'red'])
        if is_verified:
            OcLedger().transact_currents(
                entity_type_from='user',
                entity_id_from=user.userentity.id,
                entity_type_to='org',
                entity_id_to=org.orgentity.id,
                action=transaction_action,
                amount=amount_spent_cur
            )


if __name__ == '__main__':
    orgs = setup_orgs()
    users = setup_users()
    setup_events(users, orgs)
    setup_volunteer_requests(users, orgs)
    setup_offers(orgs)
    setup_redemptions(users, orgs)
