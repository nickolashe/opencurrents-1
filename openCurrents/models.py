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

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date last updated', auto_now=True)

    def __unicode__(self):
        return ' '.join([self.user.username, '\'s account'])


class Project(models.Model):
    name = models.CharField(max_length=1024)
    org = models.ForeignKey(Org)
    description = models.CharField(max_length=8192)
    location = models.CharField(max_length=1024)

    # coordinator contact info
    coordinator_firstname = models.CharField(max_length=128)
    coordinator_email = models.EmailField()

    # start / end timestamps of the project
    datetime_start = models.DateTimeField('start datetime')
    datetime_end = models.DateTimeField('end datetime')

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


class UserProjectRegistration(models.Model):
    user = models.ForeignKey(User)
    project = models.ForeignKey(Project)
    is_confirmed = models.BooleanField(default=False)

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)

    def __unicode__(self):
        return ' '.join([
            self.user.username,
            'is registered for',
            self.project.name
        ])


class UserTimeLog(models.Model):
    user = models.ForeignKey(User)
    project = models.ForeignKey(Project)
    is_verified = models.BooleanField(default=False)

    # start / end timestamps of the contributed time
    date_start = models.DateTimeField('start time')
    date_end = models.DateTimeField('end time')

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date updated', auto_now=True)

    def __unicode__(self):
        return ' '.join([
            self.user.username,
            'contributed time at',
            self.project.name,
            'from',
            str(self.date_start),
            'to',
            str(self.date_end)
        ])


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

    def __unicode__(self):
        return ' '.join([
            'Verification token for',
            self.email,
            'expiring on',
            str(self.date_expires),
            '(%sverified)' % (self.verified if '' else 'not yet')
        ])
