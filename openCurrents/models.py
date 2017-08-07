from __future__ import unicode_literals
from django.contrib.auth.models import User
from django.db import models

from uuid import uuid4

import pytz

# Notes:
# *) unverified users are still created as User objects but with unusable password


def one_week_from_now():
    return timezone.now() + timedelta(days=7)

def diffInMinutes(t1, t2):
    return round((t2 - t1).total_seconds() / 60, 1)


def diffInHours(t1, t2):
    return round((t2 - t1).total_seconds() / 3600, 1)


# org model


class Org(models.Model):
    name = models.CharField(max_length=100, unique=True)
    website = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=50, null=True)
    mission = models.CharField(max_length=4096, null=True)
    reason = models.CharField(max_length=4096, null=True)
    users = models.ManyToManyField(User, through='OrgUser')
    timezone = models.CharField(max_length=128, default='America/Chicago')

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)

    def __unicode__(self):
        return ' '.join([
            str(self.status),
            str(self.name)
        ])


# user-org affiliations
class OrgUser(models.Model):
    user = models.ForeignKey(User)
    org = models.ForeignKey(Org)
    affiliation = models.CharField(max_length=50, null=True)
    approved = models.BooleanField(default=False)

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)

    class Meta:
        unique_together = ('user', 'org')

    def __unicode__(self):
        return ' '.join([
            'User',
            self.user.email,
            'is',
            str(self.affiliation),
            'at',
            self.org.name
        ])


class Account(models.Model):
    user = models.OneToOneField(User)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pending = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    timezone = models.CharField(max_length=128, default='America/Chicago')
    monthly_updates = models.BooleanField(default=False)

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date last updated', auto_now=True)

    def __unicode__(self):
        return ' '.join([self.user.username, '\'s account'])


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

'''
class ManualTracking(models.Model):
    project = models.ForeignKey(Project)
    description = models.CharField(max_length=8192)
    #location = models.CharField(max_length=1024)

    # coordinator contact info
    #coordinator_firstname = models.CharField(max_length=128)
    #coordinator_email = models.EmailField()

    # start / end timestamps of the project
    datetime_start = models.DateTimeField('start datetime')
    datetime_end = models.DateTimeField('end datetime')

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)

    class Meta:
        get_latest_by = 'datetime_start'
        ordering = ['datetime_start']

    def __unicode__(self):
        tz = self.project.org.timezone
        return ' '.join([
            'Event',
            self.project.name,
            'by',
            self.project.org.name,
            'on',
            self.datetime_start.astimezone(pytz.timezone(tz)).strftime('%b %d'),
            'from',
            self.datetime_start.astimezone(pytz.timezone(tz)).strftime('%-I:%m %p'),
            'to',
            self.datetime_end.astimezone(pytz.timezone(tz)).strftime('%-I:%m %p')
        ])
'''

class Event(models.Model):
    project = models.ForeignKey(Project)
    description = models.CharField(max_length=8192)
    location = models.CharField(max_length=1024)

    # coordinator contact info
    coordinator_firstname = models.CharField(max_length=128)
    coordinator_email = models.EmailField()
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
    user = models.ForeignKey(User)
    event = models.ForeignKey(Event)
    is_confirmed = models.BooleanField(default=False)

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)

    def __unicode__(self):
        return ' '.join([
            self.user.username,
            'is registered for',
            self.event.project.name
        ])


class UserTimeLog(models.Model):
    user = models.ForeignKey(User)
    event = models.ForeignKey(Event)
    is_verified = models.BooleanField(default=False)

    # start / end timestamps of the contributed time
    datetime_start = models.DateTimeField('start time')
    datetime_end = models.DateTimeField('end time', null=True, blank=True)

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)

    class Meta:
        get_latest_by = 'datetime_start'

    def __unicode__(self):
        tz = self.event.project.org.timezone
        status = ' '.join([
            self.user.username,
            'contributed %s starting',
            self.datetime_start.astimezone(pytz.timezone(tz)).strftime('%Y-%m-%d %I-%M %p'),
            'at',
            self.event.project.name
        ])

        if self.datetime_end:
            minutes = ' '.join([
                str(diffInHours(self.datetime_start, self.datetime_end)),
                'min.'
            ])
        else:
            minutes = '(but has not been checked out)'

        status %= minutes
        return status


# verification tokens
class Token(models.Model):
    email = models.EmailField()
    is_verified = models.BooleanField(default=False)
    token = models.UUIDField(default=uuid4)
    token_type = models.CharField(max_length=20)

    # referring user
    referrer = models.ForeignKey(User, null=True)

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
