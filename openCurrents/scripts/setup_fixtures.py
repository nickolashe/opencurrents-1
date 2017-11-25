from django.contrib.auth.models import User

from openCurrents.interfaces.ocuser import OcUser, UserExistsException
from openCurrents.interfaces.orgs import OcOrg, \
    OrgUserInfo, \
    OrgExistsException, \
    InvalidOrgException, \
    InvalidOrgUserException, \
    ExistingAdminException

from openCurrents.models import Org, \
    AdminActionUserTime, \
    UserTimeLog, \
    TransactionAction, \
    Transaction

from datetime import datetime, timedelta
from numpy import random
import string

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

# set up orgs
for org in fixtures_orgs:
    try:
        OcOrg().setup_org(org['name'], org['status'])
    except OrgExistsException:
        print 'Org %s already exists' % org['name']

# set up users and user <=> org mappings
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

    if fxt['type'] != 'volunteer':
        org = None
        print fxt['type']
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


def volunteer_requests():
    for i in xrange(random.randint(10)):
        user = random.choice(User.objects.all())
        admin = random.choice(User.objects.filter(
            lastname='GreatDeedsAdmin'
        ))
        org = random.choice(Org.objects.all())
        action = random.choice(['req', 'app', 'dec'])

        project = Project.objects.get_or_create(
            org=org,
            name='ManualTracking'
        )
        project.save()

        rnd_digits = ''.join([
            random.choice(string.digits)
            for i in xrange(8)
        ])
        rnd_chars = ''.join([
            random.choice(string.letters)
            for i in xrange(15)
        ])

        datetime_start = datetime.now() - \
            timedelta(days=random.randint(7)) + \
            timedelta(hours=random.randint(24)) + \
            timedelta(minutes=random.randint(4) * 15)
        datetime_end = datetime_start + \
            timedelta(minutes=random.randint(16) * 15)

        event = Event.objects.create(
            project=project,
            description=rnd_chars + rnd_digits,
            event_type='MN',
            datetime_start=datetime_start,
            datetime_end=datetime_end
        )

        usertimelog = UserTimeLog.objects.create(
            user=user,
            event=event,
            datetime_start=datetime_start,
            datetime_end=datetime_end
        )

        actiontimelog = AdminActionUserTime.objects.create(
            user=,
            usertimelog=usertimelog,
            action_type=action
        )
