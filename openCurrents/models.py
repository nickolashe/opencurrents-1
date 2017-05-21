from __future__ import unicode_literals
from django.contrib.auth.models import User
from uuid import uuid4

from django.db import models

# Notes:
# *) unverified users are still created as User objects but with unusable password

def one_week_from_now():
    return timezone.now() + timedelta(days=7)

# org model
class Org(models.Model):
    name = models.CharField(max_length=100, unique=True)
    website = models.CharField(max_length=100, unique=True, null=True)
    status = models.CharField(max_length=50, null=True)
    mission = models.CharField(max_length=4096, null=True)
    reason = models.CharField(max_length=4096, null=True)
    users = models.ManyToManyField(User, through='OrgUser')
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

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date last updated', auto_now=True)

    def __unicode__(self):
        return ' '.join([self.user.username, '\'s account'])


class Project(models.Model):
    name = models.CharField(max_length=1024)
    org = models.ForeignKey(Org)
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)


class Event(models.Model):
    project = models.ForeignKey(Project)
    location = models.CharField(max_length=1024)
    date_start = models.DateTimeField('start date')
    date_end = models.DateTimeField('end date')
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)


class UserEventRegistration(models.Model):
    event = models.ForeignKey(Event)
    user = models.ForeignKey(User)
    confirmed = models.BooleanField(default=False)
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)


class UserTimeLog(models.Model):
    user = models.ForeignKey(User)
    event = models.ForeignKey(Event)
    date_start = models.DateTimeField('start time')
    date_end = models.DateTimeField('end time')
    verified = models.BooleanField(default=False)
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)


# verification tokens
class Token(models.Model):
    email = models.EmailField()
    is_verified = models.BooleanField(default=False)
    token = models.UUIDField(default=uuid4)
    token_type = models.CharField(max_length=20)
    referrer = models.ForeignKey(User, null=True)
    date_expires = models.DateTimeField(
        'date invite token expires',
        default=one_week_from_now
    )
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)

    def __unicode__(self):
        return ' '.join([
            'Verification token for',
            self.email
        ])
