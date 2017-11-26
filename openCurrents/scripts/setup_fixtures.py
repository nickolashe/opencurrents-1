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
        'email': 'replace1@withyouremail.com',
        'firstname': 'John',
        'lastname': 'Volunteer',
        'type': 'volunteer'
    },
    {
        'email': 'replace2@withyouremail.com',
        'firstname': 'Patrick',
        'lastname': 'Volunteer',
        'type': 'volunteer'
    },
    {
        'email': 'replace3@withyouremail.com',
        'firstname': 'Chris',
        'lastname': 'GreatDeedsAdmin',
        'type': 'npf'
    },
    {
        'email': 'replace4@withyouremail.com',
        'firstname': 'Ed',
        'lastname': 'GreatDeedsAdmin',
        'type': 'npf'
    },
    {
        'email': 'replace5@withyouremail.com',
        'firstname': 'Mark',
        'lastname': 'ConciousBizAdmin',
        'type': 'biz'
    }
]

fixtures_orgs = [
    {'name': 'GreatDeeds', 'status': 'npf'},
    {'name': 'ConciousBiz', 'status': 'biz'}
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

        users_all.append(user)

        if fxt['type'] != 'volunteer':
            org = None
            if fxt['type'] == 'npf':
                org = Org.objects.get(name='GreatDeeds')
            else:
                org = Org.objects.get(name='ConciousBiz')

            oui = OrgUserInfo(user.id)

            try:
                oui.setup_orguser(org)
            except InvalidOrgUserException:
                print 'org <=> %s mapping already exists' % fxt['email']

            try:
                oui.make_org_admin(org.id)
            except InvalidOrgException:
                print 'error: %s does not have admin group' % org.name
            except ExistingAdminException:
                print '%s already admin of %s' % (user.email, org.name)

    return users_all


def setup_volunteer_requests():
    users = User.objects.filter(email__endswith='withyouremail.com')
    usertimelogs = UserTimeLog.objects.filter(user__in=users)
    if len(usertimelogs) >= 10:
        print 'Enough hour requests by user fixtures'
        return

    for i in xrange(10):
        user = _get_random_item(User.objects.filter(
            email__endswith='withyouremail.com'
        ))

        org = random.choice(Org.objects.filter(name='GreatDeeds'))
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
            last_name='GreatDeedsAdmin'
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


def setup_offers():
    org = Org.objects.get(name='ConciousBiz')
    offer_items = [
        'All products',
        'Kombucha',
        'Jun'
    ]

    offers_all = Offer.objects.filter(org=org)
    if len(offers_all) < 3:
        offers_all = []
        for name in offer_items:
            limit = random.randint(-5, 5)
            item, created = Item.objects.get_or_create(name=name)
            offer, created = Offer.objects.get_or_create(
                org=org,
                item=item,
                currents_share=random.randint(1, 20) * 5,
                limit=(-1 if limit <= 0 else limit * 5)
            )
            offers_all.append(offer)
            #print 'Offer for %s by %s' % (offer.item.name, offer.org.name)
            print str(offer)
    else:
        print '%s already has enough offers' % org.name

    return offers_all


def setup_redemptions():
    users_all = User.objects.filter(email__endswith='withyouremail.com')
    transactions = Transaction.objects.filter(user__in=users_all)
    if len(transactions) >= 10:
        print 'Enough user transactions'
        return

    org = Org.objects.get(name='ConciousBiz')
    offers_all = Offer.objects.filter(org=org)

    for i in xrange(10):
        users = [
            user
            for user in users_all
            if OcLedger().get_balance(user.userentity.id) > 0
        ]

        if not users:
            print 'No users with currents!'
            return

        user = _get_random_item(users)
        user_balance = OcLedger().get_balance(user.userentity.id)
        amount_spent_cur = round(random.random() * float(user_balance), 3)

        offer = _get_random_item(offers_all)
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
        # print 'Action [%s] for %s\'s redemption of %s\'s offer for %s' % (
        #     action,
        #     user.email,
        #     offer.org.name,
        #     offer.item.name
        # )
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
    setup_orgs()
    setup_users()
    setup_volunteer_requests()
    setup_offers()
    setup_redemptions()
