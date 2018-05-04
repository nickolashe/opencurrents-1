from __future__ import unicode_literals
from django.contrib.auth.models import User
from django.db import models

from uuid import uuid4

from datetime import datetime, timedelta

from openCurrents.interfaces.common import one_week_from_now, diffInHours
from openCurrents.interfaces import convert

import os
import pytz
import re

# Notes:
# *) unverified users are still created as User objects but with unusable password


# org model
class Org(models.Model):
    name = models.CharField(max_length=100, unique=True)
    website = models.CharField(max_length=100, null=True, blank=True)
    phone = models.CharField(max_length=10, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    address = models.CharField(max_length=1024, null=True, blank=True)
    intro = models.CharField(max_length=16192, null=True, blank=True)

    org_types = (
        ('biz', 'business'),
        ('npf', 'non-profit')
    )
    status = models.CharField(
        max_length=3,
        choices=org_types,
        default='npf'
    )

    users = models.ManyToManyField(User, through='OrgUser')
    timezone = models.CharField(max_length=128, default='America/Chicago')

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)

    @property
    def no_info(self):
        no_info = True
        fields = [self.website, self.phone, self.email, self.address, self.intro]

        if any(f != '' for f in fields):
            no_info = False

        return no_info

    def __unicode__(self):
        return ' '.join([
            str(self.status),
            str(self.name),
            'with id',
            str(self.id)
        ])


# user-org affiliations
class OrgUser(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    org = models.ForeignKey(Org)

    affiliation = models.CharField(max_length=50, null=True)

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)

    class Meta:
        unique_together = ('user', 'org')

    def __unicode__(self):
        return ' '.join([
            self.user.email,
            'is',
            str(self.affiliation),
            'at',
            self.org.name
        ])


class Entity(models.Model):
    def __unicode__(self):
        try:
            entity = OrgEntity.objects.get(id=self.id)
            name_from = entity.org.name
        except:
            entity = UserEntity.objects.get(id=self.id)
            name_from = entity.user.username

        return name_from


class UserEntity(Entity):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE
    )
    entity_type = 'user'

    def __unicode__(self):
        return '%s\'s user entity' % self.user.username


class OrgEntity(Entity):
    org = models.OneToOneField(
        Org,
        on_delete=models.CASCADE
    )
    entity_type = 'org'

    def __unicode__(self):
        return '%s\'s org entity' % self.org.name


class UserSettings(models.Model):
    '''
    user settings
    '''
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE
    )
    timezone = models.CharField(max_length=128, default='America/Chicago')
    monthly_updates = models.BooleanField(default=False)
    popup_reaction = models.NullBooleanField(blank=True, null=True, default=None)

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date last updated', auto_now=True)

    def __unicode__(self):
        return '%s\'s settings' % self.user.username


class Ledger(models.Model):
    '''
    Transaction Ledger
    '''
    entity_from = models.ForeignKey(
        Entity,
        related_name='transaction_out'
    )
    entity_to = models.ForeignKey(
        Entity,
        related_name='transaction_in'
    )
    currency = models.CharField(
        choices=(
            ('cur', 'current'),
            ('usd', 'dollar')
        ),
        default='cur',
        max_length=3
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_issued = models.BooleanField(default=False)
    is_bonus = models.BooleanField(default=False)

    # related actions
    # TODO:
    #   - refactor using a joint table for actions
    #   - *and* enforce uniqueness constraint (action, entity_to, entity_from)
    action = models.ForeignKey(
        'AdminActionUserTime',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    transaction = models.ForeignKey(
        'TransactionAction',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)

    def __unicode__(self):
        try:
            entity = OrgEntity.objects.get(id=self.entity_from.id)
            name_from = entity.org.name
        except:
            entity = UserEntity.objects.get(id=self.entity_from.id)
            name_from = entity.user.username

        try:
            entity = OrgEntity.objects.get(id=self.entity_to.id)
            name_to = entity.org.name
        except:
            entity = UserEntity.objects.get(id=self.entity_to.id)
            name_to = entity.user.username

        return ' '.join([
            'Issued by' if self.is_issued else 'Transaction from',
            name_from,
            'to',
            name_to,
            'in the amount of',
            str(self.amount),
            'on',
            self.date_created.strftime(
                '%Y-%m-%d %I-%M %p'
            ),
            'UTC'
        ])


class Project(models.Model):
    name = models.CharField(max_length=1024)
    org = models.ForeignKey(Org)

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)

    def __unicode__(self):
        return ' '.join([
            'Project',
            self.name,
            'by',
            self.org.name
        ])


class Event(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    description = models.CharField(max_length=8192)
    location = models.CharField(max_length=1024)

    # coordinator
    coordinator = models.ForeignKey(User, null=True)

    # event creator userid and notification flag
    creator_id = models.IntegerField(default=0)
    notified = models.BooleanField(default=False)

    MANUAL = 'MN'
    GROUP = 'GR'
    event_type_choices = (
        (MANUAL, 'ManualTracking'),
        (GROUP, 'Group'),
    )

    event_type = models.CharField(
        max_length=2,
        choices=event_type_choices,
        default=GROUP
    )

    is_public = models.BooleanField(default=False)

    # start / end timestamps of the project
    datetime_start = models.DateTimeField('start datetime')
    datetime_end = models.DateTimeField('end datetime')

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)

    class Meta:
        get_latest_by = 'datetime_start'
        ordering = ['datetime_start']

    def save(self, *args, **kwargs):

        super(Event, self).save(*args, **kwargs)

    def __unicode__(self):
        tz = self.project.org.timezone
        return ' '.join([
            'Event',
            self.project.name,
            'by',
            self.project.org.name,
            'at',
            self.location,
            'on',
            self.datetime_start.astimezone(pytz.timezone(tz)).strftime('%b %d'),
            'from',
            self.datetime_start.astimezone(pytz.timezone(tz)).strftime('%-I:%M %p'),
            'to',
            self.datetime_end.astimezone(pytz.timezone(tz)).strftime('%-I:%M %p')
        ])


class ProjectTemplate(models.Model):
    user = models.ForeignKey(User)
    event = models.ForeignKey(Event)


class UserEventRegistration(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    is_confirmed = models.BooleanField(default=False)

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)

    class Meta:
        unique_together = ('user', 'event')

    def __unicode__(self):
        tz = self.event.project.org.timezone
        return ' '.join([
            self.user.username,
            'is registered for',
            self.event.project.name,
            'on',
            self.date_created.astimezone(pytz.timezone(tz)).strftime('%Y-%m-%d %I-%M %p'),
        ])


class UserTimeLog(models.Model):
    user = models.ForeignKey(User)
    event = models.ForeignKey(Event)
    is_verified = models.BooleanField(default=False)
    deferments = models.ManyToManyField(
        User,
        through='AdminActionUserTime',
        related_name='deferments'
    )

    # start / end timestamps of the contributed time
    datetime_start = models.DateTimeField('start time')
    datetime_end = models.DateTimeField('end time', null=True, blank=True)

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)

    class Meta:
        get_latest_by = 'datetime_start'
        unique_together = ('user', 'event')

    def __unicode__(self):
        tz = self.event.project.org.timezone
        status = ' '.join([
            self.user.username,
            'contributed %s',
            'to',
            self.event.project.org.name,
            'starting',
            self.datetime_start.astimezone(pytz.timezone(tz)).strftime('%Y-%m-%d %I-%M %p'),
        ])

        if self.event.event_type == 'GR':
            status = ' '.join([
                status,
                'at event',
                self.event.project.name
            ])

            hours = diffInHours(
                self.event.datetime_start,
                self.event.datetime_end
            )
        else:
            hours = diffInHours(
                self.datetime_start,
                self.datetime_end
            )

        status %= str(hours) + ' hr.'
        return status


class AdminActionUserTime(models.Model):
    user = models.ForeignKey(User)
    usertimelog = models.ForeignKey(
        UserTimeLog,
        on_delete=models.CASCADE
    )
    action_type_choices = (
        ('app', 'approved'),
        ('dec', 'declined'),
        ('req', 'approval_request')
    )
    action_type = models.CharField(
        max_length=3,
        choices=action_type_choices
    )

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)

    class Meta:
        unique_together = ('action_type', 'user', 'usertimelog')

    def __unicode__(self):
        if self.usertimelog.datetime_end:
            hours = diffInHours(
                self.usertimelog.datetime_start,
                self.usertimelog.datetime_end
            )
        else:
            hours = diffInHours(
                self.usertimelog.event.datetime_start,
                self.usertimelog.event.datetime_end
            )

        tz = self.usertimelog.event.project.org.timezone

        if self.action_type == 'req':
            return ' '.join([
                self.usertimelog.user.username,
                'requested approval of',
                str(hours),
                'hours starting on',
                self.usertimelog.datetime_start.astimezone(pytz.timezone(tz)).strftime('%Y-%m-%d %I-%M %p'),
                'from',
                self.usertimelog.event.project.org.name,
                'admin',
                self.user.username,
            ])
        else:
            if self.action_type == 'app':
                act = 'approved'
            elif self.action_type == 'dec':
                act = 'declined'

            return ' '.join([
                self.usertimelog.event.project.org.name,
                'admin',
                self.user.email,
                act,
                str(hours),
                'hours by',
                self.usertimelog.user.email,
                'starting on',
                self.usertimelog.datetime_start.astimezone(pytz.timezone(tz)).strftime('%Y-%m-%d %I-%M %p'),
            ])


# verification tokens
class Token(models.Model):
    email = models.EmailField()
    is_verified = models.BooleanField(default=False)
    token = models.UUIDField(default=uuid4)

    # TODO: restrict to choices
    token_type = models.CharField(max_length=20)

    # referring user
    referrer = models.ForeignKey(
        User,
        null=True,
        on_delete=models.CASCADE
    )

    # token expiration timestamp
    date_expires = models.DateTimeField(
        'date invite token expires',
        default=one_week_from_now
    )

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)

    class Meta:
        get_latest_by = 'date_created'

    def __unicode__(self):
        return ' '.join([
            'Verification token for',
            self.email,
            'expiring on',
            str(self.date_expires),
            '(%sverified)' % ('' if self.is_verified else 'not yet ')
        ])


class Item(models.Model):
    name = models.CharField(max_length=256)

    def __unicode__(self):
        return self.name


class Offer(models.Model):
    org = models.ForeignKey(Org)
    item = models.ForeignKey(Item)
    is_master = models.BooleanField(default=False)
    currents_share = models.IntegerField()
    limit = models.IntegerField(default=-1)
    is_active = models.BooleanField(default=True)

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)

    def __unicode__(self):
        return ' '.join([
            'Master offer' if self.is_master else 'Offer',
            'for',
            str(self.currents_share) + '% on',
            self.item.name,
            'by',
            self.org.name
        ])


def path_and_rename(instance, filename):
        upload_to = 'receipts/{}/'.format(datetime.now().strftime('%Y/%m'))
        ext = filename.split('.')[-1]

        # get filename
        if instance:
            filename = 'org_{}.offer_{}.user_{}.price_reported_{}.date_{}.time_{}.{}'.format(
                instance.offer.org.name,
                instance.offer.id,
                instance.user.id,
                instance.price_reported,
                datetime.now().strftime('%d'),
                datetime.now().strftime('%H-%M-%S.%f'),
                ext
            )
        else:
            # set filename as random string
            filename = '{}.{}'.format(uuid4().hex, ext)

        # return the whole path to the file
        return os.path.join(upload_to, filename)


class Transaction(models.Model):
    user = models.ForeignKey(User)

    offer = models.ForeignKey(Offer)

    pop_image = models.ImageField(
        upload_to=path_and_rename,
        max_length=512,
        null=True
    )

    # text description
    pop_no_proof = models.CharField(
        max_length=8096,
        null=True
    )

    pop_type = models.CharField(
        max_length=3,
        choices=[
            ('rec', 'receipt'),
            ('oth', 'other')
        ],
        default='rec'
    )

    # price paid as reported in the form
    price_reported = models.DecimalField(
        decimal_places=2,
        max_digits=10
    )

    # actual price based on receipt / proof
    price_actual = models.DecimalField(
        decimal_places=2,
        max_digits=10
    )

    # actual current to be redeemed
    currents_amount = models.DecimalField(
        decimal_places=3,
        max_digits=12
    )

    # used to store biz name for master offer
    biz_name = models.CharField(
        max_length=256,
        null=True
    )

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)

    def save(self, *args, **kwargs):
        if not self.price_actual:
            self.price_actual = self.price_reported
        super(Transaction, self).save(*args, **kwargs)

    def __unicode__(self):
        return ' '.join([
            'Transaction initiated by user',
            self.user.username,
            'for',
            'master' if self.offer.is_master else '',
            'offer',
            str(self.offer.id),
            'in the amount of',
            str(self.currents_amount),
            'currents at',
            self.date_updated.strftime('%m/%d/%Y %H:%M:%S'),
        ])


class TransactionAction(models.Model):
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE
    )
    action_type = models.CharField(
        max_length=7,
        choices=[
            ('req', 'pending'),
            ('app', 'approved'),
            ('red', 'redeemed'),
            ('dec', 'declined')
        ],
        default='req'
    )

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)

    class Meta:
        unique_together = ('transaction', 'action_type')
        get_latest_by = 'date_updated'

    # trigger ledger record on approve action
    def save(self, *args, **kwargs):
        super(TransactionAction, self).save(*args, **kwargs)

        if self.action_type == 'app':
            tr = self.transaction

            # transact cur from user to org
            Ledger.objects.create(
                entity_from=tr.user.userentity,
                entity_to=tr.offer.org.orgentity,
                currency='cur',
                amount=tr.currents_amount,
                transaction=self
            )

            # transact usd from oC to user
            Ledger.objects.create(
                entity_from=OrgEntity.objects.get(org__name='openCurrents'),
                entity_to=tr.user.userentity,
                currency='usd',
                amount=convert.cur_to_usd(tr.currents_amount, True),
                transaction=self
            )

    def __unicode__(self):
        return ' '.join([
            'Action',
            '[%s]' % self.action_type,
            'taken at',
            self.date_updated.strftime('%m/%d/%Y %H:%M:%S'),
            'for',
            str(self.transaction)
        ])


class UserCashOut(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    balance = models.DecimalField(max_digits=12, decimal_places=2)

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)

    def __unicode__(self):
        return ' '.join([
            'User',
            '%s' % self.user.username,
            'requested cashout in the amount of',
            '%.3f' % self.balance,
            'on',
            self.date_created.strftime('%m/%d/%Y %H:%M:%S'),
        ])
